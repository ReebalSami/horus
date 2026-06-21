"""Per-field F1 scorer for pilot #13 (PR(b) per ADR-013).

Takes a predicted dict (from `adapters.to_predicted_dict()`) + a `GroundTruth`
(from PR(a)'s `parse_cii_xml()`) + an `EvalConfig` (tolerance knobs) and
produces an `InvoiceFieldScores` with:

  - per-field outcomes (TP / FP / FN / TN / EXCLUDED) per the 12-cell truth
    table from ADR-013 §"Decision + integration thoughts"
  - per-field comparator scores (ANLS\\* for STRING, 0.0 or 1.0 for typed)
  - micro + macro F1, precision, recall
  - ADR-027 additive metrics: presence-conditional F1, KIEval group-level F1,
    spurious-emission rate (per-invoice); per-canonical-label F1 (cohort)

Truth table (GT 4-state × Pred 3-state → outcome):

==================== ============== ============= =============
GT state             Pred = None    Pred = ""     Pred = content
==================== ============== ============= =============
absent               TN             FP            FP
present_empty        FN             TN            TN (soft)
present_content      FN             FN            TP if score ≥ τ
                                                  else FN
normalizer_rejected  EXCLUDED       EXCLUDED      EXCLUDED
==================== ============== ============= =============

Per-field-type comparator dispatch (via `FieldSpec.field_type`):

  - ``STRING``: ANLS\\* with `cfg.anls_threshold` (Biten+ ICCV'19)
  - ``MONEY``:  exact match on canonical Decimal-2 string
  - ``DATE``:   exact match on ISO-8601 string
  - ``CODE``:   exact match on whitespace-stripped NFC string

Refs: ADR-013 (this), ADR-012 (parent: GT parser), Biten+ ICCV'19 (ANLS metric),
      DocILE (`docs/sources/tools/docile-rossumai.md` — micro-F1 framework).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from horus.config import EvalConfig
from horus.eval.anls import anls, nls
from horus.eval.ground_truth import (
    FIELDS,
    REPEATING_GROUPS,
    FieldSpec,
    FieldType,
    GroundTruth,
    GroundTruthField,
)
from horus.eval.normalizers import (
    _normalize_predicted_code,
    _normalize_predicted_date,
    _normalize_predicted_money,
    _normalize_predicted_rate,
    _normalize_predicted_string,
)

__all__ = [
    "DOCUMENT_FIELDS",
    "FIELD_GROUPS",
    "FieldResult",
    "InvoiceFieldScores",
    "RepeatingGroupResult",
    "f1_from_counts",
    "group_level_counts",
    "group_level_f1",
    "label_outcome_counts",
    "presence_conditional_counts",
    "presence_conditional_f1",
    "score",
    "score_repeating_group",
    "spurious_emission_counts",
    "spurious_emission_rate",
]

Outcome = Literal["TP", "FP", "FN", "TN", "EXCLUDED"]


# ---------------------------------------------------------------------------
# Result dataclasses — frozen, JSON-serializable via dataclasses.asdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldResult:
    """One field's scoring outcome — the per-cell content of the F1 heatmap.

    Frozen for cheap hashing + clean serialization through
    ``dataclasses.asdict()`` (the path MLflow's `log_dict` consumes per
    ADR-011).

    Attributes:
        english_key: HORUS-canonical English field name (matches ``FIELDS``).
        bt_code: EN16931 business-term code (e.g., ``"BT-1"``) — preserves
            standards traceability through to the per-field artifact dict.
        field_type: comparator-dispatch discriminator from ``FieldSpec``.
        outcome: TP / FP / FN / TN / EXCLUDED per the truth table.
        score: float in [0.0, 1.0]. For ``STRING`` outcomes, the post-threshold
            ANLS\\* score (1.0 = exact match, 0.0 = collapsed below threshold).
            For ``MONEY`` / ``DATE`` / ``CODE`` outcomes, 1.0 (TP) or 0.0 (any
            non-TP outcome) — typed fields are exact-match-or-bust.
        predicted_normalized: post-normalization predicted value (the form
            actually used in the comparator). ``None`` if predicted was None.
        gt_normalized: ``GroundTruthField.normalized_value`` — the form used
            on the GT side of the comparator.
        gt_present: ``GroundTruthField.is_present``.
    """

    english_key: str
    bt_code: str
    field_type: FieldType
    outcome: Outcome
    score: float
    predicted_normalized: str | None
    gt_normalized: str | None
    gt_present: bool


@dataclass(frozen=True)
class RepeatingGroupResult:
    """Scored result for one repeating group (ADR-042).

    Covers the VAT breakdown (BG-23), Skonto tiers, and the line-item table
    (BG-25). Predicted rows are aligned to GT rows by greedy maximum-similarity
    bipartite matching; each aligned cell is then scored with the SAME truth-table
    + comparator dispatch as a flat field. `cell_results` is the flattened
    per-cell `FieldResult` list (each keyed ``<group>[<pair>].<sub_field>``); the
    group P/R/F1 pools their TP/FP/FN. Matched/missed/spurious row counts are kept
    for diagnostics.
    """

    group_key: str
    cell_results: list[FieldResult] = field(default_factory=list)
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    n_gt_rows: int = 0
    n_pred_rows: int = 0
    n_matched_rows: int = 0


@dataclass(frozen=True)
class InvoiceFieldScores:
    """Scored results for one (invoice, model) pair.

    Frozen + JSON-friendly. The ``per_field`` dict has one entry per
    ``FIELDS`` key; aggregate F1 / precision / recall are micro + macro
    flavors as documented in ADR-013 §"Decision + integration thoughts".

    Attributes:
        invoice_id: human-readable invoice identifier (e.g.,
            ``"EN16931_Einfach"``) — for grouping per-invoice rows in
            the heatmap.
        model_id: cohort model identifier (e.g.,
            ``"ibm-granite/granite-docling-258M-mlx"``).
        per_field: ``dict[english_key, FieldResult]`` — 16 entries (or
            whichever subset of FIELDS was scored).
        micro_f1: aggregated TP/FP/FN across all per_field results,
            single F1.
        macro_f1: average of per-field F1 across the 16 fields, skipping
            fields where the per-field denominator is 0 (the EXCLUDED-only
            edge case).
        micro_precision: TP / (TP + FP) aggregated across all fields.
        micro_recall: TP / (TP + FN) aggregated across all fields.
        presence_conditional_f1: F1 over GT-present fields only (ADR-027
            metric 2). Recall-faithful — HORUS's truth table yields FP only
            on the absent-GT row, so precision ≡ 1 on the present subset.
        group_level_f1: KIEval (arXiv 2503.05488 §4.1) all-or-nothing group
            F1 over ``FIELD_GROUPS`` (seller / buyer / totals); document-level
            scalars excluded as the non-group G′ (ADR-027 metric 3).
        spurious_emission_rate: FP / (FP + TN) over genuinely-absent fields —
            the hallucination rate (ADR-027 metric 4).
    """

    invoice_id: str
    model_id: str
    per_field: dict[str, FieldResult] = field(default_factory=dict)
    micro_f1: float = 0.0
    macro_f1: float = 0.0
    micro_precision: float = 0.0
    micro_recall: float = 0.0
    presence_conditional_f1: float = 0.0
    group_level_f1: float = 0.0
    spurious_emission_rate: float = 0.0
    # ADR-042 repeating groups. Populated ONLY when `score(predicted_groups=...)`
    # is given; otherwise empty + the overall_* fields equal the flat micro_*.
    repeating: dict[str, RepeatingGroupResult] = field(default_factory=dict)
    overall_micro_f1: float = 0.0
    overall_micro_precision: float = 0.0
    overall_micro_recall: float = 0.0


# ---------------------------------------------------------------------------
# Predicted-side normalizers (moved to `normalizers.py` per ADR-035)
# ---------------------------------------------------------------------------
#
# `_normalize_predicted_{money,date,code,string}` + the new `_rate` now live in
# `src/horus/eval/normalizers.py` so `schema.py`'s `InvoiceFields` validate/
# repair reuses the SAME canonicalization (one home, no duplication). They are
# imported above and re-exported here, so existing call sites + tests
# (`from horus.eval.scorer import _normalize_predicted_money`) keep working.


# ---------------------------------------------------------------------------
# Per-field-type comparators
# ---------------------------------------------------------------------------


def _compare_string(predicted: str, gt: str, *, threshold: float) -> tuple[float, bool]:
    """Compare two STRING values using ANLS\\* with the configured threshold.

    Returns:
        ``(anls_score, is_tp)`` where ``is_tp`` is ``True`` iff
        ``anls_score >= threshold`` (i.e., the prediction is acceptable
        OCR-tolerant match).
    """
    score = anls(predicted, gt, threshold=threshold)
    is_tp = score >= threshold and score > 0.0
    return score, is_tp


def _compare_typed_exact(predicted_norm: str, gt_norm: str) -> tuple[float, bool]:
    """Compare two normalized typed values (MONEY/DATE/CODE) by exact match.

    Returns:
        ``(1.0, True)`` if values are byte-equal post-normalization, else
        ``(0.0, False)``. The 1.0/0.0 score reflects the exact-match
        semantics — there is no partial credit on typed fields.
    """
    if predicted_norm == gt_norm:
        return 1.0, True
    return 0.0, False


# ---------------------------------------------------------------------------
# Truth-table dispatch
# ---------------------------------------------------------------------------
#
# Categorize the GT side into one of 4 states based on `GroundTruthField`:
#   - "absent"               — is_present=False (XPath returned 0 elements)
#   - "present_empty"        — is_present=True, normalized_value == ""
#   - "present_content"      — is_present=True, normalized_value is non-empty
#   - "normalizer_rejected"  — is_present=True, normalized_value is None
#                              (corpus anomaly per ADR-012)


def _gt_state(gt_field: GroundTruthField) -> str:
    """Categorize a GT field into one of the 4 truth-table rows."""
    if not gt_field.is_present:
        return "absent"
    if gt_field.normalized_value is None:
        return "normalizer_rejected"
    if gt_field.normalized_value == "":
        return "present_empty"
    return "present_content"


def _score_one_field(
    english_key: str,
    predicted: str | None,
    gt_field: GroundTruthField,
    *,
    cfg: EvalConfig,
) -> FieldResult:
    """Score one flat field against its GT (spec read from `FIELDS`)."""
    return _score_against_spec(english_key, FIELDS[english_key], predicted, gt_field, cfg=cfg)


def _score_against_spec(
    english_key: str,
    spec: FieldSpec,
    predicted: str | None,
    gt_field: GroundTruthField,
    *,
    cfg: EvalConfig,
) -> FieldResult:
    """Score one (predicted, gt_field) pair against an explicit `FieldSpec`.

    The spec-explicit core shared by flat fields (`_score_one_field`, spec from
    `FIELDS`) and repeating-group cells (spec from a sub-field registry; ADR-042).
    Full truth-table + comparator dispatch. `english_key` is the label stamped on
    the returned `FieldResult` (a flat key, or ``<group>[<pair>].<sub_field>``).
    """
    state = _gt_state(gt_field)

    # ---- EXCLUDED row: GT was rejected by normalizer (corpus anomaly) ----
    if state == "normalizer_rejected":
        return FieldResult(
            english_key=english_key,
            bt_code=spec.bt_code,
            field_type=spec.field_type,
            outcome="EXCLUDED",
            score=0.0,
            predicted_normalized=None,
            gt_normalized=None,
            gt_present=gt_field.is_present,
        )

    # Normalize the prediction side (None passes through). A field may carry an
    # explicit `predicted_normalize` hook (ADR-048) that overrides the
    # field_type-based dispatch — used where the GT is a controlled-vocabulary
    # code that is never printed verbatim (vat_breakdown.category_code), so the
    # model's rendering must be mapped back to the code.
    if predicted is None:
        pred_norm: str | None = None
    elif spec.predicted_normalize is not None:
        pred_norm = spec.predicted_normalize(predicted)
    elif spec.field_type == "MONEY":
        pred_norm = _normalize_predicted_money(predicted)
    elif spec.field_type == "DATE":
        pred_norm = _normalize_predicted_date(predicted)
    elif spec.field_type == "CODE":
        pred_norm = _normalize_predicted_code(predicted, nfc=cfg.string_normalize_nfc)
    elif spec.field_type == "RATE":
        pred_norm = _normalize_predicted_rate(predicted)
    elif spec.field_type == "STRING":
        pred_norm = _normalize_predicted_string(predicted, nfc=cfg.string_normalize_nfc)
    else:  # pragma: no cover — exhaustive over FieldType Literal
        pred_norm = predicted

    # ---- "absent" row: GT has no value ----
    if state == "absent":
        if pred_norm is None:
            # Pred is also None → TN (correct rejection)
            return FieldResult(
                english_key=english_key,
                bt_code=spec.bt_code,
                field_type=spec.field_type,
                outcome="TN",
                score=1.0,
                predicted_normalized=None,
                gt_normalized=None,
                gt_present=False,
            )
        # Pred has content (empty or otherwise) → FP (model invented a value)
        return FieldResult(
            english_key=english_key,
            bt_code=spec.bt_code,
            field_type=spec.field_type,
            outcome="FP",
            score=0.0,
            predicted_normalized=pred_norm,
            gt_normalized=None,
            gt_present=False,
        )

    # ---- "present_empty" row: GT is "" ----
    if state == "present_empty":
        if pred_norm is None or pred_norm == "":
            # Both empty-ish → TN (acceptable)
            return FieldResult(
                english_key=english_key,
                bt_code=spec.bt_code,
                field_type=spec.field_type,
                outcome="TN",
                score=1.0,
                predicted_normalized=pred_norm,
                gt_normalized="",
                gt_present=True,
            )
        # Pred has content but GT is empty → FN (we don't know what the
        # right answer is; treat the over-prediction as not-correct)
        return FieldResult(
            english_key=english_key,
            bt_code=spec.bt_code,
            field_type=spec.field_type,
            outcome="FN",
            score=0.0,
            predicted_normalized=pred_norm,
            gt_normalized="",
            gt_present=True,
        )

    # ---- "present_content" row: GT has a real value ----
    # state == "present_content" — gt_normalized is non-empty
    gt_norm = gt_field.normalized_value
    assert gt_norm is not None and gt_norm != ""

    if pred_norm is None:
        # Pred missing → FN
        return FieldResult(
            english_key=english_key,
            bt_code=spec.bt_code,
            field_type=spec.field_type,
            outcome="FN",
            score=0.0,
            predicted_normalized=None,
            gt_normalized=gt_norm,
            gt_present=True,
        )

    # Both sides have content — run the comparator
    if spec.field_type == "STRING":
        score, is_tp = _compare_string(pred_norm, gt_norm, threshold=cfg.anls_threshold)
    else:
        # MONEY / DATE / CODE — exact match on normalized
        score, is_tp = _compare_typed_exact(pred_norm, gt_norm)

    outcome: Outcome = "TP" if is_tp else "FN"
    # On TP for STRING, we still report the ANLS\\* score (which may be < 1.0).
    # On TP for typed fields, the score is 1.0 by construction.
    # On FN for STRING, the score is the (sub-threshold) NLS for diagnostic value.
    if not is_tp and spec.field_type == "STRING":
        # Capture the raw NLS even when below threshold, so the heatmap shows
        # "how close" each model got. This is diagnostic; F1 dispatch uses
        # is_tp not score.
        score = nls(pred_norm, gt_norm)
    return FieldResult(
        english_key=english_key,
        bt_code=spec.bt_code,
        field_type=spec.field_type,
        outcome=outcome,
        score=score,
        predicted_normalized=pred_norm,
        gt_normalized=gt_norm,
        gt_present=True,
    )


# ---------------------------------------------------------------------------
# Aggregation — micro + macro F1
# ---------------------------------------------------------------------------


def _f1_from_counts(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Compute (precision, recall, F1) from raw TP/FP/FN counts.

    Returns 0.0 for any denominator-zero case (matches the DocILE convention
    + scikit-learn's ``zero_division=0`` default).
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def f1_from_counts(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Public (precision, recall, F1) from TP/FP/FN counts.

    Thin public wrapper over `_f1_from_counts` so cohort-pooling callers
    (`scripts/inspect_pilot_13.py`) compute F1 from pooled counts via the same
    zero-division convention as the per-invoice path (ADR-027 single-source).
    """
    return _f1_from_counts(tp, fp, fn)


