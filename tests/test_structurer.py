"""Tests for the Layer-2 structurer (`src/horus/eval/structurer.py`, ADR-038).

The structurer turns a structuring model's (Gemma's) reasoning-then-strict-JSON
output into the canonical 19-field scored dict via the shared `adapters_json`
recovery ladder + `InvoiceFields.validate_and_repair` (ADR-035). Covers:

  - clean JSON -> 19-key dict with locale coercion (German date/money/rate)
  - JSON recovered from a reasoning wrapper + markdown fences
  - garbage / empty -> honest all-null (never raises) — the tax-domain guardrail
  - per-page multipage merge (first-non-None-wins; page 1 dominant)
  - `to_full_dict` keeps the non-scored `purpose_summary`; `to_predicted_dict` drops it
  - nested objects are NOT flattened (honest "missing canonical key")
  - public-surface signature parity with `adapters` / `adapters_json` (harness swap)
"""

from __future__ import annotations

import inspect
import json

from horus.eval import adapters as adapters_regex
from horus.eval import structurer
from horus.eval.ground_truth import FIELDS
from horus.eval.schema import PURPOSE_SUMMARY_KEY

_MODEL = "google/gemma-4-E4B-it"


def test_to_predicted_dict_clean_json_coerces_locale() -> None:
    """A clean German-locale JSON object is parsed + locale-coerced to canonical forms."""
    raw = json.dumps(
        {
            "invoice_number": "471102",
            "issue_date": "05.03.2018",
            "grand_total_amount": "529,87",
            "tax_rate": "19 %",
            "seller_name": "Lieferant GmbH",
        }
    )
    out = structurer.to_predicted_dict(raw, _MODEL)
    # Exactly the 19 scored keys (never purpose_summary).
    assert set(out) == set(FIELDS)
    assert out["invoice_number"] == "471102"
    assert out["issue_date"] == "2018-03-05"  # DD.MM.YYYY -> ISO
    assert out["grand_total_amount"] == "529.87"  # German comma -> canonical 2-dp
    assert out["tax_rate"] == "19"  # "19 %" -> trailing-zero-stripped numeric
    assert out["seller_name"] == "Lieferant GmbH"
    # Unmentioned fields are honest nulls (the model emitted nothing).
    assert out["buyer_vat_id"] is None


def test_to_predicted_dict_recovers_json_from_reasoning_wrapper() -> None:
    """Reasoning prose + a fenced JSON block -> the JSON is recovered (ADR-038 prompt shape)."""
    raw = (
        "Let me reason about this invoice. The number is 471102.\n\n"
        "```json\n"
        '{"invoice_number": "471102", "seller_name": "Lieferant GmbH"}\n'
        "```\n"
        "Hope this helps!"
    )
    out = structurer.to_predicted_dict(raw, _MODEL)
    assert out["invoice_number"] == "471102"
    assert out["seller_name"] == "Lieferant GmbH"


def test_to_predicted_dict_garbage_is_all_null() -> None:
    """Unparseable output -> all-null 19-key dict (honest; never raises)."""
    out = structurer.to_predicted_dict("this is not json at all <eos>", _MODEL)
    assert set(out) == set(FIELDS)
    assert all(value is None for value in out.values())


def test_to_predicted_dict_empty_is_all_null() -> None:
    """Empty output -> all-null 19-key dict."""
    out = structurer.to_predicted_dict("", _MODEL)
    assert set(out) == set(FIELDS)
    assert all(value is None for value in out.values())


def test_to_predicted_dict_nested_object_not_flattened() -> None:
    """A nested `{"seller": {...}}` is dropped (honest missing key), not flattened."""
    raw = json.dumps({"seller": {"name": "X"}, "invoice_number": "471102"})
    out = structurer.to_predicted_dict(raw, _MODEL)
    assert out["invoice_number"] == "471102"
    assert out["seller_name"] is None


