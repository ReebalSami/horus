r"""German-canonical extraction schema — typed `InvoiceFields` + post-hoc repair (ADR-035).

The structurer (Gemma-4, both arms per ADR-034) emits a JSON object; local MLX
has **no constrained decoding** (ADR-018), so type safety + locale robustness
are enforced **post-hoc** here rather than at decode time. This module is:

  1. The **typed schema** — a Pydantic model of the 19 scored canonical fields
     (ADR-012's 16 + ADR-035's `tax_rate` / `seller_address` / `buyer_address`)
     plus the **non-scored** `purpose_summary` (rendered in the Streamlit app
     only; excluded from every F1 metric — it is NOT in `FIELDS`).
  2. The **validate/repair entry point** — `validate_and_repair(raw)` maps a
     model's (possibly messy, possibly mixed-case) JSON dict to the canonical
     19-key `dict[str, str | None]` the scorer (`scorer.score`) consumes:
     case-insensitive key matching, per-field-type locale coercion (German
     `1.234,56` / `DD.MM.YYYY` / `19 %`), honest `null` on missing/unparseable.
  3. The canonical **JSON-arm fine-tuning target** (#88) — the same typed shape
     a future LoRA (#55) trains toward.

Design (ADR-035 §"Decision"):

  - **Values are canonical strings**, not Python `Decimal`/`date`. The scorer's
    contract is `dict[str, str | None]`; the canonical *forms* (2-dp money
    string, ISO-8601 date, trailing-zero-stripped rate) satisfy ADR-035's
    typing intent while staying on the string interface. Idempotent: the
    scorer re-normalizes at compare time, so double-normalization is safe.
  - **One validate/repair home** — the per-field coercion delegates to
    `normalizers.py` (shared with `scorer.py`), so the prediction side is
    canonicalized identically wherever it is produced (no duplication).
  - **Language-agnostic** (ADR-034 §"Decision" pt 4): keys are canonical
    English/EN16931; values are as-printed in any language. No German-label
    regex on the path — this is what makes the held-out multilingual eval valid.

Layering: depends only on `ground_truth.FIELDS` (the scored-field registry,
single source of truth) + `normalizers` (stdlib-only). Does NOT import
`scorer` (the scorer scores plain dicts; no cycle).

Refs: ADR-035 (this), ADR-034 (parent strategy + honesty guardrail), ADR-012
(16-field schema + forward-compat clause), ADR-018 (no constrained decoding on
MLX), ADR-029 (JSON-arm spurious-emission evidence), ADR-013/027 (scorer).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from horus.eval.ground_truth import (
    FIELDS,
    LINE_ITEM_FIELDS,
    SKONTO_FIELDS,
    VAT_BREAKDOWN_FIELDS,
)
from horus.eval.normalizers import (
    _normalize_predicted_code,
    _normalize_predicted_date,
    _normalize_predicted_money,
    _normalize_predicted_rate,
    _normalize_predicted_string,
)

# The non-scored demo field — present on the model + emitted by the structurer
# for the Streamlit app, but deliberately absent from `FIELDS` so the scorer
# (which iterates `FIELDS`) never includes it in any F1 metric (ADR-035 §A).
PURPOSE_SUMMARY_KEY = "purpose_summary"


def _coerce_by_type(field_type: str, s: str) -> str | None:
    """Coerce a raw string to its canonical form for the given `FieldType`."""
    if field_type == "MONEY":
        return _normalize_predicted_money(s)
    if field_type == "DATE":
        return _normalize_predicted_date(s)
    if field_type == "RATE":
        return _normalize_predicted_rate(s)
    if field_type == "CODE":
        return _normalize_predicted_code(s)
    # STRING (names / addresses / payment free text)
    return _normalize_predicted_string(s)


def _coerce_one(canonical_key: str, raw_value: Any) -> str | None:
    """Coerce one raw model value to its canonical string form (or None).

    Dispatches on the field's `FieldType` (from `FIELDS`) to the matching
    prediction-side normalizer in `normalizers.py`. `purpose_summary` (not in
    `FIELDS`) is treated as free-text. `None` / unparseable → `None` (honest
    null — the model invented nothing).
    """
    if raw_value is None:
        return None
    s = raw_value if isinstance(raw_value, str) else str(raw_value)
    if canonical_key == PURPOSE_SUMMARY_KEY:
        return _normalize_predicted_string(s)
    spec = FIELDS.get(canonical_key)
    if spec is None:  # pragma: no cover — defensive; model fields ⊆ FIELDS ∪ non-scored
        return None
    return _coerce_by_type(spec.field_type, s)


# Repeating-group sub-field registries (ADR-041 Step 1b). The structurer may emit
# `vat_breakdown` / `skonto` as a JSON list of row objects; each cell is coerced
# by its sub-field `FieldType`, mirroring the flat path. SCORING of these groups
# is unified with line items in ADR-042 — they are NOT in the flat scored dict.
_REPEATING_SUBFIELDS = {
    "vat_breakdown": VAT_BREAKDOWN_FIELDS,
    "skonto": SKONTO_FIELDS,
    "line_items": LINE_ITEM_FIELDS,
}


def _coerce_repeating(group_key: str, raw_value: Any) -> list[dict[str, str | None]] | None:
    """Coerce a raw model list-of-rows into canonical per-row dicts (or None).

    Non-list input → ``None`` (honest absence). Each row is matched
    case-insensitively against the group's sub-field registry; each cell is
    coerced by the sub-field's `FieldType`; unknown row keys are dropped.
    """
    if not isinstance(raw_value, list):
        return None
    subfields = _REPEATING_SUBFIELDS[group_key]
    rows: list[dict[str, str | None]] = []
    for item in raw_value:
        if not isinstance(item, Mapping):
            continue
        lower_to_original = {str(k).lower(): k for k in item}
        row: dict[str, str | None] = {}
        for sub_key, spec in subfields.items():
            original = lower_to_original.get(sub_key.lower())
            raw_cell = item[original] if original is not None else None
            if raw_cell is None:
                row[sub_key] = None
            else:
                cell = raw_cell if isinstance(raw_cell, str) else str(raw_cell)
                row[sub_key] = _coerce_by_type(spec.field_type, cell)
        rows.append(row)
    return rows


class VatBreakdownLine(BaseModel):
    """One per-VAT-rate breakdown row (BG-23) as canonical strings (ADR-041)."""

    model_config = ConfigDict(extra="ignore")
    category_code: str | None = None
    rate_percent: str | None = None
    taxable_amount: str | None = None
    tax_amount: str | None = None


class SkontoLine(BaseModel):
    """One early-payment-discount tier as canonical strings (ADR-041)."""

    model_config = ConfigDict(extra="ignore")
    percent: str | None = None
    days: str | None = None
    basis_amount: str | None = None


class LineItemLine(BaseModel):
    """One invoice line-item row (BG-25) as canonical strings (ADR-042)."""

    model_config = ConfigDict(extra="ignore")
    line_id: str | None = None
    name: str | None = None
    seller_assigned_id: str | None = None
    net_price: str | None = None
    quantity: str | None = None
    vat_rate: str | None = None
    line_amount: str | None = None


class InvoiceFields(BaseModel):
    """Typed, locale-repaired German-canonical invoice schema (ADR-035).

    19 scored fields (ADR-012's 16 + `tax_rate` / `seller_address` /
    `buyer_address`) carried as canonical `str | None`, plus the non-scored
    `purpose_summary`. Construct via `model_validate(raw_dict)` (the
    `mode="before"` validator does case-insensitive key matching + per-type
    coercion) or via the `validate_and_repair` convenience wrapper.

    `extra="ignore"`: unknown keys a model may emit (e.g. a nested `seller`
    object, or a hallucinated extra field) are dropped, not errored — the
    before-validator only pulls the known canonical fields.
    """

    model_config = ConfigDict(extra="ignore")

    # --- ADR-012 document scalars ---
    invoice_number: str | None = None
    issue_date: str | None = None
    invoice_currency_code: str | None = None
    delivery_date: str | None = None
    # --- ADR-012 seller block ---
    seller_name: str | None = None
    seller_vat_id: str | None = None
    seller_tax_id: str | None = None
    seller_gln: str | None = None
    # --- ADR-012 buyer block ---
    buyer_name: str | None = None
    buyer_reference: str | None = None
    buyer_vat_id: str | None = None
    # --- ADR-012 totals ---
    line_total_amount: str | None = None
    tax_basis_total_amount: str | None = None
    tax_total_amount: str | None = None
    grand_total_amount: str | None = None
    due_payable_amount: str | None = None
    # --- ADR-035 additions (scored) ---
    tax_rate: str | None = None
    seller_address: str | None = None
    buyer_address: str | None = None
    # --- ADR-041 Step 1a additions (scored) — document identity ---
    document_type: str | None = None
    buyer_order_reference: str | None = None
    billing_period_start: str | None = None
    billing_period_end: str | None = None
    # --- ADR-041 Step 1a additions (scored) — payment ---
    payment_due_date: str | None = None
    payment_means_code: str | None = None
    payment_means_text: str | None = None
    seller_iban: str | None = None
    seller_bic: str | None = None
    seller_account_name: str | None = None
    payment_reference: str | None = None
    # --- ADR-041 Step 1a additions (scored) — totals ---
    prepaid_amount: str | None = None
    allowance_total_amount: str | None = None
    charge_total_amount: str | None = None
    rounding_amount: str | None = None
    # --- ADR-041 Step 1b repeating groups (NOT in the flat scored dict; scored
    #     via the unified repeating-group metric in ADR-042) ---
    vat_breakdown: list[VatBreakdownLine] | None = None
    skonto: list[SkontoLine] | None = None
    # --- ADR-042 Step 2 line-item table (BG-25; scored via the unified
    #     repeating-group metric, NOT the flat scored dict) ---
    line_items: list[LineItemLine] | None = None
    # --- ADR-035 addition (NON-scored; Streamlit display only) ---
    purpose_summary: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_match_keys(cls, data: Any) -> Any:
        """Case-insensitively match incoming keys + coerce each value (ADR-035 repair pass).

        Builds a `lower(key) → original-key` map over the incoming dict, then
        for each declared model field pulls the matching raw value (if any) and
        runs `_coerce_one`. Non-dict input (e.g. a JSON list / scalar that
        slipped through) yields an all-None model. The result has exactly the
        declared field set, so Pydantic validation sees only canonical strings.
        """
        if not isinstance(data, Mapping):
            return {}
        lower_to_original: dict[str, Any] = {}
        for key in data:
            lower_to_original.setdefault(str(key).lower(), key)
        coerced: dict[str, Any] = {}
        for field_name in cls.model_fields:
            original_key = lower_to_original.get(field_name.lower())
            raw_value = data[original_key] if original_key is not None else None
            if field_name in _REPEATING_SUBFIELDS:
                coerced[field_name] = _coerce_repeating(field_name, raw_value)
            else:
                coerced[field_name] = _coerce_one(field_name, raw_value)
        return coerced

    def to_scored_dict(self) -> dict[str, str | None]:
        """Return the 19 scored canonical fields (excludes `purpose_summary`).

        This is the `dict[str, str | None]` shape `scorer.score` consumes —
        keyed by exactly `FIELDS`. `purpose_summary` is omitted (non-scored).
        """
        dumped = self.model_dump()
        return {key: dumped[key] for key in FIELDS}

    def to_full_dict(self) -> dict[str, Any]:
        """Return all fields incl. `purpose_summary` + repeating groups (Streamlit app).

        `vat_breakdown` / `skonto` serialize to a list of row dicts (or `None`).
        """
        return self.model_dump()


def validate_and_repair(raw: Mapping[str, Any] | None) -> dict[str, str | None]:
    """Validate + locale-repair a model's JSON dict into the scored 19-key dict.

    The post-hoc validation path of ADR-035: parse (upstream, via the
    `adapters_json` recovery ladder) → `validate_and_repair` → `scorer.score`.
    Maps mixed-case keys to canonical, coerces German/locale money/date/rate
    variance to canonical forms, and emits honest `null` for missing or
    unparseable fields (the tax-domain guardrail — a generative structurer
    must never invent a value).

    Args:
        raw: the parsed model JSON object (or `None` if recovery failed).

    Returns:
        `dict[str, str | None]` keyed by exactly the 19 scored `FIELDS` keys.
    """
    if raw is None:
        raw = {}
    return InvoiceFields.model_validate(raw).to_scored_dict()
