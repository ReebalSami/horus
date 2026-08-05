"""Unit tests for the printed-evidence gate (`horus.eval.printed_evidence`).

These tests encode the three failure modes that motivate per-field policies, using
synthetic text layers so nothing depends on the private held-out corpus:

- a grouped IBAN on the page vs a bare one in GT,
- an address wrapped across lines on the page vs one line in GT,
- locale-formatted money/dates on the page vs canonical forms in GT.

They also pin the two things the gate must NOT do: pass a fabricated value, and report a
confident verdict where it has no warrant (no text layer, exempt vocabulary, or a null).
"""

from __future__ import annotations

import pytest

from horus.eval.ground_truth import FIELDS
from horus.eval.printed_evidence import (
    EvidencePolicy,
    EvidenceStatus,
    check_gt_document,
    check_value,
    date_printed_variants,
    fold_characters,
    money_printed_variants,
    policy_for_field,
    policy_for_group_cell,
    prepare_text_layer,
    rate_printed_variants,
    summarize,
)

# --------------------------------------------------------------------------------------
# Character folding + haystack preparation
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1\u00a0234", "1 234"),  # no-break space
        ("1\u202f234", "1 234"),  # narrow no-break space
        ("-\u221214", "--14"),  # minus sign folds to hyphen
        ("en\u2013dash", "en-dash"),
        ("soft\u00adhyphen", "softhyphen"),
        ("\ufb01n", "fin"),  # NFKC decomposes the fi ligature
    ],
)
def test_fold_characters_normalizes_typographic_variants(raw: str, expected: str) -> None:
    assert fold_characters(raw) == expected


def test_prepare_text_layer_builds_both_haystacks() -> None:
    layer = prepare_text_layer("Rechnung  Nr.\n 2026-001\n")
    assert layer.collapsed == "rechnung nr. 2026-001"
    assert layer.dense == "rechnungnr.2026-001"
    assert layer.word_count == 3
    assert layer.exists is True


def test_empty_text_layer_reports_not_existing() -> None:
    """The Tier B signal: a scanned PDF yields no words, so no value can be evidenced."""
    layer = prepare_text_layer("   \n\n  ")
    assert layer.exists is False
    assert layer.word_count == 0


# --------------------------------------------------------------------------------------
# Printed-variant generation
# --------------------------------------------------------------------------------------


def test_money_variants_cover_german_and_anglo_grouping() -> None:
    variants = money_printed_variants("1234.56")
    assert {"1.234,56", "1,234.56", "1234,56", "1234.56", "1 234,56"} <= variants


def test_money_variants_cover_german_whole_amount_shorthand() -> None:
    variants = money_printed_variants("50.00")
    assert {"50,00", "50", "50,-"} <= variants


def test_money_variants_emit_both_signs() -> None:
    """Presence, not sign convention: a deduction may print signed either way."""
    variants = money_printed_variants("-14.73")
    assert "14,73" in variants
    assert "-14,73" in variants


def test_date_variants_cover_german_anglo_and_long_forms() -> None:
    variants = date_printed_variants("2026-03-17")
    assert {
        "17.03.2026",
        "17.3.2026",
        "2026-03-17",
        "17/03/2026",
        "03/17/2026",
        "17. März 2026",
        "March 17, 2026",
    } <= variants


def test_date_variants_reject_non_iso_input() -> None:
    assert date_printed_variants("17.03.2026") == set()


def test_rate_variants_include_percent_context() -> None:
    variants = rate_printed_variants("19")
    assert {"19", "19,00", "19%", "19 %"} <= variants


# --------------------------------------------------------------------------------------
# Policy resolution
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("seller_name", EvidencePolicy.TEXT),
        ("seller_iban", EvidencePolicy.CODE),
        ("grand_total_amount", EvidencePolicy.MONEY),
        ("issue_date", EvidencePolicy.DATE),
        ("tax_rate", EvidencePolicy.RATE),
        ("document_type", EvidencePolicy.EXEMPT),
        ("payment_means_code", EvidencePolicy.EXEMPT),
    ],
)
def test_policy_for_field(key: str, expected: EvidencePolicy) -> None:
    assert policy_for_field(key) == expected


def test_every_registered_field_has_a_policy() -> None:
    """No field may be silently unhandled — an unhandled field is an ungated value."""
    for key in FIELDS:
        assert isinstance(policy_for_field(key), EvidencePolicy)


