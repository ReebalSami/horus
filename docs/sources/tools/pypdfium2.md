---
source_url: "https://github.com/pypdfium2-team/pypdfium2"
source_title: "pypdfium2 — Python binding to PDFium for PDF rendering, inspection, and manipulation"
source_author: "pypdfium2-team (community fork; PDFium = Google/Foxit/Chromium)"
source_date: "2024-12-19"
retrieved_date: "2026-05-18"
extracted_concepts: []
tags: ["pypdfium2", "pdfium", "pdf-rendering", "rasterization", "python-library", "apache-2.0", "bsd-3-clause", "primary-tooling", "adr-014"]
archived_pdf: ""
status: stub
---

ABI-level Python binding (Apache-2.0 OR BSD-3-Clause; user picks) to **PDFium**, Google's PDF renderer extracted from Chromium. PyPI: `pypdfium2` 4.30.0 (Dec 2024 release; current stable). Already installed in HORUS at the time of ADR-014 authoring as a transitive dependency of `mineru` + `pdftext` (verified via `uv pip show pypdfium2`).

**Role in HORUS (per ADR-014)** — multi-page PDF rasterizer for the pilot #13 cohort harness. Replaces the page-1-only `sips --resampleWidth 2480` baseline used by `make cohort-smoke` (ADR-009 + ADR-013). Lifts the page-1-only F1 ceiling that PR(b) deferred here.

**API used by HORUS** (`src/horus/eval/rasterize.py`):

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument(pdf_path)
try:
    for i, page in enumerate(pdf):
        bitmap = page.render(scale=300/72)  # 300 DPI ≈ sips 2480px on A4
        pil = bitmap.to_pil()
        pil.save(cache_dir / f"page-{i+1}.png")
finally:
    pdf.close()  # explicit; weakref auto-finalizer is the safety net
```

**Why pypdfium2 over alternatives** (ADR-014 §Options considered):

- **vs PyMuPDF** — PyMuPDF is AGPL (viral copyleft); pypdfium2 is Apache-2.0 / BSD-3-Clause (permissive). For a thesis project the AGPL distribution implications are an unnecessary complication; `mindee/doctr#486` is the precedent for AGPL-driven removal of PyMuPDF. Comparable rendering performance per `py-pdf/benchmarks`.
- **vs pdf2image** — pdf2image is a `pdftoppm` (Poppler) subprocess wrapper; requires `brew install poppler` system dep and is per-page-subprocess slow. pypdfium2 has zero system deps.
- **vs `sips` loop** — `sips` is macOS-only; kills cross-platform reproducibility (M3 Max / Linux thesis-defense scenarios).

**Native arm64 wheels** ship for macOS arm64 (M1 Pro per `know-your-hardware`); also Linux x86_64 / arm64 / Windows.

**Memory management** — pypdfium2 helper classes (`PdfDocument`, `PdfPage`, `PdfBitmap`) auto-finalize via `weakref.finalize`; explicit `close()` is recommended for immediate resource release. `bitmap.to_pil()` creates an independent PIL.Image; the underlying PDFium bitmap can be safely closed afterwards.

**Pinned range**: `pypdfium2 >= 4.30, < 5` in `pyproject.toml` (per ADR-014). 4.x line is stable as of authoring; 5.x supersession trigger documented in ADR-014.

**Upstream**: `pypdfium2-team/pypdfium2` (community fork of the original `pdfium-binaries` project). Active development; releases at ~quarterly cadence.
