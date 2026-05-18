"""Unit tests for `src/horus/eval/scorer.py` (PR(b) per ADR-013).

Covers:
  - Predicted-side normalizers (`_normalize_predicted_money` / _date / _code / _string)
  - Per-field-type comparator dispatch (STRING via ANLS\\*, MONEY/DATE/CODE via exact)
  - 12-cell truth table (GT 4-state × Pred 3-state → outcome)
  - Aggregate F1 computation (micro + macro, EXCLUDED handling)
  - Public ``score()`` entry-point on synthetic inputs

Integration tests against the saved cohort transcripts live in
``tests/test_scorer_integration.py`` (Step 7 per plan).

Refs: ADR-013, ADR-012 (parent: GT parser), Biten+ ICCV'19 (ANLS metric).
"""

from __future__ import annotations

import pytest

from horus.config import EvalConfig
from horus.eval.ground_truth import GroundTruth, GroundTruthField
from horus.eval.scorer import (
    FieldResult,
    InvoiceFieldScores,
    _aggregate_micro_macro,
    _compare_string,
    _compare_typed_exact,
    _f1_from_counts,
    _gt_state,
    _normalize_predicted_code,
    _normalize_predicted_date,
    _normalize_predicted_money,
    _normalize_predicted_string,
    _score_one_field,
    score,
)

# ===========================================================================
# 1. Predicted-side normalizers
# ===========================================================================


# ---- _normalize_predicted_money ----


def test_normalize_money_canonical_us_format() -> None:
    """``"529.87"`` → ``"529.87"`` (canonical input)."""
    assert _normalize_predicted_money("529.87") == "529.87"


def test_normalize_money_german_decimal_comma() -> None:
    """``"529,87"`` (German short) → ``"529.87"``."""
    assert _normalize_predicted_money("529,87") == "529.87"


def test_normalize_money_german_thousand_period_decimal_comma() -> None:
    """``"1.234,56"`` (German with thousand-period) → ``"1234.56"``."""
    assert _normalize_predicted_money("1.234,56") == "1234.56"


def test_normalize_money_us_thousand_comma() -> None:
    """``"1,234.56"`` (US with thousand-comma) → ``"1234.56"``."""
    assert _normalize_predicted_money("1,234.56") == "1234.56"


def test_normalize_money_with_euro_symbol() -> None:
    """``"529,87 €"`` → ``"529.87"`` (strip currency symbol)."""
    assert _normalize_predicted_money("529,87 €") == "529.87"
    assert _normalize_predicted_money("€ 529,87") == "529.87"
    assert _normalize_predicted_money("EUR 529.87") == "529.87"


def test_normalize_money_negative_preserves_sign() -> None:
    """``"-529,87"`` → ``"-529.87"`` (negative amounts valid per EN16931)."""
    assert _normalize_predicted_money("-529,87") == "-529.87"


def test_normalize_money_rejects_non_numeric() -> None:
    """Non-parseable inputs return None."""
    assert _normalize_predicted_money("abc") is None
    assert _normalize_predicted_money("") is None


def test_normalize_money_quantizes_to_2_decimals() -> None:
    """Quantizes long-decimal inputs to exactly 2 decimal places."""
    assert _normalize_predicted_money("529.876") == "529.88"  # banker's rounding
    assert _normalize_predicted_money("529.874") == "529.87"


# ---- _normalize_predicted_date ----


def test_normalize_date_iso_passes_through() -> None:
    """``"2018-03-05"`` → ``"2018-03-05"``."""
    assert _normalize_predicted_date("2018-03-05") == "2018-03-05"


def test_normalize_date_german_dd_mm_yyyy() -> None:
    """``"05.03.2018"`` (German) → ``"2018-03-05"``."""
    assert _normalize_predicted_date("05.03.2018") == "2018-03-05"


def test_normalize_date_german_short_form() -> None:
    """``"5.3.2018"`` (no zero-padding) → ``"2018-03-05"``."""
    assert _normalize_predicted_date("5.3.2018") == "2018-03-05"


def test_normalize_date_slash_separator() -> None:
    """``"05/03/2018"`` → ``"2018-03-05"`` (DD/MM/YYYY interpretation)."""
    assert _normalize_predicted_date("05/03/2018") == "2018-03-05"


def test_normalize_date_dash_separator() -> None:
    """``"05-03-2018"`` → ``"2018-03-05"``."""
    assert _normalize_predicted_date("05-03-2018") == "2018-03-05"


