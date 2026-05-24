"""Tests for `horus.eval.rasterize.rasterize_pdf` (ADR-014 PR(c)).

Six tests covering:
  1. Page count on the canonical EN16931_Einfach.pdf fixture (2 pages).
  2. DPI matches the legacy sips baseline (A4 @ 300 DPI ≈ 2480 px wide ± 5%).
  3. Cache hit on second invocation — no re-render when PNG mtime > PDF mtime.
  4. Cache invalidation when PDF mtime is bumped past PNG mtime.
  5. Parametrized smoke across all 26 paired ZUGFeRD invoices — every PDF rasterizes
     without error; total page count > 26 (proves multi-page coverage).
  6. Negative-sign edge case — `EN16931_Einfach_negativePaymentDue.pdf` doesn't error
     on its page-2 content (which carries a negative `paymentDue` line item).

Each test uses a per-test `tempfile.TemporaryDirectory()` for the cache; no test
mutates the corpus PDF mtime in place (the cache-invalidation test bumps mtime via
`os.utime` then restores it via try/finally).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from horus.eval.rasterize import rasterize_pdf
from tests._corpus import skip_if_no_corpus
from tests.conftest import EINFACH_PDF, ZUGFERD_FX_DIR

# ADR-023: every test in this module requires the ZUGFeRD corpus on disk
# (rasterizes real PDFs from EINFACH_PDF + ZUGFERD_FX_DIR).
# Skips automatically when the corpus is absent (CI or fresh dev clone).
pytestmark = skip_if_no_corpus

# ---------------------------------------------------------------------------
# Test 1 — canonical fixture has 2 pages
# ---------------------------------------------------------------------------


def test_rasterize_einfach_page_count(tmp_path: Path) -> None:
    """`EN16931_Einfach.pdf` is empirically a 2-page invoice (header + totals)."""
    pages = rasterize_pdf(EINFACH_PDF, cache_dir=tmp_path)

    assert len(pages) == 2
    assert pages[0].name == "page-1.png"
    assert pages[1].name == "page-2.png"
    assert all(p.is_file() for p in pages)
    # Per-PDF cache subdir is the PDF stem
    assert pages[0].parent.name == EINFACH_PDF.stem


# ---------------------------------------------------------------------------
# Test 2 — DPI matches the legacy sips baseline
# ---------------------------------------------------------------------------


def test_rasterize_dpi_matches_existing_sips_baseline(tmp_path: Path) -> None:
    """A4 @ 300 DPI = 2480 px width (the `sips --resampleWidth 2480` legacy default).

    Asserts ±5% to absorb any DPI-rounding within pypdfium2. The empirical observation
    on `EN16931_Einfach.pdf` is exactly 2480 px (no rounding error in pypdfium2 4.30).
    """
    from PIL import Image

    pages = rasterize_pdf(EINFACH_PDF, cache_dir=tmp_path, dpi=300)
    with Image.open(pages[0]) as img:
        width, height = img.size

    assert 2480 * 0.95 <= width <= 2480 * 1.05, f"width {width} outside ±5% of 2480"
    # A4 aspect ratio: 8.27 × 11.69 ≈ 1.4143; height ≈ 3508 at 300 DPI
    assert 3508 * 0.95 <= height <= 3508 * 1.05, f"height {height} outside ±5% of 3508"


# ---------------------------------------------------------------------------
# Test 3 — cache hit on second invocation
# ---------------------------------------------------------------------------


def test_rasterize_cache_hit_skips_render(tmp_path: Path) -> None:
    """Second invocation with a fresh cache returns instantly — no re-render.

    Detection: capture the PNG's mtime after the first call, sleep briefly, call
    again, assert the mtime is unchanged (re-render would bump it).
    """
    pages_1 = rasterize_pdf(EINFACH_PDF, cache_dir=tmp_path)
    mtime_after_first_call = pages_1[0].stat().st_mtime

    # Sleep just past filesystem mtime resolution (HFS+ / APFS = 1 nanosecond, but
    # be conservative for cross-FS portability).
    time.sleep(0.05)

    pages_2 = rasterize_pdf(EINFACH_PDF, cache_dir=tmp_path)
    mtime_after_second_call = pages_2[0].stat().st_mtime

    assert pages_1 == pages_2
    assert mtime_after_first_call == mtime_after_second_call, "Cache hit should not bump PNG mtime"


# ---------------------------------------------------------------------------
# Test 4 — cache invalidation when PDF mtime is bumped
# ---------------------------------------------------------------------------


def test_rasterize_cache_invalidates_on_pdf_change(tmp_path: Path) -> None:
    """Bumping PDF mtime past PNG mtime forces a re-render.

    To avoid mutating the corpus PDF in place, this test copies `EN16931_Einfach.pdf`
    to `tmp_path` first, then bumps the COPY's mtime.
    """
    from shutil import copy2

    pdf_copy = tmp_path / "einfach-copy.pdf"
    copy2(EINFACH_PDF, pdf_copy)

    cache_dir = tmp_path / "cache"
    pages_1 = rasterize_pdf(pdf_copy, cache_dir=cache_dir)
    mtime_after_first_render = pages_1[0].stat().st_mtime

    # Bump PDF mtime to "now + 10s" (well past PNG mtime)
    future = time.time() + 10.0
    os.utime(pdf_copy, (future, future))

    # Brief sleep so the re-rendered PNG's mtime is unambiguously later than the first
    time.sleep(0.05)

    pages_2 = rasterize_pdf(pdf_copy, cache_dir=cache_dir)
    mtime_after_second_render = pages_2[0].stat().st_mtime

    assert pages_1 == pages_2  # same paths
    assert mtime_after_second_render > mtime_after_first_render, (
        "Cache miss should produce a fresh PNG with a later mtime"
    )


# ---------------------------------------------------------------------------
# Test 5 — parametrized smoke across all 26 paired invoices
# ---------------------------------------------------------------------------


def test_rasterize_all_paired_invoices(
    paired_invoice: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Every paired ZUGFeRD invoice rasterizes without error; ≥1 page per PDF.

    Parametrized via `pytest_generate_tests` in `tests/conftest.py` over all 26
    EN16931 + XRECHNUNG paired invoices. Catches PDFs that pypdfium2 cannot parse
    (corrupt / unsupported feature / encrypted).

    Lightweight assertion: page count ≥ 1 (the deeper "multi-page coverage" check is
    the cohort-level test_rasterize_multipage_coverage below).
    """
    pdf_path, _ = paired_invoice
    pages = rasterize_pdf(pdf_path, cache_dir=tmp_path)

    assert len(pages) >= 1, f"{pdf_path.name} produced 0 pages"
    assert all(p.is_file() for p in pages)