def _aggregate_micro_macro(
    per_field: dict[str, FieldResult],
) -> tuple[float, float, float, float]:
    """Aggregate per-field results into (micro_precision, micro_recall, micro_f1, macro_f1).

    Micro: pool TP/FP/FN across all fields, then compute one global F1.
    Macro: compute per-field F1, then average (excluding fields with no
    TP/FP/FN/TN at all — i.e., EXCLUDED).

    The EXCLUDED outcome contributes to neither numerator nor denominator
    on either flavor (per ADR-013 §"Truth table").
    """
    # Pool TP/FP/FN for micro
    micro_tp = sum(1 for r in per_field.values() if r.outcome == "TP")
    micro_fp = sum(1 for r in per_field.values() if r.outcome == "FP")
    micro_fn = sum(1 for r in per_field.values() if r.outcome == "FN")
    micro_p, micro_r, micro_f1 = _f1_from_counts(micro_tp, micro_fp, micro_fn)

    # Per-field F1 for macro
    per_field_f1s: list[float] = []
    for r in per_field.values():
        if r.outcome == "EXCLUDED":
            continue  # drops from numerator + denominator
        # For a single field: TP=1 if outcome==TP, FP=1 if FP, FN=1 if FN,
        # else 0. TN contributes 0 to numerator + denominator (the precision
        # and recall denominators are zero → F1=0 per `_f1_from_counts`).
        tp = 1 if r.outcome == "TP" else 0
        fp = 1 if r.outcome == "FP" else 0
        fn = 1 if r.outcome == "FN" else 0
        if tp + fp + fn == 0:
            # Pure TN — skip from macro average (no signal)
            continue
        _, _, f1 = _f1_from_counts(tp, fp, fn)
        per_field_f1s.append(f1)
    macro_f1 = sum(per_field_f1s) / len(per_field_f1s) if per_field_f1s else 0.0

    return micro_p, micro_r, micro_f1, macro_f1


