"""Evaluate the structurer (zero-shot OR LoRA) over a sealed split (issue #55).

ONE runner, two passes — the matched-precision comparison:

    # zero-shot baseline over the held-out val split
    uv run python scripts/finetune_evaluate.py --split val --label zero-shot \
        --out data/finetune/eval-zeroshot-val.json

    # fine-tuned over the SAME val split (adapter applied)
    uv run python scripts/finetune_evaluate.py --split val --adapter data/finetune/adapter \
        --label finetuned --out data/finetune/eval-finetuned-val.json

`--adapter` is opt-in: omit it for the zero-shot baseline (so the baseline can never
accidentally load an adapter). `--limit N` runs a quick spike over the first N invoices.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.dataset import build_records  # noqa: E402
from horus.finetune.evaluate import EvalReport, evaluate_structurer  # noqa: E402
from horus.finetune.split import load_split  # noqa: E402


def _print_summary(report: EvalReport) -> None:
    print()
    print(f"## Eval summary [{report.label}]")
    print(f"  structurer : {report.structurer_model}")
    print(f"  adapter    : {report.adapter_dir or '<none> (zero-shot)'}")
    print(f"  invoices   : {report.n_ok} ok / {report.n_failed} failed / {report.n_total} total")
    print(f"  overall_micro_f1        : {report.mean_overall_micro_f1:.4f}")
    print(f"  micro_f1 (flat)         : {report.mean_micro_f1:.4f}")
    print(f"  presence_conditional_f1 : {report.mean_presence_conditional_f1:.4f}")
    print(f"  spurious_emission_rate  : {report.mean_spurious_emission_rate:.4f}  (lower = better)")
    worst = sorted((e for e in report.per_invoice if e.ok), key=lambda e: e.overall_micro_f1)[:5]
    if worst:
        print("  weakest invoices (overall_micro_f1):")
        for e in worst:
            print(f"    {e.overall_micro_f1:.3f}  {e.stem}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="finetune_evaluate")
    parser.add_argument("--config", default="configs/finetune-structurer.yaml")
    parser.add_argument("--split", choices=["val", "train", "all"], default="val")
    parser.add_argument(
        "--adapter",
        default=None,
        help="LoRA adapter dir (omit for the zero-shot baseline).",
    )
    parser.add_argument("--label", default=None, help="Report label (default derived from mode).")
    parser.add_argument("--out", default=None, help="Write the JSON report to this path.")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N invoices (spike).")
    parser.add_argument("--max-tokens", type=int, default=0, help="Override decode budget.")
    args = parser.parse_args(argv[1:])

    cfg = FinetuneConfig.from_yaml(args.config)
    prompt = cfg.structuring_prompt()
    split = load_split(Path(cfg.split_path))
    stems = {
        "val": set(split.val),
        "train": set(split.train),
        "all": set(split.train) | set(split.val),
    }[args.split]

    records = build_records(
        Path(cfg.corpus_root),
        transcript_dir=Path(cfg.transcript_dir),
        reader_model=cfg.reader_model,
    )
    subset = [r for r in records if r.stem in stems]
    subset.sort(key=lambda r: r.stem)
    if args.limit > 0:
        subset = subset[: args.limit]

    adapter_dir = Path(args.adapter) if args.adapter else None
    label = args.label or ("finetuned" if adapter_dir else "zero-shot")
    max_tokens = args.max_tokens or cfg.eval_max_tokens

    report = evaluate_structurer(
        subset,
        structurer_model=cfg.structurer_model,
        structuring_prompt=prompt,
        adapter_dir=adapter_dir,
        max_tokens=max_tokens,
        label=label,
    )
    _print_summary(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nWrote report -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
