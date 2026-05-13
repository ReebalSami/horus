"""Orchestrated-baseline smoke runner — ADR-008 §"Smoke evidence" generator.

Runs Docling's ``StandardPdfPipeline`` (default ``DocumentConverter``) against a
single ZUGFeRD invoice PDF and prints a transcript-style report to stdout.
Captures: load wall-time, conversion wall-time, output character count, output
snippet (first ~500 chars of markdown export), and structural counts (pages /
tables / pictures).

Single-backend by design: this ADR's smoke is Docling-only (per plan Q4 = A);
MinerU pipeline backend is install-verified but its on-invoice smoke is
deferred to pilot loop #13. ADR-007's dual-backend smoke pattern is the
template; ADR-008 adapts it to install-ADR scope.

Usage:
    python scripts/orchestrated_smoke.py [path/to/invoice.pdf]

Default input: ``data/raw/smoke/invoice-001.pdf`` (produced by
``make zugferd-smoke`` per ADR-005 + ADR-006).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from docling.document_converter import DocumentConverter

DEFAULT_PDF = Path("data/raw/smoke/invoice-001.pdf")
SNIPPET_CHARS = 500


def run_docling_smoke(pdf_path: Path) -> None:
    """Run Docling's StandardPdfPipeline on ``pdf_path`` and print transcript."""
    print("=" * 72)
    print("HORUS orchestrated-baseline smoke — ADR-008 evidence")
    print("=" * 72)
    print(f"Input PDF:      {pdf_path}")
    print(f"Input size:     {pdf_path.stat().st_size:,} bytes")
    print()
    print("-" * 72)
    print("Backend:        docling (StandardPdfPipeline, default)")

    load_start = time.perf_counter()
    converter = DocumentConverter()
    load_wall = time.perf_counter() - load_start
    print(f"Load wall-time: {load_wall:6.2f} s")

    convert_start = time.perf_counter()
    result = converter.convert(str(pdf_path))
    convert_wall = time.perf_counter() - convert_start
    print(f"Convert wall-time: {convert_wall:6.2f} s")

    document = result.document
    markdown = document.export_to_markdown()

    n_pages = len(getattr(document, "pages", {}) or {})
    n_tables = len(getattr(document, "tables", []) or [])
    n_pictures = len(getattr(document, "pictures", []) or [])
    n_texts = len(getattr(document, "texts", []) or [])

    print(f"Output length:  {len(markdown):,} chars (markdown export)")
    print(
        f"Structure:      pages={n_pages} texts={n_texts} tables={n_tables} pictures={n_pictures}"
    )
    print("Status:         ok")
    print()
    print(f"Output snippet (first {SNIPPET_CHARS} chars of markdown):")
    print()
    snippet = markdown[:SNIPPET_CHARS]
    print(snippet)
    if len(markdown) > SNIPPET_CHARS:
        print(f"... [truncated; full length {len(markdown)} chars]")
    print("-" * 72)
    print()
    print("=" * 72)
    print("SUMMARY: Docling StandardPdfPipeline ran to completion")
    print("=" * 72)


def main() -> int:
    pdf_arg = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_PDF)
    pdf_path = Path(pdf_arg)
    if not pdf_path.exists():
        print(f"ERROR: Input PDF not found: {pdf_path}", file=sys.stderr)
        print("Run 'make zugferd-smoke' first to produce the smoke input.", file=sys.stderr)
        return 1
    run_docling_smoke(pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
