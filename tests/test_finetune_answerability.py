"""Tests for the transcript-answerability probe's pure logic (issue #55, #114 ruler fix)."""

from __future__ import annotations

from horus.finetune.answerability import _composite_findable, value_variants


def test_iso_date_variants() -> None:
    v = value_variants(None, "2017-05-09")
    assert "2017-05-09" in v
    assert "09.05.2017" in v
    assert "9.5.2017" in v


def test_amount_variants_german_shapes() -> None:
    v = value_variants(None, "12345.67")
    assert "12345,67" in v
    assert "12.345,67" in v
    v_small = value_variants(None, "571.04")
    assert "571,04" in v_small
    assert not any("." in s and "," in s for s in v_small)  # no grouping under 4 digits


def test_iban_grouping() -> None:
    v = value_variants("DE88200800000970375700", None)
    assert "de88 2008 0000 0970 3757 00" in v


def test_raw_and_normalized_both_seeded_and_canonicalized() -> None:
    v = value_variants("Musterfirma  GmbH", "musterfirma gmbh")
    assert v == {"musterfirma gmbh"}  # whitespace collapsed + lowercased -> single canon form


def test_empty_values() -> None:
    assert value_variants(None, None) == set()
    assert value_variants("  ", "") == set()


# ---- #114 ruler-fix variant classes ---------------------------------------


def test_slash_date_variant_french() -> None:
    v = value_variants("20171116", "2017-11-16")
    assert "16/11/2017" in v  # French invoices print DD/MM/YYYY


def test_spaced_iban_gt_matches_compact_print() -> None:
    v = value_variants("DE88 2008 0000 0970 3757 00", None)
    assert "de88200800000970375700" in v  # page prints the IBAN compact
    assert "de88 2008 0000 0970 3757 00" in v  # 4-grouped re-derived from compact


def test_doctype_token_maps_to_printed_words() -> None:
    v = value_variants("380", "invoice", "document_type")
    assert "rechnung" in v
    v_cn = value_variants("381", "credit_note", "document_type")
    assert "gutschrift" in v_cn
    assert "avoir" in v_cn
    # field-agnostic call stays unchanged (no surface words leak in)
    assert "rechnung" not in value_variants("380", "invoice")


def test_currency_code_maps_to_symbol() -> None:
    v = value_variants("EUR", "EUR", "invoice_currency_code")
    assert "€" in v
    assert "€" not in value_variants("EUR", "EUR")


def test_composite_address_component_wise() -> None:
    text = "verkäufer: lieferant gmbh lieferantenstraße 20 de 80333 münchen"
    raw = "Lieferantenstraße 20, 80333, München, DE"
    assert _composite_findable(text, raw, raw)  # multi-line block, reordered country
    assert not _composite_findable("völlig anderer text", raw, raw)
    # a component genuinely absent (wrong city) stays missing
    assert not _composite_findable("lieferantenstraße 20 de 80333 hamburg", raw, raw)
