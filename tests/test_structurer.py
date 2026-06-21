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

import pytest

from horus.eval import adapters as adapters_regex
from horus.eval import structurer
from horus.eval.ground_truth import FIELDS
from horus.eval.schema import PURPOSE_SUMMARY_KEY

_MODEL = "google/gemma-4-E4B-it"


@pytest.fixture
def _rabatte_missing_brace() -> str:
    """The exact Arm-B Gemma malformation for EN16931_Rabatte (ADR-044 regression).

    The 4th `line_items` object's closing `}` is substituted by `]`, leaving a
    spurious extra `]` after the array already closes (`... "55,40" ] ], ...`);
    pre-ADR-044 the whole object was unparseable (micro_f1=0.000). German comma
    decimals are quoted (valid JSON strings) so only the structural slip matters.
    Reproduced verbatim from the saved transcript
    (`docs/sources/transcripts-arms-dev/google__gemma-4-e4b-it__EN16931_Rabatte.txt`).
    """
    return (
        "Here is the extracted invoice data.\n\n"
        "```json\n"
        "{\n"
        '  "invoice_number": "471102",\n'
        '  "seller_name": "Lieferant GmbH",\n'
        '  "grand_total_amount": "215,07",\n'
        '  "vat_breakdown": [\n'
        '    {"rate_percent": "7", "tax_amount": "9,06"},\n'
        '    {"rate_percent": "19", "tax_amount": "12,24"}\n'
        "  ],\n"
        '  "line_items": [\n'
        '    {"line_id": "1", "line_amount": "10,00"},\n'
        '    {"line_id": "2", "line_amount": "27,50"},\n'
        '    {"line_id": "3", "line_amount": "109,80"},\n'
        "    {\n"
        '      "line_id": "4",\n'
        '      "line_amount": "55,40"\n'
        "    ]\n"
        "  ],\n"
        '  "purpose_summary": "goods supplied"\n'
        "}\n"
        "```\n"
    )


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


def test_to_predicted_dict_recovers_missing_brace_via_arm_b_path(
    _rabatte_missing_brace: str,
) -> None:
    """The real Arm-B failure (Rabatte missing-`}`) recovers through the typed structurer path.

    Pre-ADR-044 this output scored micro_f1=0.000 (whole-object unparseable);
    after the structural-repair rung the flat fields are recovered AND
    locale-coerced (German `215,07` -> canonical `215.07`).
    """
    out = structurer.to_predicted_dict(_rabatte_missing_brace, _MODEL)
    assert out["invoice_number"] == "471102"
    assert out["seller_name"] == "Lieferant GmbH"
    assert out["grand_total_amount"] == "215.07"  # German comma -> canonical 2-dp


def test_to_predicted_groups_recovers_missing_brace(_rabatte_missing_brace: str) -> None:
    """The repeating-group path also recovers all 4 line_items from the repaired object."""
    groups = structurer.to_predicted_groups(_rabatte_missing_brace)
    assert len(groups["line_items"]) == 4
    assert len(groups["vat_breakdown"]) == 2


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


# ---------------------------------------------------------------------------
# ADR-049 — registry-driven structurer field glossary (totals + references)
# ---------------------------------------------------------------------------


def test_render_field_glossary_includes_confusable_fields() -> None:
    """The guide carries the 7 commonly-confused fields with their German anchors."""
    glossary = structurer.render_field_glossary()
    # the two reference fields the model swapped, with disambiguating labels
    assert "- buyer_reference:" in glossary
    assert "Kundennummer" in glossary
    assert "- buyer_order_reference:" in glossary
    assert "Bestellnummer" in glossary
    # the 5 document totals, each anchored to its printed German label
    for key, label in (
        ("line_total_amount", "Positionssumme"),
        ("tax_basis_total_amount", "Rechnungssumme ohne USt."),
        ("tax_total_amount", "Steuerbetrag"),
        ("grand_total_amount", "Bruttosumme"),
        ("due_payable_amount", "Zahlbetrag"),
    ):
        assert f"- {key}:" in glossary
        assert label in glossary


def test_render_field_glossary_excludes_fields_without_description() -> None:
    """Fields with no `description` are omitted — the bare key list already names them."""
    glossary = structurer.render_field_glossary()
    for key in ("invoice_number", "seller_name", "seller_gln", "buyer_vat_id"):
        assert f"- {key}:" not in glossary


def test_render_field_glossary_carries_no_ground_truth_values() -> None:
    """The generic guardrail: the guide holds field SEMANTICS + LABEL names only.

    No invoice-specific value may leak into the prompt (e.g. EN16931_Einfach's
    473.00 / 56.87 / 529.87 totals or the GE2020211 customer number). This test
    fails loudly if a future description accidentally embeds a ground-truth value.
    """
    glossary = structurer.render_field_glossary()
    for leak in ("473", "529", "56.87", "198.00", "GE2020211"):
        assert leak not in glossary


def test_render_field_glossary_is_registry_sourced() -> None:
    """Every guide line maps to a FieldSpec with a `description` (single source of truth).

    Open/closed: adding a `description` to another flat FieldSpec auto-extends the
    guide; the renderer special-cases nothing. Repeating-group cells are NOT
    glossed (measured net-negative, rejected per ADR-053), so the rendered keys
    are exactly the described flat fields.
    """
    described = {key for key, spec in FIELDS.items() if spec.description is not None}
    assert described  # the confusable flat fields are populated
    rendered_keys = {
        line[2:].split(":", 1)[0]
        for line in structurer.render_field_glossary().splitlines()
        if line.startswith("- ")
    }
    assert rendered_keys == described


def test_render_structuring_prompt_substitutes_token() -> None:
    """The `{field_glossary}` placeholder is filled with the registry guide."""
    out = structurer.render_structuring_prompt("keys:\n{field_glossary}\nend")
    assert "{field_glossary}" not in out
    assert "Positionssumme" in out


def test_render_structuring_prompt_preserves_literal_json_braces() -> None:
    """Substitution uses str.replace (not str.format) → JSON braces survive verbatim."""
    template = "row {category_code, rate_percent} and {field_glossary}"
    out = structurer.render_structuring_prompt(template)
    assert "{category_code, rate_percent}" in out
    assert "Bruttosumme" in out


def test_render_structuring_prompt_noop_without_token() -> None:
    """A prompt without the placeholder (regex baseline / OCR defaults) is unchanged."""
    template = "Convert this page to docling."
    assert structurer.render_structuring_prompt(template) == template


def test_build_structuring_input_fills_glossary_and_appends_reader_text() -> None:
    """The composed input renders the guide and appends the reader transcript."""
    full = structurer.build_structuring_input(
        "Extract fields.\n{field_glossary}", "Belegsummen\nZahlbetrag 529,87"
    )
    assert "{field_glossary}" not in full
    assert "- due_payable_amount:" in full
    assert "Zahlbetrag 529,87" in full
    assert "<<<" in full and ">>>" in full
