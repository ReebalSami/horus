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

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from horus.config import EvalConfig
from horus.eval.anls import anls, nls
from horus.eval.ground_truth import FIELDS, FieldType, GroundTruth, GroundTruthField

__all__ = [
    "DOCUMENT_FIELDS",
    "FIELD_GROUPS",
    "FieldResult",
    "InvoiceFieldScores",
    "f1_from_counts",
    "group_level_counts",
    "group_level_f1",
    "label_outcome_counts",
    "presence_conditional_counts",
    "presence_conditional_f1",
    "score",
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


# ---------------------------------------------------------------------------
# Predicted-side normalizers — mirror PR(a)'s GT-side normalizers but
# tolerate the messier shapes that VLM outputs produce.
# ---------------------------------------------------------------------------
#
# Each normalizer accepts a raw string from the adapter and returns the
# canonical form (the same canonical form PR(a) produces on the GT side),
# or None if the value is unparseable. Returning None signals to the
# comparator that the prediction is malformed → the truth-table cell maps
# to FN (predicted-malformed against a present GT) or TN (against absent GT).


_MONTHS_DE = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "mae": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}


def _normalize_predicted_money(raw: str) -> str | None:
    """Normalize a predicted money value to canonical 2-decimal string.

    Accepts:
      - ``"529.87"`` (canonical) → ``"529.87"``
      - ``"529,87"`` (German decimal-comma) → ``"529.87"``
      - ``"1.234,56"`` (German thousand-period + decimal-comma) → ``"1234.56"``
      - ``"1,234.56"`` (US thousand-comma + decimal-period) → ``"1234.56"``
      - ``"529,87 €"`` / ``"€529,87"`` / ``"EUR 529,87"`` → ``"529.87"``
      - Negative values via leading ``-`` (preserved)

    Returns:
        Canonical 2-decimal string (matching PR(a)'s ``_normalize_money``
        output format), or ``None`` if the input doesn't parse as a number.
    """
    if not raw:
        return None
    s = raw.strip()
    # Strip currency symbols + ISO code prefixes
    s = re.sub(r"(€|EUR|USD|\$)", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    # Detect format by looking at the LAST decimal separator:
    #   "1.234,56" → ',' is the decimal (German); strip dots, replace comma with dot
    #   "1,234.56" → '.' is the decimal (US); strip commas
    #   "529,87"   → ',' is the decimal (German short)
    #   "529.87"   → '.' is the decimal (US short)
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")
    if last_comma > last_dot:
        # Comma is the decimal separator → German format
        s = s.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        # Dot is the decimal separator → US format
        s = s.replace(",", "")
    else:
        # No separator → integer (treat as exact)
        pass
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return str(d.quantize(Decimal("0.01")))


def _normalize_predicted_date(raw: str) -> str | None:
    """Normalize a predicted date to ISO-8601 (``YYYY-MM-DD``).

    Accepts:
      - ``"2018-03-05"`` (ISO, canonical) → ``"2018-03-05"``
      - ``"05.03.2018"`` (German DD.MM.YYYY) → ``"2018-03-05"``
      - ``"5.3.2018"`` (German with no zero-padding) → ``"2018-03-05"``
      - ``"05. März 2018"`` (German month name) → ``"2018-03-05"``
      - ``"05/03/2018"`` (DD/MM/YYYY) → ``"2018-03-05"``
      - ``"05-03-2018"`` (DD-MM-YYYY) → ``"2018-03-05"``

    Year-month-day vs day-month-year ambiguity: when the first component is
    4 digits, treat as ``YYYY-MM-DD``; otherwise treat as ``DD-MM-YYYY``
    (the German invoice convention).

    Returns:
        ISO-8601 date string ``"YYYY-MM-DD"``, or ``None`` if the input
        doesn't parse.
    """
    if not raw:
        return None
    s = raw.strip()
    # Try ISO first (year-first)
    iso_match = re.fullmatch(r"(\d{4})[\-./](\d{1,2})[\-./](\d{1,2})", s)
    if iso_match:
        y, m, d = (int(g) for g in iso_match.groups())
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            return None
    # German month-name pattern: "05. März 2018" or "5 März 2018"
    month_match = re.fullmatch(
        r"(\d{1,2})\.?\s+([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", s, flags=re.IGNORECASE
    )
    if month_match:
        d_str, month_name, y_str = month_match.groups()
        month_int = _MONTHS_DE.get(month_name.lower())
        if month_int is None:
            return None
        try:
            return date(int(y_str), month_int, int(d_str)).isoformat()
        except ValueError:
            return None
    # German/EU day-first: "05.03.2018" / "05/03/2018" / "05-03-2018"
    day_first = re.fullmatch(r"(\d{1,2})[\-./](\d{1,2})[\-./](\d{4})", s)
    if day_first:
        d, m, y = (int(g) for g in day_first.groups())
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            return None
    return None


def _normalize_predicted_code(raw: str, *, nfc: bool = True) -> str | None:
    """Normalize a predicted code (VAT ID, GLN, invoice number, currency code).

    Strips outer whitespace, applies optional NFC, removes internal whitespace
    in well-known formats (e.g., ``"DE 123456789"`` → ``"DE123456789"``).

    Args:
        raw: predicted value.
        nfc: if True, apply Unicode NFC normalization (default).

    Returns:
        Normalized code string, or ``None`` if input is empty.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if nfc:
        s = unicodedata.normalize("NFC", s)
    # Strip internal whitespace for VAT IDs and similar codes where spaces
    # are formatting noise (e.g., "DE 123 456 789" → "DE123456789")
    # Detect: starts with country code (2 letters) followed by digits
    if re.match(r"^[A-Z]{2}\s*\d", s):
        s = re.sub(r"\s+", "", s)
    return s


def _normalize_predicted_string(raw: str, *, nfc: bool = True) -> str | None:
    """Normalize a predicted free-text string (names, addresses).

    Strips outer whitespace + applies NFC (preserves internal whitespace).
    Returns None on empty input.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if nfc:
        s = unicodedata.normalize("NFC", s)
    return s


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
    """Score one field against its GT — full truth-table + comparator dispatch."""
    spec = FIELDS[english_key]
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

    # Normalize the prediction side (None passes through)
    if predicted is None:
        pred_norm: str | None = None
    elif spec.field_type == "MONEY":
        pred_norm = _normalize_predicted_money(predicted)
    elif spec.field_type == "DATE":
        pred_norm = _normalize_predicted_date(predicted)
    elif spec.field_type == "CODE":
        pred_norm = _normalize_predicted_code(predicted, nfc=cfg.string_normalize_nfc)
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

# KIEval (§4.1) group partition over the 16-field registry. seller / buyer /
# totals are EN16931 business groups; the document-level scalars are the
# non-group entities KIEval folds into the excluded 1st group (G').
FIELD_GROUPS: dict[str, frozenset[str]] = {
    "seller": frozenset({"seller_name", "seller_vat_id", "seller_tax_id", "seller_gln"}),
    "buyer": frozenset({"buyer_name", "buyer_reference", "buyer_vat_id"}),
    "totals": frozenset(
        {
            "line_total_amount",
            "tax_basis_total_amount",
            "tax_total_amount",
            "grand_total_amount",
            "due_payable_amount",
        }
    ),
}

# G' — non-group document-level scalars, EXCLUDED from group-level F1 (ADR-027).
DOCUMENT_FIELDS: frozenset[str] = frozenset(
    {"invoice_number", "issue_date", "invoice_currency_code", "delivery_date"}
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
# Public surface — `score`
# ---------------------------------------------------------------------------


def score(
    predicted: dict[str, str | None],
    gt: GroundTruth,
    *,
    cfg: EvalConfig | None = None,
    invoice_id: str = "<unknown>",
    model_id: str = "<unknown>",
) -> InvoiceFieldScores:
    """Score a predicted dict against the parsed CII ground truth.

    Iterates over ``FIELDS`` (PR(a)'s registry), runs the per-field
    comparator dispatch, and aggregates micro + macro F1.

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

    Returns:
        ``InvoiceFieldScores`` with ``per_field`` populated for every key
        in ``FIELDS`` and aggregate micro/macro F1.

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

    per_field: dict[str, FieldResult] = {}
    for english_key in FIELDS:
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
    )
