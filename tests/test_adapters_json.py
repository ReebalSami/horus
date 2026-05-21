"""Tests for the Layer-2 JSON adapter -- ``src/horus/eval/adapters_json.py``.

Per ADR-018 §"Test coverage" §"JSON adapter" row: 12+ tests covering the
permissive-JSON-recovery ladder + value-shape edge cases + the public-surface
contract that mirrors ``adapters.py``.

Tests organized into four blocks:

    1. preprocess() -- markdown-fence + chat-artifact + NFC normalization
    2. to_predicted_dict() -- canonical key mapping + value-shape handling
    3. to_predicted_dict() -- permissive-JSON recovery ladder
    4. Public-surface contract -- shape + signature parity with adapters.py

Refs:

    - ADR-018 (this module's ratifying ADR)
    - ADR-013 (sibling adapters.py public surface)
    - ADR-012 (FIELDS canonical 16-key registry)
"""

from __future__ import annotations

from horus.eval.adapters_json import preprocess, to_predicted_dict
from horus.eval.ground_truth import FIELDS

# ---------------------------------------------------------------------------
# 1. preprocess() -- markdown-fence + chat-artifact + NFC normalization
# ---------------------------------------------------------------------------


def test_preprocess_passthrough_when_no_fence_or_artifact() -> None:
    """Plain text without fence / artifact passes through (only stripped + NFC-normalized)."""
    raw = '{"invoice_number": "INV-001"}'
    out = preprocess(raw, model_id="m")
    assert out == '{"invoice_number": "INV-001"}'


def test_preprocess_strips_canonical_json_fence() -> None:
    """Canonical Gemma-style ` ```json\\n ... \\n``` ` fence is stripped to inner content."""
    raw = '```json\n{"invoice_number": "INV-002"}\n```'
    out = preprocess(raw, model_id="m")
    assert out == '{"invoice_number": "INV-002"}'


def test_preprocess_strips_bare_triple_backtick_fence() -> None:
    """Bare ` ```\\n ... \\n``` ` fence (no lang tag) is also stripped."""
    raw = '```\n{"invoice_number": "INV-003"}\n```'
    out = preprocess(raw, model_id="m")
    assert out == '{"invoice_number": "INV-003"}'


def test_preprocess_strips_chat_artifact_tokens() -> None:
    """Trailing chat-template tokens are stripped pre-JSON-parse."""
    im_end = "<" + "|im_end|" + ">"
    raw = '{"invoice_number": "INV-004"}' + im_end
    out = preprocess(raw, model_id="m")
    assert im_end not in out
    assert "INV-004" in out


def test_preprocess_nfc_normalizes_decomposed_diacritics() -> None:
    """NFD-encoded German diacritics (e.g., 'Mu\u0308nchen') normalize to NFC ('M\u00fcnchen')."""
    decomposed = '{"seller_name": "Mu\u0308nchen GmbH"}'
    out = preprocess(decomposed, model_id="m")
    assert "M\u00fcnchen GmbH" in out, "NFC normalization should compose 'u' + combining-diaeresis"


# ---------------------------------------------------------------------------
# 2. to_predicted_dict() -- canonical key mapping + value-shape handling
# ---------------------------------------------------------------------------


def test_to_predicted_dict_returns_all_16_canonical_keys() -> None:
    """Result always contains exactly the 16 canonical FIELDS keys (no extras, no missing)."""
    raw = '{"invoice_number": "INV-001"}'
    result = to_predicted_dict(raw, model_id="m")
    assert set(result.keys()) == set(FIELDS.keys())
    assert len(result) == 16


