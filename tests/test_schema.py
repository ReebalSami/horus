"""Tests for the ADR-035 canonical-schema extension (corpus-independent).

Covers the 16→19 field extension end-to-end WITHOUT the ZUGFeRD corpus on disk
(so these run in CI): the `RATE` normalizers (GT + predicted, byte-identical
canonical), composite-address parsing in `parse_cii_xml` over in-memory CII
XML, the `FIELDS` / `FIELDS_V1` registry extension, the `InvoiceFields`
Pydantic model, `validate_and_repair`, and `RATE` scoring dispatch.

Refs: ADR-035 (schema extension), ADR-033 (v1/v2 byte-identical leaves),
ADR-013/027 (scorer), ADR-012 (16-field base).
"""

from __future__ import annotations

import pytest

from horus.config import EvalConfig
from horus.eval.ground_truth import (
    FIELDS,
    FIELDS_V1,
    GroundTruth,
    GroundTruthField,
    _normalize_doctype,
    _normalize_rate,
    _parse_freetext_due_date,
    _parse_freetext_skonto,
    parse_cii_xml,
)
from horus.eval.normalizers import _normalize_predicted_rate
from horus.eval.schema import (
    PURPOSE_SUMMARY_KEY,
    InvoiceFields,
    validate_and_repair,
)
from horus.eval.scorer import score

# ===========================================================================
# 1. RATE normalizers — GT-side `_normalize_rate` + predicted-side mirror
# ===========================================================================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("19.00", "19"),
        ("19", "19"),
        ("7.50", "7.5"),
        ("7.00", "7"),
        ("0.00", "0"),
        ("16.000", "16"),
        ("  19.00  ", "19"),  # outer whitespace stripped
    ],
)
def test_normalize_rate_gt_side(raw: str, expected: str) -> None:
    """GT-side `_normalize_rate` strips trailing zeros to a canonical decimal string."""
    assert _normalize_rate(raw) == expected


@pytest.mark.parametrize("bad", ["abc", "", "   ", "19%notnumber"])
def test_normalize_rate_gt_side_rejects_non_numeric(bad: str) -> None:
    """GT-side `_normalize_rate` raises ValueError on unparseable input (corpus-anomaly path)."""
    with pytest.raises(ValueError, match="not parseable as Decimal"):
        _normalize_rate(bad)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("19", "19"),
        ("19.0", "19"),
        ("19.00", "19"),
        ("19%", "19"),
        ("19 %", "19"),
        ("19,00", "19"),  # German decimal-comma
        ("7,5", "7.5"),
        ("7.5 %", "7.5"),
        ("0", "0"),
    ],
)
def test_normalize_predicted_rate(raw: str, expected: str) -> None:
    """Predicted-side `_normalize_predicted_rate` tolerates %, German comma, trailing zeros."""
    assert _normalize_predicted_rate(raw) == expected


@pytest.mark.parametrize("bad", ["", "   ", "abc", "%", "1.2.3"])
def test_normalize_predicted_rate_returns_none_on_garbage(bad: str) -> None:
    """Unparseable predicted rate → None (honest null; scorer maps to FN/TN)."""
    assert _normalize_predicted_rate(bad) is None


@pytest.mark.parametrize(
    ("gt_raw", "pred_raw"),
    [
        ("19.00", "19 %"),
        ("19.00", "19,00"),
        ("7.50", "7,5"),
        ("0.00", "0"),
    ],
)
def test_gt_and_predicted_rate_canonical_agree(gt_raw: str, pred_raw: str) -> None:
    """GT-side and predicted-side rate normalizers produce byte-identical canonical strings.

    This is the load-bearing invariant that lets `RATE` use exact-match: the GT
    parser and the structurer output must canonicalize to the same string.
    """
    assert _normalize_rate(gt_raw) == _normalize_predicted_rate(pred_raw)


# ===========================================================================
# 2. FIELDS / FIELDS_V1 registry extension (ADR-035 + ADR-033)
# ===========================================================================


def test_new_fields_present_with_expected_types() -> None:
    """The 3 ADR-035 fields exist with the right field_type + composite config."""
    assert FIELDS["tax_rate"].field_type == "RATE"
    assert FIELDS["tax_rate"].composite_leaves is None
    assert FIELDS["seller_address"].field_type == "STRING"
    assert FIELDS["buyer_address"].field_type == "STRING"
    # Addresses are composite (PostalTradeAddress own .text is empty).
    assert FIELDS["seller_address"].composite_leaves is not None
    assert FIELDS["buyer_address"].composite_leaves is not None
    assert "LineOne" in FIELDS["seller_address"].composite_leaves
    assert "CountryID" in FIELDS["seller_address"].composite_leaves


