"""Visual PDF renderer for synthetic ZUGFeRD/Factur-X invoices (ADR-006).

Renders a recognisable A4 B2B invoice from a CII XML payload using fpdf2.
The output PDF is a regular PDF (not yet PDF/A-3); facturx.generate_from_file
upgrades it to PDF/A-3 during bonding.

Single public function: render_invoice_pdf(cii_xml, out_path).

The renderer parses the CII XML via lxml (already a transitive dep via factur-x)
and extracts all display fields. Layout: header band → address block (seller left,
buyer right) → line-items table → totals block → footer. All labels are
German to match the HORUS German-B2B invoice framing.

Refs: ADR-006, issue #21, brainstorm §8 step 2 follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from lxml import etree

_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}

_PAGE_W = 210.0
_MARGIN = 15.0
_USABLE_W = _PAGE_W - 2 * _MARGIN
_COL1_X = _MARGIN
_COL1_W = 87.0
_COL2_X = _MARGIN + _COL1_W + 6.0
_COL2_W = _USABLE_W - _COL1_W - 6.0
_LINE_H = 5.5


@dataclass
class _LineView:
    pos: str
    description: str
    qty: str
    unit_code: str
    unit_price: str
    line_total: str
    currency: str


@dataclass
class _InvoiceView:
    invoice_id: str
    date_str: str
    seller_name: str
    seller_addr: list[str]
    seller_vat: str
    buyer_name: str
    buyer_addr: list[str]
    currency: str
    lines: list[_LineView] = field(default_factory=list)
    tax_rate: str = ""
    tax_basis: str = ""
    tax_total: str = ""
    grand_total: str = ""
    due_payable: str = ""
    line_total_sum: str = ""


def _text(el: etree._Element, xpath: str) -> str:
    node = el.find(xpath, _NS)
    return node.text.strip() if node is not None and node.text else ""


def _parse_cii(cii_xml: bytes) -> _InvoiceView:
    """Parse a Factur-X CII XML payload into a display-ready view object."""
    root = etree.fromstring(cii_xml)

    invoice_id = _text(root, "rsm:ExchangedDocument/ram:ID")
    date_raw = _text(root, "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString")
    date_str = (
        f"{date_raw[6:8]}.{date_raw[4:6]}.{date_raw[0:4]}" if len(date_raw) == 8 else date_raw
    )

    txn = root.find("rsm:SupplyChainTradeTransaction", _NS)
    if txn is None:
        raise ValueError("CII XML missing SupplyChainTradeTransaction element")
    agreement = txn.find("ram:ApplicableHeaderTradeAgreement", _NS)
    settlement = txn.find("ram:ApplicableHeaderTradeSettlement", _NS)
    if agreement is None or settlement is None:
        raise ValueError("CII XML missing required trade agreement or settlement elements")

    seller = agreement.find("ram:SellerTradeParty", _NS)
    if seller is None:
        raise ValueError("CII XML missing SellerTradeParty")
    seller_name = _text(seller, "ram:Name")
    seller_vat_el = seller.find("ram:SpecifiedTaxRegistration", _NS)
    seller_vat = _text(seller_vat_el, "ram:ID") if seller_vat_el is not None else ""
    seller_addr: list[str] = []
    s_addr_el = seller.find("ram:PostalTradeAddress", _NS)
    if s_addr_el is not None:
        line1 = _text(s_addr_el, "ram:LineOne")
        postcode = _text(s_addr_el, "ram:PostcodeCode")
        city = _text(s_addr_el, "ram:CityName")
        country = _text(s_addr_el, "ram:CountryID")
        pc_city = f"{postcode} {city}".strip()
        seller_addr = [v for v in (line1, pc_city, country) if v]

    buyer = agreement.find("ram:BuyerTradeParty", _NS)
    if buyer is None:
        raise ValueError("CII XML missing BuyerTradeParty")
    buyer_name = _text(buyer, "ram:Name")
    buyer_addr: list[str] = []
    b_addr_el = buyer.find("ram:PostalTradeAddress", _NS)
    if b_addr_el is not None:
        country = _text(b_addr_el, "ram:CountryID")
        if country:
            buyer_addr.append(country)

    currency = _text(settlement, "ram:InvoiceCurrencyCode")

    lines: list[_LineView] = []
    for li in txn.findall("ram:IncludedSupplyChainTradeLineItem", _NS):
        desc = _text(li, "ram:SpecifiedTradeProduct/ram:Name")
        qty_el = li.find(
            "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity",
            _NS,
        )
        qty = qty_el.text.strip() if qty_el is not None and qty_el.text else ""
        unit_code = qty_el.get("unitCode", "") if qty_el is not None else ""
        unit_price = _text(
            li, "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount"
        )
        line_total = _text(
            li,
            "ram:SpecifiedLineTradeSettlement"
            "/ram:SpecifiedTradeSettlementLineMonetarySummation"
            "/ram:LineTotalAmount",
        )
        lines.append(
            _LineView(str(len(lines) + 1), desc, qty, unit_code, unit_price, line_total, currency)
        )

    tax_el = settlement.find("ram:ApplicableTradeTax", _NS)
    tax_rate = _text(tax_el, "ram:RateApplicablePercent") if tax_el is not None else ""
    tax_total_val = _text(tax_el, "ram:CalculatedAmount") if tax_el is not None else ""

    summ = settlement.find("ram:SpecifiedTradeSettlementHeaderMonetarySummation", _NS)
    if summ is None:
        raise ValueError("CII XML missing SpecifiedTradeSettlementHeaderMonetarySummation")
    line_total_sum = _text(summ, "ram:LineTotalAmount")
    tax_basis = _text(summ, "ram:TaxBasisTotalAmount")
    grand_total = _text(summ, "ram:GrandTotalAmount")
    due_payable = _text(summ, "ram:DuePayableAmount")
    tax_total_node = summ.find("ram:TaxTotalAmount", _NS)
    tax_total = (
        tax_total_node.text.strip()
        if tax_total_node is not None and tax_total_node.text
        else tax_total_val
    )

    return _InvoiceView(
        invoice_id=invoice_id,
        date_str=date_str,
        seller_name=seller_name,
        seller_addr=seller_addr,
        seller_vat=seller_vat,
        buyer_name=buyer_name,
        buyer_addr=buyer_addr,
        currency=currency,
        lines=lines,
        tax_rate=tax_rate,
        tax_basis=tax_basis,
        tax_total=tax_total,
        grand_total=grand_total,
        due_payable=due_payable,
        line_total_sum=line_total_sum,
    )


def _fmt_amount(value: str, currency: str) -> str:
    try:
        return f"{float(value):,.2f} {currency}"
    except ValueError:
        return f"{value} {currency}"


def _draw_header(pdf: FPDF, view: _InvoiceView) -> None:
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(_USABLE_W * 0.6, 10, "RECHNUNG", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        _USABLE_W * 0.4,
        10,
        f"Nr. {view.invoice_id}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="R",
    )
    pdf.set_x(_MARGIN)
    pdf.cell(
        _USABLE_W,
        6,
        f"Datum: {view.date_str}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="R",
    )
    pdf.ln(2)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(_MARGIN, pdf.get_y(), _PAGE_W - _MARGIN, pdf.get_y())
    pdf.ln(5)


def _draw_address_block(pdf: FPDF, view: _InvoiceView) -> None:
    addr_start_y = pdf.get_y()
    row_h = _LINE_H

    seller_lines = [view.seller_name] + view.seller_addr
    if view.seller_vat:
        seller_lines.append(f"USt-ID: {view.seller_vat}")
    buyer_lines = [view.buyer_name] + view.buyer_addr

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_xy(_COL1_X, addr_start_y)
    pdf.cell(_COL1_W, row_h, "LIEFERANT", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_xy(_COL2_X, addr_start_y)
    pdf.cell(_COL2_W, row_h, "RECHNUNGSEMPF\u00c4NGER", new_x=XPos.RIGHT, new_y=YPos.TOP)

    pdf.set_font("Helvetica", "", 9)
    for i, line in enumerate(seller_lines, start=1):
        pdf.set_xy(_COL1_X, addr_start_y + i * row_h)
        pdf.cell(_COL1_W, row_h, line, new_x=XPos.RIGHT, new_y=YPos.TOP)

    for i, line in enumerate(buyer_lines, start=1):
        pdf.set_xy(_COL2_X, addr_start_y + i * row_h)
        pdf.cell(_COL2_W, row_h, line, new_x=XPos.RIGHT, new_y=YPos.TOP)

    max_rows = max(len(seller_lines), len(buyer_lines)) + 1
    pdf.set_y(addr_start_y + max_rows * row_h)


def _draw_line_items_table(pdf: FPDF, view: _InvoiceView) -> None:
    col_widths = (12, 80, 18, 16, 27, 27)
    headers = ("Pos.", "Bezeichnung", "Menge", "Einheit", "Einzelpreis", "Gesamt")
    headings_style = FontFace(emphasis="BOLD", color=(0, 0, 0))
    with pdf.table(
        col_widths=col_widths,
        line_height=6,
        borders_layout="SINGLE_TOP_LINE",
        headings_style=headings_style,
        text_align=("CENTER", "LEFT", "RIGHT", "LEFT", "RIGHT", "RIGHT"),
    ) as t:
        hr = t.row()
        for h in headers:
            hr.cell(h)
        for li in view.lines:
            dr = t.row()
            dr.cell(li.pos)
            dr.cell(li.description)
            dr.cell(_fmt_qty(li.qty))
            dr.cell(li.unit_code)
            dr.cell(_fmt_amount(li.unit_price, li.currency))
            dr.cell(_fmt_amount(li.line_total, li.currency))


def _fmt_qty(qty: str) -> str:
    try:
        return f"{float(qty):g}"
    except ValueError:
        return qty


def _draw_totals(pdf: FPDF, view: _InvoiceView) -> None:
    label_w = _USABLE_W * 0.65
    value_w = _USABLE_W * 0.35
    lh = 7.0

    rows = [
        ("Zwischensumme (netto):", _fmt_amount(view.tax_basis, view.currency)),
        (f"USt. {view.tax_rate}\u00a0%:", _fmt_amount(view.tax_total, view.currency)),
        ("Bruttosumme:", _fmt_amount(view.grand_total, view.currency)),
        ("Zahlbar:", _fmt_amount(view.due_payable, view.currency)),
    ]
    pdf.set_font("Helvetica", "", 9)
    for i, (label, value) in enumerate(rows):
        if i == len(rows) - 1:
            pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(_MARGIN)
        pdf.cell(label_w, lh, label, new_x=XPos.RIGHT, new_y=YPos.TOP, align="R")
        pdf.cell(value_w, lh, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")


def _draw_footer(pdf: FPDF) -> None:
    pdf.set_y(-20)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(_MARGIN, pdf.get_y(), _PAGE_W - _MARGIN, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Generiert von HORUS - Synthetic ZUGFeRD invoice (ADR-006)", align="C")
    pdf.set_text_color(0, 0, 0)


def render_invoice_pdf(cii_xml: bytes, out_path: Path) -> None:
    """Render a Factur-X CII XML payload to a visual A4 invoice PDF.

    Parses the CII XML, extracts display fields (seller/buyer/ID/date/line
    items/totals), and lays them out on a single A4 page via fpdf2.

    The output is a regular PDF (not yet PDF/A-3). Pass the result to
    facturx.generate_from_file to upgrade to PDF/A-3 during bonding.

    Args:
        cii_xml: Raw bytes of the CII XML payload (any Factur-X profile).
        out_path: Destination path for the rendered PDF.
    """
    view = _parse_cii(cii_xml)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=_MARGIN, top=_MARGIN, right=_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    _draw_header(pdf, view)
    _draw_address_block(pdf, view)
    pdf.ln(8)
    _draw_line_items_table(pdf, view)
    pdf.ln(5)
    _draw_totals(pdf, view)
    _draw_footer(pdf)

    pdf.output(str(out_path))
