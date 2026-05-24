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

from horus.eval.adapters_json import preprocess, to_predicted_dict, to_predicted_dict_multipage
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
    raw = '{"invoice_number": "INV-001", "seller_name": "Test GmbH", }'
    result = to_predicted_dict(raw, model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["seller_name"] == "Test GmbH"


def test_to_predicted_dict_non_json_text_yields_all_none() -> None:
    """Plain prose / OCR-style output -> all 16 canonical keys map to None."""
    raw = (
        "Rechnung Nr. INV-001 vom 15.01.2024. Verk\u00e4ufer: Test GmbH. Gesamtbetrag: 119,00 EUR."
    )
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

    # ADR-019 Wave 3.1: multipage API parity. Both adapters expose the same
    # `to_predicted_dict_multipage(per_page_texts, model_id)` signature so the
    # harness can swap modules via cohort.adapter_mode without per-call branching.
    multi_sig_a = inspect.signature(adapters_regex.to_predicted_dict_multipage)
    multi_sig_b = inspect.signature(adapters_module.to_predicted_dict_multipage)
    assert list(multi_sig_a.parameters) == list(multi_sig_b.parameters), (
        "to_predicted_dict_multipage() argument names must match across regex and json adapters"
    )


# ---------------------------------------------------------------------------
# 5. to_predicted_dict_multipage() -- per-page parse + first-non-null-wins merge
# ---------------------------------------------------------------------------
#
# Per ADR-019 §"Wave 3.1 architecture": the harness has `per_page_results` already
# (one ExtractionResult per page). The single-input `to_predicted_dict` was
# silently dropping valid model output when models emitted per-page-valid JSON
# concatenated with `\n` (Gemma-4 unfenced) or with mixed fence styles
# (olmOCR Arm A). The multipage API parses each page independently and merges
# with first-non-null-wins (page 1 dominates; defends against page-2
# hallucinations like olmOCR Arm B "Joghurt Banane" overwriting Lieferant GmbH).
#
# These tests are derived from empirical evidence in
# `docs/sources/transcripts-structured-probe-{uniform,native-json}/*.txt`,
# audited and locked in ADR-019.


def test_multipage_unfenced_real_values_gemma_shape() -> None:
    """Gemma-4 shape: 2 unfenced dicts with real values per page → all real values recovered.

    Empirical: ``docs/sources/transcripts-structured-probe-uniform/
    google__gemma-4-e4b-it__EN16931_Einfach.txt``.
    Per ADR-019 B1 (load-bearing): single-input adapter returned all-None on the
    `{p1}\\n{p2}` concat. Multipage API recovers it.
    """
    p1 = (
        '{"invoice_number": "471102", "issue_date": "2018-03-05", '
        '"invoice_currency_code": "EUR", "delivery_date": "2018-03-05", '
        '"seller_name": "Lieferant GmbH", "seller_gln": "40000001123452", '
        '"buyer_name": "Kunden AG Mitte"}'
    )
    p2 = '{"grand_total_amount": "529,87", "due_payable_amount": "529,87"}'
    result = to_predicted_dict_multipage([p1, p2], model_id="google/gemma-4-E4B-it")
    assert result["invoice_number"] == "471102"
    assert result["issue_date"] == "2018-03-05"
    assert result["invoice_currency_code"] == "EUR"
    assert result["seller_name"] == "Lieferant GmbH"
    assert result["seller_gln"] == "40000001123452"
    assert result["buyer_name"] == "Kunden AG Mitte"
    assert result["grand_total_amount"] == "529,87"
    assert result["due_payable_amount"] == "529,87"


def test_multipage_fenced_real_values_glm_arm_b_shape() -> None:
    """GLM-OCR Arm B shape: 2 fenced dicts with real values per page → page 1 dominates.

    Empirical: docs/sources/transcripts-structured-probe-native-json/
    zai-org__glm-ocr__EN16931_Einfach.txt.
    Per ADR-019 B2: GLM-OCR Arm B's _FENCE_RE non-greedy match captured
    only page 1 under the single-input API. Multipage API parses BOTH per-page;
    page 1 real values are preserved.
    """
    p1 = (
        "```json\n"
        '{"invoice_number": "471102", "issue_date": "2018-03-05", '
        '"seller_name": "Lieferant GmbH", "seller_gln": "4000001123452"}\n'
        "```"
    )
    # Page 2 of GLM-OCR Arm B: line-item content leaked into JSON keys
    # ("seller_name": "Art-Nr-Kunde", "buyer_name": "TB100A4"). Page 1 must win.
    p2 = (
        "```json\n"
        '{"seller_name": "Art-Nr-Kunde", "buyer_name": "TB100A4", '
        '"line_total_amount": "9,900.00"}\n'
        "```"
    )
    result = to_predicted_dict_multipage([p1, p2], model_id="zai-org/GLM-OCR")
    assert result["invoice_number"] == "471102"
    assert result["seller_name"] == "Lieferant GmbH", (
        "page 1 must NOT be overwritten by page 2 line-item leak"
    )
    assert result["seller_gln"] == "4000001123452"
    # buyer_name absent from page 1 → page 2's leaked value is the only signal.
    # First-non-null-wins surfaces it (the threshold gate B4 in Wave 3.2 catches the F1 cost).
    assert result["buyer_name"] == "TB100A4"
    assert result["line_total_amount"] == "9,900.00"


def test_multipage_repeated_placeholder_dicts_granite_arm_a_shape() -> None:
    """Granite Arm A shape: 8 identical placeholder dicts per page → 16 placeholder keys recovered.

    Empirical: docs/sources/transcripts-structured-probe-uniform/
    ibm-granite__granite-docling-258m-mlx__EN16931_Einfach.txt.
    Per ADR-019 B3: Granite Arm A's decoder-loop emits 8+ identical <BT-N>-shape
    placeholder dicts. Multipage API parses the FIRST valid JSON dict on each page;
    placeholder values surface in the result. Wave 3.2 threshold gate (B4) catches
    the F1=0 schema-mimicry case at the verdict layer, NOT here.
    """
    placeholder = (
        '{"invoice_number": "<BT-1>", "issue_date": "<BT-2 ISO 8601>", '
        '"invoice_currency_code": "<BT-5>", "seller_name": "<BT-27>"}'
    )
    p1 = "\n\n".join([placeholder] * 8)  # 8 repeats per page (Granite Arm A shape)
    p2 = "\n\n".join([placeholder] * 8)
    result = to_predicted_dict_multipage([p1, p2], model_id="ibm-granite/granite-docling-258M-mlx")
    assert result["invoice_number"] == "<BT-1>"  # placeholder surfaces (F1=0 by design)
    assert result["issue_date"] == "<BT-2 ISO 8601>"
    assert result["invoice_currency_code"] == "<BT-5>"
    assert result["seller_name"] == "<BT-27>"


def test_multipage_mixed_fenced_unfenced_olmocr_arm_a_shape() -> None:
    """olmOCR Arm A shape: page 1 unfenced + page 2 fenced — both recovered independently.

    Empirical: docs/sources/transcripts-structured-probe-uniform/
    allenai__olmocr-2-7b-1025__EN16931_Einfach.txt.
    The single-input adapter's _FENCE_RE searches the WHOLE text and captures
    only the page-2 fence (losing page 1 entirely). Multipage API parses each
    page independently → page 1 real values are preserved.
    """
    p1 = (
        '{"invoice_number": "471102", "issue_date": "2018-03-05", '
        '"seller_name": "Lieferantant GmbH", "buyer_name": "Kunden AG Mitte"}'
    )
    p2 = (
        "```json\n"
        '{"line_total_amount": "198,00", "tax_total_amount": "198,00", '
        '"grand_total_amount": "529,87", "due_payable_amount": "529,87"}\n'
        "```"
    )
    result = to_predicted_dict_multipage([p1, p2], model_id="allenai/olmOCR-2-7B-1025")
    assert result["invoice_number"] == "471102"
    assert result["seller_name"] == "Lieferantant GmbH"
    assert result["buyer_name"] == "Kunden AG Mitte"
    assert result["line_total_amount"] == "198,00"
    assert result["due_payable_amount"] == "529,87"


def test_multipage_first_non_null_wins_policy() -> None:
    """Page 1 fills field A, page 2 fills field B → both present; no overwrite."""
    p1 = '{"invoice_number": "INV-001", "issue_date": "2024-01-15"}'
    p2 = '{"grand_total_amount": "100.00", "due_payable_amount": "100.00"}'
    result = to_predicted_dict_multipage([p1, p2], model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["issue_date"] == "2024-01-15"
    assert result["grand_total_amount"] == "100.00"
    assert result["due_payable_amount"] == "100.00"


def test_multipage_page_2_hallucination_does_not_overwrite_page_1() -> None:
    """Page 1 has correct value, page 2 has hallucinated value → page 1 wins.

    Defends against the olmOCR Arm B page-2 hallucination class:
    `"seller_name": "Joghurt Banane"` (the line-item product name leaks into
    canonical keys because page 2's table content reuses the schema's key names).
    Page 1 had the correct "Lieferant GmbH". First-non-null-wins keeps page 1.
    """
    p1 = '{"seller_name": "Lieferant GmbH", "buyer_name": "Kunden AG Mitte"}'
    p2 = '{"seller_name": "Joghurt Banane", "buyer_name": "Trennblätter A4"}'
    result = to_predicted_dict_multipage([p1, p2], model_id="m")
    assert result["seller_name"] == "Lieferant GmbH"
    assert result["buyer_name"] == "Kunden AG Mitte"


def test_multipage_null_in_page_1_filled_by_page_2() -> None:
    """Page 1 has explicit null, page 2 has real value → page 2 fills it.

    JSON `null` parses to Python `None` → treated as "not extracted" → page 2 wins.
    Empirical: Gemma-4 Arm A page 1 has `grand_total_amount: null` and page 2
    has `grand_total_amount: "529,87"` (page-1 footer line item missing,
    page-2 totals block present).
    """
    p1 = '{"invoice_number": "471102", "grand_total_amount": null, "due_payable_amount": null}'
    p2 = '{"grand_total_amount": "529,87", "due_payable_amount": "529,87"}'
    result = to_predicted_dict_multipage([p1, p2], model_id="m")
    assert result["invoice_number"] == "471102"
    assert result["grand_total_amount"] == "529,87"  # page 2 fills page-1 null
    assert result["due_payable_amount"] == "529,87"


def test_multipage_empty_string_in_page_1_preserved_per_adr_012_tristate() -> None:
    """Page 1 empty string is a present value (ADR-012 tristate); page 2 does NOT overwrite.

    Per ADR-012 §"Tristate value semantics": empty string ≠ None. The multipage
    merge policy is strictly "first-non-None-wins", so empty-string from page 1
    counts as a present value and dominates over page 2's content.

    The scorer's comparator handles the empty-vs-missing distinction downstream;
    the adapter must not silently collapse empty to null.
    """
    p1 = '{"buyer_reference": ""}'
    p2 = '{"buyer_reference": "REF-42"}'
    result = to_predicted_dict_multipage([p1, p2], model_id="m")
    assert result["buyer_reference"] == "", (
        "ADR-012 tristate: empty string is a present value; page 1 dominates"
    )


def test_multipage_singlepage_input_works() -> None:
    """Single-element list: multipage API generalizes the single-page case."""
    p1 = '{"invoice_number": "INV-001", "seller_name": "Test GmbH"}'
    result = to_predicted_dict_multipage([p1], model_id="m")
    assert result["invoice_number"] == "INV-001"
    assert result["seller_name"] == "Test GmbH"


def test_multipage_empty_list_yields_all_none() -> None:
    """Empty list (no pages) → all 16 canonical keys map to None."""
    result = to_predicted_dict_multipage([], model_id="m")
    assert set(result.keys()) == set(FIELDS.keys())
    assert all(v is None for v in result.values())


def test_multipage_all_pages_unparseable_yields_all_none() -> None:
    """Every page fails parse → all-None (preserves the empirical signal).

    PaliGemma2 shape: both pages emit refusal text, no JSON anywhere.
    """
    p1 = "Sorry, as a base VLM I am not trained to answer this question."
    p2 = "OK"
    result = to_predicted_dict_multipage([p1, p2], model_id="google/paligemma2-3b-mix-448")
    assert all(v is None for v in result.values())


def test_multipage_returns_all_16_canonical_keys() -> None:
    """Result dict always contains exactly the 16 canonical FIELDS keys."""
    result = to_predicted_dict_multipage(['{"invoice_number": "X"}'], model_id="m")
    assert set(result.keys()) == set(FIELDS.keys())
    assert len(result) == 16


def test_multipage_german_diacritics_preserved_across_pages() -> None:
    """German diacritics (NFC-normalized) survive per-page parse + merge."""
    p1 = '{"seller_name": "M\u00fcnchen GmbH"}'
    p2 = '{"buyer_name": "Sch\u00f6ne Werke AG"}'
    result = to_predicted_dict_multipage([p1, p2], model_id="m")
    assert result["seller_name"] == "M\u00fcnchen GmbH"
    assert result["buyer_name"] == "Sch\u00f6ne Werke AG"