# ---------------------------------------------------------------------------
# ADR-027 — additive metric expansion (per-canonical-label F1, presence-
# conditional F1, KIEval group-level F1, spurious-emission rate).
#
# All four re-aggregate the per-field `FieldResult.outcome` data the scorer
# already produces — no VLM, no re-run. The count-returning helpers accept any
# `Iterable[FieldResult]`, so the SAME math serves both the per-invoice path
# (here, via `score`) and the cohort-pooled path (`scripts/inspect_pilot_13.py`
# reconstructs `FieldResult` from `per_field_scores.json` and pools).
# ---------------------------------------------------------------------------

# KIEval (§4.1) group partition over the `FIELDS` registry. seller / buyer /
# totals / payment are EN16931 business groups; the document-level scalars are
# the non-group entities KIEval folds into the excluded 1st group (G'). The
# ADR-035 address fields join their party groups (seller_address → seller,
# buyer_address → buyer); tax_rate is a document-level scalar (→ DOCUMENT_FIELDS).
# ADR-041 Step 1a adds the `payment` business group (due date / means / bank
# details / reference), grows `totals` with the prepaid/allowance/charge/
# rounding amounts, and adds document_type / order ref / billing period as
# document-level scalars.
FIELD_GROUPS: dict[str, frozenset[str]] = {
    "seller": frozenset(
        {"seller_name", "seller_vat_id", "seller_tax_id", "seller_gln", "seller_address"}
    ),
    "buyer": frozenset({"buyer_name", "buyer_reference", "buyer_vat_id", "buyer_address"}),
    "totals": frozenset(
        {
            "line_total_amount",
            "tax_basis_total_amount",
            "tax_total_amount",
            "grand_total_amount",
            "due_payable_amount",
            "prepaid_amount",
            "allowance_total_amount",
            "charge_total_amount",
            "rounding_amount",
        }
    ),
    "payment": frozenset(
        {
            "payment_due_date",
            "payment_means_code",
            "payment_means_text",
            "seller_iban",
            "seller_bic",
            "seller_account_name",
            "payment_reference",
        }
    ),
}

