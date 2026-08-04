"""Unit tests for `src/horus/finetune/evaluate.py` per-field reporting (issue #55).

Covers `_per_field_f1` — the pooled per-field diagnostic that replaced ranking on
`per_field_mean`. `per_field_mean` was a mean over EVERY `FieldResult.score`,
including TN (score 1.0) and EXCLUDED (score 0.0), so a field's reported number
tracked how often it was absent rather than how well it was read. See
`eval/per-field-reporting-audit.md`.

Refs: ADR-045 / ADR-052 (the tax_rate EXCLUDED paths), ADR-027 (metric surface).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus.eval.ground_truth import FIELDS, GroundTruth, GroundTruthField
from horus.finetune.dataset import InvoiceRecord
from horus.finetune.evaluate import _per_field_f1, score_saved_outputs

STRUCTURER = "google/gemma-4-E4B-it"


def _counts(
    tp: int = 0, fp: int = 0, fn: int = 0, tn: int = 0, excluded: int = 0
) -> dict[str, int]:
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "EXCLUDED": excluded}


def _gt(present: dict[str, str]) -> GroundTruth:
    """Full-registry GroundTruth; keys in ``present`` are present-with-value."""
    header: dict[str, GroundTruthField] = {}
    for key, spec in FIELDS.items():
        value = present.get(key)
        header[key] = GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=value,
            normalized_value=value,
            xpath=spec.xpath,
            is_present=value is not None,
        )
    return GroundTruth(header=header)


def _record(tmp_path: Path, stem: str, gt: GroundTruth) -> InvoiceRecord:
    transcript = tmp_path / f"{stem}.transcript.txt"
    transcript.write_text("irrelevant (score-only never reads the transcript)", encoding="utf-8")
    return InvoiceRecord(
        pdf_path=tmp_path / f"{stem}.pdf",
        stem=stem,
        subdir="synthetic",
        gt=gt,
        gt_error=None,
        transcript_path=transcript,
    )


def test_per_field_f1_pools_tp_fp_fn() -> None:
    """Pooled F1 = 2TP / (2TP + FP + FN), per field."""
    result = _per_field_f1({"invoice_number": _counts(tp=8, fp=1, fn=1)})
    assert result["invoice_number"] == pytest.approx(16 / 18)


def test_per_field_f1_ignores_tn_and_excluded() -> None:
    """TN and EXCLUDED move neither numerator nor denominator.

    The regression guard: the same field with 0 vs 100 TN/EXCLUDED occurrences must
    report the identical F1.
    """
    lean = _per_field_f1({"f": _counts(tp=3, fn=1)})
    padded = _per_field_f1({"f": _counts(tp=3, fn=1, tn=100, excluded=50)})
    assert lean["f"] == padded["f"] == pytest.approx(6 / 7)


def test_per_field_f1_omits_never_tested_fields() -> None:
    """A field with no TP/FP/FN was never tested → omitted, not reported as 1.0.

    `rounding_amount` on the sealed val split is 29/29 TN; the old reporting
    surfaced it as a perfect 1.000, which read as "always right" when it actually
    meant "never asked".
    """
    result = _per_field_f1(
        {
            "rounding_amount": _counts(tn=29),
            "tax_rate": _counts(excluded=13),
            "issue_date": _counts(tp=27, fn=2),
        }
    )
    assert "rounding_amount" not in result
    assert "tax_rate" not in result
    assert result["issue_date"] == pytest.approx(54 / 56)


def test_per_field_f1_all_wrong_is_zero_not_omitted() -> None:
    """A field that is tested and always wrong reports 0.0 (distinct from omitted).

    `allowance_total_amount` scores 0.0 on 6 signal-bearing cases across every arm
    including the perfect-transcript oracle — a real finding that must stay visible,
    not be confused with an untested field.
    """
    result = _per_field_f1({"allowance_total_amount": _counts(fn=6)})
    assert result["allowance_total_amount"] == 0.0


def test_per_field_f1_is_sorted() -> None:
    """Keys come out sorted, so report diffs stay stable across runs."""
    result = _per_field_f1(
        {
            "seller_name": _counts(tp=1),
            "buyer_name": _counts(tp=1),
            "invoice_number": _counts(tp=1),
        }
    )
    assert list(result) == ["buyer_name", "invoice_number", "seller_name"]


# ---------------------------------------------------------------------------
# score_saved_outputs — offline re-scoring (no model load, no inference)
# ---------------------------------------------------------------------------


def test_score_saved_outputs_scores_saved_generations(tmp_path: Path) -> None:
    """Reads DIR/<stem>.txt, scores it, and reports through the shared accumulator."""
    gt = _gt({"invoice_number": "471102", "seller_name": "Lieferant GmbH"})
    rec = _record(tmp_path, "inv-1", gt)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "inv-1.txt").write_text(
        json.dumps({"invoice_number": "471102", "seller_name": "Lieferant GmbH"}),
        encoding="utf-8",
    )

    report = score_saved_outputs(
        [rec], outputs, structurer_model=STRUCTURER, progress=False, label="t"
    )

    assert report.n_total == 1
    assert report.n_ok == 1
    assert report.n_failed == 0
    assert report.per_field_f1["invoice_number"] == 1.0
    assert report.per_field_f1["seller_name"] == 1.0
    # Absent-and-not-predicted fields are TN → present in the raw counts, absent
    # from per_field_f1 (never tested; must not read as a perfect 1.0).
    assert report.per_field_outcomes["seller_iban"]["TN"] == 1
    assert "seller_iban" not in report.per_field_f1


def test_score_saved_outputs_reports_missing_generation_as_failure(tmp_path: Path) -> None:
    """A record with no saved output is a counted failure, never a silent drop."""
    rec = _record(tmp_path, "inv-missing", _gt({"invoice_number": "1"}))
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    report = score_saved_outputs(
        [rec], outputs, structurer_model=STRUCTURER, progress=False, label="t"
    )

    assert (report.n_total, report.n_ok, report.n_failed) == (1, 0, 1)
    assert report.per_invoice[0].error is not None
    assert "no saved output" in report.per_invoice[0].error


def test_score_saved_outputs_rejects_missing_dir(tmp_path: Path) -> None:
    """A non-existent outputs dir fails loudly rather than reporting an empty eval."""
    rec = _record(tmp_path, "inv-1", _gt({"invoice_number": "1"}))
    with pytest.raises(FileNotFoundError, match="Saved-outputs dir not found"):
        score_saved_outputs([rec], tmp_path / "nope", structurer_model=STRUCTURER, progress=False)
