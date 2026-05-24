"""End-to-end integration tests for the PR(b) scorer pipeline (ADR-013).

Combines all four PR(b) modules + PR(a)'s parser:

  1. Load a saved cohort transcript (`docs/sources/transcripts/<model>.txt`)
  2. Extract the raw VLM output via `extract_transcript_body`
  3. Convert to a 16-key predicted dict via `to_predicted_dict(raw, model_id)`
  4. Parse the matching CII XML via PR(a)'s `parse_cii_xml`
  5. Score predicted vs GT via `score(...)`
  6. Assert per-model F1 + outcome distribution against the empirical baseline

Empirical baselines (captured from the actual cohort transcripts; serve as
regression guards — drift surfaces here for review):

  - Granite-Docling 258M: micro_F1 ≈ 0.125 (baseline-of-failure)
  - MinerU 2.5 Pro:       micro_F1 ≈ 0.636 (best-of-cohort within page-1 constraint)
  - GLM-OCR:              micro_F1 ≈ 0.571
  - Gemma-4-E4B-it:       micro_F1 ≈ 0.421
  - olmOCR-2-7B:          micro_F1 ≈ 0.333
  - PaddleOCR-VL:         micro_F1 ≈ 0.333
  - PaliGemma-2-3B:       micro_F1 ≈ 0.235

Cross-cohort invariant: the 5 MONEY fields (BT-106/109/110/112/115) are
uniformly FN across all working models because page-1 rasterization hides
the totals block (page 2 of EN16931_Einfach.pdf). PR(c) re-rasterizes all
pages and lifts this constraint.

Refs: ADR-013 §"Decision + integration thoughts", ADR-012 (PR(a) GT parser),
      ADR-009 (cohort manifest), `docs/sources/transcripts/`.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

import pytest

from horus.config import EvalConfig
from horus.eval.adapters import extract_transcript_body, to_predicted_dict
from horus.eval.ground_truth import GroundTruth, parse_cii_xml
from horus.eval.scorer import InvoiceFieldScores, score
from tests._corpus import skip_if_no_corpus

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "docs" / "sources" / "transcripts"
EINFACH_CII = (
    REPO_ROOT
    / "data"
    / "raw"
    / "german"
    / "zugferd-corpus"
    / "XML-Rechnung"
    / "CII"
    / "EN16931_Einfach.cii.xml"
)

# ADR-023: every test in this module requires the ZUGFeRD corpus on disk
# (the `einfach_gt` fixture parses EINFACH_CII; transcripts are not corpus).
# Skips automatically when the corpus is absent (CI or fresh dev clone).
pytestmark = skip_if_no_corpus


# Working cohort transcripts (7 of 10 models that ran to completion per ADR-009).
# DeepSeek-OCR-2 / Qwen3-VL-4B / Molmo-7B-D errored at load/inference and have
# empty Output snippet sections — they're skipped by `extract_transcript_body`.
WORKING_TRANSCRIPTS = [
    "granite-docling-258m.txt",
    "mineru-2-5-pro-vlm.txt",
    "olmocr-2-7b.txt",
    "gemma-4-e4b-it.txt",
    "glm-ocr.txt",
    "paddleocr-vl.txt",
    "paligemma2-3b-mix-448.txt",
]


# Per-model empirical baseline ranges. Format: (micro_f1_min, micro_f1_max).
# Bounds are wider than the observed values to absorb minor adapter tuning;
# narrow them if/when the cohort numbers stabilize for the thesis writeup.
EXPECTED_F1_RANGES: dict[str, tuple[float, float]] = {
    "granite-docling-258m.txt": (0.05, 0.20),  # baseline-of-failure (observed: 0.125)
    "mineru-2-5-pro-vlm.txt": (0.45, 0.70),  # best-of-cohort (observed: 0.636)
    "olmocr-2-7b.txt": (0.20, 0.45),  # observed: 0.333
    "gemma-4-e4b-it.txt": (0.25, 0.55),  # observed: 0.421
    "glm-ocr.txt": (0.40, 0.65),  # observed: 0.571
    "paddleocr-vl.txt": (0.20, 0.45),  # observed: 0.333
    "paligemma2-3b-mix-448.txt": (0.10, 0.40),  # observed: 0.235
}


MONEY_FIELDS = (
    "line_total_amount",
    "tax_basis_total_amount",
    "tax_total_amount",
    "grand_total_amount",
    "due_payable_amount",
)


def _load_transcript(name: str) -> tuple[str, str]:
    """Load a saved transcript and return ``(body, model_id)``.

    Skips with `pytest.skip` if the transcript file is missing OR the
    Output snippet section is empty (error-status models).
    """
    path = TRANSCRIPTS_DIR / name
    if not path.is_file():
        pytest.skip(f"Transcript missing: {path}")
    content = path.read_text()
    match = re.search(r"Model:\s+(\S+)", content)
    assert match is not None, f"Could not find 'Model:' header in {name}"
    body = extract_transcript_body(content)
    if not body:
        pytest.skip(f"Empty Output snippet (error transcript): {name}")
    return body, match.group(1)


@pytest.fixture(scope="module")
def einfach_gt() -> GroundTruth:
    """Parse the EN16931_Einfach CII XML once per module — used by all scorer tests."""
    if not EINFACH_CII.is_file():
        pytest.skip(f"Missing CII fixture: {EINFACH_CII}")
    return parse_cii_xml(EINFACH_CII.read_bytes())


# ===========================================================================
# 1. Per-model F1 range assertions
# ===========================================================================


@pytest.mark.parametrize("transcript_name", list(EXPECTED_F1_RANGES.keys()))
def test_per_model_micro_f1_within_empirical_range(
    einfach_gt: GroundTruth,
    transcript_name: str,
) -> None:
    """Per-model micro_F1 falls within the empirical baseline range.

    The ranges are derived from a smoke run of the actual cohort transcripts
    against the EN16931_Einfach GT. Tight enough to catch adapter regressions;
    loose enough to absorb minor tuning. If a future change moves a model out
    of range, update the bound + add a note in the commit message.
    """
    body, model_id = _load_transcript(transcript_name)
    pred = to_predicted_dict(body, model_id)
    result = score(
        pred,
        einfach_gt,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    lo, hi = EXPECTED_F1_RANGES[transcript_name]
    assert lo <= result.micro_f1 <= hi, (
        f"{transcript_name}: micro_F1={result.micro_f1:.3f} outside range [{lo}, {hi}]. "
        f"If drift is intentional, update EXPECTED_F1_RANGES."
    )


# ===========================================================================
# 2. Cross-cohort invariant — page-1 baseline (5 MONEY fields uniformly FN)
# ===========================================================================


def test_monetary_fields_uniformly_fn_across_cohort(einfach_gt: GroundTruth) -> None:
    """All 5 MONEY fields are FN across every working cohort model.

    This captures the ADR-013 §Decision page-1-only baseline as a single
    deterministic test: the totals block lives on page 2 of EN16931_Einfach.pdf,
    so no cohort model running on the page-1 rasterization can produce a TP
    for any MONEY field. PR(c) (ADR-014) re-rasterizes all pages and lifts
    this constraint.

    Per-model: predicted MONEY value is None → outcome FN against GT
    `present_content`.
    """
    for transcript_name in WORKING_TRANSCRIPTS:
        body, model_id = _load_transcript(transcript_name)
        pred = to_predicted_dict(body, model_id)
        result = score(
            pred,
            einfach_gt,
            cfg=EvalConfig(),
            invoice_id="EN16931_Einfach",
            model_id=model_id,
        )
        for money_field in MONEY_FIELDS:
            outcome = result.per_field[money_field].outcome
            assert outcome == "FN", (
                f"{transcript_name}: {money_field} outcome={outcome} "
                f"(expected FN per page-1 baseline). Re-rasterized PR(c) "
                f"transcripts would change this."
            )


def test_buyer_vat_id_is_tn_across_cohort(einfach_gt: GroundTruth) -> None:
    """`buyer_vat_id` is TN across the cohort (absent in GT + uniformly None in pred).

    EN16931_Einfach has no buyer VAT ID (per `test_buyer_vat_id_absent_in_einfach`
    in PR(a)). The cohort doesn't hallucinate one, so the outcome is TN
    (correct rejection) on every model.
    """
    for transcript_name in WORKING_TRANSCRIPTS:
        body, model_id = _load_transcript(transcript_name)
        pred = to_predicted_dict(body, model_id)
        result = score(
            pred,
            einfach_gt,
            cfg=EvalConfig(),
            invoice_id="EN16931_Einfach",
            model_id=model_id,
        )
        outcome = result.per_field["buyer_vat_id"].outcome
        assert outcome == "TN", (
            f"{transcript_name}: buyer_vat_id outcome={outcome} (expected TN — "
            f"GT absent + no hallucination on cohort)"
        )


# ===========================================================================
# 3. Per-model TP breakdown — what each model gets right (heatmap evidence)
# ===========================================================================


def test_granite_docling_baseline_of_failure(einfach_gt: GroundTruth) -> None:
    """Granite-Docling 258M extracts exactly invoice_number (the one TP)."""
    body, model_id = _load_transcript("granite-docling-258m.txt")
    pred = to_predicted_dict(body, model_id)
    result = score(
        pred,
        einfach_gt,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    tps = {k for k, r in result.per_field.items() if r.outcome == "TP"}
    assert "invoice_number" in tps, (
        f"Granite-Docling baseline should include invoice_number TP; got TPs={tps}"
    )
    # The "baseline-of-failure" framing: ≤ 2 TPs total
    assert len(tps) <= 2, (
        f"Granite-Docling extracted {len(tps)} TPs — baseline-of-failure exceeded. "
        f"If model output improved, update the assertion."
    )


def test_mineru_extracts_seller_name_via_anls_tolerance(einfach_gt: GroundTruth) -> None:
    """MinerU 2.5 Pro's 'Lieferent' vs GT 'Lieferant' → TP via ANLS\\* tolerance.

    Empirical demonstration that the ANLS\\* threshold-0.5 design catches
    real OCR errors as soft matches — without it, MinerU's single-character
    typo would be FN and the model's overall F1 would be visibly lower.
    """
    body, model_id = _load_transcript("mineru-2-5-pro-vlm.txt")
    pred = to_predicted_dict(body, model_id)
    result = score(
        pred,
        einfach_gt,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    seller = result.per_field["seller_name"]
    assert seller.outcome == "TP"
    assert seller.predicted_normalized == "Lieferent GmbH"
    assert seller.gt_normalized == "Lieferant GmbH"
    assert 0.85 < seller.score < 1.0  # NLS ≈ 0.929 (one sub in 14 chars)


def test_gemma_recognizes_name_fehlt_as_absent(einfach_gt: GroundTruth) -> None:
    """Gemma-4-it's ``[Name fehlt]`` for seller_name → predicted=None → outcome=FN."""
    body, model_id = _load_transcript("gemma-4-e4b-it.txt")
    pred = to_predicted_dict(body, model_id)
    result = score(
        pred,
        einfach_gt,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    seller = result.per_field["seller_name"]
    assert seller.predicted_normalized is None
    assert seller.outcome == "FN"  # GT present_content + Pred None


# ===========================================================================
# 4. Serialization — InvoiceFieldScores round-trips through asdict() for MLflow
# ===========================================================================


def test_invoice_field_scores_round_trips_through_asdict(einfach_gt: GroundTruth) -> None:
    """`InvoiceFieldScores` serializes cleanly through `dataclasses.asdict`.

    Per ADR-011 the `Tracker.log_dict()` protocol consumes plain dicts; the
    scorer's result dataclass must round-trip so the per-field heatmap data
    can be logged as an MLflow artifact without custom serialization code.
    """
    body, model_id = _load_transcript("mineru-2-5-pro-vlm.txt")
    pred = to_predicted_dict(body, model_id)
    result = score(
        pred,
        einfach_gt,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    d = asdict(result)

    # Round-trip invariants
    assert d["invoice_id"] == "EN16931_Einfach"
    assert d["model_id"] == model_id
    assert isinstance(d["per_field"], dict)
    assert isinstance(d["per_field"]["invoice_number"], dict)
    # The nested FieldResult dataclasses also become dicts
    assert d["per_field"]["invoice_number"]["outcome"] == "TP"
    assert "score" in d["per_field"]["invoice_number"]
    # No callable / non-JSON-friendly values leaked
    import json

    json.dumps(d)  # raises if any non-JSON-serializable value remains


# ===========================================================================
# 5. Aggregate sanity — counts add up to 16 across outcome categories
# ===========================================================================


def test_per_field_outcome_counts_sum_to_16(einfach_gt: GroundTruth) -> None:
    """Across all 16 fields, the outcome categories partition the field set.

    Sanity check: every field gets exactly one outcome ∈ {TP, FP, FN, TN, EXCLUDED}.
    """
    for transcript_name in WORKING_TRANSCRIPTS:
        body, model_id = _load_transcript(transcript_name)
        pred = to_predicted_dict(body, model_id)
        result = score(
            pred,
            einfach_gt,
            cfg=EvalConfig(),
            invoice_id="EN16931_Einfach",
            model_id=model_id,
        )
        outcomes = [r.outcome for r in result.per_field.values()]
        assert len(outcomes) == 16
        # Tally across categories
        from collections import Counter

        counts = Counter(outcomes)
        # All outcomes ∈ allowed set
        assert set(counts.keys()) <= {"TP", "FP", "FN", "TN", "EXCLUDED"}
        # No EXCLUDED on EN16931_Einfach (no normalizer-rejected GT in this corpus)
        assert counts.get("EXCLUDED", 0) == 0, (
            f"{transcript_name}: unexpected EXCLUDED outcomes={counts['EXCLUDED']}"
        )


def test_micro_f1_consistent_with_macro_f1(einfach_gt: GroundTruth) -> None:
    """Micro and macro F1 are both in [0, 1] across the cohort + non-negative."""
    for transcript_name in WORKING_TRANSCRIPTS:
        body, model_id = _load_transcript(transcript_name)
        pred = to_predicted_dict(body, model_id)
        result = score(
            pred,
            einfach_gt,
            cfg=EvalConfig(),
            invoice_id="EN16931_Einfach",
            model_id=model_id,
        )
        assert 0.0 <= result.micro_f1 <= 1.0
        assert 0.0 <= result.macro_f1 <= 1.0
        assert 0.0 <= result.micro_precision <= 1.0
        assert 0.0 <= result.micro_recall <= 1.0


# ===========================================================================
# 6. Heatmap-row helper — useful for the PR description's evidence block
# ===========================================================================


def test_cohort_heatmap_row_format(einfach_gt: GroundTruth) -> None:
    """Render a heatmap-row-like dict for each model — sanity-check the shape.

    Produces something like:
      {model_id: {field_name: 1.0 if TP else 0.0, ...}, ...}

    This is the shape PR(c)'s harness would log to MLflow as the per-field
    artifact dict. Validates the data is in good shape for that consumer.
    """
    heatmap: dict[str, dict[str, float]] = {}
    for transcript_name in WORKING_TRANSCRIPTS:
        body, model_id = _load_transcript(transcript_name)
        pred = to_predicted_dict(body, model_id)
        result: InvoiceFieldScores = score(
            pred,
            einfach_gt,
            cfg=EvalConfig(),
            invoice_id="EN16931_Einfach",
            model_id=model_id,
        )
        heatmap[model_id] = {
            key: (1.0 if r.outcome == "TP" else 0.0) for key, r in result.per_field.items()
        }

    # Shape sanity: 7 working cohort models, 16 fields each
    assert len(heatmap) == 7
    for model_row in heatmap.values():
        assert len(model_row) == 16
        assert all(v in (0.0, 1.0) for v in model_row.values())
