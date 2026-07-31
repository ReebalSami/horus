"""Reader-pass CLI — transcribe GT-bearing ZUGFeRD invoices lacking a transcript (issue #55).

Runs the reader (Granite) over every corpus invoice that has a parseable answer key but no
cached transcript, writing transcripts byte-compatible with the pilot-13 cohort archive so the
structurer fine-tune sees one consistent input distribution. Resumable: re-invoking skips
invoices already transcribed.

Foreground + streaming per `long-running-foreground`. Spike with `--limit 2` first, verify,
then run without `--limit` for the rest.

Usage:
    uv run python scripts/finetune_reader_pass.py --limit 2     # spike (verify first)
    uv run python scripts/finetune_reader_pass.py               # full pass (resumable)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.finetune.dataset import (  # noqa: E402
    DEFAULT_READER_MODEL,
    DEFAULT_TRANSCRIPT_DIR,
    build_records,
)
from horus.finetune.reader_pass import ReaderPassConfig, run_reader_pass  # noqa: E402

_DEFAULT_CORPUS_ROOT = REPO_ROOT / "data/raw/german/zugferd-corpus"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="finetune_reader_pass",
        description="Transcribe GT-bearing invoices that lack a reader transcript (Granite).",
    )
    parser.add_argument("--corpus-root", default=str(_DEFAULT_CORPUS_ROOT))
    parser.add_argument("--transcript-dir", default=str(DEFAULT_TRANSCRIPT_DIR))
    parser.add_argument("--reader-model", default=DEFAULT_READER_MODEL)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Transcribe at most N invoices this run (spike-first; the pass is resumable).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-transcribe invoices that already have a transcript.",
    )
    args = parser.parse_args(argv[1:])

    corpus_root = Path(args.corpus_root)
    if not corpus_root.is_dir():
        print(f"ERROR: corpus root not found: {corpus_root}", file=sys.stderr)
        return 1

    transcript_dir = Path(args.transcript_dir)
    records = build_records(
        corpus_root,
        transcript_dir=transcript_dir,
        reader_model=args.reader_model,
    )
    config = ReaderPassConfig(reader_model=args.reader_model, transcript_dir=transcript_dir)
    result = run_reader_pass(
        records,
        config=config,
        overwrite=args.overwrite,
        limit=args.limit,
    )

    if result.failures:
        print()
        print(f"Failures ({len(result.failures)}):")
        for stem, err in result.failures:
            print(f"  - {stem}: {err}")
        # Non-zero only if nothing succeeded — partial progress is still useful + resumable.
        if not result.written:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
