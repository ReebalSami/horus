"""Corpus discovery + GT-coverage report for structurer fine-tuning (issue #55).

Offline, read-only, deterministic (no VLM). Walks the WHOLE ZUGFeRD corpus — not
just the 26 wired `XML-Rechnung/FX` pairs that `harness._list_paired_invoices`
returns — and reports, per top-level subdir + overall:

  - PDFs found
  - how many yield a parseable factur-x answer key (embedded-XML route; v1+v2)
  - how many already have a cached Granite reader transcript
  - how many are therefore trainable NOW (GT + transcript) vs need a reader pass

This resolves the real fine-tuning training-set size (the 26-vs-~149 question) with
actual parse results, and lists exactly which GT-bearing invoices still need a
reader pass.

Per `horus-config-discipline` this is a diagnostic (like `scripts/inspect_arms.py`),
so it takes plain CLI flags rather than a YAML config.

Usage:
    uv run python scripts/finetune_corpus_report.py
    uv run python scripts/finetune_corpus_report.py --corpus-root data/raw/german/zugferd-corpus
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.finetune.dataset import (  # noqa: E402
    DEFAULT_READER_MODEL,
    DEFAULT_TRANSCRIPT_DIR,
    build_records,
    summarize,
    target_self_score,
)

_DEFAULT_CORPUS_ROOT = REPO_ROOT / "data/raw/german/zugferd-corpus"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="finetune_corpus_report",
        description="ZUGFeRD corpus GT-coverage report for structurer fine-tuning.",
    )
    parser.add_argument("--corpus-root", default=str(_DEFAULT_CORPUS_ROOT))
    parser.add_argument("--transcript-dir", default=str(DEFAULT_TRANSCRIPT_DIR))
    parser.add_argument("--reader-model", default=DEFAULT_READER_MODEL)
    parser.add_argument(
        "--list-missing",
        action="store_true",
        help="Print the full list of GT-bearing invoices that lack a reader transcript.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Score every GT-derived target against its own GT (must be ~1.0, spurious 0).",
    )
    args = parser.parse_args(argv[1:])

    corpus_root = Path(args.corpus_root)
    if not corpus_root.is_dir():
        print(f"ERROR: corpus root not found: {corpus_root}", file=sys.stderr)
        return 1

    print(f"Scanning {corpus_root} (reader={args.reader_model}) ...", flush=True)
    records = build_records(
        corpus_root,
        transcript_dir=Path(args.transcript_dir),
        reader_model=args.reader_model,
    )
    report = summarize(records)

    print()
    print("## GT coverage by subdir")
    print()
    print("| subdir | PDFs | GT ok | GT fail | transcript | ready |")
    print("|---|--:|--:|--:|--:|--:|")
    for subdir, row in report["by_subdir"].items():
        print(
            f"| {subdir} | {row['pdfs']} | {row['gt_ok']} | {row['gt_fail']} "
            f"| {row['transcript']} | {row['ready']} |"
        )
    t = report["totals"]
    print(
        f"| **TOTAL** | **{t['pdfs']}** | **{t['gt_ok']}** | **{t['gt_fail']}** "
        f"| **{t['transcript']}** | **{t['ready']}** |"
    )

    print()
    print(
        f"GT-bearing invoices WITHOUT a cached transcript (need a reader pass): "
        f"{len(report['gt_no_transcript'])}"
    )
    if args.list_missing and report["gt_no_transcript"]:
        for stem in report["gt_no_transcript"]:
            print(f"  - {stem}")

    if report["gt_failures"]:
        print()
        print(f"GT-parse failures ({len(report['gt_failures'])}) — first 12:")
        for stem, subdir, err in report["gt_failures"][:12]:
            print(f"  - [{subdir}] {stem}: {err}")

    if args.self_check:
        print()
        print("## Target self-consistency (GT → target JSON → real scorer)")
        gt_records = [r for r in records if r.gt is not None]
        clean = 0
        offenders: list[tuple[str, str, float, str]] = []
        bad_field_counts: Counter[str] = Counter()
        for r in gt_records:
            if r.gt is None:
                continue
            s = target_self_score(r.gt)
            if s.overall_micro_f1 >= 0.999 and s.spurious_emission_rate == 0.0:
                clean += 1
                continue
            bad_fields = [k for k, fr in s.per_field.items() if fr.outcome in ("FN", "FP")]
            bad_field_counts.update(bad_fields)
            offenders.append(
                (r.stem, r.subdir, s.overall_micro_f1, ",".join(bad_fields) or "(group cells)")
            )
        print(f"clean targets: {clean}/{len(gt_records)}")
        if offenders:
            print(
                f"offenders ({len(offenders)}); flat fields that fail to self-score, by frequency:"
            )
            for field_key, count in bad_field_counts.most_common():
                print(f"  {count:>3}  {field_key}")
            print("first 8 offenders:")
            for stem, subdir, overall, bad_label in offenders[:8]:
                print(f"  - [{subdir}] {stem}: overall={overall:.3f} bad=[{bad_label}]")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