def test_v1_registry_covers_new_fields_and_preserves_composite() -> None:
    """FIELDS_V1 derivation keeps the 3 new fields + their composite_leaves (ADR-033)."""
    for key in ("tax_rate", "seller_address", "buyer_address"):
        assert key in FIELDS_V1
    # composite_leaves survives the `replace(spec, xpath=...)` derivation.
    assert FIELDS_V1["seller_address"].composite_leaves == FIELDS["seller_address"].composite_leaves
    # v1 derivation retargeted the container + root.
    assert "/rsm:CrossIndustryDocument" in FIELDS_V1["tax_rate"].xpath
    assert "ram:ApplicableSupplyChainTradeAgreement" in FIELDS_V1["seller_address"].xpath


# ===========================================================================
# 3. parse_cii_xml — composite address + tax_rate (in-memory v2 CII)
# ===========================================================================

_V2_NS = (
    'xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" '
    'xmlns:ram="urn:un:unece:uncefact:data:standard:'
    'ReusableAggregateBusinessInformationEntity:100" '
    'xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"'
)


def _v2_invoice(*, seller_addr: str = "", buyer_addr: str = "", tax: str = "") -> bytes:
    """Build a minimal CII v2 invoice XML with optional address + tax fragments."""
    return (
        f"<rsm:CrossIndustryInvoice {_V2_NS}>"
        "<rsm:SupplyChainTradeTransaction>"
        "<ram:ApplicableHeaderTradeAgreement>"
        f"<ram:SellerTradeParty>{seller_addr}</ram:SellerTradeParty>"
        f"<ram:BuyerTradeParty>{buyer_addr}</ram:BuyerTradeParty>"
        "</ram:ApplicableHeaderTradeAgreement>"
        f"<ram:ApplicableHeaderTradeSettlement>{tax}</ram:ApplicableHeaderTradeSettlement>"
        "</rsm:SupplyChainTradeTransaction>"
        "</rsm:CrossIndustryInvoice>"
    ).encode()


def test_parse_composite_address_canonical_order() -> None:
    """seller/buyer address children concatenate in `_ADDRESS_LEAVES` order, not doc order."""
    # Note: PostcodeCode is placed BEFORE LineOne in the XML to prove the join
    # follows declaration order (LineOne first), not document order.
    seller = (
        "<ram:PostalTradeAddress>"
        "<ram:PostcodeCode>80331</ram:PostcodeCode>"
        "<ram:LineOne>Lieferantenstraße 20</ram:LineOne>"
        "<ram:CityName>München</ram:CityName>"
        "<ram:CountryID>DE</ram:CountryID>"
        "</ram:PostalTradeAddress>"
    )
    buyer = (
        "<ram:PostalTradeAddress>"
        "<ram:LineOne>Kundenweg 1</ram:LineOne>"
        "<ram:PostcodeCode>69115</ram:PostcodeCode>"
        "<ram:CityName>Heidelberg</ram:CityName>"
        "<ram:CountryID>DE</ram:CountryID>"
        "</ram:PostalTradeAddress>"
    )
    gt = parse_cii_xml(_v2_invoice(seller_addr=seller, buyer_addr=buyer))

    sa = gt.header["seller_address"]
    assert sa.is_present
    assert sa.normalized_value == "Lieferantenstraße 20, 80331, München, DE"

    ba = gt.header["buyer_address"]
    assert ba.is_present
    assert ba.normalized_value == "Kundenweg 1, 69115, Heidelberg, DE"


def test_parse_absent_address_is_not_present() -> None:
    """No PostalTradeAddress element → field absent (is_present=False, raw=None)."""
    gt = parse_cii_xml(_v2_invoice(seller_addr="", buyer_addr=""))
    assert gt.header["seller_address"].is_present is False
    assert gt.header["seller_address"].raw_value is None


def test_parse_empty_address_is_present_but_empty() -> None:
    """Present PostalTradeAddress with no child text → present-but-empty (raw='')."""
    gt = parse_cii_xml(_v2_invoice(seller_addr="<ram:PostalTradeAddress/>"))
    sa = gt.header["seller_address"]
    assert sa.is_present is True
    assert sa.raw_value == ""
    assert sa.normalized_value == ""


def test_parse_tax_rate_normalized() -> None:
    """RateApplicablePercent '19.00' → canonical '19'."""
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    assert gt.header["tax_rate"].is_present
    assert gt.header["tax_rate"].normalized_value == "19"