# G' — non-group document-level scalars, EXCLUDED from group-level F1 (ADR-027).
DOCUMENT_FIELDS: frozenset[str] = frozenset(
    {
        "invoice_number",
        "issue_date",
        "invoice_currency_code",
        "delivery_date",
        "tax_rate",
        "document_type",
        "buyer_order_reference",
        "billing_period_start",
        "billing_period_end",
    }
)

# Partition sanity: groups ∪ document-fields must exactly cover FIELDS, with no
# overlap. Fails fast at import if the registry drifts from this partition.
_GROUPED_KEYS: frozenset[str] = frozenset().union(*FIELD_GROUPS.values())
assert _GROUPED_KEYS.isdisjoint(DOCUMENT_FIELDS), "FIELD_GROUPS overlaps DOCUMENT_FIELDS"
assert _GROUPED_KEYS | DOCUMENT_FIELDS == set(FIELDS), (
    "FIELD_GROUPS ∪ DOCUMENT_FIELDS must exactly cover FIELDS (ADR-027 partition drift)"
)


def label_outcome_counts(results: Iterable[FieldResult]) -> dict[str, tuple[int, int, int]]:
    """Per-canonical-label (TP, FP, FN) tally — the per-label pooling primitive.

    Pass one invoice's results for per-invoice counts, or a cohort-wide iterable
    for pooled per-label counts. TN / EXCLUDED contribute no signal. Returns
    ``{english_key: (tp, fp, fn)}`` (only keys with ≥1 signal-bearing outcome).
    """
    counts: dict[str, list[int]] = {}
    for r in results:
        if r.outcome == "TP":
            idx = 0
        elif r.outcome == "FP":
            idx = 1
        elif r.outcome == "FN":
            idx = 2
        else:  # TN / EXCLUDED — no signal
            continue
        bucket = counts.setdefault(r.english_key, [0, 0, 0])
        bucket[idx] += 1
    return {k: (v[0], v[1], v[2]) for k, v in counts.items()}


