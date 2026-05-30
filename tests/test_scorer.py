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
from horus.eval.ground_truth import FieldType, GroundTruth, GroundTruthField
from horus.eval.scorer import (
    DOCUMENT_FIELDS,
    FIELD_GROUPS,
    FieldResult,
    InvoiceFieldScores,
    Outcome,
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
    f1_from_counts,
    group_level_counts,
    group_level_f1,
    label_outcome_counts,
    presence_conditional_counts,
    presence_conditional_f1,
    score,
    spurious_emission_counts,
    spurious_emission_rate,
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


# ===========================================================================
# 7. ADR-027 additive metrics — per-canonical-label F1, presence-conditional
#    F1, KIEval group-level F1, spurious-emission rate
# ===========================================================================


def _fr(
    english_key: str,
    outcome: Outcome,
    *,
    gt_present: bool,
    field_type: FieldType = "CODE",
) -> FieldResult:
    """Build a synthetic FieldResult for ADR-027 metric tests."""
    return FieldResult(
        english_key=english_key,
        bt_code="BT-X",
        field_type=field_type,
        outcome=outcome,
        score=1.0 if outcome == "TP" else 0.0,
        predicted_normalized="x" if outcome in ("TP", "FP") else None,
        gt_normalized="x" if gt_present else None,
        gt_present=gt_present,
    )


# ---- partition + public f1 helper ----


def test_field_groups_partition_exactly_covers_registry() -> None:
    """seller ∪ buyer ∪ totals ∪ document == FIELDS, pairwise disjoint (ADR-027)."""
    from horus.eval.ground_truth import FIELDS

    grouped = frozenset().union(*FIELD_GROUPS.values())
    assert grouped.isdisjoint(DOCUMENT_FIELDS)
    assert grouped | DOCUMENT_FIELDS == set(FIELDS)
    # `totals` is exactly the 5 MONEY fields.
    money = {k for k, s in FIELDS.items() if s.field_type == "MONEY"}
    assert FIELD_GROUPS["totals"] == money


def test_f1_from_counts_public_matches_private() -> None:
    """Public wrapper delegates to the private implementation (ADR-027 single-source)."""
    assert f1_from_counts(3, 1, 1) == _f1_from_counts(3, 1, 1)


# ---- label_outcome_counts (per-canonical-label F1 primitive) ----


def test_label_outcome_counts_tallies_per_label() -> None:
    results = [
        _fr("invoice_number", "TP", gt_present=True),
        _fr("invoice_number", "FN", gt_present=True),
        _fr("seller_name", "FP", gt_present=False),
    ]
    counts = label_outcome_counts(results)
    assert counts["invoice_number"] == (1, 0, 1)  # (tp, fp, fn)
    assert counts["seller_name"] == (0, 1, 0)


def test_label_outcome_counts_skips_tn_and_excluded() -> None:
    results = [
        _fr("invoice_number", "TN", gt_present=False),
        _fr("seller_name", "EXCLUDED", gt_present=True),
    ]
    assert label_outcome_counts(results) == {}


# ---- presence-conditional F1 ----


def test_presence_conditional_counts_restricts_to_present() -> None:
    """Absent-GT fields drop out; present TP/FN are pooled."""
    results = [
        _fr("a", "TP", gt_present=True),
        _fr("b", "FN", gt_present=True),
        _fr("c", "FP", gt_present=False),  # absent → excluded
        _fr("d", "TN", gt_present=False),  # absent → excluded
    ]
    assert presence_conditional_counts(results) == (1, 0, 1)


def test_presence_conditional_f1_is_recall_faithful() -> None:
    """3 TP + 2 FN over present fields → F1 = 0.75 (precision ≡ 1 by truth table)."""
    results = [_fr(f"k{i}", "TP", gt_present=True) for i in range(3)]
    results += [_fr(f"k{i}", "FN", gt_present=True) for i in range(3, 5)]
    assert presence_conditional_f1(results) == pytest.approx(0.75)


def test_presence_conditional_excludes_excluded_present_field() -> None:
    results = [
        _fr("a", "TP", gt_present=True),
        _fr("b", "EXCLUDED", gt_present=True),
    ]
    assert presence_conditional_counts(results) == (1, 0, 0)


# ---- spurious-emission rate ----


def test_spurious_emission_rate_on_absent_fields() -> None:
    """1 hallucinated FP among 4 absent fields → rate 0.25."""
    results = [
        _fr("a", "FP", gt_present=False),
        _fr("b", "TN", gt_present=False),
        _fr("c", "TN", gt_present=False),
        _fr("d", "TN", gt_present=False),
        _fr("e", "TP", gt_present=True),  # present → not in denominator
    ]
    assert spurious_emission_counts(results) == (1, 4)
    assert spurious_emission_rate(results) == pytest.approx(0.25)


def test_spurious_emission_rate_zero_when_no_absent_fields() -> None:
    results = [_fr("a", "TP", gt_present=True)]
    assert spurious_emission_rate(results) == 0.0


# ---- KIEval group-level F1 (§4.1, all-or-nothing) ----


def test_group_level_fully_correct_group_is_tp() -> None:
    """All seller members TP → seller group scores TP."""
    results = [
        _fr("seller_name", "TP", gt_present=True),
        _fr("seller_vat_id", "TP", gt_present=True),
        _fr("seller_tax_id", "TP", gt_present=True),
        _fr("seller_gln", "TP", gt_present=True),
    ]
    assert group_level_counts(results) == (1, 0, 0)
    assert group_level_f1(results) == 1.0


def test_group_level_partial_group_is_miss() -> None:
    """One FN in the seller group → not TP (matched-non-identical → fn + fp)."""
    results = [
        _fr("seller_name", "TP", gt_present=True),
        _fr("seller_vat_id", "FN", gt_present=True),
    ]
    assert group_level_counts(results) == (0, 1, 1)
    assert group_level_f1(results) == 0.0


def test_group_level_skips_group_with_no_signal() -> None:
    """A group whose members are all TN/absent contributes nothing."""
    results = [
        _fr("buyer_name", "TN", gt_present=False),
        _fr("buyer_reference", "TN", gt_present=False),
        _fr("buyer_vat_id", "TN", gt_present=False),
    ]
    assert group_level_counts(results) == (0, 0, 0)


def test_group_level_hallucinated_group_is_fp_only() -> None:
    """A group with only FP members (no GT content) → FP, not FN."""
    results = [_fr("buyer_name", "FP", gt_present=False)]
    assert group_level_counts(results) == (0, 1, 0)


def test_group_level_f1_multi_group() -> None:
    """seller TP + buyer TP + totals miss → tp=2, fp=1, fn=1 → F1 = 2/3."""
    results = [
        _fr("seller_name", "TP", gt_present=True),
        _fr("buyer_name", "TP", gt_present=True),
        _fr("line_total_amount", "TP", gt_present=True, field_type="MONEY"),
        _fr("tax_basis_total_amount", "TP", gt_present=True, field_type="MONEY"),
        _fr("tax_total_amount", "TP", gt_present=True, field_type="MONEY"),
        _fr("grand_total_amount", "TP", gt_present=True, field_type="MONEY"),
        _fr("due_payable_amount", "FN", gt_present=True, field_type="MONEY"),
    ]
    assert group_level_counts(results) == (2, 1, 1)
    assert group_level_f1(results) == pytest.approx(2 / 3)


# ---- score() integration: new metrics populated + additive guarantee ----


def test_score_populates_adr027_metrics() -> None:
    """score() fills presence_conditional_f1 / group_level_f1 / spurious_emission_rate."""
    from horus.eval.ground_truth import FIELDS

    overrides: dict[str, GroundTruthField] = {}
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    for key, spec in FIELDS.items():
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
    # Perfect extraction → all new metrics maxed, no hallucination.
    assert result.presence_conditional_f1 == 1.0
    assert result.group_level_f1 == 1.0
    assert result.spurious_emission_rate == 0.0
    # Additive guarantee: existing micro/macro unchanged.
    assert result.micro_f1 == 1.0
    assert result.macro_f1 == 1.0


def test_score_adr027_metrics_serialize_through_asdict() -> None:
    """The 3 new per-invoice metric fields survive `dataclasses.asdict` (MLflow-friendly)."""
    from dataclasses import asdict

    from horus.eval.ground_truth import FIELDS

    gt = _make_full_gt()
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    d = asdict(score(predicted, gt, cfg=EvalConfig()))
    assert "presence_conditional_f1" in d
    assert "group_level_f1" in d
    assert "spurious_emission_rate" in d
