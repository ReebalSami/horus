#!/usr/bin/env python3
"""Reader bake-off — transcribe the sealed val split with a candidate reader, score answerability.

The zero-shot baseline investigation (2026-07-11) showed the structurer's F1 is capped by
reader recall: Pearson(answerability, micro_f1) = 0.927 over the 29 val invoices, with the
canonical Granite reader at mean answerability 0.658. A stronger reader is the prerequisite
for the >=0.90 target — fine-tuning the structurer on transcripts that lack the values would
teach hallucination, not extraction.

For each --reader, this script:
  1. transcribes the sealed val split into data/finetune/bakeoff/<reader-slug>/ (resumable),
  2. scores transcript answerability per invoice,
  3. prints the per-invoice table + per-subdir means, next to the canonical-reader baseline.

Candidates must be COHORT_MANIFEST members (ADR-009). Usage:

    uv run python scripts/finetune_reader_bakeoff.py --reader opendatalab/MinerU2.5-Pro-2604-1.2B
    uv run python scripts/finetune_reader_bakeoff.py --reader zai-org/GLM-OCR --split train

Refs: issue #55, ADR-038 (Arm-B), ADR-009 (cohort manifest).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from horus.eval.harness import _model_slug
from horus.finetune.answerability import score_answerability
from horus.finetune.dataset import DEFAULT_TRANSCRIPT_DIR, build_records
from horus.finetune.reader_pass import ReaderPassConfig, run_reader_pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus"
DEFAULT_SPLIT = REPO_ROOT / "data" / "finetune" / "split.json"
BAKEOFF_ROOT = REPO_ROOT / "data" / "finetune" / "bakeoff"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reader bake-off: transcribe the sealed split, score answerability."
    )
    parser.add_argument("--reader", required=True, help="candidate reader model_id (cohort member)")
    parser.add_argument("--split", choices=["val", "train"], default="val")
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--split-path", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--limit", type=int, default=None, help="cap invoices (spike)")
    parser.add_argument(
        "--stems",
        default=None,
        help="comma-separated invoice stems: transcribe + score ONLY these (wave mode)",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--force-transformers",
        action="store_true",
        help="run the CANONICAL HF repo at bf16 via transformers (CUDA bake-off path), "
        "ignoring the manifest's MLX/quant wiring",
    )
    parser.add_argument(
        "--score-only", action="store_true", help="skip transcription; score existing transcripts"
    )
    args = parser.parse_args()

    split = json.loads(args.split_path.read_text(encoding="utf-8"))
    stems: set[str] = set(split[args.split])
    if args.stems:
        wave = {s.strip() for s in args.stems.split(",") if s.strip()}
        unknown = wave - stems
        if unknown:
            print(f"stems not in the {args.split} split: {sorted(unknown)}")
            return 1
        stems = wave
    records = build_records(args.corpus_root)
    out_dir = BAKEOFF_ROOT / _model_slug(args.reader)

    if not args.score_only:
        result = run_reader_pass(
            records,
            config=ReaderPassConfig(
                reader_model=args.reader,
                transcript_dir=out_dir,
                force_transformers=args.force_transformers,
            ),
            overwrite=args.overwrite,
            limit=args.limit,
            stems=stems,
        )
        if result.failures:
            print(f"\n{len(result.failures)} transcription failure(s):", flush=True)
            for stem, err in result.failures:
                print(f"  {stem}: {err}", flush=True)

    candidate_slug = _model_slug(args.reader)
    print(f"\n{'stem':46} {'subdir':12} {'base':>6} {'cand':>6} {'delta':>6}")
    per_subdir: dict[str, list[tuple[float, float]]] = defaultdict(list)
    base_ratios: list[float] = []
    cand_ratios: list[float] = []
    for rec in records:
        if rec.stem not in stems:
            continue
        base = score_answerability(rec)
        cand = score_answerability(
            rec, transcript_path=out_dir / f"{candidate_slug}__{rec.stem}.txt"
        )
        if base is None or cand is None:
            continue
        base_ratios.append(base.ratio)
        cand_ratios.append(cand.ratio)
        per_subdir[rec.subdir].append((base.ratio, cand.ratio))
        marker = "+" if cand.ratio > base.ratio else (" " if cand.ratio == base.ratio else "-")
        print(
            f"{rec.stem[:46]:46} {rec.subdir[:12]:12} {base.ratio:6.2f} {cand.ratio:6.2f} "
            f"{cand.ratio - base.ratio:+6.2f} {marker}"
        )

    if not cand_ratios:
        print("no scored invoices — did transcription fail?")
        return 1

    n = len(cand_ratios)
    print(f"\n=== {args.reader} vs canonical ({DEFAULT_TRANSCRIPT_DIR.name}) on {args.split} ===")
    base_mean, cand_mean = sum(base_ratios) / n, sum(cand_ratios) / n
    print(f"mean answerability: baseline={base_mean:.3f} candidate={cand_mean:.3f}")
    for subdir in sorted(per_subdir):
        pairs = per_subdir[subdir]
        b = sum(p[0] for p in pairs) / len(pairs)
        c = sum(p[1] for p in pairs) / len(pairs)
        print(f"  {subdir:14} n={len(pairs):2d}  baseline={b:.3f} candidate={c:.3f} ({c - b:+.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
