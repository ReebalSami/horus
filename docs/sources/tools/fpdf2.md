---
source_url: "https://github.com/py-pdf/fpdf2"
source_title: "py-pdf/fpdf2 — Simple & fast PDF generation library for Python"
source_author: "py-pdf community (successor of PyFPDF)"
source_date: ""
retrieved_date: "2026-05-11"
extracted_concepts: []
tags: ["fpdf2", "pdf-generation", "python-library", "tabular-invoice", "py-pdf-ecosystem", "primary-tooling", "adr-006"]
archived_pdf: ""
status: stub
---

Pure-Python library (LGPL-3.0+) for generating PDF documents programmatically. Successor of PyFPDF; maintained by the `py-pdf` community organization (same org as `pypdf`, which HORUS already pulls transitively via `factur-x`). PyPI: `fpdf2 2.8.7` (2026-02-28). Wheel: `py3-none-any` (no compiled extensions; ARM64-native on any platform). Python ≥ 3.10 required; HORUS ≥ 3.14 satisfies.

**Runtime dependencies**: `Pillow` (image handling), `defusedxml` (XML parsing), `fonttools` (font subsetting). All permissively licensed (LGPL/MIT/BSD).

**Role in HORUS (per ADR-006)**: the **visual PDF renderer** in the synthetic-invoice toolchain. Renders a recognisable A4 B2B invoice (seller/buyer/ID/date/line items/totals) from a parsed CII XML payload, producing a regular PDF that `factur-x.generate_from_file` then upgrades to PDF/A-3 during bonding. Chosen over ReportLab on: py-pdf org consistency with the existing `pypdf` transitive dep; cleaner `with pdf.table()` context-manager API for tabular invoices; purpose-built `Templates` system for upcoming bulk-pilot generation; native German-language tutorial + Unicode-first design for HORUS's German-B2B framing.

**Key API entry points**:
- `fpdf.FPDF(orientation="P", unit="mm", format="A4")` — instantiate A4 portrait canvas
- `pdf.add_page()` — begin page
- `pdf.set_font("Helvetica", "B", size)` — built-in font, no font-file shipping needed; Latin-1 + UTF-8 including German umlauts
- `with pdf.table(borders_layout=..., col_widths=..., headings_style=...) as t:` — context manager table layout with per-row `row = t.row(); row.cell(text)` API
- `pdf.cell(w, h, text, align="R")` / `pdf.multi_cell(w, h, text)` — block-level content placement
- `pdf.output(path)` — write to file (emits valid `/ID` trailer per PDF spec)

**Supersession path**: if LGPL-3.0+ obligations become material for HORUS (public commercial distribution), swap to ReportLab (BSD-3, `docs/sources/tools/reportlab.md`). If fpdf2 maintenance lapses (≥ 2 years, no releases), same fallback. Both triggers captured in ADR-006 §5.

**PyPI**: https://pypi.org/project/fpdf2/ | **Docs**: https://py-pdf.github.io/fpdf2/ | **Tutorial (DE)**: https://py-pdf.github.io/fpdf2/Tutorial-de.html