def test_parse_multi_rate_tax_rate_excluded() -> None:
    """Multi-distinct-rate invoice (two ApplicableTradeTax) -> flat tax_rate EXCLUDED (ADR-045).

    Supersedes the pre-ADR-045 "take first rate in document order" behaviour. The
    flat document-level tax_rate is ill-posed when the invoice carries multiple
    distinct VAT rates (the per-rate truth lives in vat_breakdown), so
    parse_cii_xml records is_present=True + normalized_value=None (the scorer's
    EXCLUDED path); raw_value preserves the distinct rates for audit.
    """
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>7.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    rate = gt.header["tax_rate"]
    assert rate.is_present is True
    assert rate.normalized_value is None  # -> scorer EXCLUDED outcome
    assert rate.raw_value == "19|7"  # sorted distinct rates, preserved for audit


def test_multi_rate_tax_rate_scores_excluded() -> None:
    """A single rate emitted on a multi-rate invoice scores EXCLUDED, not FP/FN (ADR-045)."""
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>7.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    predicted["tax_rate"] = "19"
    result = score(predicted, gt, cfg=EvalConfig())
    assert result.per_field["tax_rate"].outcome == "EXCLUDED"


def test_parse_single_rate_repeated_still_scored() -> None:
    """Multiple ApplicableTradeTax that all carry the SAME rate -> still scored (ADR-045)."""
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    assert gt.header["tax_rate"].is_present is True
    assert gt.header["tax_rate"].normalized_value == "19"


def test_parse_zero_rate_tax_rate_excluded() -> None:
    """A single 0% VAT rate (reverse-charge / intra-community / exempt) -> EXCLUDED (ADR-052).

    Extends ADR-045: the flat document-level tax_rate is also ill-posed when the
    only rate is 0 — there is no positive "tax rate" rendered on the page, and the
    literal 0 is captured in the vat_breakdown group. parse_cii_xml records
    is_present=True + normalized_value=None (the scorer's EXCLUDED path).
    """
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>0.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    rate = gt.header["tax_rate"]
    assert rate.is_present is True
    assert rate.normalized_value is None  # -> scorer EXCLUDED outcome
    assert rate.raw_value == "0.00"  # preserved for audit


def test_zero_rate_tax_rate_scores_excluded() -> None:
    """A model that omits flat tax_rate on a 0%-rate invoice scores EXCLUDED, not FN (ADR-052)."""
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>0.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    result = score(predicted, gt, cfg=EvalConfig())
    assert result.per_field["tax_rate"].outcome == "EXCLUDED"


def test_parse_header_has_19_keys() -> None:
    """Parsed header always carries all 34 canonical keys (corpus-independent)."""
    gt = parse_cii_xml(_v2_invoice())
    assert set(gt.header.keys()) == set(FIELDS.keys())
    assert len(gt.header) == 34


# ===========================================================================
# 4. InvoiceFields Pydantic model + validate_and_repair (ADR-035)
# ===========================================================================


def test_model_scored_fields_match_registry() -> None:
    """InvoiceFields flat scored fields == FIELDS exactly (excluding non-scored fields).

    Non-scored model fields: purpose_summary (display) + the ADR-041 repeating
    groups vat_breakdown / skonto (scored via ADR-042, not the flat dict).
    """
    model_fields = set(InvoiceFields.model_fields)
    non_scored = {PURPOSE_SUMMARY_KEY, "vat_breakdown", "skonto", "line_items"}
    assert non_scored <= model_fields
    assert model_fields - non_scored == set(FIELDS)


def test_to_scored_dict_excludes_purpose_summary() -> None:
    """to_scored_dict has exactly the 19 FIELDS keys; purpose_summary is non-scored."""
    model = InvoiceFields.model_validate({"purpose_summary": "Beratungsleistung Q1"})
    scored = model.to_scored_dict()
    assert set(scored.keys()) == set(FIELDS)
    assert PURPOSE_SUMMARY_KEY not in scored
    # But it IS retained on the full dict for the Streamlit app.
    assert model.to_full_dict()[PURPOSE_SUMMARY_KEY] == "Beratungsleistung Q1"


def test_validate_and_repair_case_insensitive_keys() -> None:
    """Mixed-case incoming keys map to canonical (defends against capitalized schema)."""
    out = validate_and_repair({"Invoice_Number": "INV-001", "ISSUE_DATE": "05.03.2018"})
    assert out["invoice_number"] == "INV-001"
    assert out["issue_date"] == "2018-03-05"


def test_validate_and_repair_locale_coercion() -> None:
    """German money / rate locale variance coerces to canonical forms."""
    out = validate_and_repair(
        {"grand_total_amount": "1.234,56", "tax_rate": "19 %", "seller_name": "  Müller GmbH "}
    )
    assert out["grand_total_amount"] == "1234.56"
    assert out["tax_rate"] == "19"
    assert out["seller_name"] == "Müller GmbH"