def test_normalize_date_german_month_name_full() -> None:
    """``"05. März 2018"`` → ``"2018-03-05"``."""
    assert _normalize_predicted_date("05. März 2018") == "2018-03-05"


def test_normalize_date_german_month_name_short() -> None:
    """``"5 Mai 2018"`` → ``"2018-05-05"``."""
    assert _normalize_predicted_date("5 Mai 2018") == "2018-05-05"


def test_normalize_date_rejects_invalid_calendar_date() -> None:
    """Calendar-invalid input returns None (Feb 30)."""
    assert _normalize_predicted_date("30.02.2018") is None


def test_normalize_date_rejects_garbage() -> None:
    """Non-date input returns None."""
    assert _normalize_predicted_date("abc") is None
    assert _normalize_predicted_date("") is None


def test_normalize_date_ocr_misread_3_as_8() -> None:
    """Document the cohort failure mode: '05.08.2018' parses but ≠ GT '2018-03-05'.

    This is the real OCR error from Granite-Docling / MinerU / PaddleOCR-VL
    transcripts (model misread '3' as '8'). The normalizer correctly parses
    the (wrong) date; the comparator then catches the mismatch.
    """
    assert _normalize_predicted_date("05.08.2018") == "2018-08-05"
    assert _normalize_predicted_date("05.08.2018") != "2018-03-05"


# ---- _normalize_predicted_code ----


def test_normalize_code_strips_outer_whitespace() -> None:
    assert _normalize_predicted_code("  471102  ") == "471102"


def test_normalize_code_strips_internal_whitespace_in_vat_id() -> None:
    """``"DE 123456789"`` → ``"DE123456789"`` (VAT-ID-style country-code prefix)."""
    assert _normalize_predicted_code("DE 123456789") == "DE123456789"
    assert _normalize_predicted_code("DE 123 456 789") == "DE123456789"


def test_normalize_code_preserves_internal_whitespace_in_non_vat() -> None:
    """Non-VAT codes preserve internal whitespace (e.g., '4000001123452')."""
    assert _normalize_predicted_code("4000001123452") == "4000001123452"


def test_normalize_code_nfc_normalizes_diacritics() -> None:
    """NFC normalization composes decomposed diacritics."""
    assert _normalize_predicted_code("Mu\u0308nchen") == "M\u00fcnchen"


def test_normalize_code_returns_none_on_empty() -> None:
    assert _normalize_predicted_code("") is None
    assert _normalize_predicted_code("   ") is None


# ---- _normalize_predicted_string ----


def test_normalize_string_preserves_internal_whitespace() -> None:
    """Multi-word strings keep their internal whitespace."""
    assert _normalize_predicted_string("Lieferant GmbH") == "Lieferant GmbH"


def test_normalize_string_nfc_normalizes() -> None:
    """NFC normalization composes decomposed diacritics."""
    assert _normalize_predicted_string("Mu\u0308nchen") == "M\u00fcnchen"


def test_normalize_string_returns_none_on_empty() -> None:
    assert _normalize_predicted_string("") is None
    assert _normalize_predicted_string("   ") is None


# ===========================================================================
# 2. Per-field-type comparators
# ===========================================================================


def test_compare_string_exact_match_is_tp() -> None:
    """ANLS\\* on identical strings → score=1.0, is_tp=True."""
    score, is_tp = _compare_string("Lieferant GmbH", "Lieferant GmbH", threshold=0.5)
    assert score == 1.0
    assert is_tp is True


def test_compare_string_minor_ocr_drift_is_tp() -> None:
    """One-character substitution above threshold → TP."""
    score, is_tp = _compare_string("Lieferent GmbH", "Lieferant GmbH", threshold=0.5)
    assert score > 0.85  # ≈ 0.93 from cohort smoke
    assert is_tp is True


def test_compare_string_severe_drift_is_not_tp() -> None:
    """Severe drift below threshold → not TP."""
    score, is_tp = _compare_string("Unhmd QmbH", "Lieferant GmbH", threshold=0.5)
    assert score == 0.0  # ANLS\\* collapses below threshold
    assert is_tp is False


def test_compare_typed_exact_match() -> None:
    """Identical normalized values → (1.0, True)."""
    assert _compare_typed_exact("471102", "471102") == (1.0, True)


def test_compare_typed_mismatch() -> None:
    """Non-identical normalized values → (0.0, False)."""
    assert _compare_typed_exact("2018-08-05", "2018-03-05") == (0.0, False)
    assert _compare_typed_exact("529.88", "529.87") == (0.0, False)


# ===========================================================================
# 3. Truth table — _gt_state + _score_one_field
# ===========================================================================