def presence_conditional_counts(results: Iterable[FieldResult]) -> tuple[int, int, int]:
    """Pool (TP, FP, FN) over GT-present fields only (ADR-027 metric 2).

    Conditions on ground-truth presence: drops absent-GT fields (and EXCLUDED)
    so honest nulls on genuinely-missing fields neither help nor hurt. On the
    present subset HORUS's truth table yields no FP, so the F1 is recall-faithful.
    """
    tp = fp = fn = 0
    for r in results:
        if not r.gt_present or r.outcome == "EXCLUDED":
            continue
        if r.outcome == "TP":
            tp += 1
        elif r.outcome == "FP":  # structurally absent on present rows; counted defensively
            fp += 1
        elif r.outcome == "FN":
            fn += 1
    return tp, fp, fn


def presence_conditional_f1(results: Iterable[FieldResult]) -> float:
    """F1 over GT-present fields (ADR-027 metric 2). See `presence_conditional_counts`."""
    tp, fp, fn = presence_conditional_counts(results)
    return _f1_from_counts(tp, fp, fn)[2]


def spurious_emission_counts(results: Iterable[FieldResult]) -> tuple[int, int]:
    """(FP, n_absent) over genuinely-absent fields (ADR-027 metric 4).

    Absent-GT fields resolve to TN (pred None) or FP (pred content); EXCLUDED
    cannot occur on the absent row. ``n_absent`` is the denominator (FP + TN).
    """
    fp = 0
    n_absent = 0
    for r in results:
        if r.gt_present:
            continue
        n_absent += 1
        if r.outcome == "FP":
            fp += 1
    return fp, n_absent