def test_validate_and_repair_honest_null_on_missing_and_unparseable() -> None:
    """Missing keys → None; unparseable typed values → None (never invented)."""
    out = validate_and_repair({"grand_total_amount": "not-a-number"})
    assert out["grand_total_amount"] is None
    assert out["invoice_number"] is None  # absent → None


def test_validate_and_repair_drops_unknown_keys_and_returns_19() -> None:
    """Unknown keys (nested / hallucinated) are dropped; result is the 19 scored keys."""
    out = validate_and_repair({"foobar": "x", "seller": {"name": "Y"}, "invoice_number": "Z"})
    assert set(out.keys()) == set(FIELDS)
    assert out["invoice_number"] == "Z"
    assert "foobar" not in out


def test_validate_and_repair_none_and_non_dict_input() -> None:
    """None / non-Mapping input → all-None 19-key dict (no crash)."""
    for bad in (None, ["a", "b"], "string", 42):
        out = validate_and_repair(bad)  # type: ignore[arg-type]
        assert set(out.keys()) == set(FIELDS)
        assert all(v is None for v in out.values())


# ===========================================================================
# 5. RATE scoring dispatch (scorer end-to-end)
# ===========================================================================


def _gt_with_tax_rate(rate_norm: str) -> GroundTruth:
    """Build an all-absent GroundTruth with only tax_rate present_content."""
    header: dict[str, GroundTruthField] = {}
    for key, spec in FIELDS.items():
        if key == "tax_rate":
            header[key] = GroundTruthField(
                bt_code=spec.bt_code,
                raw_value=rate_norm,
                normalized_value=rate_norm,
                xpath=spec.xpath,
                is_present=True,
            )
        else:
            header[key] = GroundTruthField(
                bt_code=spec.bt_code,
                raw_value=None,
                normalized_value=None,
                xpath=spec.xpath,
                is_present=False,
            )
    return GroundTruth(header=header)


def test_rate_scoring_true_positive_across_locale() -> None:
    """Predicted '19 %' scores TP against GT '19' (numeric normalization on both sides)."""
    gt = _gt_with_tax_rate("19")
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    predicted["tax_rate"] = "19 %"
    result = score(predicted, gt, cfg=EvalConfig())
    assert result.per_field["tax_rate"].outcome == "TP"


def test_rate_scoring_false_negative_on_mismatch() -> None:
    """Predicted '7%' scores FN against GT '19'."""
    gt = _gt_with_tax_rate("19")
    predicted: dict[str, str | None] = {key: None for key in FIELDS}
    predicted["tax_rate"] = "7%"
    result = score(predicted, gt, cfg=EvalConfig())
    assert result.per_field["tax_rate"].outcome == "FN"


# ===========================================================================
# 6. ADR-041 Step 1a — full-coverage flat fields (corpus-independent)
# ===========================================================================


def _v2_full_settlement_invoice() -> bytes:
    """A CII v2 invoice exercising every ADR-041 Step 1a flat field."""
    return (
        f"<rsm:CrossIndustryInvoice {_V2_NS}>"
        "<rsm:ExchangedDocument><ram:TypeCode>380</ram:TypeCode></rsm:ExchangedDocument>"
        "<rsm:SupplyChainTradeTransaction>"
        "<ram:ApplicableHeaderTradeAgreement>"
        "<ram:BuyerOrderReferencedDocument>"
        "<ram:IssuerAssignedID>PO-4711</ram:IssuerAssignedID>"
        "</ram:BuyerOrderReferencedDocument>"
        "</ram:ApplicableHeaderTradeAgreement>"
        "<ram:ApplicableHeaderTradeSettlement>"
        "<ram:PaymentReference>RF18-1234</ram:PaymentReference>"
        "<ram:SpecifiedTradeSettlementPaymentMeans>"
        "<ram:TypeCode>58</ram:TypeCode>"
        "<ram:Information>SEPA-Überweisung</ram:Information>"
        "<ram:PayeePartyCreditorFinancialAccount>"
        "<ram:IBANID>DE89370400440532013000</ram:IBANID>"
        "<ram:AccountName>Lieferant GmbH</ram:AccountName>"
        "</ram:PayeePartyCreditorFinancialAccount>"
        "<ram:PayeeSpecifiedCreditorFinancialInstitution>"
        "<ram:BICID>COBADEFFXXX</ram:BICID>"
        "</ram:PayeeSpecifiedCreditorFinancialInstitution>"
        "</ram:SpecifiedTradeSettlementPaymentMeans>"
        "<ram:BillingSpecifiedPeriod>"
        "<ram:StartDateTime><udt:DateTimeString>20240101</udt:DateTimeString></ram:StartDateTime>"
        "<ram:EndDateTime><udt:DateTimeString>20240131</udt:DateTimeString></ram:EndDateTime>"
        "</ram:BillingSpecifiedPeriod>"
        "<ram:SpecifiedTradePaymentTerms>"
        "<ram:DueDateDateTime><udt:DateTimeString>20240215</udt:DateTimeString></ram:DueDateDateTime>"
        "</ram:SpecifiedTradePaymentTerms>"
        "<ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
        "<ram:AllowanceTotalAmount>10.00</ram:AllowanceTotalAmount>"
        "<ram:ChargeTotalAmount>5.00</ram:ChargeTotalAmount>"
        "<ram:RoundingAmount>0.01</ram:RoundingAmount>"
        "<ram:TotalPrepaidAmount>100.00</ram:TotalPrepaidAmount>"
        "</ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
        "</ram:ApplicableHeaderTradeSettlement>"
        "</rsm:SupplyChainTradeTransaction>"
        "</rsm:CrossIndustryInvoice>"
    ).encode()


