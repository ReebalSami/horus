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
    _normalize_rate,
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


def test_parse_multi_rate_takes_first_in_document_order() -> None:
    """Multi-rate invoice (two ApplicableTradeTax) → first rate in document order (ADR-035 §A)."""
    tax = (
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
        "<ram:ApplicableTradeTax>"
        "<ram:RateApplicablePercent>7.00</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )
    gt = parse_cii_xml(_v2_invoice(tax=tax))
    assert gt.header["tax_rate"].normalized_value == "19"


def test_parse_header_has_19_keys() -> None:
    """Parsed header always carries all 19 canonical keys (corpus-independent)."""
    gt = parse_cii_xml(_v2_invoice())
    assert set(gt.header.keys()) == set(FIELDS.keys())
    assert len(gt.header) == 19


# ===========================================================================
# 4. InvoiceFields Pydantic model + validate_and_repair (ADR-035)
# ===========================================================================


def test_model_scored_fields_match_registry() -> None:
    """InvoiceFields scored fields (minus purpose_summary) == FIELDS exactly (no drift)."""
    model_fields = set(InvoiceFields.model_fields)
    assert PURPOSE_SUMMARY_KEY in model_fields
    assert model_fields - {PURPOSE_SUMMARY_KEY} == set(FIELDS)


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