def test_multipage_first_non_null_wins() -> None:
    """Per-page merge keeps page 1's value; later pages only fill still-null slots."""
    page1 = json.dumps({"seller_name": "Lieferant GmbH", "invoice_number": "471102"})
    page2 = json.dumps({"seller_name": "Joghurt Banane", "grand_total_amount": "529,87"})
    out = structurer.to_predicted_dict_multipage([page1, page2], _MODEL)
    assert out["seller_name"] == "Lieferant GmbH"  # page-1 honest value preserved
    assert out["invoice_number"] == "471102"
    assert out["grand_total_amount"] == "529.87"  # page-2 fills the empty slot
    assert set(out) == set(FIELDS)


def test_multipage_empty_list_is_all_null() -> None:
    """No pages -> all-null 19-key dict."""
    out = structurer.to_predicted_dict_multipage([], _MODEL)
    assert set(out) == set(FIELDS)
    assert all(value is None for value in out.values())


def test_to_full_dict_keeps_purpose_summary_scored_drops_it() -> None:
    """`to_full_dict` carries the non-scored `purpose_summary`; `to_predicted_dict` excludes it."""
    raw = json.dumps({"invoice_number": "471102", "purpose_summary": "Office supplies."})
    full = structurer.to_full_dict(raw)
    assert full[PURPOSE_SUMMARY_KEY] == "Office supplies."
    assert full["invoice_number"] == "471102"
    scored = structurer.to_predicted_dict(raw, _MODEL)
    assert PURPOSE_SUMMARY_KEY not in scored
    assert set(scored) == set(FIELDS)


def test_public_surface_signature_parity_with_adapters() -> None:
    """`to_predicted_dict` + `to_predicted_dict_multipage` match the adapter arg shape.

    Locks the contract that the harness can dispatch `adapter_mode="structurer"`
    to this module the same way it dispatches `regex` / `json` — no per-call
    signature branching (ADR-038).
    """
    for fn_name in ("to_predicted_dict", "to_predicted_dict_multipage"):
        regex_params = list(inspect.signature(getattr(adapters_regex, fn_name)).parameters)
        structurer_params = list(inspect.signature(getattr(structurer, fn_name)).parameters)
        assert regex_params == structurer_params, (
            f"structurer.{fn_name} params {structurer_params} must match "
            f"adapters.{fn_name} params {regex_params} for harness swappability"
        )


# ---------------------------------------------------------------------------
# ADR-042 — repeating-group extraction (vat_breakdown / skonto / line_items)
# ---------------------------------------------------------------------------


def test_to_predicted_groups_parses_arrays() -> None:
    """JSON arrays parse to per-row coerced dicts; absent groups are empty lists."""
    raw = json.dumps(
        {
            "vat_breakdown": [{"rate_percent": "19 %", "tax_amount": "19,00"}],
            "line_items": [{"name": "Beratung", "line_amount": "100,00"}],
        }
    )
    groups = structurer.to_predicted_groups(raw)
    assert groups["vat_breakdown"][0]["rate_percent"] == "19"
    assert groups["vat_breakdown"][0]["tax_amount"] == "19.00"
    assert groups["line_items"][0]["name"] == "Beratung"
    assert groups["line_items"][0]["line_amount"] == "100.00"
    assert groups["skonto"] == []


def test_to_predicted_groups_multipage_first_nonempty_wins() -> None:
    """Per-page group merge keeps the first page that carries a non-empty group."""
    page1 = json.dumps({"vat_breakdown": []})
    page2 = json.dumps({"vat_breakdown": [{"rate_percent": "7"}]})
    groups = structurer.to_predicted_groups_multipage([page1, page2], _MODEL)
    assert groups["vat_breakdown"][0]["rate_percent"] == "7"


def test_to_predicted_groups_unrecoverable_is_empty() -> None:
    """Garbage output → all groups empty (honest; the model emitted no rows)."""
    groups = structurer.to_predicted_groups("not json at all <eos>")
    assert groups == {"vat_breakdown": [], "skonto": [], "line_items": []}