def test_parse_adr041_flat_fields() -> None:
    """Every ADR-041 Step 1a flat field parses + normalizes from a synthetic CII."""
    h = parse_cii_xml(_v2_full_settlement_invoice()).header
    expected = {
        "document_type": "invoice",  # BT-3 code 380 → token
        "buyer_order_reference": "PO-4711",
        "payment_reference": "RF18-1234",
        "payment_means_code": "58",
        "payment_means_text": "SEPA-Überweisung",
        "seller_iban": "DE89370400440532013000",
        "seller_bic": "COBADEFFXXX",
        "seller_account_name": "Lieferant GmbH",
        "billing_period_start": "2024-01-01",
        "billing_period_end": "2024-01-31",
        "payment_due_date": "2024-02-15",
        "allowance_total_amount": "10.00",
        "charge_total_amount": "5.00",
        "rounding_amount": "0.01",
        "prepaid_amount": "100.00",
    }
    for key, value in expected.items():
        assert h[key].is_present, f"{key} should be present"
        assert h[key].normalized_value == value, (
            f"{key}: expected {value!r}, got {h[key].normalized_value!r}"
        )


@pytest.mark.parametrize(
    ("code", "token"),
    [("380", "invoice"), ("389", "invoice"), ("381", "credit_note"), ("384", "correction")],
)
def test_document_type_code_maps_to_token(code: str, token: str) -> None:
    """BT-3 UNTDID-1001 codes map to canonical HORUS document-type tokens."""
    xml = (
        f"<rsm:CrossIndustryInvoice {_V2_NS}>"
        f"<rsm:ExchangedDocument><ram:TypeCode>{code}</ram:TypeCode></rsm:ExchangedDocument>"
        "<rsm:SupplyChainTradeTransaction></rsm:SupplyChainTradeTransaction>"
        "</rsm:CrossIndustryInvoice>"
    ).encode()
    gt = parse_cii_xml(xml)
    assert gt.header["document_type"].normalized_value == token


def test_adr041_fields_absent_are_honest_null() -> None:
    """Absent ADR-041 fields → is_present=False, normalized None (honest null)."""
    gt = parse_cii_xml(_v2_invoice())
    for key in ("seller_iban", "payment_due_date", "prepaid_amount", "document_type"):
        assert gt.header[key].is_present is False
        assert gt.header[key].normalized_value is None


def test_validate_and_repair_adr041_locale_coercion() -> None:
    """Prediction-side coercion of the new fields (German money, spaced IBAN, DE date)."""
    out = validate_and_repair(
        {
            "seller_iban": "DE89 3704 0044 0532 0130 00",
            "prepaid_amount": "100,00",
            "payment_due_date": "15.02.2024",
            "document_type": "invoice",
        }
    )
    assert out["seller_iban"] == "DE89370400440532013000"
    assert out["prepaid_amount"] == "100.00"
    assert out["payment_due_date"] == "2024-02-15"
    assert out["document_type"] == "invoice"


# ===========================================================================
# 7. ADR-041 Step 1b — repeating groups (VAT breakdown + Skonto), GT side
# ===========================================================================


