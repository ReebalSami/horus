"""Multi-page PDF rasterizer — pypdfium2-backed; replaces the page-1-only sips baseline.

Implements the rasterization step for pilot #13's cohort harness per ADR-014. Renders
every page of a PDF to PNG via Google's PDFium (via pypdfium2 4.30) at a configurable
DPI. Optional disk caching with mtime-based invalidation lets the harness re-use prior
renders across resume cycles, which is load-bearing because the full 26 × 7 cohort sweep
is interruptible (see `_skip_if_finished` in `harness.py`).

Literature anchors:

  - **DocVLM (Nacson+ CVPR'25)** — establishes per-page rasterization + per-page VLM
    call + per-document aggregation as the multi-page document-VLM convention.
  - **DocILE benchmark (Šimsa+ ICDAR'23)** — per-document key-information evaluation;
    HORUS inherits the per-document scoring contract while delegating rasterization to
    this module. Source archival: `docs/sources/tools/docile-rossumai.md`.

Implementation choice: **pypdfium2 over PyMuPDF and pdf2image** per ADR-014 §Options
considered. PyMuPDF is AGPL-licensed (viral copyleft); `mindee/doctr#486` is the
precedent for AGPL-driven removal in research projects. pdf2image wraps Poppler via
subprocess (system dep + per-page-process-startup overhead). pypdfium2 is Apache-2.0 OR
BSD-3-Clause (consumer picks), ships native arm64 wheels (M1 Pro per
`know-your-hardware`), and has zero system deps. Already installed at v4.30.0 as a
transitive dep of `mineru` + `pdftext`; ADR-014 promotes it to a direct dep so the
version is controlled. Source archival: `docs/sources/tools/pypdfium2.md`.

DPI rationale: 300 DPI on A4 yields width = 2480 px (8.27 in × 300), matching the legacy
`sips --resampleWidth 2480` baseline at `Makefile:89-91` (pre-PR(c) `make cohort-smoke`).
This means per-cohort-model `longest_edge=2048` internal resize behavior (per ADR-007)
is byte-equivalent to the page-1 baseline — no per-model recalibration needed.

Refs: ADR-014 (this module's enabling ADR), ADR-007 (cohort longest_edge=2048 contract),
ADR-009 (preserves single-image-per-`extract()` contract — per-page is one PNG; harness
concatenates outputs per ADR-014 §5.2 strategy α).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pypdfium2 as pdfium

__all__ = ["rasterize_pdf"]

_LOGGER = logging.getLogger(__name__)

# A4 @ 300 DPI ≈ 8.27 in × 300 = 2481 px wide. Empirical render of
# EN16931_Einfach.pdf at scale=300/72 = (2480, 3509) px. Matches the legacy
# `sips --resampleWidth 2480` baseline at Makefile:89-91 within rounding.
_DEFAULT_DPI = 300


def rasterize_pdf(
    pdf_path: Path,
    *,
    dpi: int = _DEFAULT_DPI,
    cache_dir: Path,
    image_format: str = "png",
) -> list[Path]:
    """Rasterize every page of `pdf_path` to a PNG file via pypdfium2.

    On cache hit (cached PNG exists AND its mtime > the PDF's mtime), the render is
    skipped and the cached path is returned. On miss or stale cache, the page is
    rendered fresh and the result overwrites any stale cached file.

    Memory contract: `pdfium.PdfDocument` and `PdfPage` instances auto-finalize via
    `weakref.finalize` per pypdfium2 4.30 docs; explicit `pdf.close()` is the
    recommended belt-and-suspenders for immediate resource release. We do NOT call
    `page.close()` because the high-level Python API doesn't expose it (page handles
    are weakref-tracked back to the document; document close cascades).

    Args:
        pdf_path: Absolute path to the source PDF. Must exist; raises `FileNotFoundError`
            if not.
        dpi: Render resolution in DPI. Default 300 (≈ A4 width 2480 px, matching the
            legacy sips baseline + ADR-007 longest_edge=2048 internal resize). Range
            [72, 600] is sensible; below 72 loses even body-text legibility, above
            600 wastes compute past the cohort-model internal resize ceiling.
        cache_dir: Directory under which page PNGs are cached. Outputs land at
            `<cache_dir>/<pdf_stem>/page-<N>.<ext>` (1-indexed). Created with
            `parents=True, exist_ok=True`. Required (not optional) — every harness
            caller wants caching for resume-safety; ad-hoc callers can pass a
            `tempfile.TemporaryDirectory()` path.
        image_format: Output image format. "png" (default; lossless, matches existing
            per-model smoke artifact convention) or "jpeg" (lossy, smaller files —
            useful for the rasterized-cache-disk-budget edge case).

    Returns:
        Sorted list of PNG paths in page order: `[page-1.png, page-2.png, …]`.
        Length equals the PDF's page count.

    Raises:
        FileNotFoundError: if `pdf_path` does not exist.
        pypdfium2.PdfiumError: if the PDF cannot be parsed (corrupt / encrypted /
            unsupported feature). Bubbles up to the caller; the harness catches this
            in `_score_single` and tags the nested run with `error_type=pdf_parse`.

    Example:
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as td:
        ...     pages = rasterize_pdf(
        ...         Path("data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf"),
        ...         cache_dir=Path(td),
        ...     )
        ...     len(pages)
        ...     pages[0].name
        2
        'page-1.png'
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    out_dir = cache_dir / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_mtime = pdf_path.stat().st_mtime

    pdf = pdfium.PdfDocument(str(pdf_path))
    out_paths: list[Path] = []
    try:
        n_pages = len(pdf)
        for i in range(n_pages):
            page_num = i + 1
            out_path = out_dir / f"page-{page_num}.{image_format}"

            if out_path.is_file() and out_path.stat().st_mtime > pdf_mtime:
                _LOGGER.debug("rasterize_pdf: cache hit %s", out_path)
                out_paths.append(out_path)
                continue

            page = pdf[i]
            bitmap = page.render(scale=dpi / 72)
            bitmap.to_pil().save(out_path)
            _LOGGER.debug("rasterize_pdf: rendered %s (dpi=%d)", out_path, dpi)
            out_paths.append(out_path)
    finally:
        pdf.close()

    return out_paths