def test_rasterize_multipage_coverage(tmp_path: Path) -> None:
    """The 26-invoice corpus contains at least one multi-page invoice (proves the
    page-1-only smoke baseline is genuinely insufficient)."""
    pdf_paths = sorted(ZUGFERD_FX_DIR.glob("*.pdf"))
    multipage_count = 0
    for pdf_path in pdf_paths:
        pages = rasterize_pdf(pdf_path, cache_dir=tmp_path)
        if len(pages) > 1:
            multipage_count += 1
    assert multipage_count >= 1, (
        f"Corpus has 0 multi-page PDFs out of {len(pdf_paths)} — page-1 baseline "
        "would not actually be a limitation; check corpus integrity."
    )


# ---------------------------------------------------------------------------
# Test 6 — negative-payment edge case fixture
# ---------------------------------------------------------------------------


def test_rasterize_handles_negative_payment_due_fixture(tmp_path: Path) -> None:
    """`EN16931_Einfach_negativePaymentDue.pdf` rasterizes cleanly.

    Per ADR-013 §"What this ADR does NOT decide", this fixture exercises a
    page-2 negative-sign-in-payment-due edge case that PR(b)'s page-1-only
    smoke could not reach. PR(c)'s rasterizer must NOT error on it; the
    page-2 content is what unblocks the deferred MONEY-fields page-2 coverage.
    """
    pdf = ZUGFERD_FX_DIR / "EN16931_Einfach_negativePaymentDue.pdf"
    pytest.importorskip("pypdfium2")
    assert pdf.is_file(), f"corpus fixture missing: {pdf}"

    pages = rasterize_pdf(pdf, cache_dir=tmp_path)
    assert len(pages) >= 2, (
        f"{pdf.name} should be multi-page (page-2 holds the negative paymentDue total)"
    )
    assert all(p.is_file() for p in pages)