def test_to_predicted_dict_full_canonical_json_roundtrips() -> None:
    """A JSON object with all 16 canonical keys + valid string values -> all preserved."""
    raw = (
        '{"invoice_number": "INV-001", '
        '"issue_date": "2024-01-15", '
        '"invoice_currency_code": "EUR", '
        '"delivery_date": "2024-01-20", '
        '"seller_name": "Test GmbH", '
        '"seller_vat_id": "DE123456789", '
        '"seller_tax_id": "12/345/67890", '
        '"seller_gln": "4012345000004", '
        '"buyer_name": "Buyer AG", '
        '"buyer_reference": "REF-42", '
        '"buyer_vat_id": "DE987654321", '
        '"line_total_amount": "100.00", '
        '"tax_basis_total_amount": "100.00", '
        '"tax_total_amount": "19.00", '
        '"grand_total_amount": "119.00", '
        '"due_payable_amount": "119.00"}'
    )
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["issue_date"] == "2024-01-15"
    assert result["seller_name"] == "Test GmbH"
    assert result["grand_total_amount"] == "119.00"
    assert result["due_payable_amount"] == "119.00"


def test_to_predicted_dict_partial_keys_fill_missing_with_none() -> None:
    """Keys NOT present in the parsed JSON map to None."""
    raw = '{"invoice_number": "INV-001"}'
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["issue_date"] is None
    assert result["seller_name"] is None
    assert result["grand_total_amount"] is None


def test_to_predicted_dict_alternate_casing_maps_to_canonical() -> None:
    """``Invoice_Number`` and ``INVOICE_NUMBER`` both map to canonical ``invoice_number``."""
    raw = '{"Invoice_Number": "INV-A", "INVOICE_CURRENCY_CODE": "EUR"}'
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-A"
    assert result["invoice_currency_code"] == "EUR"


def test_to_predicted_dict_non_canonical_keys_ignored() -> None:
    """Keys not in FIELDS (e.g., model invented its own schema) are silently ignored."""
    raw = (
        '{"invoice_number": "INV-001", '
        '"random_extra_key": "ignored", '
        '"seller": "should_be_seller_name_but_isnt"}'
    )
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["seller_name"] is None, "non-canonical 'seller' key must NOT map to seller_name"
    assert "random_extra_key" not in result


def test_to_predicted_dict_nested_object_treated_as_missing() -> None:
    """Nested object at a canonical key (model failed flat-schema instruction) -> None."""
    raw = '{"seller_name": {"first": "Test", "second": "GmbH"}, "invoice_number": "INV-001"}'
    result = to_predicted_dict(raw, model_id="m")
    assert result["seller_name"] is None, "nested object must NOT silently flatten"
    assert result["invoice_number"] == "INV-001"


def test_to_predicted_dict_numeric_values_str_cast() -> None:
    """Integer / float values -> ``str(value)`` (model emitted MONEY as number, not string)."""
    raw = '{"line_total_amount": 100.50, "tax_total_amount": 19, "due_payable_amount": 119.50}'
    result = to_predicted_dict(raw, model_id="m")
    assert result["line_total_amount"] == "100.5"
    assert result["tax_total_amount"] == "19"
    assert result["due_payable_amount"] == "119.5"


def test_to_predicted_dict_null_values_preserve_none() -> None:
    """JSON ``null`` -> Python None at the canonical key."""
    raw = '{"invoice_number": "INV-001", "delivery_date": null, "buyer_vat_id": null}'
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["delivery_date"] is None
    assert result["buyer_vat_id"] is None


def test_to_predicted_dict_empty_string_preserved() -> None:
    """Empty string from model -> empty string in result (NOT collapsed to None;
    ADR-012 tristate semantics: scorer's comparator handles empty-vs-missing)."""
    raw = '{"invoice_number": "INV-001", "buyer_reference": ""}'
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["buyer_reference"] == "", "empty string preserved (not None)"


def test_to_predicted_dict_german_diacritics_preserved() -> None:
    """German diacritics survive the JSON-parse + NFC-normalize pipeline end-to-end."""
    raw = preprocess(
        '{"seller_name": "M\u00fcnchen GmbH", "buyer_name": "Sch\u00f6ne Werke AG"}',
        model_id="m",
    )
    result = to_predicted_dict(raw, model_id="m")
    assert result["seller_name"] == "M\u00fcnchen GmbH"
    assert result["buyer_name"] == "Sch\u00f6ne Werke AG"


