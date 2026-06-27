"""Seal the structurer fine-tune train/val split (issue #55, no-HARKing).

Builds the corpus records, seals a deterministic stratified split, writes it to
``data/finetune/split.json``, and prints a summary. Commit the JSON with ``git add -f``
(``data/*`` is gitignored). Re-running with the same seed + corpus is idempotent.

Usage:
    uv run python scripts/finetune_seal_split.py
    uv run python scripts/finetune_seal_split.py --val-fraction 0.2 --seed 42
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
from horus.finetune.split import DEFAULT_SPLIT_PATH, seal_split, write_split  # noqa: E402

_DEFAULT_CORPUS_ROOT = REPO_ROOT / "data/raw/german/zugferd-corpus"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="finetune_seal_split",
        description="Seal a stratified, deterministic train/val split (no-HARKing).",
    )
    parser.add_argument("--corpus-root", default=str(_DEFAULT_CORPUS_ROOT))
    parser.add_argument("--transcript-dir", default=str(DEFAULT_TRANSCRIPT_DIR))
    parser.add_argument("--reader-model", default=DEFAULT_READER_MODEL)
    parser.add_argument("--out", default=str(DEFAULT_SPLIT_PATH))
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv[1:])

    corpus_root = Path(args.corpus_root)
    if not corpus_root.is_dir():
        print(f"ERROR: corpus root not found: {corpus_root}", file=sys.stderr)
        return 1

    records = build_records(
        corpus_root,
        transcript_dir=Path(args.transcript_dir),
        reader_model=args.reader_model,
    )
    split = seal_split(records, val_fraction=args.val_fraction, seed=args.seed)
    out_path = write_split(split, Path(args.out))

    print(f"Sealed split -> {out_path}")
    print(f"  seed={split.seed} val_fraction={split.val_fraction}")
    print(
        f"  total={len(split.train) + len(split.val)} train={len(split.train)} val={len(split.val)}"
    )
    print(f"  sha256(all)={split.sha256_all[:16]}  sha256(val)={split.sha256_val[:16]}")
    print()
    print("## Strata (train / val)")
    print("| stratum | train | val |")
    print("|---|--:|--:|")
    for stratum in sorted(split.strata):
        counts = split.strata[stratum]
        print(f"| {stratum} | {counts['train']} | {counts['val']} |")
    print()
    print("Commit with:  git add -f", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