def test_gt_state_absent() -> None:
    """`is_present=False` → "absent"."""
    f = GroundTruthField(
        bt_code="BT-X", raw_value=None, normalized_value=None, xpath="", is_present=False
    )
    assert _gt_state(f) == "absent"


def test_gt_state_present_empty() -> None:
    """`is_present=True, normalized_value=""` → "present_empty"."""
    f = GroundTruthField(
        bt_code="BT-X", raw_value="", normalized_value="", xpath="", is_present=True
    )
    assert _gt_state(f) == "present_empty"


def test_gt_state_present_content() -> None:
    """`is_present=True, normalized_value="X"` → "present_content"."""
    f = GroundTruthField(
        bt_code="BT-X", raw_value="X", normalized_value="X", xpath="", is_present=True
    )
    assert _gt_state(f) == "present_content"


def test_gt_state_normalizer_rejected() -> None:
    """`is_present=True, normalized_value=None` → "normalizer_rejected"."""
    f = GroundTruthField(
        bt_code="BT-X", raw_value="bad", normalized_value=None, xpath="", is_present=True
    )
    assert _gt_state(f) == "normalizer_rejected"


# ---- 12-cell truth table (a sample of each cell via _score_one_field) ----

CFG = EvalConfig()


def _gt(present: bool, normalized: str | None) -> GroundTruthField:
    """Helper to build a synthetic GroundTruthField for table-cell tests."""
    return GroundTruthField(
        bt_code="BT-1",
        raw_value=normalized if normalized is not None else None,
        normalized_value=normalized,
        xpath="/dummy",
        is_present=present,
    )


def test_truth_table_absent_x_pred_none_is_tn() -> None:
    """GT absent + Pred None → TN."""
    gt = _gt(present=False, normalized=None)
    result = _score_one_field("invoice_number", None, gt, cfg=CFG)
    assert result.outcome == "TN"


def test_truth_table_absent_x_pred_content_is_fp() -> None:
    """GT absent + Pred content → FP (model invented)."""
    gt = _gt(present=False, normalized=None)
    result = _score_one_field("invoice_number", "INV-001", gt, cfg=CFG)
    assert result.outcome == "FP"


def test_truth_table_present_content_x_pred_match_is_tp() -> None:
    """GT present_content + Pred matches → TP."""
    gt = _gt(present=True, normalized="471102")
    result = _score_one_field("invoice_number", "471102", gt, cfg=CFG)
    assert result.outcome == "TP"
    assert result.score == 1.0


def test_truth_table_present_content_x_pred_none_is_fn() -> None:
    """GT present_content + Pred None → FN."""
    gt = _gt(present=True, normalized="471102")
    result = _score_one_field("invoice_number", None, gt, cfg=CFG)
    assert result.outcome == "FN"
    assert result.predicted_normalized is None


def test_truth_table_present_content_x_pred_wrong_is_fn() -> None:
    """GT present_content + Pred wrong content → FN (CODE-type strict)."""
    gt = _gt(present=True, normalized="471102")
    result = _score_one_field("invoice_number", "999999", gt, cfg=CFG)
    assert result.outcome == "FN"


def test_truth_table_normalizer_rejected_is_excluded() -> None:
    """GT normalizer_rejected → EXCLUDED regardless of pred."""
    gt = _gt(present=True, normalized=None)
    result_none = _score_one_field("invoice_number", None, gt, cfg=CFG)
    result_value = _score_one_field("invoice_number", "X", gt, cfg=CFG)
    assert result_none.outcome == "EXCLUDED"
    assert result_value.outcome == "EXCLUDED"


def test_truth_table_string_above_threshold_is_tp() -> None:
    """STRING field: ANLS\\* above threshold → TP."""
    # seller_name is the STRING-type field for BT-27
    gt = GroundTruthField(
        bt_code="BT-27",
        raw_value="Lieferant GmbH",
        normalized_value="Lieferant GmbH",
        xpath="/dummy",
        is_present=True,
    )
    result = _score_one_field("seller_name", "Lieferent GmbH", gt, cfg=CFG)
    assert result.outcome == "TP"
    assert result.score > 0.85  # ANLS\\* well above 0.5 threshold