def test_policy_for_group_cell_derives_from_the_registry() -> None:
    assert policy_for_group_cell("vat_breakdown", "taxable_amount") == EvidencePolicy.MONEY
    assert policy_for_group_cell("vat_breakdown", "category_code") == EvidencePolicy.EXEMPT
    assert policy_for_group_cell("line_items", "name") == EvidencePolicy.TEXT


def test_unknown_field_and_group_raise() -> None:
    with pytest.raises(KeyError):
        policy_for_field("not_a_field")
    with pytest.raises(KeyError):
        policy_for_group_cell("not_a_group", "cell")
    with pytest.raises(KeyError):
        policy_for_group_cell("vat_breakdown", "not_a_cell")


# --------------------------------------------------------------------------------------
# The three failure modes a naive substring test gets wrong
# --------------------------------------------------------------------------------------


def test_grouped_iban_on_page_matches_bare_iban_in_gt() -> None:
    """CODE policy strips all whitespace: IBANs print in groups of four."""
    layer = prepare_text_layer("IBAN: DE89 3704 0044 0532 0130 00\nBIC: COBADEFFXXX")
    result = check_value("seller_iban", "DE89370400440532013000", EvidencePolicy.CODE, layer)
    assert result.status is EvidenceStatus.FOUND
    assert result.is_proven


def test_wrapped_address_on_page_matches_one_line_address_in_gt() -> None:
    """TEXT policy collapses whitespace: addresses wrap across lines."""
    layer = prepare_text_layer("Musterstraße 12\n20095 Hamburg\nDeutschland")
    result = check_value(
        "seller_address", "Musterstraße 12 20095 Hamburg", EvidencePolicy.TEXT, layer
    )
    assert result.status is EvidenceStatus.FOUND


def test_german_printed_money_matches_canonical_gt() -> None:
    """MONEY policy canonicalizes then searches printed renderings."""
    layer = prepare_text_layer("Gesamtbetrag 1.234,56 EUR")
    result = check_value("grand_total_amount", "1234.56", EvidencePolicy.MONEY, layer)
    assert result.status is EvidenceStatus.FOUND
    assert result.matched == "1.234,56"


def test_german_printed_money_matches_printed_gt() -> None:
    """Held-out GT stores values AS PRINTED, so the printed form must also pass."""
    layer = prepare_text_layer("Gesamtbetrag 1.234,56 EUR")
    result = check_value("grand_total_amount", "1.234,56", EvidencePolicy.MONEY, layer)
    assert result.status is EvidenceStatus.FOUND


def test_german_printed_date_matches_iso_gt() -> None:
    layer = prepare_text_layer("Rechnungsdatum: 17.03.2026")
    result = check_value("issue_date", "2026-03-17", EvidencePolicy.DATE, layer)
    assert result.status is EvidenceStatus.FOUND


def test_spaced_out_date_still_matches() -> None:
    """The dense haystack absorbs the spacing some PDFs put around separators."""
    layer = prepare_text_layer("Datum 17. 03. 2026")
    result = check_value("issue_date", "2026-03-17", EvidencePolicy.DATE, layer)
    assert result.status is EvidenceStatus.FOUND


def test_currency_code_matches_a_printed_symbol() -> None:
    """Many invoices print only the symbol, never the ISO code."""
    layer = prepare_text_layer("Summe: 100,00 €")
    result = check_value("invoice_currency_code", "EUR", EvidencePolicy.CODE, layer)
    assert result.status is EvidenceStatus.FOUND
    assert result.matched == "€"


# --------------------------------------------------------------------------------------
# What the gate must refuse to do
# --------------------------------------------------------------------------------------


def test_fabricated_value_is_not_found() -> None:
    """The whole point: a value that is not on the page cannot enter ground truth."""
    layer = prepare_text_layer("Media Markt Kundenbeleg\nSumme 63,97")
    result = check_value(
        "seller_address", "Billstedter Platz 3, 22111 Hamburg", EvidencePolicy.TEXT, layer
    )
    assert result.status is EvidenceStatus.NOT_FOUND
    assert result.needs_review


def test_wrong_amount_is_not_found_even_though_a_similar_one_is_printed() -> None:
    """53,97 must not pass on a page printing 63,97 — the retracted GT's actual defect."""
    layer = prepare_text_layer("Belegsumme 63,97 EUR")
    result = check_value("grand_total_amount", "53.97", EvidencePolicy.MONEY, layer)
    assert result.status is EvidenceStatus.NOT_FOUND


