---
source_url: "https://github.com/akretion/factur-x"
source_title: "akretion/factur-x — Python lib for Factur-X (the Franco-German e-invoicing standard)"
source_author: "Alexis de Lattre (Akretion)"
source_date: ""
retrieved_date: "2026-05-16"
extracted_concepts: []
tags: ["factur-x", "zugferd", "python-library", "pdf-a-3", "cii-xml", "binder", "extractor", "primary-tooling", "adr-005", "adr-010"]
archived_pdf: ""
status: stub
---

Pure-Python library (BSD) for the **Factur-X** e-invoicing standard (Factur-X = the Franco-German binding name; ZUGFeRD = the German binding name; both reference the same UN/CEFACT CII XML + PDF/A-3 carrier). Maintained by Akretion (FR), the FNFE-MPE-aligned Python reference implementation. PyPI: `factur-x` 4.2 (May 2026 install).

**Role in HORUS (per ADR-005 + ADR-010)** — `factur-x` plays **two complementary roles** in HORUS:

1. **Generator / binder** (ADR-005). Bonds an arbitrary CII XML payload + an arbitrary PDF into a Factur-X-compliant PDF/A-3 via `generate_from_file` / `generate_from_binary`. Used in `scripts/generate_zugferd_smoke.py` for the synthetic-invoice round-trip smoke.

2. **Canonical XML extractor** (ADR-010). Extracts the embedded XML attachment from a Factur-X / ZUGFeRD PDF via `get_xml_from_pdf(pdf_bytes) -> (filename, xml_bytes)`. Used in `scripts/extract_zugferd_xml.py` as the engine that produces pilot #13's XML-grounded F1 ground-truth substrate per ADR-009 Amendment 1. Returns `(False, False)` on PDFs without a recognized attachment (factur-x, order-x, zugferd-invoice, ZUGFeRD-invoice) — the HORUS wrapper treats this as "skip + log warning" per issue #15 acceptance criterion.

Common capabilities used by both roles:
- Built-in XSD validation (`xml_check_xsd`) — ships Factur-X 1.08 XSDs for all 5 standard profiles (`facturx/xsd/facturx-{minimum,basicwl,basic,en16931,extended}/`)
- Built-in Schematron validation (`xml_check_schematron`) — Saxon XSLT engine (`saxonche`) bundled
- Profile autodetection (`get_flavor` returns `factur-x` / `zugferd` / `order-x`; `get_level` returns `minimum` / `basicwl` / `basic` / `en16931` / `extended`)
- Wraps `pypdf` internally (`from pypdf import PdfWriter, PdfReader` at `facturx/facturx.py:34`); HORUS code never calls `pypdf` directly for ZUGFeRD work

**Upstream CLI**: `factur-x` ships `facturx-pdfextractxml` (`facturx/scripts/pdfextractxml.py`, 104 LOC). HORUS wraps it rather than uses it directly because upstream exits **1** on no-attachment cases (issue #15 needs exit **0**); HORUS also adds sidecar-path conventions, an opt-in Mustang cross-check flag, and HORUS code-style alignment with `scripts/validate_zugferd.py`. See ADR-010 §"Why a wrapper, given the upstream CLI exists".

**What it does NOT do**: generate visual PDFs from scratch (binder, not end-to-end). The HORUS pilot generator composes `factur-x` (binder) with `horus.zugferd_render` (visual-PDF renderer, fpdf2-based, ADR-006).

**Cross-tool validation + cross-tool extraction**: see `docs/sources/tools/mustang-project.md` — Mustang is the independent Java reference impl HORUS uses to verify factur-x output. ADR-005 uses Mustang's `--action validate`; ADR-010 uses Mustang's `--action extract` as the opt-in cross-check route. Both routes are byte-identical when extracting the same PDF/A-3 attachment (empirical evidence in ADR-010 §"Empirical evidence" Probe 1).