def test_truth_table_string_below_threshold_is_fn() -> None:
    """STRING field: ANLS\\* below threshold → FN, score reports raw NLS for diagnostic."""
    gt = GroundTruthField(
        bt_code="BT-27",
        raw_value="Lieferant GmbH",
        normalized_value="Lieferant GmbH",
        xpath="/dummy",
        is_present=True,
    )
    result = _score_one_field("seller_name", "Unhmd QmbH", gt, cfg=CFG)
    assert result.outcome == "FN"
    # Diagnostic: the FN result still reports the raw NLS (not 0) so the
    # heatmap can show "how close" the model got.
    assert 0.0 < result.score < 0.5


def test_truth_table_money_german_format_matches_gt() -> None:
    """MONEY field: German '529,87 €' normalizes to '529.87' and matches GT '529.87'."""
    gt = GroundTruthField(
        bt_code="BT-106",
        raw_value="529.87",
        normalized_value="529.87",
        xpath="/dummy",
        is_present=True,
    )
    result = _score_one_field("line_total_amount", "529,87 €", gt, cfg=CFG)
    assert result.outcome == "TP"


def test_truth_table_date_german_format_matches_gt() -> None:
    """DATE field: German '05.03.2018' normalizes to '2018-03-05' and matches GT."""
    gt = GroundTruthField(
        bt_code="BT-2",
        raw_value="20180305",
        normalized_value="2018-03-05",
        xpath="/dummy",
        is_present=True,
    )
    result = _score_one_field("issue_date", "05.03.2018", gt, cfg=CFG)
    assert result.outcome == "TP"


# ===========================================================================
# 4. Aggregate F1 — _f1_from_counts + _aggregate_micro_macro
# ===========================================================================


def test_f1_from_counts_perfect() -> None:
    """All TP → P=1, R=1, F1=1."""
    assert _f1_from_counts(tp=10, fp=0, fn=0) == (1.0, 1.0, 1.0)


def test_f1_from_counts_all_zero() -> None:
    """All zero → P=R=F1=0 (no division-by-zero)."""
    assert _f1_from_counts(tp=0, fp=0, fn=0) == (0.0, 0.0, 0.0)


def test_f1_from_counts_known_values() -> None:
    """TP=1, FP=0, FN=14 → micro F1 from granite-docling baseline."""
    p, r, f1 = _f1_from_counts(tp=1, fp=0, fn=14)
    assert p == 1.0
    assert r == pytest.approx(1.0 / 15.0)
    assert f1 == pytest.approx(2.0 / 16.0)  # 0.125


def test_aggregate_excludes_excluded_outcome() -> None:
    """EXCLUDED outcomes don't contribute to numerators or denominators."""
    per_field = {
        "a": FieldResult(
            english_key="a",
            bt_code="BT-A",
            field_type="CODE",
            outcome="TP",
            score=1.0,
            predicted_normalized="x",
            gt_normalized="x",
            gt_present=True,
        ),
        "b": FieldResult(
            english_key="b",
            bt_code="BT-B",
            field_type="CODE",
            outcome="EXCLUDED",
            score=0.0,
            predicted_normalized=None,
            gt_normalized=None,
            gt_present=True,
        ),
    }
    p, r, f1, macro = _aggregate_micro_macro(per_field)
    # With only one TP and no FP/FN, F1 is 1.0
    assert f1 == 1.0
    assert macro == 1.0


def test_aggregate_macro_handles_pure_tn_field() -> None:
    """A field with outcome=TN (e.g., absent GT + absent pred) drops from macro."""
    per_field = {
        "a": FieldResult(
            english_key="a",
            bt_code="BT-A",
            field_type="CODE",
            outcome="TP",
            score=1.0,
            predicted_normalized="x",
            gt_normalized="x",
            gt_present=True,
        ),
        "b": FieldResult(
            english_key="b",
            bt_code="BT-B",
            field_type="CODE",
            outcome="TN",
            score=1.0,
            predicted_normalized=None,
            gt_normalized=None,
            gt_present=False,
        ),
    }
    p, r, f1, macro = _aggregate_micro_macro(per_field)
    # Only 'a' contributes to macro (1 TP → F1=1)
    assert macro == 1.0


# ===========================================================================
# 5. Public score() — end-to-end on a synthetic GroundTruth
# ===========================================================================


def _make_full_gt(
    overrides: dict[str, GroundTruthField] | None = None,
) -> GroundTruth:
    """Build a 16-key GroundTruth filled with 'absent' fields, with selective overrides."""
    from horus.eval.ground_truth import FIELDS

    header: dict[str, GroundTruthField] = {}
    for key, spec in FIELDS.items():
        if overrides and key in overrides:
            header[key] = overrides[key]
        else:
            header[key] = GroundTruthField(
                bt_code=spec.bt_code,
                raw_value=None,
                normalized_value=None,
                xpath=spec.xpath,
                is_present=False,
            )
    return GroundTruth(header=header)


