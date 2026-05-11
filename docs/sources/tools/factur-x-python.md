---
source_url: "https://github.com/akretion/factur-x"
source_title: "akretion/factur-x — Python lib for Factur-X (the Franco-German e-invoicing standard)"
source_author: "Alexis de Lattre (Akretion)"
source_date: ""
retrieved_date: "2026-05-11"
extracted_concepts: []
tags: ["factur-x", "zugferd", "python-library", "pdf-a-3", "cii-xml", "binder", "primary-tooling", "adr-005"]
archived_pdf: ""
status: stub
---

Pure-Python library (BSD) for the **Factur-X** e-invoicing standard (Factur-X = the Franco-German binding name; ZUGFeRD = the German binding name; both reference the same UN/CEFACT CII XML + PDF/A-3 carrier). Maintained by Akretion (FR), the FNFE-MPE-aligned Python reference implementation. PyPI: `factur-x` 4.2 (May 2026 install).

**Role in HORUS (per ADR-005)**: the **generator (binder)** in the dual-track synthetic-invoice toolchain. Bonds an arbitrary CII XML payload + an arbitrary PDF into a Factur-X-compliant PDF/A-3 via `generate_from_file` / `generate_from_binary`. Built-in XSD + Schematron validation (`xml_check_xsd`, `xml_check_schematron`); ships Factur-X 1.08 XSDs for all 5 standard profiles (`facturx/xsd/facturx-{minimum,basicwl,basic,en16931,extended}/`). Round-trip extraction via `get_xml_from_pdf` + `get_flavor` / `get_level`. Saxon XSLT engine (`saxonche`) bundled for Schematron evaluation.

**What it does NOT do**: generate visual PDFs from scratch (binder, not end-to-end). The HORUS pilot generator will compose `factur-x` with a separate CII-XML builder + a visual-PDF generator (decision deferred to the next ADR per ADR-005 §"What this ADR does NOT decide").

**Cross-tool validation**: see `docs/sources/tools/mustang-project.md` — Mustang is the independent Java validator HORUS uses to verify factur-x output. See ADR-005 for the dual-track rationale + smoke evidence.
