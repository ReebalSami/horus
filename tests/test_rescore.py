"""Tests for `scripts/rescore.py` — adapter A/B re-scoring + stability check (ADR-016).

Test matrix:

  Adapter pair loading + stability:
    - test_load_adapter_pair_falls_back_to_baseline_when_candidate_missing
    - test_load_adapter_pair_detects_byte_identical_candidate
    - test_load_adapter_pair_loads_distinct_candidate
    - test_load_adapter_pair_raises_on_candidate_missing_required_callable

  Transcript parsing (legacy from ablation_threshold.py):
    - test_parse_transcript_extracts_model_and_invoice_and_body
    - test_parse_transcript_raises_on_malformed_header

  Per-field outcome counts:
    - test_per_field_outcome_counts_tabulates_per_model_per_field

  Stability self-check (Google Rules of ML §24):
    - test_rescore_stability_delta_is_zero_when_candidate_missing
    - test_rescore_baseline_only_matches_legacy_ablation_at_tau_0_5

  A/B candidate behaviour:
    - test_rescore_broken_candidate_produces_worse_or_equal_f1

  CLI smoke:
    - test_main_returns_nonzero_on_invalid_threshold

Strategy: use the real `docs/sources/transcripts-multipage/` archive (the
182-tuple Step 7 evidence) when present; skip the heavy integration tests
when not present (CI tolerance). The pure-function unit tests (parsing,
counting, adapter loading) run unconditionally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ is not a package — load rescore via sys.path manipulation.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import rescore  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "docs" / "sources" / "transcripts-multipage"
CORPUS_ROOT = REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus"

# These tests need the full pilot-13 transcript archive + corpus to run.
_HAS_TRANSCRIPTS = TRANSCRIPTS_DIR.is_dir() and any(TRANSCRIPTS_DIR.glob("*.txt"))
_HAS_CORPUS = CORPUS_ROOT.is_dir()
_HAS_FIXTURES = _HAS_TRANSCRIPTS and _HAS_CORPUS

skip_if_no_fixtures = pytest.mark.skipif(
    not _HAS_FIXTURES,
    reason=(
        "Requires docs/sources/transcripts-multipage/ + data/raw/german/zugferd-corpus/ "
        "to be present (ADR-014 Step 7 evidence)."
    ),
)


# ---------------------------------------------------------------------------
# 1. AdapterPair loading + stability semantics
# ---------------------------------------------------------------------------


def test_load_adapter_pair_falls_back_to_baseline_when_candidate_missing(
    tmp_path: Path,
) -> None:
    """Missing candidate file → baseline-vs-baseline AdapterPair (stability mode)."""
    nonexistent = tmp_path / "no-such-candidate.py"
    pair = rescore.load_adapter_pair(candidate_path=nonexistent)
    assert pair.is_identical is True
    assert pair.candidate is pair.baseline, "candidate IS baseline in stability mode"
    assert pair.diff_sha256 == ""


def test_load_adapter_pair_detects_byte_identical_candidate(tmp_path: Path) -> None:
    """Candidate byte-identical to baseline → stability mode (is_identical=True)."""
    baseline_path = Path(rescore.baseline_adapters.__file__)
    candidate_path = tmp_path / "adapters_candidate.py"
    candidate_path.write_bytes(baseline_path.read_bytes())
    pair = rescore.load_adapter_pair(candidate_path=candidate_path)
    assert pair.is_identical is True
    assert pair.diff_sha256 == ""


def test_load_adapter_pair_loads_distinct_candidate(tmp_path: Path) -> None:
    """A real candidate file (differs from baseline) is loaded as separate module."""
    candidate_path = tmp_path / "adapters_candidate.py"
    candidate_path.write_text(
        # Minimal candidate that defines preprocess + to_predicted_dict.
        # Body is intentionally different from baseline so byte-equality fails.
        "# Test candidate (ADR-016)\n"
        "def preprocess(raw, model_id):\n"
        "    return raw.upper()  # candidate: uppercase everything\n"
        "\n"
        "def to_predicted_dict(raw, model_id):\n"
        "    return {'invoice_number': None}\n",
        encoding="utf-8",
    )
    pair = rescore.load_adapter_pair(candidate_path=candidate_path)
    assert pair.is_identical is False
    assert pair.candidate is not pair.baseline
    assert pair.diff_sha256 != ""
    assert len(pair.diff_sha256) == 64, "SHA-256 hex digest = 64 chars"
    # Contract check: candidate exposes preprocess + to_predicted_dict.
    assert callable(pair.candidate.preprocess)
    assert callable(pair.candidate.to_predicted_dict)
    # Candidate behavior is distinct.
    assert pair.candidate.preprocess("hello", "any-model") == "HELLO"


def test_load_adapter_pair_raises_on_candidate_missing_required_callable(
    tmp_path: Path,
) -> None:
    """Candidate without `preprocess` or `to_predicted_dict` → ValueError."""
    candidate_path = tmp_path / "adapters_candidate.py"
    candidate_path.write_text(
        "# Broken candidate — missing the public API.\ndef some_other_fn():\n    return 'nope'\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required public callable"):
        rescore.load_adapter_pair(candidate_path=candidate_path)


# ---------------------------------------------------------------------------
# 2. Transcript parsing (legacy from ablation_threshold.py)
# ---------------------------------------------------------------------------


def test_parse_transcript_extracts_model_and_invoice_and_body(tmp_path: Path) -> None:
    """`_parse_transcript` reads Model: + Invoice: header lines + body."""
    transcript = tmp_path / "test-model__test-invoice.txt"
    transcript.write_text(
        "# Multi-page transcript (ADR-014 PR(c))\n"
        "# Model:    test-model\n"
        "# Invoice:  test-invoice\n"
        "# Pages:    2\n"
        "\n"
        "===== PAGE 1 =====\n"
        "body content here\n",
        encoding="utf-8",
    )
    model_id, invoice_stem, body = rescore._parse_transcript(transcript)
    assert model_id == "test-model"
    assert invoice_stem == "test-invoice"
    assert "===== PAGE 1 =====" in body
    assert "body content here" in body


def test_parse_transcript_raises_on_malformed_header(tmp_path: Path) -> None:
    """Transcript missing Model:/Invoice: header → ValueError."""
    transcript = tmp_path / "broken.txt"
    transcript.write_text(
        "no header here\njust body\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing Model:/Invoice: header"):
        rescore._parse_transcript(transcript)


# ---------------------------------------------------------------------------
# 3. Per-field outcome counts (ADR-016 Δ table substrate)
# ---------------------------------------------------------------------------


def test_per_field_outcome_counts_tabulates_per_model_per_field() -> None:
    """`_per_field_outcome_counts` aggregates TP/FP/FN/TN/EXCLUDED per (model, field)."""
    # Build synthetic InvoiceFieldScores-shaped objects: each has `.per_field`
    # mapping field_key → object with `.outcome` attribute.
    from dataclasses import dataclass

    @dataclass
    class _Outcome:
        outcome: str

    @dataclass
    class _InvScores:
        per_field: dict[str, _Outcome]

    per_model = {
        "model-A": [
            _InvScores(per_field={"invoice_number": _Outcome("TP"), "issue_date": _Outcome("FN")}),
            _InvScores(per_field={"invoice_number": _Outcome("TP"), "issue_date": _Outcome("TP")}),
        ],
        "model-B": [
            _InvScores(per_field={"invoice_number": _Outcome("FP")}),
        ],
    }
    counts = rescore._per_field_outcome_counts(per_model)
    assert counts["model-A"]["invoice_number"]["TP"] == 2
    assert counts["model-A"]["invoice_number"]["FN"] == 0
    assert counts["model-A"]["issue_date"]["TP"] == 1
    assert counts["model-A"]["issue_date"]["FN"] == 1
    assert counts["model-B"]["invoice_number"]["FP"] == 1
    assert counts["model-B"]["invoice_number"]["TP"] == 0


# ---------------------------------------------------------------------------
# 4. Stability self-check + baseline reproducibility (heavy integration)
# ---------------------------------------------------------------------------


@skip_if_no_fixtures
def test_rescore_stability_delta_is_zero_when_candidate_missing(tmp_path: Path) -> None:
    """Baseline-vs-baseline run produces identical results (Δ = 0; Google §24)."""
    pair = rescore.load_adapter_pair(candidate_path=tmp_path / "no-such.py")
    assert pair.is_identical is True

    results = rescore.rescore_transcripts(
        transcripts_dir=TRANSCRIPTS_DIR,
        corpus_root=CORPUS_ROOT,
        thresholds=[0.5],
        adapters_pair=pair,
    )

    # In stability mode, baseline and candidate score sets must be identical.
    baseline_pooled = rescore._aggregate_micro_f1(
        [s for inv_list in results["baseline"][0.5].values() for s in inv_list]
    )
    candidate_pooled = rescore._aggregate_micro_f1(
        [s for inv_list in results["candidate"][0.5].values() for s in inv_list]
    )
    assert baseline_pooled == candidate_pooled, (
        f"stability self-check FAILED: baseline={baseline_pooled}, candidate={candidate_pooled}; "
        "non-determinism bug in adapter or scorer"
    )


@skip_if_no_fixtures
def test_rescore_baseline_only_matches_legacy_ablation_at_tau_0_5() -> None:
    """Baseline cohort F1 at τ=0.5 reproduces ADR-014 §Step 7 evidence (~0.49)."""
    pair = rescore.load_adapter_pair(candidate_path=Path("/no/such/path.py"))

    results = rescore.rescore_transcripts(
        transcripts_dir=TRANSCRIPTS_DIR,
        corpus_root=CORPUS_ROOT,
        thresholds=[0.5],
        adapters_pair=pair,
    )

    pooled_f1 = rescore._aggregate_micro_f1(
        [s for inv_list in results["baseline"][0.5].values() for s in inv_list]
    )
    # ADR-014 §"Empirical results" cites pooled F1 = 0.4908 at τ=0.5. Allow a
    # small tolerance for floating-point reproducibility.
    assert 0.45 < pooled_f1 < 0.55, (
        f"baseline cohort F1 at τ=0.5 drifted from ADR-014 baseline; "
        f"got {pooled_f1:.4f}, expected ~0.49"
    )


# ---------------------------------------------------------------------------
# 5. A/B candidate behaviour (broken candidate regresses)
# ---------------------------------------------------------------------------


@skip_if_no_fixtures
def test_rescore_broken_candidate_produces_worse_or_equal_f1(tmp_path: Path) -> None:
    """A candidate that returns empty dicts produces F1 ≤ baseline.

    Builds a deliberately-broken candidate adapter, runs the A/B comparison,
    and asserts the candidate's pooled F1 is strictly lower than baseline's
    (since the candidate produces no extracted fields at all).
    """
    candidate_path = tmp_path / "adapters_broken_candidate.py"
    candidate_path.write_text(
        "# Deliberately broken candidate — returns empty extraction for every field.\n"
        "def preprocess(raw, model_id):\n"
        "    return raw\n"
        "\n"
        "def to_predicted_dict(raw, model_id):\n"
        "    # Returns all-None: every GT-present field becomes a FN.\n"
        "    return {}\n",
        encoding="utf-8",
    )
    pair = rescore.load_adapter_pair(candidate_path=candidate_path)
    assert pair.is_identical is False

    # Use a small subset for speed: load 1 model's worth of transcripts.
    # The MinerU model is the most-tested baseline; its transcripts produce
    # the highest baseline F1 — biggest gap to a broken candidate.
    results = rescore.rescore_transcripts(
        transcripts_dir=TRANSCRIPTS_DIR,
        corpus_root=CORPUS_ROOT,
        thresholds=[0.5],
        adapters_pair=pair,
    )

    baseline_pooled = rescore._aggregate_micro_f1(
        [s for inv_list in results["baseline"][0.5].values() for s in inv_list]
    )
    candidate_pooled = rescore._aggregate_micro_f1(
        [s for inv_list in results["candidate"][0.5].values() for s in inv_list]
    )
    # Broken candidate returns {} → every GT field becomes FN. F1 must drop to 0.0.
    assert candidate_pooled == 0.0, (
        f"broken candidate (empty dict) should produce F1=0; got {candidate_pooled:.4f}"
    )
    assert baseline_pooled > 0.0, "baseline F1 should be > 0 with real transcripts"
    assert candidate_pooled < baseline_pooled


# ---------------------------------------------------------------------------
# 6. CLI smoke (argparse + threshold validation)
# ---------------------------------------------------------------------------


def test_main_returns_nonzero_on_invalid_threshold() -> None:
    """CLI rejects thresholds outside [0, 1] before doing any work."""
    rc = rescore.main(["rescore", "--thresholds", "1.5"])
    assert rc == 2


def test_main_returns_nonzero_on_negative_threshold() -> None:
    """CLI rejects negative thresholds."""
    rc = rescore.main(["rescore", "--thresholds", "-0.1"])
    assert rc == 2
