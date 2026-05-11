# ADR-006 — Visual PDF renderer for synthetic ZUGFeRD invoices: fpdf2 (py-pdf ecosystem)

| Field | Value |
|---|---|
| **Status** | Accepted (smoke evidence captured 2026-05-11) |
| **Date** | 2026-05-11 |
| **Milestone** | M2D.5 step 2 visual-realism follow-up — issue #21 |
| **Authored by** | Cascade D (M2D.5 session, plan `~/.windsurf/plans/issue-21-visual-pdf-realism-7a0bb9.md`) |
| **Issue** | `ReebalSami/horus#21` |
| **Supersession trigger** | (a) fpdf2 lapses maintenance (no release ≥ 2 years AND issue tracker stalls) → fallback = ReportLab (BSD-3; `docs/sources/tools/reportlab.md`); OR (b) HORUS distribution context shifts to public commercial release (LGPL-3.0+ obligations on fpdf2 modifications become material) → fallback = ReportLab; OR (c) thesis adopts a per-locale HTML/CSS templated-design workflow requiring visual richness beyond fpdf2's canvas → fallback = WeasyPrint (`docs/sources/tools/weasyprint.md`, with `brew install pango` system-deps install captured under `tools/`); OR (d) rendered output proves visually inadequate for VLM evaluation at M2D.6+ and a richer template engine is required. |

## Context

ADR-005's smoke generator (`scripts/generate_zugferd_smoke.py`) produces a Factur-X PDF/A-3 invoice with a blank visual layer — a `pypdf.PdfWriter` blank page plus the embedded CII XML payload. This was explicitly scoped as "smoke-only" in ADR-005 §"What this ADR does NOT decide":

> **PDF visual realism.** Blank A4 vs. ReportLab-rendered invoice-looking PDF vs. HTML+WeasyPrint. Walked at the pilot-generator ADR if VLM evaluation requires non-blank inputs (likely it does — Granite-Docling looks at pixels).

The thesis evaluates VLMs on recognisable invoice documents. Blank white PDFs are not invoices — they lack the structured visual context (seller/buyer header blocks, line-item table, totals column) that VLMs use to locate extraction targets. Issue #21 acceptance criterion: produce a realistic-looking B2B invoice whose visual layer is rendered from the **same CII XML used for the structured layer** (single source of truth; no hand-drawn layout data not in the XML).

