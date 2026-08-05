"""Azure `prebuilt-invoice` → HORUS field mapping (ADR-061, channel 2).

Hermetic: every test runs against a hand-built payload in the exact wire shape
`AnalyzeResult.as_dict()` emits (camelCase, verified empirically against the installed SDK),
so `make test` needs no credentials and spends no F0 quota.

The tests that matter most are the ones guarding the distinctions that make a second channel
worth having at all: `not-covered` must never look like `not-present`, `content` must win over
Azure's typed re-formatting, and merging pages must not let silence beat a reading.
"""

from __future__ import annotations

from typing import Any

from horus.eval.azure_invoice import (
    AZURE_FIELD_MAP,
    AzureCoverage,
    AzureReading,
    coverage_summary,
    merge_page_groups,
    merge_page_readings,
    not_covered_fields,
    read_analyzed_document,
    read_groups,
    unmapped_azure_fields,
)
from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS


def _field(
    content: str | None = None,
    *,
    field_type: str = "string",
    confidence: float | None = None,
    page: int | None = None,
    value_string: str | None = None,
    value_currency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One `DocumentField` in `as_dict()` wire shape."""
    payload: dict[str, Any] = {"type": field_type}
    if content is not None:
        payload["content"] = content
    if value_string is not None:
        payload["valueString"] = value_string
    if value_currency is not None:
        payload["valueCurrency"] = value_currency
    if confidence is not None:
        payload["confidence"] = confidence
    if page is not None:
        payload["boundingRegions"] = [{"pageNumber": page, "polygon": [0.0, 0.0]}]
    return payload


def _document(fields: dict[str, Any]) -> dict[str, Any]:
    """One `AnalyzedDocument` in `as_dict()` wire shape."""
    return {"docType": "invoice", "confidence": 0.9, "spans": [], "fields": fields}


# ---------------------------------------------------------------------------
# Registry coverage
# ---------------------------------------------------------------------------


def test_every_registry_field_gets_a_reading() -> None:
    """All 34 fields are answered, including the ones Azure cannot express.

    An omitted key would be indistinguishable from an absent value downstream.
    """
    readings = read_analyzed_document(_document({}))
    assert set(readings) == set(FIELDS)


def test_mapping_table_covers_the_whole_registry() -> None:
    """No registry field is missing from the table — silence there would be accidental."""
    assert set(AZURE_FIELD_MAP) == set(FIELDS)


def test_not_covered_fields_are_reported_as_such_not_as_absent() -> None:
    """The distinction the whole channel rests on.

    If a field Azure cannot express were reported `NOT_PRESENT`, a Tier B null would gain a
    second-channel confirmation it never earned.
    """
    readings = read_analyzed_document(_document({}))
    assert readings["seller_account_name"].coverage is AzureCoverage.NOT_COVERED
    assert readings["payment_means_code"].coverage is AzureCoverage.NOT_COVERED
    assert readings["document_type"].coverage is AzureCoverage.NOT_COVERED
    # Mapped but simply absent from this payload.
    assert readings["invoice_number"].coverage is AzureCoverage.NOT_PRESENT


def test_not_covered_readings_are_not_evidence() -> None:
    """`is_evidence` excludes NOT_COVERED — it describes Azure, not the document."""
    readings = read_analyzed_document(_document({}))
    assert not readings["seller_account_name"].is_evidence
    assert readings["invoice_number"].is_evidence


def test_prepaid_amount_is_not_mapped_to_previous_unpaid_balance() -> None:
    """BT-113 is money already paid; `PreviousUnpaidBalance` is the opposite.

    Mapping them would invert the meaning of the cell in an answer key.
    """
    assert AZURE_FIELD_MAP["prepaid_amount"] == ()
    readings = read_analyzed_document(
        _document({"PreviousUnpaidBalance": _field("50,00", confidence=0.9)})
    )
    assert readings["prepaid_amount"].coverage is AzureCoverage.NOT_COVERED
    assert readings["prepaid_amount"].value is None


def test_not_covered_fields_listing_is_stable_and_non_empty() -> None:
    uncovered = not_covered_fields()
    assert "seller_gln" in uncovered
    assert "buyer_reference" in uncovered
    assert "invoice_number" not in uncovered
    assert uncovered == tuple(key for key in FIELDS if key in set(uncovered))


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------


def test_content_is_preferred_over_typed_value() -> None:
    """As-printed wins (ADR-058).

    Taking `valueDate` would rewrite a printed German date into ISO and destroy the
    as-printed contract that held-out GT is scored against.
    """
    readings = read_analyzed_document(
        _document(
            {
                "InvoiceDate": {
                    "type": "date",
                    "content": "28.09.2022",
                    "valueDate": "2022-09-28",
                    "confidence": 0.97,
                }
            }
        )
    )
    assert readings["issue_date"].value == "28.09.2022"


def test_value_string_is_the_fallback_when_content_is_absent() -> None:
    """A structured field can report a value without a flat content span."""
    readings = read_analyzed_document(_document({"VendorName": _field(value_string="ACME GmbH")}))
    assert readings["seller_name"].value == "ACME GmbH"


def test_blank_content_is_absence_not_an_empty_string() -> None:
    readings = read_analyzed_document(_document({"InvoiceId": _field("   ")}))
    assert readings["invoice_number"].coverage is AzureCoverage.NOT_PRESENT
    assert readings["invoice_number"].value is None


def test_confidence_and_page_are_carried() -> None:
    """Both exist for triage ordering and page context, never as a warrant."""
    readings = read_analyzed_document(
        _document({"InvoiceId": _field("R-2022-01", confidence=0.42, page=3)})
    )
    reading = readings["invoice_number"]
    assert reading.confidence == 0.42
    assert reading.page == 3
    assert reading.azure_field == "InvoiceId"


def test_currency_code_comes_from_the_typed_currency_value() -> None:
    """BT-5 is never its own field; the code only exists inside a currency value."""
    readings = read_analyzed_document(
        _document(
            {
                "InvoiceTotal": _field(
                    "1.234,56",
                    field_type="currency",
                    value_currency={"amount": 1234.56, "currencyCode": "eur"},
                    confidence=0.95,
                )
            }
        )
    )
    assert readings["invoice_currency_code"].value == "EUR"
    # The amount field itself still reads as printed.
    assert readings["grand_total_amount"].value == "1.234,56"


def test_currency_falls_through_to_the_next_candidate() -> None:
    """Preference order is honoured when the leading candidate carries no code."""
    readings = read_analyzed_document(
        _document(
            {
                "InvoiceTotal": _field("1.234,56", field_type="currency"),
                "AmountDue": _field(
                    "1.234,56",
                    field_type="currency",
                    value_currency={"amount": 1234.56, "currencyCode": "CHF"},
                ),
            }
        )
    )
    assert readings["invoice_currency_code"].value == "CHF"


def test_ambiguous_totals_both_read_the_same_azure_field() -> None:
    """`SubTotal` can plausibly answer BT-106 or BT-109.

    The ambiguity is preserved rather than resolved by guessing — adjudication decides,
    because a wrong assignment in an answer key is permanent.
    """
    readings = read_analyzed_document(_document({"SubTotal": _field("100,00")}))
    assert readings["line_total_amount"].value == "100,00"
    assert readings["tax_basis_total_amount"].value == "100,00"


def test_vendor_tax_id_feeds_both_german_tax_number_fields() -> None:
    """Azure merges what German invoices print as two different numbers."""
    readings = read_analyzed_document(_document({"VendorTaxId": _field("DE123456789")}))
    assert readings["seller_vat_id"].value == "DE123456789"
    assert readings["seller_tax_id"].value == "DE123456789"


def test_buyer_address_prefers_customer_over_billing() -> None:
    readings = read_analyzed_document(
        _document(
            {
                "CustomerAddress": _field("Hauptstr. 1, 20095 Hamburg"),
                "BillingAddress": _field("PO Box 42, 20095 Hamburg"),
            }
        )
    )
    assert readings["buyer_address"].value == "Hauptstr. 1, 20095 Hamburg"
    assert readings["buyer_address"].azure_field == "CustomerAddress"


# ---------------------------------------------------------------------------
# Flat fields nested inside an array (the payment block)
# ---------------------------------------------------------------------------


def _payment_details(*rows: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "array",
        "valueArray": [{"type": "object", "valueObject": row} for row in rows],
    }


def test_iban_and_bic_are_read_from_the_payment_block() -> None:
    """The audit's headline correction.

    `seller_iban`/`seller_bic` were wrongly declared structurally uncoverable; they live in
    `PaymentDetails[]`, not at the top level. Had this stayed unmapped, every IBAN and BIC
    in the corpus would have rested on a single channel forever.
    """
    readings = read_analyzed_document(
        _document(
            {
                "PaymentDetails": _payment_details(
                    {
                        "IBAN": _field("DE02 1203 0000 0000 2020 51", confidence=0.88, page=2),
                        "SWIFT": _field("BYLADEM1001"),
                    }
                )
            }
        )
    )
    assert readings["seller_iban"].value == "DE02 1203 0000 0000 2020 51"
    assert readings["seller_iban"].coverage is AzureCoverage.VALUE
    assert readings["seller_iban"].confidence == 0.88
    assert readings["seller_iban"].page == 2
    assert readings["seller_iban"].azure_field == "PaymentDetails[].IBAN"
    assert readings["seller_bic"].value == "BYLADEM1001"


def test_iban_and_bic_are_no_longer_reported_as_uncoverable() -> None:
    uncovered = not_covered_fields()
    assert "seller_iban" not in uncovered
    assert "seller_bic" not in uncovered
    # The holder's NAME still has no Azure counterpart — a number is not a name.
    assert "seller_account_name" in uncovered


def test_absent_payment_block_is_not_present_not_not_covered() -> None:
    """Azure can express these now, so silence is a claim about the page."""
    readings = read_analyzed_document(_document({}))
    assert readings["seller_iban"].coverage is AzureCoverage.NOT_PRESENT
    assert readings["seller_bic"].coverage is AzureCoverage.NOT_PRESENT


def test_first_row_carrying_the_cell_wins() -> None:
    """An invoice normally prints one account; a second is a claim the author can contest."""
    readings = read_analyzed_document(
        _document(
            {
                "PaymentDetails": _payment_details(
                    {"SWIFT": _field("FIRSTBIC")},
                    {"IBAN": _field("DE99")},
                )
            }
        )
    )
    assert readings["seller_bic"].value == "FIRSTBIC"
    # The IBAN is found on the second row because the first carries no IBAN cell.
    assert readings["seller_iban"].value == "DE99"


def test_payment_block_outranks_the_flat_fallback() -> None:
    """A dedicated payment block is a stronger source than a loose top-level field."""
    readings = read_analyzed_document(
        _document(
            {
                "BankAccountNumber": _field("0000202051"),
                "PaymentDetails": _payment_details({"IBAN": _field("DE02 1203")}),
            }
        )
    )
    assert readings["seller_iban"].value == "DE02 1203"
    assert readings["seller_iban"].azure_field == "PaymentDetails[].IBAN"


def test_flat_bank_account_number_is_the_fallback() -> None:
    """BT-84 permits a domestic account identifier, not only an IBAN."""
    readings = read_analyzed_document(_document({"BankAccountNumber": _field("0000202051")}))
    assert readings["seller_iban"].value == "0000202051"
    assert readings["seller_iban"].azure_field == "BankAccountNumber"


def test_payment_details_is_not_reported_as_an_unknown_field() -> None:
    document = _document({"PaymentDetails": _payment_details({"IBAN": _field("DE02")})})
    assert unmapped_azure_fields(document) == set()


def test_line_item_tax_rate_is_mapped() -> None:
    """`Items[].TaxRate` was observed on 40 rows; it had been assumed unavailable."""
    groups = read_groups(
        _document(
            {
                "Items": {
                    "type": "array",
                    "valueArray": [
                        {
                            "type": "object",
                            "valueObject": {
                                "Description": _field("Widget"),
                                "TaxRate": _field("19%"),
                            },
                        }
                    ],
                }
            }
        )
    )
    assert groups["line_items"][0]["vat_rate"] == "19%"


# ---------------------------------------------------------------------------
# Repeating groups
# ---------------------------------------------------------------------------


def test_line_items_rows_are_mapped_in_document_order() -> None:
    groups = read_groups(
        _document(
            {
                "Items": {
                    "type": "array",
                    "valueArray": [
                        {
                            "type": "object",
                            "valueObject": {
                                "Description": _field("Widget"),
                                "Quantity": _field("2"),
                                "UnitPrice": _field("10,00"),
                                "Amount": _field("20,00"),
                                "ProductCode": _field("W-1"),
                            },
                        },
                        {
                            "type": "object",
                            "valueObject": {"Description": _field("Gadget")},
                        },
                    ],
                }
            }
        )
    )
    rows = groups["line_items"]
    assert [row["name"] for row in rows] == ["Widget", "Gadget"]
    assert rows[0]["quantity"] == "2"
    assert rows[0]["net_price"] == "10,00"
    assert rows[0]["line_amount"] == "20,00"
    assert rows[0]["seller_assigned_id"] == "W-1"


def test_unmapped_group_cells_stay_none_rather_than_being_invented() -> None:
    """A group row is a shape claim; padding it would score as phantom content forever."""
    groups = read_groups(
        _document(
            {
                "Items": {
                    "type": "array",
                    "valueArray": [
                        {"type": "object", "valueObject": {"Description": _field("Widget")}}
                    ],
                }
            }
        )
    )
    row = groups["line_items"][0]
    assert row["line_id"] is None
    assert row["vat_rate"] is None
    assert set(row) == set(REPEATING_GROUPS["line_items"][1])


def test_skonto_always_abstains() -> None:
    """`prebuilt-invoice` has no early-payment-discount concept, so it does not vote."""
    groups = read_groups(_document({"Items": {"type": "array", "valueArray": []}}))
    assert groups["skonto"] == []


def test_all_groups_are_present_even_when_empty() -> None:
    groups = read_groups(_document({}))
    assert set(groups) == set(REPEATING_GROUPS)
    assert all(rows == [] for rows in groups.values())


def test_fully_empty_group_rows_are_dropped() -> None:
    groups = read_groups(
        _document(
            {
                "Items": {
                    "type": "array",
                    "valueArray": [
                        {"type": "object", "valueObject": {"Description": _field("  ")}},
                        {"type": "object", "valueObject": {"Description": _field("Real")}},
                    ],
                }
            }
        )
    )
    assert [row["name"] for row in groups["line_items"]] == ["Real"]


# ---------------------------------------------------------------------------
# Per-page merge
# ---------------------------------------------------------------------------


def test_merge_prefers_a_reading_over_silence() -> None:
    """Requests are per page, so a field printed on page 2 is absent from page 1."""
    page1 = read_analyzed_document(_document({}))
    page2 = read_analyzed_document(_document({"InvoiceId": _field("R-1", confidence=0.8)}))
    merged = merge_page_readings([page1, page2])
    assert merged["invoice_number"].value == "R-1"
    assert merged["invoice_number"].coverage is AzureCoverage.VALUE


def test_merge_prefers_the_more_confident_of_two_readings() -> None:
    low = read_analyzed_document(_document({"InvoiceId": _field("R-BAD", confidence=0.3)}))
    high = read_analyzed_document(_document({"InvoiceId": _field("R-GOOD", confidence=0.9)}))
    assert merge_page_readings([low, high])["invoice_number"].value == "R-GOOD"
    assert merge_page_readings([high, low])["invoice_number"].value == "R-GOOD"


def test_a_scored_reading_beats_an_unscored_one() -> None:
    """An unscored guess is the weaker claim."""
    unscored = {"invoice_number": AzureReading("invoice_number", "R-X", AzureCoverage.VALUE)}
    scored = {
        "invoice_number": AzureReading("invoice_number", "R-Y", AzureCoverage.VALUE, confidence=0.1)
    }
    assert merge_page_readings([unscored, scored])["invoice_number"].value == "R-Y"


def test_not_covered_is_sticky_across_pages() -> None:
    """No number of pages can supply a field the model cannot express."""
    pages = [read_analyzed_document(_document({})) for _ in range(3)]
    merged = merge_page_readings(pages)
    assert merged["seller_account_name"].coverage is AzureCoverage.NOT_COVERED


def test_merge_of_no_pages_still_answers_every_field() -> None:
    merged = merge_page_readings([])
    assert set(merged) == set(FIELDS)
    assert all(r.coverage is AzureCoverage.NOT_COVERED for r in merged.values())


def test_group_merge_concatenates_rather_than_deduplicating() -> None:
    """A real invoice can repeat a line across pages; collapsing would delete content."""
    row: dict[str, str | None] = dict.fromkeys(REPEATING_GROUPS["line_items"][1])
    row["name"] = "Widget"
    merged = merge_page_groups([{"line_items": [dict(row)]}, {"line_items": [dict(row)]}])
    assert len(merged["line_items"]) == 2


def test_group_merge_ignores_unknown_group_names() -> None:
    merged = merge_page_groups([{"not_a_group": [{"x": "y"}]}])
    assert set(merged) == set(REPEATING_GROUPS)


# ---------------------------------------------------------------------------
# Vocabulary measurement
# ---------------------------------------------------------------------------


def test_unmapped_fields_are_reported() -> None:
    """The measurement that keeps the mapping table honest.

    Microsoft documents the authoritative vocabulary behind a link rather than inline, so
    the table is a hypothesis and this is how its gaps surface.
    """
    document = _document(
        {
            "InvoiceId": _field("R-1"),
            "SomeFieldWeHaveNeverSeen": _field("x"),
            "AnotherNewOne": _field("y"),
        }
    )
    assert unmapped_azure_fields(document) == {"SomeFieldWeHaveNeverSeen", "AnotherNewOne"}


def test_address_recipient_is_a_fallback_not_an_override() -> None:
    """Observed live on 2026-08-05 and wired in as a fallback.

    When Azure reports a primary name field the recipient line must not displace it; when
    it does not, the recipient line is still a reading of the name.
    """
    both = read_analyzed_document(
        _document(
            {
                "VendorName": _field("ACME GmbH"),
                "VendorAddressRecipient": _field("ACME GmbH Headquarters"),
            }
        )
    )
    assert both["seller_name"].value == "ACME GmbH"
    assert both["seller_name"].azure_field == "VendorName"

    fallback = read_analyzed_document(
        _document({"VendorAddressRecipient": _field("ACME GmbH Headquarters")})
    )
    assert fallback["seller_name"].value == "ACME GmbH Headquarters"
    assert fallback["seller_name"].azure_field == "VendorAddressRecipient"


def test_deliberately_unused_azure_fields_are_not_reported_as_discoveries() -> None:
    """Suppression keeps the vocabulary report signal-bearing.

    Ship-to and the seller-assigned customer number have no registry counterpart, so
    reporting them every run would bury a genuine new field in known noise.
    """
    document = _document(
        {
            "ShippingAddress": _field("x"),
            "ShippingAddressRecipient": _field("y"),
            "CustomerId": _field("CID-1"),
        }
    )
    assert unmapped_azure_fields(document) == set()


def test_group_source_fields_are_not_reported_as_unmapped() -> None:
    document = _document(
        {"Items": {"type": "array", "valueArray": []}, "TaxDetails": {"type": "array"}}
    )
    assert unmapped_azure_fields(document) == set()


def test_coverage_summary_counts_all_three_states() -> None:
    readings = read_analyzed_document(_document({"InvoiceId": _field("R-1")}))
    counts = coverage_summary(readings)
    assert sum(counts.values()) == len(FIELDS)
    assert counts[AzureCoverage.VALUE.value] == 1
    assert counts[AzureCoverage.NOT_COVERED.value] == len(not_covered_fields())


# ---------------------------------------------------------------------------
# Malformed payloads
# ---------------------------------------------------------------------------


def test_missing_fields_dict_is_tolerated() -> None:
    readings = read_analyzed_document({"docType": "invoice"})
    assert set(readings) == set(FIELDS)


def test_non_mapping_field_entries_are_ignored() -> None:
    readings = read_analyzed_document({"fields": {"InvoiceId": "not-a-mapping"}})
    assert readings["invoice_number"].coverage is AzureCoverage.NOT_PRESENT


def test_malformed_confidence_and_page_degrade_to_none() -> None:
    document = _document(
        {
            "InvoiceId": {
                "type": "string",
                "content": "R-1",
                "confidence": "high",
                "boundingRegions": [{"polygon": [0.0]}],
            }
        }
    )
    reading = read_analyzed_document(document)["invoice_number"]
    assert reading.value == "R-1"
    assert reading.confidence is None
    assert reading.page is None


def test_malformed_group_payload_yields_no_rows() -> None:
    groups = read_groups(_document({"Items": {"type": "array", "valueArray": "nope"}}))
    assert groups["line_items"] == []