def test_no_text_layer_is_reported_distinctly_from_not_found() -> None:
    """Tier B must be distinguishable from "checked and absent" — different warrants."""
    layer = prepare_text_layer("")
    result = check_value("seller_name", "Media Markt", EvidencePolicy.TEXT, layer)
    assert result.status is EvidenceStatus.NO_TEXT_LAYER
    assert result.needs_review


def test_null_claim_is_never_reported_as_proven() -> None:
    """ "Absent" is unfalsifiable by search, so it can never be strong evidence."""
    layer = prepare_text_layer("Rechnung 2026-001")
    result = check_value("seller_iban", None, EvidencePolicy.CODE, layer)
    assert result.status is EvidenceStatus.NULL_CLAIM
    assert result.is_proven is False
    assert result.needs_review


def test_exempt_vocabulary_is_flagged_not_silently_passed() -> None:
    layer = prepare_text_layer("Rechnung Nr. 5")
    result = check_value("document_type", "invoice", EvidencePolicy.EXEMPT, layer)
    assert result.status is EvidenceStatus.EXEMPT
    assert result.is_proven is False


def test_unparseable_value_is_distinguished_from_absent() -> None:
    """A stored value that is not even parseable as its type is a GT defect of its own."""
    layer = prepare_text_layer("Gesamt 100,00")
    result = check_value("grand_total_amount", "not a number", EvidencePolicy.MONEY, layer)
    assert result.status is EvidenceStatus.UNPARSEABLE


def test_bare_rate_match_is_weak() -> None:
    """A bare "19" occurs incidentally; without percent context it is not evidence."""
    layer = prepare_text_layer("Position 19 Stück")
    result = check_value("tax_rate", "19", EvidencePolicy.RATE, layer)
    assert result.status is EvidenceStatus.FOUND
    assert result.weak is True
    assert result.is_proven is False


def test_rate_with_percent_context_is_strong() -> None:
    layer = prepare_text_layer("MwSt 19 % 1,90")
    result = check_value("tax_rate", "19", EvidencePolicy.RATE, layer)
    assert result.status is EvidenceStatus.FOUND
    assert result.weak is False
    assert result.is_proven


# --------------------------------------------------------------------------------------
# Document-level checking
# --------------------------------------------------------------------------------------


def test_check_gt_document_covers_every_field_and_keys_group_cells() -> None:
    layer = prepare_text_layer(
        "Muster GmbH\nRechnung 2026-001\nDatum 17.03.2026\n"
        "Netto 1.000,00\nMwSt 19 % 190,00\nGesamt 1.190,00 EUR"
    )
    fields = {
        "seller_name": "Muster GmbH",
        "issue_date": "2026-03-17",
        "grand_total_amount": "1190.00",
        "document_type": "invoice",
    }
    groups = {
        "vat_breakdown": [
            {
                "category_code": "S",
                "rate_percent": "19",
                "taxable_amount": "1000.00",
                "tax_amount": "190.00",
            }
        ]
    }
    results = check_gt_document(fields, groups, layer)
    by_key = {r.key: r for r in results}

    assert len(by_key) == len(FIELDS) + 4
    assert by_key["seller_name"].status is EvidenceStatus.FOUND
    assert by_key["issue_date"].status is EvidenceStatus.FOUND
    assert by_key["grand_total_amount"].status is EvidenceStatus.FOUND
    assert by_key["document_type"].status is EvidenceStatus.EXEMPT
    assert by_key["vat_breakdown[0].taxable_amount"].status is EvidenceStatus.FOUND
    assert by_key["vat_breakdown[0].category_code"].status is EvidenceStatus.EXEMPT
    # A field GT never mentioned is still a null CLAIM that needs its own warrant.
    assert by_key["seller_iban"].status is EvidenceStatus.NULL_CLAIM


def test_summarize_counts_statuses_and_rollups() -> None:
    layer = prepare_text_layer("Muster GmbH\nGesamt 1.190,00")
    results = check_gt_document(
        {"seller_name": "Muster GmbH", "grand_total_amount": "9999.99"}, {}, layer
    )
    counts = summarize(results)
    assert counts["found"] == 1
    assert counts["not_found"] == 1
    assert counts["proven"] == 1
    assert counts["needs_review"] == len(results) - 1