# ---------------------------------------------------------------------------
# 3. to_predicted_dict() -- permissive-JSON recovery ladder
# ---------------------------------------------------------------------------


def test_to_predicted_dict_recovers_from_prose_around_json() -> None:
    """``Here is the JSON: {...}. Hope this helps!`` -> substring extraction recovers."""
    raw = (
        'Here is the extracted JSON: {"invoice_number": "INV-001", '
        '"seller_name": "Test"}. Hope this helps!'
    )
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["seller_name"] == "Test"


def test_to_predicted_dict_recovers_from_trailing_comma() -> None:
    """``{"a": "b",}`` (Python / JS-style trailing comma) -> sanitizer recovers."""
    raw = (
        '{"invoice_number": "INV-001", '
        '"seller_name": "Test GmbH", }'
    )
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["seller_name"] == "Test GmbH"


def test_to_predicted_dict_non_json_text_yields_all_none() -> None:
    """Plain prose / OCR-style output -> all 16 canonical keys map to None."""
    raw = "Rechnung Nr. INV-001 vom 15.01.2024. Verk\u00e4ufer: Test GmbH. Gesamtbetrag: 119,00 EUR."
    result = to_predicted_dict(raw, model_id="m")
    assert all(v is None for v in result.values()), (
        "non-JSON text must yield all-None (signals 'model ignored JSON instruction')"
    )


def test_to_predicted_dict_empty_string_input_yields_all_none() -> None:
    """Empty string input -> all-None (no JSON to parse, no keys to extract)."""
    result = to_predicted_dict("", model_id="m")
    assert set(result.keys()) == set(FIELDS.keys())
    assert all(v is None for v in result.values())


def test_to_predicted_dict_malformed_json_yields_all_none() -> None:
    """Malformed JSON beyond the recovery ladder -> all-None."""
    raw = '{"invoice_number": "INV-001'  # unclosed string + unclosed brace
    result = to_predicted_dict(raw, model_id="m")
    assert all(v is None for v in result.values())


def test_to_predicted_dict_top_level_array_yields_all_none() -> None:
    """``[{"a": "b"}]`` (model emitted array, not object) -> all-None.

    Per design: top-level dict ONLY; arrays of objects (e.g., one-per-page) are
    NOT silently unwrapped. The empirical signal "model failed top-level-object
    schema" is more useful than implicit unwrapping.
    """
    raw = '[{"invoice_number": "INV-001"}]'
    result = to_predicted_dict(raw, model_id="m")
    assert all(v is None for v in result.values())


# ---------------------------------------------------------------------------
# 4. Public-surface contract -- shape + signature parity with adapters.py
# ---------------------------------------------------------------------------


def test_public_surface_signature_parity_with_adapters() -> None:
    """Both ``preprocess`` and ``to_predicted_dict`` accept ``(raw_or_text, model_id)``
    arg shape (same as ``adapters.preprocess`` + ``adapters.to_predicted_dict``).

    Locks the contract that the harness can swap modules via
    ``adapter_mod = adapters_json if cohort_cfg.adapter_mode == "json" else adapters``
    without per-call signature adjustment. Per ADR-018 §"Decision + integration
    thoughts" §"Architecture" item 3.
    """
    import inspect

    from horus.eval import adapters as adapters_regex
    from horus.eval import adapters_json as adapters_module

    pre_sig_a = inspect.signature(adapters_regex.preprocess)
    pre_sig_b = inspect.signature(adapters_module.preprocess)
    assert list(pre_sig_a.parameters) == list(pre_sig_b.parameters), (
        "preprocess() argument names must match across regex and json adapters"
    )

    pred_sig_a = inspect.signature(adapters_regex.to_predicted_dict)
    pred_sig_b = inspect.signature(adapters_module.to_predicted_dict)
    assert list(pred_sig_a.parameters) == list(pred_sig_b.parameters), (
        "to_predicted_dict() argument names must match across regex and json adapters"
    )