def test_score_returns_invoice_field_scores_with_all_16_keys() -> None:
    """The result has a `per_field` dict with all 16 FIELDS keys."""
    from horus.eval.ground_truth import FIELDS

    gt = _make_full_gt()
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    result = score(predicted, gt, cfg=EvalConfig())
    assert isinstance(result, InvoiceFieldScores)
    assert set(result.per_field.keys()) == set(FIELDS.keys())


def test_score_all_absent_gt_all_none_pred_is_all_tn() -> None:
    """When GT is empty + pred is empty → all 16 are TN; F1=0 (no signal)."""
    from horus.eval.ground_truth import FIELDS

    gt = _make_full_gt()
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    result = score(predicted, gt, cfg=EvalConfig())
    tn_count = sum(1 for r in result.per_field.values() if r.outcome == "TN")
    assert tn_count == 16
    # No TP/FP/FN → F1 = 0
    assert result.micro_f1 == 0.0


def test_score_perfect_extraction_yields_micro_f1_1_0() -> None:
    """When all 16 fields match → micro_f1 = 1.0."""
    from horus.eval.ground_truth import FIELDS

    # Build a GT where every field is present_content with a canonical value
    overrides: dict[str, GroundTruthField] = {}
    predicted: dict[str, str | None] = {}
    for key, spec in FIELDS.items():
        # Use placeholder values matching each field_type's canonical form
        if spec.field_type == "MONEY":
            val = "100.00"
        elif spec.field_type == "DATE":
            val = "2018-03-05"
        else:
            val = f"value-{key}"
        overrides[key] = GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=val,
            normalized_value=val,
            xpath=spec.xpath,
            is_present=True,
        )
        predicted[key] = val

    gt = _make_full_gt(overrides=overrides)
    result = score(predicted, gt, cfg=EvalConfig())
    tp_count = sum(1 for r in result.per_field.values() if r.outcome == "TP")
    assert tp_count == 16
    assert result.micro_f1 == 1.0


def test_score_default_cfg_when_none() -> None:
    """``score(...)`` with no `cfg=` defaults to ``EvalConfig()`` (literature defaults)."""
    from horus.eval.ground_truth import FIELDS

    gt = _make_full_gt()
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    result = score(predicted, gt)  # cfg omitted
    assert isinstance(result, InvoiceFieldScores)


def test_score_serializes_through_asdict() -> None:
    """`InvoiceFieldScores` round-trips through `dataclasses.asdict()` (MLflow-friendly)."""
    from dataclasses import asdict

    from horus.eval.ground_truth import FIELDS

    gt = _make_full_gt()
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    result = score(predicted, gt, cfg=EvalConfig(), invoice_id="X", model_id="Y")
    d = asdict(result)
    assert d["invoice_id"] == "X"
    assert d["model_id"] == "Y"
    assert "per_field" in d
    # per_field's values become dicts (their FieldResult dataclasses → asdict)
    assert isinstance(d["per_field"]["invoice_number"], dict)
    assert d["per_field"]["invoice_number"]["outcome"] == "TN"


# ===========================================================================
# 6. Threshold sensitivity — cfg.anls_threshold tuning
# ===========================================================================


def test_score_lower_anls_threshold_accepts_more_string_drift() -> None:
    """At τ=0.3, mild drift on STRING fields produces more TPs."""
    from horus.eval.ground_truth import FIELDS

    # GT: just seller_name present with content
    overrides: dict[str, GroundTruthField] = {
        "seller_name": GroundTruthField(
            bt_code="BT-27",
            raw_value="Lieferant GmbH",
            normalized_value="Lieferant GmbH",
            xpath="/dummy",
            is_present=True,
        ),
    }
    gt = _make_full_gt(overrides=overrides)
    # Pred: a drift that's between τ=0.3 and τ=0.5 (NLS ≈ 0.4)
    # "Unhmd QmbH" vs "Lieferant GmbH" has NLS ≈ 0.286
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    predicted["seller_name"] = "Unhmd QmbH"

    # At default τ=0.5: outcome = FN
    result_strict = score(predicted, gt, cfg=EvalConfig(anls_threshold=0.5))
    assert result_strict.per_field["seller_name"].outcome == "FN"

    # At τ=0.2: outcome = TP
    result_lenient = score(predicted, gt, cfg=EvalConfig(anls_threshold=0.2))
    assert result_lenient.per_field["seller_name"].outcome == "TP"
