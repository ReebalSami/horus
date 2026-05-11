"""Tests for horus.zugferd_render — visual PDF renderer for ZUGFeRD invoices.

Covers:
1. CII XML parser extracts expected fields from the BASIC literal.
2. Rendered PDF is a valid PDF file (magic bytes, size, page count).
3. Rendered PDF emits a /ID trailer entry — regression for ADR-005 honest caveat.
4. Rendered PDF text contains all AC-required visible fields.

Uses BASIC_CII_XML from scripts.generate_zugferd_smoke as the single source
of truth; all tests use tmp_path for output paths.

Refs: ADR-006, issue #21.
"""

from __future__ import annotations

from pathlib import Path

import pypdf


def _xml() -> bytes:
    from scripts.generate_zugferd_smoke import BASIC_CII_XML  # noqa: PLC0415

    return BASIC_CII_XML


def test_parse_cii_extracts_invoice_view() -> None:
    """_parse_cii correctly extracts all display fields from the BASIC literal."""
    from horus.zugferd_render import _parse_cii  # noqa: PLC0415

    view = _parse_cii(_xml())

    assert view.invoice_id == "HORUS-SMOKE-001"
    assert view.date_str == "11.05.2026"
    assert view.seller_name == "HORUS Test Seller GmbH"
    assert any("Hamburg" in line for line in view.seller_addr), (
        f"Expected Hamburg in seller_addr, got {view.seller_addr}"
    )
    assert view.seller_vat == "DE123456789"
    assert view.buyer_name == "HORUS Test Buyer GmbH"
    assert view.currency == "EUR"
    assert len(view.lines) >= 1, "Expected at least one line item"
    assert view.lines[0].description == "Beratungsleistung"
    assert view.grand_total == "119.00"
    assert view.due_payable == "119.00"


def test_render_invoice_pdf_writes_valid_pdf(tmp_path: Path) -> None:
    """render_invoice_pdf writes a valid single-page A4 PDF."""
    from horus.zugferd_render import render_invoice_pdf  # noqa: PLC0415

    out = tmp_path / "invoice.pdf"
    render_invoice_pdf(_xml(), out)

    assert out.exists(), "Output PDF was not created"
    data = out.read_bytes()
    assert data[:5] == b"%PDF-", f"Expected PDF magic bytes, got {data[:8]!r}"
    assert out.stat().st_size > 1_000, (
        f"PDF is suspiciously small ({out.stat().st_size} bytes); likely empty render"
    )
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) >= 1, f"Expected at least 1 page, got {len(reader.pages)}"


def test_render_invoice_pdf_emits_id_trailer(tmp_path: Path) -> None:
    """Rendered PDF has a non-empty /ID trailer entry.

    Regression test for ADR-005 'Honest caveat: PDF/A-3 trailer ID' — the blank
    pypdf.PdfWriter PDF was missing /ID. fpdf2's PDF emitter follows the PDF spec
    and populates /ID, closing the caveat (pre-bonding; post-bonding Mustang
    evidence is captured in ADR-006 §3 after make zugferd-smoke).
    """
    from horus.zugferd_render import render_invoice_pdf  # noqa: PLC0415

    out = tmp_path / "invoice.pdf"
    render_invoice_pdf(_xml(), out)

    reader = pypdf.PdfReader(str(out))
    trailer = reader.trailer
    assert "/ID" in trailer, (
        "PDF trailer missing /ID entry — ADR-005 caveat not closed; "
        f"trailer keys: {list(trailer.keys())}"
    )


def test_render_invoice_pdf_contains_required_fields(tmp_path: Path) -> None:
    """Rendered PDF text contains all AC-required visible fields.

    Issue #21 AC #2: visual layer shows seller name, buyer name, invoice ID,
    date, line item description, grand total amount, currency.
    """
    from horus.zugferd_render import render_invoice_pdf  # noqa: PLC0415

    out = tmp_path / "invoice.pdf"
    render_invoice_pdf(_xml(), out)

    reader = pypdf.PdfReader(str(out))
    page_text = reader.pages[0].extract_text() or ""

    required = {
        "seller name": "HORUS Test Seller GmbH",
        "buyer name": "HORUS Test Buyer GmbH",
        "invoice ID": "HORUS-SMOKE-001",
        "issue date": "11.05.2026",
        "line item description": "Beratungsleistung",
        "grand total": "119",
        "currency": "EUR",
    }
    missing = {label: value for label, value in required.items() if value not in page_text}
    assert not missing, (
        "Required fields missing from rendered PDF text:\n"
        + "\n".join(f"  {label}: {value!r}" for label, value in missing.items())
        + f"\n\nFull page text:\n{page_text}"
    )