def test_parse_vat_breakdown_multi_rate() -> None:
    """A 19% + 7% invoice yields a 2-row vat_breakdown with per-row cells parsed."""
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:CalculatedAmount>19.00</ram:CalculatedAmount>"
        "<ram:BasisAmount>100.00</ram:BasisAmount>"
        "<ram:CategoryCode>S</ram:CategoryCode>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
        "<ram:ApplicableTradeTax>"
        "<ram:CalculatedAmount>3.50</ram:CalculatedAmount>"
        "<ram:BasisAmount>50.00</ram:BasisAmount>"
        "<ram:CategoryCode>S</ram:CategoryCode>"
        "<ram:RateApplicablePercent>7.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    assert gt.vat_breakdown is not None
    assert len(gt.vat_breakdown) == 2
    r0, r1 = gt.vat_breakdown
    assert r0["rate_percent"].normalized_value == "19"
    assert r0["taxable_amount"].normalized_value == "100.00"
    assert r0["tax_amount"].normalized_value == "19.00"
    assert r0["category_code"].normalized_value == "S"
    assert r1["rate_percent"].normalized_value == "7"
    assert r1["tax_amount"].normalized_value == "3.50"
    # ADR-045: with two distinct header rates the flat tax_rate is EXCLUDED
    # (is_present=True, normalized_value=None); the per-rate truth is the
    # vat_breakdown rows above.
    assert gt.header["tax_rate"].is_present is True
    assert gt.header["tax_rate"].normalized_value is None


