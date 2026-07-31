"""Regenerate the full-corpus reader transcripts with the bake-off winner.

Step 5 of the rented-GPU runbook (scripts/gpu/README.md). Replaces the former
inline heredoc so the step is drivable as a single-line SSH command (the
Windsurf-macOS terminal crashes on embedded newlines in quoted args — see the
`no-terminal-oneline-scripts` rule; a script file is safe from any shell).

Resume-safe: run_reader_pass skips stems whose transcript already exists in
--out, so an interrupted run continues where it stopped.

Usage (on the GPU box):
    uv run python scripts/gpu/regen_transcripts.py \
        --winner opendatalab/MinerU2.5-Pro-2605-1.2B
"""

from __future__ import annotations

import argparse
from pathlib import Path

from horus.finetune.dataset import build_records
from horus.finetune.reader_pass import ReaderPassConfig, run_reader_pass


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="regen_transcripts",
        description="Transcribe the full ZUGFeRD corpus with the bake-off winner.",
    )
    parser.add_argument(
        "--winner",
        required=True,
        help="winning reader model_id from the bake-off (COHORT_MANIFEST key)",
    )
    parser.add_argument(
        "--corpus",
        default="data/raw/german/zugferd-corpus",
        help="corpus root (default: %(default)s)",
    )
    parser.add_argument(
        "--out",
        default="data/finetune/gpu-transcripts",
        help="transcript output dir (default: %(default)s)",
    )
    parser.add_argument(
        "--force-transformers",
        action="store_true",
        default=True,
        help="run the canonical HF repo at bf16 via transformers (default on: "
        "this script targets the CUDA box)",
    )
    args = parser.parse_args()

    records = build_records(Path(args.corpus))
    print(f"Regenerating {len(records)} transcripts with {args.winner} -> {args.out}")
    result = run_reader_pass(
        records,
        config=ReaderPassConfig(
            reader_model=args.winner,
            transcript_dir=Path(args.out),
            force_transformers=args.force_transformers,
        ),
    )
    print(f"Done: {result}")


if __name__ == "__main__":
    main()
