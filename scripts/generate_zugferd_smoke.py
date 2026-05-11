"""Smoke generator for ZUGFeRD/Factur-X synthetic invoices (ADR-005).

Generates ONE Factur-X 1.08 MINIMUM-profile PDF/A-3 invoice end-to-end:
1. Build a minimal CII XML (BT-1..BT-115 mandatory fields for MINIMUM profile)
2. Create a blank visual PDF via pypdf
3. Bond XML + PDF into a Factur-X PDF/A-3 via facturx.generate_from_file
4. Run facturx's own XSD + Schematron checks (built-in, ships with library)

Output: data/raw/smoke/invoice-001.pdf (gitignored)

Cross-tool validation against Mustang is the next step — invoke
`scripts/validate_zugferd.py data/raw/smoke/invoice-001.pdf`.

Scope per ADR-005: smoke verification (1 invoice round-trip). Bulk
generation with parameterised fixture data is deferred to a follow-up
issue alongside the XML-extraction script.

Refs: ADR-005, issue #9, brainstorm §8 step 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

import facturx
from lxml import etree
from pypdf import PdfWriter

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "raw" / "smoke"
OUT_PDF = OUT_DIR / "invoice-001.pdf"

# Minimal Factur-X 1.08 MINIMUM-profile CII XML.
# This is the smallest schema-valid Factur-X invoice payload — used purely
# to prove the toolchain (generator + binder + validator) works end-to-end.
# Pilot-scale invoices will use EN16931 profile via parameterised builders
# in a follow-up issue. MINIMUM profile is intended for B2C reduced reporting;
# it carries fewer line-item details but is still XSD + Schematron valid.
MINIMUM_CII_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
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
      <ram:ID>urn:factur-x.eu:1p0:minimum</ram:ID>
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
    <ram:ApplicableHeaderTradeAgreement>
      <ram:BuyerReference>HORUS-BUYER-REF-001</ram:BuyerReference>
      <ram:SellerTradeParty>
        <ram:Name>HORUS Test Seller GmbH</ram:Name>
        <ram:PostalTradeAddress>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="VA">DE123456789</ram:ID>
        </ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>HORUS Test Buyer GmbH</ram:Name>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">19.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>119.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""


def make_blank_pdf(path: Path) -> None:
    """Create a minimal single-page A4 PDF.

    factur-x will upgrade this to PDF/A-3 during bonding. A blank page is
    intentional for smoke — the visual layer is irrelevant; the structured
    XML payload is what HORUS evaluates against.
    """
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)  # A4 (210 x 297 mm in points)
    with path.open("wb") as fh:
        writer.write(fh)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    blank_pdf = OUT_DIR / "_blank.pdf"
    print(f"[1/3] Creating blank visual PDF → {blank_pdf.relative_to(REPO_ROOT)}")
    make_blank_pdf(blank_pdf)

    print(f"[2/3] Bonding CII XML (MINIMUM profile) + PDF → {OUT_PDF.relative_to(REPO_ROOT)}")
    # check_xsd=True + check_schematron=True is the default; we keep them
    # explicit here as the smoke's primary assertion.
    facturx.generate_from_file(
        pdf_file=str(blank_pdf),
        xml=MINIMUM_CII_XML,
        flavor="factur-x",
        level="minimum",
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
    print("=" * 60)
    print()
    print(
        "Next step: run `uv run python scripts/validate_zugferd.py "
        f"{OUT_PDF.relative_to(REPO_ROOT)}` for independent Mustang validation."
    )

    # Cleanup intermediate.
    blank_pdf.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