An additional constraint surfaced at planning: the MINIMUM-profile CII XML used in ADR-005 does not carry `IncludedSupplyChainTradeLineItem` (MINIMUM only covers header-level totals). Rendering a believable invoice requires at least one line item, which in turn requires BASIC profile (the smallest Factur-X/ZUGFeRD profile with `IncludedSupplyChainTradeLineItem`). The MINIMUM → BASIC upgrade is a clean XML-literal change that keeps the dual-track toolchain intact (Mustang validates BASIC via `FACTUR-X_BASIC.xslt`); EN16931 is not required here (deferred to bulk pilot per issue #15).

## Current-state survey (2026-05-11)

Survey methodology: PyPI JSON API query for version/license/release-date/deps + web-survey of 2025–2026 PDF-library comparison articles (analyticsinsight.net, nutrient.io, templated.io, docupotion.com, pdfnoodle.com) + `context7` MCP query `/py-pdf/fpdf2` for API confirmation + GitHub README for borb/weasyprint license and system-dep requirements.

| Library | Latest | Released | License | Runtime deps | Wheel | Notes |
|---|---|---|---|---|---|---|
| **fpdf2** | 2.8.7 | 2026-02-28 | LGPL-3.0+ | Pillow, defusedxml, fonttools | `py3-none-any` | py-pdf org; 1300+ unit tests; qpdf-validated; German tutorial; Templates system |
| ReportLab | 4.5.0 | 2026-04-29 | BSD-3-Clause | Pillow, charset-normalizer | `py3-none-any` | Since 2000; "best for financial/precise layouts" per 3 comparison articles; Platypus framework |
| WeasyPrint | 68.1 | 2026-02-06 | BSD-3-Clause | + Pango + Cairo + GLib via Homebrew | `py3-none-any` (Python) | HTML/CSS → PDF; thesis-pedagogically clear; system-deps fragile on macOS |
| borb | 3.0.x | active | **AGPL-3.0** + commercial | — | — | License-poison for linking; eliminated |
| pikepdf | — | — | MPL-2.0 | qpdf C lib | binary | Wrong tool — modifies existing PDFs, not generation from scratch |
| pylatex / LaTeX | — | — | MIT + full-TeX | multi-GB TeX install | — | Eliminated — install footprint vs `know-your-hardware` |
| pdfme | — | — | varies | JS-first | — | Python port unmaintained; eliminated |

All three viable candidates (fpdf2, ReportLab, WeasyPrint) support Python ≥ 3.14 and ARM64 macOS (both fpdf2 and ReportLab ship `py3-none-any` wheels in their 2026 releases; WeasyPrint's Python wheel is `py3-none-any` but requires system libs separately).

## Options considered

| Option | Why considered | Outcome |
|---|---|---|
| **fpdf2 2.8.7** (LGPL-3.0+) | py-pdf org consistency with `pypdf` already in deps; modern `with pdf.table()` API; purpose-built Templates system; 1300+ qpdf-validated tests; active 2026 maintenance; German tutorial | **Chosen — see Decision** |
| ReportLab 4.5.0 (BSD-3) | Mature (since 2000); comparison articles call it "best for financial reports and precise layouts"; BSD license is cleanest | **Rejected** — Platypus + Canvas API more verbose than fpdf2 for our 6-field invoice; no py-pdf org consistency; fpdf2's Templates system is a forward advantage for bulk-pilot generation (next issue). BSD license advantage is noted in §5 supersession trigger (b). |
| WeasyPrint 68.1 (BSD-3) | HTML/CSS → PDF is pedagogically clear for thesis defense; active maintenance | **Rejected** — requires Pango + Cairo + GLib via Homebrew; system-deps fragile on macOS; conflicts with `know-your-hardware` rule. No advantage over fpdf2 for a simple tabular invoice. Named fallback in §5 trigger (c). |
| borb (AGPL-3.0) | Pure-Python; Pythonic API | **Rejected** — AGPL-3.0 is license-poison for any project using it as a linked dep without disclosing all source. Eliminated on license grounds alone. |
| pikepdf | Existing dep mentioned in ADR-005 caveat path | **Rejected** — wrong tool: pikepdf modifies existing PDFs; it does not generate visual layout from scratch. |
| pylatex / LaTeX templating | Highest typographic fidelity | **Rejected** — multi-GB TeX install incompatible with `know-your-hardware` (lean local environment). |
| pdfme | Mentioned in peer ZUGFeRD tooling discussions | **Rejected** — Python port unmaintained; JS-first ecosystem. |

## Decision + integration thoughts

**Chosen: fpdf2 2.8.7** (LGPL-3.0+, py-pdf community, PyPI `fpdf2`, imports as `from fpdf import FPDF`).

### Rationale

1. **py-pdf org consistency.** HORUS already pulls `pypdf` transitively via `factur-x`. `fpdf2` is maintained by the same `py-pdf` org — the thesis can present a coherent "we use the py-pdf ecosystem: `pypdf` parses, `fpdf2` generates" narrative. No cross-org maintenance tracking needed.

2. **API ergonomics for tabular invoices.** fpdf2's `with pdf.table(borders_layout="SINGLE_TOP_LINE", headings_style=FontFace(...), col_widths=...) as t:` context-manager produces clean tabular output with minimal boilerplate — vs ReportLab's `Table(data, colWidths=[...]) + TableStyle([ ("BACKGROUND", ...), ... ])` approach which requires explicit cell-coordinate styling for comparable output.

3. **Forward fit for bulk-pilot generation.** fpdf2 ships a purpose-built `Templates` system for rendering PDFs in batch — directly relevant to the next issue (parameterised bulk generation with faker-style data per brainstorm §8 step 3-4).

4. **Multilingual / German support.** fpdf2's built-in Helvetica family renders German umlauts (ä/ö/ü/ß) natively via its UTF-8 string pipeline. A German-language tutorial is included in the official docs (`py-pdf.github.io/fpdf2/Tutorial-de.html`), consistent with HORUS's German-B2B invoice framing.

5. **Active 2026 maintenance.** 2.8.7 released 2026-02-28; 1300+ unit tests with `qpdf`-based PDF-diffing validation (3 different PDF checkers); recognized as mature and stable by the py-pdf community.

### Trade-off table (fpdf2 vs ReportLab)

| Criterion | fpdf2 | ReportLab | Winner |
|---|---|---|---|
| License | LGPL-3.0+ | BSD-3-Clause | ReportLab |
| py-pdf org consistency | ✅ same org as pypdf | ❌ different org | fpdf2 |
| API ergonomics (tabular invoice) | ✅ context-manager table | ⚠️ Platypus/TableStyle soup | fpdf2 |
| Templates system for bulk | ✅ purpose-built | ⚠️ workable via Platypus | fpdf2 |
| German / multilingual | ✅ native Helvetica + German tutorial | ✅ Helvetica built-in | tie |
| Runtime deps | Pillow + defusedxml + fonttools (3) | Pillow + charset-normalizer (2) | tie |
| Pure-Python wheel | `py3-none-any` ✅ | `py3-none-any` ✅ | tie |
| 2026 release freshness | 2026-02-28 | 2026-04-29 | ReportLab |
| Maturity / track record | 2017 (fpdf2 fork) | 2000 | ReportLab |

fpdf2 wins 3, ReportLab wins 3, 4 ties → decision on the **strongest discriminator for HORUS**: py-pdf org consistency + API ergonomics + Templates forward fit. fpdf2 chosen.

### LGPL-3.0+ license note

LGPL-3.0+ only constrains *modifications and redistribution of fpdf2 itself*. HORUS uses fpdf2 as a runtime library (linking only) — no fpdf2 source code is modified or distributed. LGPL linking-only usage is well-established in Python (PyPI packages regularly carry LGPL; the uv resolver has no special treatment for LGPL vs BSD). The LGPL note is captured here for completeness; it is not a blocker for an academic non-distributed thesis project.

### CII BASIC profile upgrade (from MINIMUM)

The CII XML literal in `scripts/generate_zugferd_smoke.py` is upgraded from MINIMUM to **BASIC** profile as part of this issue. BASIC is the smallest Factur-X/ZUGFeRD profile carrying `IncludedSupplyChainTradeLineItem`, satisfying the "line items from XML" single-source-of-truth requirement. The upgrade adds: one line item (BT-129/BT-130/BT-146/BT-151/BT-155), a tax breakdown (`ApplicableTradeTax` with `BasisAmount`/`CategoryCode`/`RateApplicablePercent`), and expanded address fields for seller + buyer. Totals (100.00/19.00/119.00/119.00) are unchanged. Mustang validates BASIC output against `xslt/ZF_240/FACTUR-X_BASIC.xslt` (~70 rules vs MINIMUM's 27).

### PDF/A-3 substrate — ADR-005 trailer /ID caveat status + new findings

ADR-005 §"Honest caveat" recorded that `pypdf.PdfWriter` does not populate `/ID` in the PDF trailer, causing one ISO 19005-3:2012 §6.1.3 assertion failure in Mustang's PDF/A-3 conformance check.

**Evidence from `make zugferd-smoke` on 2026-05-11 (fpdf2 2.8.7 output, BASIC profile):**

```
XML rules fired: 64 / failed: 0
Top-level summary: status="valid"
ZUGFeRD profile: urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic
Errors:[] ErrorIDs:[]
```

**ADR-005 `/ID` trailer caveat: CLOSED.** The `/ID` assertion (`§6.1.3`) is NOT in the failure list — fpdf2's PDF emitter correctly populates the trailer `/ID` array. The regression test `tests/test_zugferd_render.py::test_render_invoice_pdf_emits_id_trailer` confirms this pre-bonding; Mustang confirms it post-bonding.

**New PDF/A-3 substrate failures (fpdf2 built-in font limitations):**

1. **ISO 19005-3:2012 §6.2.11.4.1** — Helvetica and Helvetica-Bold fonts not embedded. PDF/A-3 requires all fonts embedded; fpdf2's "standard 14 core fonts" are not embedded (they are PDF-viewer-resident fonts). These failures appear once per font instance in the content stream.
2. **ISO 19005-3:2012 §6.2.4.3** — DeviceGray colour space used without an output intent profile (from `pdf.set_draw_color(180,180,180)` and `pdf.set_text_color(120,120,120)` in the renderer).

**Thesis acceptability:** Mustang's overall verdict is `status="valid"` and `Errors:[] ErrorIDs:[]`. The ZUGFeRD-spec compliance claim is clean. PDF/A-3 substrate conformance is a separate concern — HORUS evaluates VLM extraction against embedded XML ground truth, not against the PDF/A-3 substrate. The same acceptability argument as ADR-005 §"Honest caveat" applies.

**Path to strict PDF/A-3 conformance (supersession trigger (d)):** swap built-in Helvetica for an embedded TTF font (e.g., DejaVu Sans shipped with fpdf2 `FPDF2_FONT_DIR`, or any `.ttf` added via `pdf.add_font()`), and add a PDF/A output intent (`pdf.set_output_intent()`). Both are fpdf2-native capabilities; the change is isolated to `_draw_*` functions in `zugferd_render.py`. This is deferred until a strict PDF/A-3 archival experiment is designed.

### Integration with HORUS components

- **`src/horus/zugferd_render.py`** — new module. Exposes `render_invoice_pdf(cii_xml: bytes, out_path: Path) -> None`. Parses CII XML via `lxml.etree.fromstring` into a `_InvoiceView` dataclass (private), renders to A4 PDF via fpdf2. CII namespace map centralised in module-level `_NS` dict. Font: Helvetica (built-in, no font files shipped).
- **`scripts/generate_zugferd_smoke.py`** — mutated: `make_blank_pdf` replaced by `render_invoice_pdf`; `MINIMUM_CII_XML` replaced by `BASIC_CII_XML`; `level="minimum"` → `level="basic"`.
- **`tests/test_zugferd_render.py`** — 4 tests: CII parser unit test, PDF file validity, `/ID` trailer regression, visible-field content extraction.
- **`pyproject.toml`** — `fpdf2` added to `[project] dependencies`; mypy override for `fpdf` + `fpdf.*` added.
- **`Makefile`** — no change needed; `make zugferd-smoke` already invokes the smoke script.
- **Future bulk pilot**: `render_invoice_pdf` exported as-is or upgraded to use fpdf2 `Templates` system when parameterised generation lands (next issue).

## Source archival

Per `horus-source-archival` rule + ADR-002:

- `docs/sources/tools/fpdf2.md` — **new** (this PR). Chosen renderer.
- `docs/sources/tools/reportlab.md` — **new** (this PR). Named fallback in §5 triggers (a) + (b).
- `docs/sources/tools/weasyprint.md` — **new** (this PR). Named fallback in §5 trigger (c).
- borb, pikepdf, pylatex, pdfme — eliminated-by-reference (not archived per `horus-source-archival` §"When the rule does NOT fire": alternatives considered-and-rejected with no positive citation in Decision text).

## Consequences

- **Positive**: every synthetic invoice produced for HORUS evaluation now has a recognisable B2B visual layer rendered from the same CII XML as the structured layer (single source of truth). The fpdf2 renderer is self-contained (no system dependencies); `make install` pulls it in. The BASIC profile upgrade provides a richer Schematron validation surface (70+ rules vs 27) — any BASIC-profile compliance gap is now detectable by Mustang. The ADR-005 `/ID` trailer caveat is expected to close.
- **Negative**: LGPL-3.0+ enters the dependency tree for the first time (fpdf2). For the current scope (academic / linking-only) this is immaterial; supersession trigger (b) captures the path back to BSD if distribution context changes. Pilot generator (next issue) will need to decide whether to use fpdf2 `Templates` directly or wrap in a new `src/horus/invoice_renderer.py` abstraction.
- **Neutral**: `make zugferd-smoke` now renders a full invoice layout before bonding — slightly slower than blank-PDF smoke (~100 ms vs ~5 ms) but still fast enough to be in every developer's pre-commit check.

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate)
- **ADR-002** — source-archival convention (this ADR's §"Source archival" cites)
- **ADR-004** — config library; not directly relevant to visual rendering (no YAML knobs in this issue)
- **ADR-005** — predecessor; explicitly deferred PDF visual realism to this ADR (§"What this ADR does NOT decide" bullet 2)
- **Cascade-system ADR-013** — `/commit` workflow (used for commits in this PR)
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager`; artifact-review gate at step 4 fires explicitly)
