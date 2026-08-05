"""Rasterize and/or transcribe the private held-out Belege set (ADR-040).

Held-out counterpart of `scripts/gpu/regen_transcripts.py`. Both drive
`run_reader_pass`; only the record source differs (`build_heldout_records` instead of
`build_records`), so the 39 real invoices pass through the same rasterizer, DPI,
prompt, blank-page guard, and transcript format as the 146 synthetic ones. That
identity is the point — any score difference is then attributable to the invoices
rather than to a second pipeline.

Two modes:

  ``--rasterize-only``  Render every page into the raster cache and report page
                        counts. Loads NO model, so it finishes in seconds anywhere.
                        Needed in its own right: the LLM-judge pass consumes these
                        page images directly.

  (default)             Full reader pass — one transcript per invoice.

**Resolution warning** (`know-your-hardware`). On Apple silicon the reader runs
through `TransformersMPSExtractor`, whose manifest ``max_pixels`` cap
LANCZOS-downscales a 300 DPI A4 page to roughly 150 DPI — the native-resolution ViT
would otherwise demand a 35 GiB Metal buffer on a 16 GB machine. That cap is
MPS-only and CUDA ignores it, so a LOCAL run is **wiring verification only**. The
measurement pass belongs on the CUDA box; otherwise the resulting score confounds
"real invoices are harder" with "we read them at half resolution".

Privacy (ADR-040): every input and output stays under `data/self-collected/`, which
`.gitignore` blocks in full. This script prints sanitized ids ONLY — never a source
filename, never a field value.

Usage:
    uv run python scripts/transcribe_heldout.py --rasterize-only
    uv run python scripts/transcribe_heldout.py --limit 1              # local smoke
    uv run python scripts/transcribe_heldout.py --force-transformers   # GPU box
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from horus.eval.rasterize import rasterize_pdf
from horus.finetune.dataset import (
    DEFAULT_HELDOUT_CORPUS_ROOT,
    DEFAULT_HELDOUT_RASTER_CACHE,
    DEFAULT_HELDOUT_TRANSCRIPT_DIR,
    DEFAULT_READER_MODEL,
    InvoiceRecord,
    build_heldout_records,
)
from horus.finetune.reader_pass import ReaderPassConfig, run_reader_pass


def _report_set(records: list[InvoiceRecord]) -> None:
    """Print a sanitized inventory of the set (ids + aggregates, no filenames)."""
    by_subdir: Counter[str] = Counter(rec.subdir for rec in records)
    missing_gt = [rec.stem for rec in records if not rec.has_gt]
    print(f"Held-out set: {len(records)} invoice(s)", flush=True)
    for subdir, count in sorted(by_subdir.items()):
        print(f"  {subdir:<28} {count}", flush=True)
    if missing_gt:
        # Not fatal: run_reader_pass skips GT-less records, and a drafted-GT gap is
        # worth seeing explicitly rather than silently shrinking the set.
        print(f"  WARN: {len(missing_gt)} without loadable GT: {', '.join(missing_gt)}", flush=True)


def _rasterize_all(records: list[InvoiceRecord], *, cache_dir: Path, dpi: int) -> int:
    """Render every record's pages into the cache. Returns the failure count."""
    print(f"Rasterizing {len(records)} invoice(s) at {dpi} DPI -> {cache_dir}", flush=True)
    total_pages = 0
    failures = 0
    for idx, rec in enumerate(records, start=1):
        try:
            pages = rasterize_pdf(rec.pdf_path, dpi=dpi, cache_dir=cache_dir, image_format="png")
        except Exception as exc:  # noqa: BLE001 — one unreadable PDF must not abort the set
            failures += 1
            print(
                f"  [{idx}/{len(records)}] {rec.stem}: FAILED {type(exc).__name__}: {exc}",
                flush=True,
            )
            continue
        total_pages += len(pages)
        print(f"  [{idx}/{len(records)}] {rec.stem}: {len(pages)} page(s)", flush=True)
    print(f"Rasterize done: {total_pages} page(s) total, {failures} failed.", flush=True)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="transcribe_heldout",
        description="Rasterize and/or transcribe the private held-out Belege set.",
    )
    parser.add_argument(
        "--reader",
        default=DEFAULT_READER_MODEL,
        help="reader model_id (COHORT_MANIFEST key; default: %(default)s)",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_HELDOUT_CORPUS_ROOT,
        help="held-out corpus root holding index.json (default: %(default)s)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_HELDOUT_TRANSCRIPT_DIR,
        help="transcript output dir; MUST stay inside the git-ignored tree (default: %(default)s)",
    )
    parser.add_argument(
        "--raster-cache",
        type=Path,
        default=DEFAULT_HELDOUT_RASTER_CACHE,
        help="page-image cache dir (default: %(default)s)",
    )
    parser.add_argument("--dpi", type=int, default=300, help="render DPI (default: %(default)s)")
    parser.add_argument(
        "--rasterize-only",
        action="store_true",
        help="render pages and exit; loads no model (the judge pass needs these images)",
    )
    parser.add_argument(
        "--force-transformers",
        action="store_true",
        help="run the canonical HF repo at bf16 via transformers — the CUDA-box path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="re-transcribe invoices that already have a transcript",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="cap invoices transcribed this invocation (spike-first / smoke)",
    )
    parser.add_argument(
        "--stems",
        nargs="*",
        default=None,
        help="restrict to these sanitized ids (e.g. belege-de-email-001)",
    )
    args = parser.parse_args(argv)

    records = build_heldout_records(args.corpus, transcript_dir=args.out, reader_model=args.reader)
    if not records:
        # Absent index.json is the documented corpus-absent signal (ADR-023), not a
        # crash — but for a deliberate run it IS an error, so say so and fail.
        print(
            f"No held-out records found under {args.corpus} "
            f"(missing {args.corpus / 'index.json'}?).",
            file=sys.stderr,
        )
        return 1
    _report_set(records)

    if args.rasterize_only:
        return 1 if _rasterize_all(records, cache_dir=args.raster_cache, dpi=args.dpi) else 0

    result = run_reader_pass(
        records,
        config=ReaderPassConfig(
            reader_model=args.reader,
            transcript_dir=args.out,
            raster_cache_dir=args.raster_cache,
            dpi=args.dpi,
            force_transformers=args.force_transformers,
        ),
        overwrite=args.overwrite,
        limit=args.limit,
        stems=set(args.stems) if args.stems else None,
    )
    print(
        f"Transcripts: {len(result.written)} written, {len(result.skipped)} skipped, "
        f"{len(result.failures)} failed -> {args.out}",
        flush=True,
    )
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