def spurious_emission_rate(results: Iterable[FieldResult]) -> float:
    """FP / (FP + TN) hallucination rate on absent fields (ADR-027 metric 4)."""
    fp, n_absent = spurious_emission_counts(results)
    return fp / n_absent if n_absent > 0 else 0.0


def group_level_counts(results: Iterable[FieldResult]) -> tuple[int, int, int]:
    """Per-invoice KIEval group (TP, FP, FN) over `FIELD_GROUPS` (ADR-027 metric 3).

    Pass ONE invoice's results. A group is all-or-nothing (KIEval §4.1): TP iff
    every signal-bearing member is TP (the whole group reproduced identically).
    A matched-but-non-identical group counts as the remaining GT group (FN) and
    the remaining predicted group (FP); a purely-hallucinated group (no present
    members) counts as FP only. Document-level G′ fields are excluded.

    Cohort aggregation = sum these per-invoice counts across invoices, then
    `_f1_from_counts` — never pool fields across invoices into one group.
    """
    by_key = {r.english_key: r for r in results}
    tp = fp = fn = 0
    for members in FIELD_GROUPS.values():
        signal = [
            by_key[k].outcome
            for k in members
            if k in by_key and by_key[k].outcome in ("TP", "FP", "FN")
        ]
        if not signal:
            continue  # group carries no gradable signal this invoice
        gt_group_exists = any(o in ("TP", "FN") for o in signal)
        all_correct = all(o == "TP" for o in signal)
        if all_correct:
            tp += 1
        else:
            if gt_group_exists:
                fn += 1
            fp += 1
    return tp, fp, fn


def group_level_f1(results: Iterable[FieldResult]) -> float:
    """Per-invoice KIEval group-level F1 (ADR-027 metric 3). See `group_level_counts`."""
    tp, fp, fn = group_level_counts(results)
    return _f1_from_counts(tp, fp, fn)[2]


# ---------------------------------------------------------------------------
# ADR-042 — repeating-group scoring (VAT breakdown / Skonto / line items)
# ---------------------------------------------------------------------------
#
# Repeating groups are lists of rows. Predicted rows are aligned to GT rows by
# greedy maximum-similarity bipartite matching (similarity = fraction of the GT
# row's gradable cells the prediction reproduces); every aligned cell is then
# scored with the SAME `_score_against_spec` dispatch as a flat field. Unmatched
# GT rows contribute their gradable cells as FN (missed); unmatched predicted
# rows contribute their content cells as FP (spurious). The group F1 pools the
# cell TP/FP/FN; `score` folds all cells into the headline `overall_micro_f1`.
#
# Greedy (not optimal Hungarian) matching is the pragmatic line-item-eval
# standard (DocILE) and is exact at the row counts German invoices carry. The
# matching is deterministic: candidates sorted by (-similarity, pred_idx, gt_idx).


def _absent_gt_field(spec: FieldSpec) -> GroundTruthField:
    """A synthetic ``is_present=False`` GT field for an unmatched predicted row."""
    return GroundTruthField(
        bt_code=spec.bt_code,
        raw_value=None,
        normalized_value=None,
        xpath=spec.xpath,
        is_present=False,
    )


