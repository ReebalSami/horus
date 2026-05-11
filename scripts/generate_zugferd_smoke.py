"""Smoke generator for ZUGFeRD/Factur-X synthetic invoices (ADR-005 + ADR-006).

Generates ONE Factur-X 1.08 BASIC-profile PDF/A-3 invoice end-to-end:
1. Build a BASIC-profile CII XML (adds IncludedSupplyChainTradeLineItem +
   ApplicableTradeTax to the MINIMUM-profile fields; see ADR-006 §Context)
2. Render a visually-realistic A4 invoice PDF from the same CII XML via
   horus.zugferd_render (fpdf2; ADR-006)
3. Bond XML + PDF into a Factur-X PDF/A-3 via facturx.generate_from_file
4. Run facturx's own XSD + Schematron checks (built-in, ships with library)

Output: data/raw/smoke/invoice-001.pdf (gitignored)

Cross-tool validation against Mustang is the next step — invoke
`scripts/validate_zugferd.py data/raw/smoke/invoice-001.pdf`.

Scope per ADR-005 + ADR-006: smoke verification (1 realistic invoice
round-trip). Bulk generation with parameterised fixture data is deferred to
a follow-up issue alongside the XML-extraction script.

Refs: ADR-005, ADR-006, issue #9, issue #21, brainstorm §8 step 2 follow-up.
"""

from __future__ import annotations

import sys
from pathlib import Path

import facturx
from lxml import etree

from horus.zugferd_render import render_invoice_pdf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "raw" / "smoke"
OUT_PDF = OUT_DIR / "invoice-001.pdf"

# Factur-X 1.08 BASIC-profile CII XML — single source of truth for both the
# visual layer (rendered by render_invoice_pdf) and the structured XML layer
# (embedded as factur-x.xml in the PDF/A-3 output).
#
# BASIC is the smallest Factur-X/ZUGFeRD profile carrying
# IncludedSupplyChainTradeLineItem (MINIMUM does not; see ADR-006 §Context).
# Totals preserved from ADR-005 smoke (100.00 net / 19.00 VAT / 119.00 gross).
#
# XSD element ordering follows Factur-X_1.08_BASIC_RABIE.xsd:
#   SupplyChainTradeTransaction: IncludedSupplyChainTradeLineItem FIRST, then
#   ApplicableHeaderTradeAgreement / Delivery / Settlement.
#   ApplicableHeaderTradeSettlement: InvoiceCurrencyCode → ApplicableTradeTax
#   → SpecifiedTradeSettlementHeaderMonetarySummation (with LineTotalAmount
#   required as first child in BASIC, absent in MINIMUM).
BASIC_CII_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
  xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
  xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:BusinessProcessSpecifiedDocumentContextParameter>
      <ram:ID>A1</ram:ID>
    </ram:BusinessProcessSpecifiedDocumentContextParameter>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>HORUS-SMOKE-001</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260511</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument>
        <ram:LineID>1</ram:LineID>
      </ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct>
        <ram:Name>Beratungsleistung</ram:Name>
      </ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice>
          <ram:ChargeAmount>100.00</ram:ChargeAmount>
        </ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="C62">1.00</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:ApplicableTradeTax>
          <ram:TypeCode>VAT</ram:TypeCode>
          <ram:CategoryCode>S</ram:CategoryCode>
          <ram:RateApplicablePercent>19</ram:RateApplicablePercent>
        </ram:ApplicableTradeTax>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>100.00</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:BuyerReference>HORUS-BUYER-REF-001</ram:BuyerReference>
      <ram:SellerTradeParty>
        <ram:Name>HORUS Test Seller GmbH</ram:Name>
        <ram:PostalTradeAddress>
          <ram:PostcodeCode>20095</ram:PostcodeCode>
          <ram:LineOne>Teststra\xc3\x9fe 1</ram:LineOne>
          <ram:CityName>Hamburg</ram:CityName>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="VA">DE123456789</ram:ID>
        </ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>HORUS Test Buyer GmbH</ram:Name>
        <ram:PostalTradeAddress>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery>
      <ram:ActualDeliverySupplyChainEvent>
        <ram:OccurrenceDateTime>
          <udt:DateTimeString format="102">20260511</udt:DateTimeString>
        </ram:OccurrenceDateTime>
      </ram:ActualDeliverySupplyChainEvent>
    </ram:ApplicableHeaderTradeDelivery>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>19.00</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>100.00</ram:BasisAmount>
        <ram:CategoryCode>S</ram:CategoryCode>
        <ram:RateApplicablePercent>19</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      <ram:SpecifiedTradePaymentTerms>
        <ram:Description>Zahlung sofort faellig</ram:Description>
      </ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>100.00</ram:LineTotalAmount>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">19.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>119.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    visual_pdf = OUT_DIR / "_visual.pdf"
    print(f"[1/3] Rendering visual invoice PDF → {visual_pdf.relative_to(REPO_ROOT)}")
    render_invoice_pdf(BASIC_CII_XML, visual_pdf)

    print(f"[2/3] Bonding CII XML (BASIC profile) + PDF → {OUT_PDF.relative_to(REPO_ROOT)}")
    # check_xsd=True + check_schematron=True is the default; we keep them
    # explicit here as the smoke's primary assertion.
    facturx.generate_from_file(
        pdf_file=str(visual_pdf),
        xml=BASIC_CII_XML,
        flavor="factur-x",
        level="basic",
        check_xsd=True,
        check_schematron=True,
        output_pdf_file=str(OUT_PDF),
    )

    print("[3/3] Round-trip read: extract XML back from the generated PDF")
    pdf_bytes = OUT_PDF.read_bytes()
    extracted_filename, extracted_xml = facturx.get_xml_from_pdf(pdf_bytes)
    extracted_tree = etree.fromstring(extracted_xml)
    flavor = facturx.get_flavor(extracted_tree)
    level = facturx.get_level(extracted_tree)

    print()
    print("=" * 60)
    print("SMOKE GENERATION — facturx self-check evidence")
    print("=" * 60)
    print(f"  Output PDF:         {OUT_PDF.relative_to(REPO_ROOT)}")
    print(f"  Output size:        {OUT_PDF.stat().st_size:,} bytes")
    print(f"  Embedded XML name:  {extracted_filename}")
    print(f"  Embedded XML size:  {len(extracted_xml):,} bytes")
    print(f"  Detected flavor:    {flavor}")
    print(f"  Detected level:     {level}")
    print("  XSD check:          PASS (raised no exception)")
    print("  Schematron check:   PASS (raised no exception)")
    print("  Visual layer:       fpdf2-rendered realistic B2B invoice (ADR-006)")
    print("=" * 60)
    print()
    print(
        "Next step: run `uv run python scripts/validate_zugferd.py "
        f"{OUT_PDF.relative_to(REPO_ROOT)}` for independent Mustang validation."
    )

    # Cleanup intermediate.
    visual_pdf.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
