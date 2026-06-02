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

from horus.eval.ground_truth import FIELDS
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
    if spec is None:  # pragma: no cover — defensive; model fields ⊆ FIELDS ∪ {purpose_summary}
        return None
    field_type = spec.field_type
    if field_type == "MONEY":
        return _normalize_predicted_money(s)
    if field_type == "DATE":
        return _normalize_predicted_date(s)
    if field_type == "RATE":
        return _normalize_predicted_rate(s)
    if field_type == "CODE":
        return _normalize_predicted_code(s)
    # STRING (seller/buyer names + addresses)
    return _normalize_predicted_string(s)


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
        coerced: dict[str, str | None] = {}
        for field_name in cls.model_fields:
            original_key = lower_to_original.get(field_name.lower())
            raw_value = data[original_key] if original_key is not None else None
            coerced[field_name] = _coerce_one(field_name, raw_value)
        return coerced

    def to_scored_dict(self) -> dict[str, str | None]:
        """Return the 19 scored canonical fields (excludes `purpose_summary`).

        This is the `dict[str, str | None]` shape `scorer.score` consumes —
        keyed by exactly `FIELDS`. `purpose_summary` is omitted (non-scored).
        """
        dumped = self.model_dump()
        return {key: dumped[key] for key in FIELDS}

    def to_full_dict(self) -> dict[str, str | None]:
        """Return all 20 fields incl. `purpose_summary` (for the Streamlit app)."""
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