def _row_similarity(
    sub_fields: Mapping[str, FieldSpec],
    pred_row: Mapping[str, str | None],
    gt_row: Mapping[str, GroundTruthField],
    *,
    cfg: EvalConfig,
) -> float:
    """Fraction of the GT row's gradable (present_content) cells the prediction matches.

    Returns 0.0 if the GT row has no gradable cell (it cannot be matched on
    content), which excludes it from greedy matching.
    """
    gradable = 0
    matched = 0
    for sub_key, spec in sub_fields.items():
        gt_field = gt_row.get(sub_key)
        if gt_field is None or _gt_state(gt_field) != "present_content":
            continue
        gradable += 1
        result = _score_against_spec(sub_key, spec, pred_row.get(sub_key), gt_field, cfg=cfg)
        if result.outcome == "TP":
            matched += 1
    return matched / gradable if gradable > 0 else 0.0


def _align_rows(
    sub_fields: Mapping[str, FieldSpec],
    pred_rows: Sequence[Mapping[str, str | None]],
    gt_rows: Sequence[Mapping[str, GroundTruthField]],
    *,
    cfg: EvalConfig,
) -> list[tuple[int | None, int | None]]:
    """Greedy maximum-similarity bipartite matching of predicted↔GT rows (ADR-042).

    Returns aligned ``(pred_idx, gt_idx)`` pairs; an unmatched row appears as
    ``(pred_idx, None)`` (spurious) or ``(None, gt_idx)`` (missed). Deterministic.
    """
    candidates: list[tuple[float, int, int]] = []
    for i, pred_row in enumerate(pred_rows):
        for j, gt_row in enumerate(gt_rows):
            sim = _row_similarity(sub_fields, pred_row, gt_row, cfg=cfg)
            if sim > 0.0:
                candidates.append((sim, i, j))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    pairs: list[tuple[int | None, int | None]] = []
    for _sim, i, j in candidates:
        if i in matched_pred or j in matched_gt:
            continue
        matched_pred.add(i)
        matched_gt.add(j)
        pairs.append((i, j))
    for i in range(len(pred_rows)):
        if i not in matched_pred:
            pairs.append((i, None))
    for j in range(len(gt_rows)):
        if j not in matched_gt:
            pairs.append((None, j))
    return pairs


def score_repeating_group(
    group_key: str,
    pred_rows: Sequence[Mapping[str, str | None]],
    gt_rows: Sequence[Mapping[str, GroundTruthField]],
    *,
    cfg: EvalConfig | None = None,
) -> RepeatingGroupResult:
    """Score one repeating group: align rows, then score every aligned cell (ADR-042).

    `group_key` selects the sub-field registry from `REPEATING_GROUPS`. `pred_rows`
    are coerced row dicts (``InvoiceFields.to_full_dict()[group_key]``); `gt_rows`
    are parsed GT rows (``getattr(GroundTruth, group_key)``). Each cell is scored
    with the same comparator dispatch as a flat field.
    """
    if cfg is None:
        cfg = EvalConfig()
    sub_fields = REPEATING_GROUPS[group_key][1]
    pairs = _align_rows(sub_fields, pred_rows, gt_rows, cfg=cfg)
    cell_results: list[FieldResult] = []
    for pair_idx, (i, j) in enumerate(pairs):
        pred_row: Mapping[str, str | None] = pred_rows[i] if i is not None else {}
        gt_row = gt_rows[j] if j is not None else None
        for sub_key, spec in sub_fields.items():
            gt_field = gt_row.get(sub_key) if gt_row is not None else None
            if gt_field is None:
                gt_field = _absent_gt_field(spec)
            cell_key = f"{group_key}[{pair_idx}].{sub_key}"
            cell_results.append(
                _score_against_spec(cell_key, spec, pred_row.get(sub_key), gt_field, cfg=cfg)
            )
    tp = sum(1 for r in cell_results if r.outcome == "TP")
    fp = sum(1 for r in cell_results if r.outcome == "FP")
    fn = sum(1 for r in cell_results if r.outcome == "FN")
    precision, recall, f1 = _f1_from_counts(tp, fp, fn)
    n_matched = sum(1 for i, j in pairs if i is not None and j is not None)
    return RepeatingGroupResult(
        group_key=group_key,
        cell_results=cell_results,
        precision=precision,
        recall=recall,
        f1=f1,
        n_gt_rows=len(gt_rows),
        n_pred_rows=len(pred_rows),
        n_matched_rows=n_matched,
    )


# ---------------------------------------------------------------------------
# Public surface — `score`
# ---------------------------------------------------------------------------