def test_parse_skonto_from_discount_terms() -> None:
    """Structured Skonto (ApplicableTradePaymentDiscountTerms) parses to one tier."""
    settlement = (
        "<ram:SpecifiedTradePaymentTerms>"
        "<ram:ApplicableTradePaymentDiscountTerms>"
        "<ram:BasisPeriodMeasure>14</ram:BasisPeriodMeasure>"
        "<ram:BasisAmount>119.00</ram:BasisAmount>"
        "<ram:CalculationPercent>2.00</ram:CalculationPercent>"
        "</ram:ApplicableTradePaymentDiscountTerms>"
        "</ram:SpecifiedTradePaymentTerms>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=settlement))
    assert gt.skonto is not None
    assert len(gt.skonto) == 1
    assert gt.skonto[0]["percent"].normalized_value == "2"
    assert gt.skonto[0]["days"].normalized_value == "14"
    assert gt.skonto[0]["basis_amount"].normalized_value == "119.00"


def test_repeating_groups_absent_are_none() -> None:
    """Absent repeating groups → None (honest null); line_items reserved for Step 2."""
    gt = parse_cii_xml(_v2_invoice())
    assert gt.vat_breakdown is None
    assert gt.skonto is None
    assert gt.line_items is None


def test_invoice_fields_coerces_repeating_groups() -> None:
    """The structurer's nested vat_breakdown / skonto rows are locale-coerced per cell."""
    model = InvoiceFields.model_validate(
        {
            "vat_breakdown": [
                {
                    "rate_percent": "19 %",
                    "taxable_amount": "100,00",
                    "tax_amount": "19,00",
                    "category_code": "S",
                },
                {"rate_percent": "7%", "taxable_amount": "50,00", "tax_amount": "3,50"},
            ],
            "skonto": [{"percent": "2,00", "days": "14", "basis_amount": "119,00"}],
        }
    )
    full = model.to_full_dict()
    assert full["vat_breakdown"][0]["rate_percent"] == "19"
    assert full["vat_breakdown"][0]["taxable_amount"] == "100.00"
    assert full["vat_breakdown"][1]["rate_percent"] == "7"
    assert full["skonto"][0]["percent"] == "2"
    assert full["skonto"][0]["basis_amount"] == "119.00"
    # Repeating groups are NOT part of the flat scored dict (scored via ADR-042).
    assert "vat_breakdown" not in model.to_scored_dict()
    assert "skonto" not in model.to_scored_dict()


def test_invoice_fields_repeating_absent_is_none() -> None:
    """No repeating-group keys in the input → None (honest absence)."""
    model = InvoiceFields.model_validate({"invoice_number": "X"})
    assert model.vat_breakdown is None
    assert model.skonto is None
    assert model.line_items is None


# ===========================================================================
# 8. ADR-042 Step 2 — line items (BG-25), GT side + prediction side
# ===========================================================================


def _v2_with_lines(lines_xml: str) -> bytes:
    """A CII v2 invoice carrying the given line-item rows under the transaction."""
    return (
        f"<rsm:CrossIndustryInvoice {_V2_NS}>"
        "<rsm:SupplyChainTradeTransaction>"
        f"{lines_xml}"
        "<ram:ApplicableHeaderTradeSettlement></ram:ApplicableHeaderTradeSettlement>"
        "</rsm:SupplyChainTradeTransaction>"
        "</rsm:CrossIndustryInvoice>"
    ).encode()


def test_parse_line_items_multi_row() -> None:
    """A 2-line invoice yields a 2-row line_items list; per-row cells parse + normalize."""
    lines = (
        "<ram:IncludedSupplyChainTradeLineItem>"
        "<ram:AssociatedDocumentLineDocument><ram:LineID>1</ram:LineID>"
        "</ram:AssociatedDocumentLineDocument>"
        "<ram:SpecifiedTradeProduct>"
        "<ram:SellerAssignedID>ART-1</ram:SellerAssignedID>"
        "<ram:Name>Beratungsleistung</ram:Name>"
        "</ram:SpecifiedTradeProduct>"
        "<ram:SpecifiedLineTradeAgreement>"
        "<ram:NetPriceProductTradePrice><ram:ChargeAmount>100.00</ram:ChargeAmount>"
        "</ram:NetPriceProductTradePrice>"
        "</ram:SpecifiedLineTradeAgreement>"
        "<ram:SpecifiedLineTradeDelivery>"
        "<ram:BilledQuantity unitCode='HUR'>2.0000</ram:BilledQuantity>"
        "</ram:SpecifiedLineTradeDelivery>"
        "<ram:SpecifiedLineTradeSettlement>"
        "<ram:ApplicableTradeTax><ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
        "<ram:SpecifiedTradeSettlementLineMonetarySummation>"
        "<ram:LineTotalAmount>200.00</ram:LineTotalAmount>"
        "</ram:SpecifiedTradeSettlementLineMonetarySummation>"
        "</ram:SpecifiedLineTradeSettlement>"
        "</ram:IncludedSupplyChainTradeLineItem>"
        "<ram:IncludedSupplyChainTradeLineItem>"
        "<ram:AssociatedDocumentLineDocument><ram:LineID>2</ram:LineID>"
        "</ram:AssociatedDocumentLineDocument>"
        "<ram:SpecifiedTradeProduct><ram:Name>Material</ram:Name></ram:SpecifiedTradeProduct>"
        "<ram:SpecifiedLineTradeSettlement>"
        "<ram:SpecifiedTradeSettlementLineMonetarySummation>"
        "<ram:LineTotalAmount>50.00</ram:LineTotalAmount>"
        "</ram:SpecifiedTradeSettlementLineMonetarySummation>"
        "</ram:SpecifiedLineTradeSettlement>"
        "</ram:IncludedSupplyChainTradeLineItem>"
    )
    gt = parse_cii_xml(_v2_with_lines(lines))
    assert gt.line_items is not None
    assert len(gt.line_items) == 2
    r0, r1 = gt.line_items
    assert r0["line_id"].normalized_value == "1"
    assert r0["name"].normalized_value == "Beratungsleistung"
    assert r0["seller_assigned_id"].normalized_value == "ART-1"
    assert r0["net_price"].normalized_value == "100.00"
    assert r0["vat_rate"].normalized_value == "19"
    assert r0["line_amount"].normalized_value == "200.00"
    assert r0["quantity"].raw_value == "2.0000"
    assert r0["quantity"].is_present is True
    # Row 2 carries only name + line_amount; the rest are honest-absent.
    assert r1["name"].normalized_value == "Material"
    assert r1["line_amount"].normalized_value == "50.00"
    assert r1["seller_assigned_id"].is_present is False
    assert r1["line_id"].normalized_value == "2"


def test_invoice_fields_coerces_line_items() -> None:
    """The structurer's nested line_items rows are locale-coerced per cell."""
    model = InvoiceFields.model_validate(
        {
            "line_items": [
                {
                    "line_id": "1",
                    "name": "Beratung",
                    "seller_assigned_id": "ART-1",
                    "net_price": "100,00",
                    "quantity": "2",
                    "vat_rate": "19 %",
                    "line_amount": "200,00",
                },
            ],
        }
    )
    full = model.to_full_dict()
    assert full["line_items"][0]["net_price"] == "100.00"
    assert full["line_items"][0]["vat_rate"] == "19"
    assert full["line_items"][0]["line_amount"] == "200.00"
    assert full["line_items"][0]["name"] == "Beratung"
    assert "line_items" not in model.to_scored_dict()


# ===========================================================================
# 9. ADR-046 — document_type code map covers the EN16931 invoice family
# ===========================================================================


@pytest.mark.parametrize(
    ("code", "token"),
    [
        ("380", "invoice"),  # commercial
        ("386", "invoice"),  # prepayment
        ("387", "invoice"),  # hire / rental (the Miete bug)
        ("388", "invoice"),  # tax invoice
        ("389", "invoice"),  # self-billed
        ("393", "invoice"),  # factored
        ("395", "invoice"),  # consignment
        ("381", "credit_note"),
        ("396", "credit_note"),  # factored credit note
        ("384", "correction"),
    ],
)
def test_doctype_invoice_family_maps_to_token(code: str, token: str) -> None:
    """ADR-046: every in-scope UNTDID-1001 invoice-family code maps to its HORUS token."""
    assert _normalize_doctype(code) == token


def test_doctype_unknown_code_passes_through() -> None:
    """An out-of-family code is returned stripped (honest present-but-unmapped, not dropped)."""
    assert _normalize_doctype("751") == "751"


# ===========================================================================
# 10. ADR-047 — free-text payment-terms fallback (due date + Skonto)
# ===========================================================================


def _v2_with_payment_terms(description: str, *, structured_due: str = "") -> bytes:
    """A CII v2 invoice whose settlement carries a free-text payment-terms Description.

    `structured_due` (a ``DueDateDateTime`` fragment) lets a test assert that
    structured data wins over the free-text fallback.
    """
    settlement = (
        "<ram:SpecifiedTradePaymentTerms>"
        f"{structured_due}"
        f"<ram:Description>{description}</ram:Description>"
        "</ram:SpecifiedTradePaymentTerms>"
    )
    return _v2_invoice(tax=settlement)


def test_freetext_due_date_helper() -> None:
    """`netto bis DD.MM.YYYY` → ISO; the Skonto deadline date is never picked."""
    desc = [
        "Zahlbar innerhalb 30 Tagen netto bis 04.04.2018, "
        "3% Skonto innerhalb 10 Tagen bis 15.03.2018"
    ]
    assert _parse_freetext_due_date(desc) == "2018-04-04"


def test_freetext_due_date_helper_no_match_returns_none() -> None:
    """No explicit `netto bis` phrasing → None (conservative; never a guessed GT)."""
    assert _parse_freetext_due_date(["Der Betrag wird gutgeschrieben."]) is None
    assert _parse_freetext_due_date(["Zahlbar bis 04.04.2018"]) is None  # no 'netto'


def test_freetext_due_date_helper_invalid_date_returns_none() -> None:
    """A syntactically-matched but impossible date → None (validated via datetime)."""
    assert _parse_freetext_due_date(["... netto bis 31.02.2018"]) is None


def test_freetext_skonto_helper_single_and_multi_tier() -> None:
    """`X% Skonto innerhalb N Tagen` parses one row per tier; cells normalize."""
    rows = _parse_freetext_skonto(
        ["3% Skonto innerhalb 10 Tagen bis 15.03.2018, 1,5 % Skonto innerhalb 20 Tagen"]
    )
    assert len(rows) == 2
    assert rows[0]["percent"].normalized_value == "3"
    assert rows[0]["days"].normalized_value == "10"
    assert rows[0]["basis_amount"].is_present is False
    assert rows[1]["percent"].normalized_value == "1.5"
    assert rows[1]["days"].normalized_value == "20"


def test_freetext_payment_terms_fill_due_and_skonto_via_parse() -> None:
    """End-to-end: parse_cii_xml fills BT-9 + Skonto from free text when structured is absent."""
    gt = parse_cii_xml(
        _v2_with_payment_terms(
            "Zahlbar innerhalb 30 Tagen netto bis 04.04.2018, "
            "3% Skonto innerhalb 10 Tagen bis 15.03.2018"
        )
    )
    assert gt.header["payment_due_date"].is_present is True
    assert gt.header["payment_due_date"].normalized_value == "2018-04-04"
    assert gt.skonto is not None
    assert len(gt.skonto) == 1
    assert gt.skonto[0]["percent"].normalized_value == "3"
    assert gt.skonto[0]["days"].normalized_value == "10"


def test_structured_due_date_wins_over_freetext() -> None:
    """Structured DueDateDateTime is authoritative; free-text fallback never overrides it."""
    structured = (
        "<ram:DueDateDateTime><udt:DateTimeString format='102'>"
        "20180401</udt:DateTimeString></ram:DueDateDateTime>"
    )
    gt = parse_cii_xml(
        _v2_with_payment_terms(
            "Zahlbar innerhalb 30 Tagen netto bis 04.04.2018",
            structured_due=structured,
        )
    )
    # Structured 2018-04-01 wins over the free-text 2018-04-04.
    assert gt.header["payment_due_date"].normalized_value == "2018-04-01"


def test_freetext_fallback_absent_when_no_payment_terms() -> None:
    """No payment terms at all → due date absent + skonto None (no fabricated GT)."""
    gt = parse_cii_xml(_v2_invoice())
    assert gt.header["payment_due_date"].is_present is False
    assert gt.skonto is None