def score(
    predicted: dict[str, str | None],
    gt: GroundTruth,
    *,
    cfg: EvalConfig | None = None,
    invoice_id: str = "<unknown>",
    model_id: str = "<unknown>",
    fields: Mapping[str, FieldSpec] | None = None,
    predicted_groups: Mapping[str, Sequence[Mapping[str, str | None]]] | None = None,
) -> InvoiceFieldScores:
    """Score a predicted dict against the parsed CII ground truth.

    Iterates over the scored field set (``fields`` if given, else the full
    ``FIELDS`` registry), runs the per-field comparator dispatch, and
    aggregates micro + macro F1.

    Args:
        predicted: ``dict[english_key, str | None]`` from
            ``adapters.to_predicted_dict()``. Must have all 16 keys present
            (None for not-extracted). Extra keys are ignored.
        gt: ``GroundTruth`` from PR(a)'s ``parse_cii_xml()``. ``gt.header``
            must have all 16 keys (per PR(a)'s contract).
        cfg: ``EvalConfig`` knobs (threshold, tolerances, NFC). If ``None``,
            literature defaults are used (``EvalConfig()`` constructor).
        invoice_id: human-readable invoice ID for heatmap grouping.
        model_id: cohort model ID for heatmap grouping.
        fields: optional subset of ``FIELDS`` to score (keys must exist in
            ``FIELDS`` — their specs are always read from ``FIELDS``). Defaults
            to all 19 fields. Pass ``ground_truth.LEGACY_EXPERIMENT_FIELDS`` to
            reproduce a closed milestone's 16-field in-sample baseline without
            the ADR-035 fields shifting it (ADR-037).

    Returns:
        ``InvoiceFieldScores`` with ``per_field`` populated for every scored
        key (``fields`` or all of ``FIELDS``) and aggregate micro/macro F1.

    Example:
        >>> from horus.config import EvalConfig
        >>> from horus.eval.scorer import score
        >>> # ... predicted = {...16 keys...}, gt = parse_cii_xml(...)
        >>> result = score(predicted, gt, cfg=EvalConfig(), invoice_id="EN16931_Einfach",
        ...                model_id="ibm-granite/granite-docling-258M-mlx")  # doctest: +SKIP
        >>> result.micro_f1  # doctest: +SKIP
        0.125
    """
    if cfg is None:
        cfg = EvalConfig()

    fields_to_score = fields if fields is not None else FIELDS
    per_field: dict[str, FieldResult] = {}
    for english_key in fields_to_score:
        pred_value = predicted.get(english_key)
        gt_field = gt.header.get(english_key)
        if gt_field is None:
            # Defensive: PR(a)'s parser always emits all 16 keys; this would
            # be a programming error upstream. Construct a synthetic "absent"
            # GT field so the scorer doesn't crash mid-aggregation.
            gt_field = GroundTruthField(
                bt_code=FIELDS[english_key].bt_code,
                raw_value=None,
                normalized_value=None,
                xpath=FIELDS[english_key].xpath,
                is_present=False,
            )
        per_field[english_key] = _score_one_field(english_key, pred_value, gt_field, cfg=cfg)

    micro_p, micro_r, micro_f1, macro_f1 = _aggregate_micro_macro(per_field)

    inv_results = list(per_field.values())

    # Repeating groups (ADR-042). Opt-in: scored ONLY when the caller passes
    # `predicted_groups`. The headline `overall_micro_*` pools the flat field
    # TP/FP/FN with every repeating-group cell so the single number covers the
    # whole schema; when no groups are passed it equals the flat micro_*.
    repeating: dict[str, RepeatingGroupResult] = {}
    overall_tp = sum(1 for r in inv_results if r.outcome == "TP")
    overall_fp = sum(1 for r in inv_results if r.outcome == "FP")
    overall_fn = sum(1 for r in inv_results if r.outcome == "FN")
    if predicted_groups is not None:
        for group_key in REPEATING_GROUPS:
            gt_rows = getattr(gt, group_key) or []
            pred_rows = list(predicted_groups.get(group_key) or [])
            if not gt_rows and not pred_rows:
                continue
            grp = score_repeating_group(group_key, pred_rows, gt_rows, cfg=cfg)
            repeating[group_key] = grp
            for r in grp.cell_results:
                if r.outcome == "TP":
                    overall_tp += 1
                elif r.outcome == "FP":
                    overall_fp += 1
                elif r.outcome == "FN":
                    overall_fn += 1
    overall_p, overall_r, overall_f1 = _f1_from_counts(overall_tp, overall_fp, overall_fn)

    return InvoiceFieldScores(
        invoice_id=invoice_id,
        model_id=model_id,
        per_field=per_field,
        micro_f1=micro_f1,
        macro_f1=macro_f1,
        micro_precision=micro_p,
        micro_recall=micro_r,
        presence_conditional_f1=presence_conditional_f1(inv_results),
        group_level_f1=group_level_f1(inv_results),
        spurious_emission_rate=spurious_emission_rate(inv_results),
        repeating=repeating,
        overall_micro_f1=overall_f1,
        overall_micro_precision=overall_p,
        overall_micro_recall=overall_r,
    )
