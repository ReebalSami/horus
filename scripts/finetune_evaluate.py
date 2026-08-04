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

`--score-only DIR` re-scores generations previously persisted by `--save-outputs`,
without loading the structurer or running any inference:

    uv run python scripts/finetune_evaluate.py --split val \
        --score-only data/finetune/oracle-outputs --label oracle-rescored \
        --out data/finetune/eval-oracle-val-rescored.json

That isolates a scorer / normalizer / parser change from any generation change (the
two-tier measurement in `eval/per-field-reporting-audit.md`), and is how an adapter
A/B is compared after a LoRA run.
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
from horus.finetune.dataset import build_records, render_oracle_transcript  # noqa: E402
from horus.finetune.evaluate import (  # noqa: E402
    EvalReport,
    evaluate_structurer,
    score_saved_outputs,
)
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

    # Pooled per-field F1 — the trustworthy per-field diagnostic. `per_field_mean`
    # is a mean comparator score, not an F1; don't rank on it.
    if report.per_field_f1:
        print("  weakest fields (pooled per-field F1, signal-bearing outcomes only):")
        for key, f1 in sorted(report.per_field_f1.items(), key=lambda kv: kv[1])[:10]:
            c = report.per_field_outcomes.get(key, {})
            n_sig = c.get("TP", 0) + c.get("FP", 0) + c.get("FN", 0)
            print(f"    {f1:.3f}  {key:<32} n={n_sig} excluded={c.get('EXCLUDED', 0)}")

    never_tested = sorted(set(report.per_field_outcomes) - set(report.per_field_f1))
    if never_tested:
        print(f"  fields with NO signal-bearing outcome (untested, not scored): {never_tested}")


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
    parser.add_argument(
        "--save-outputs",
        default=None,
        metavar="DIR",
        help="Persist each invoice's raw structurer generation to DIR/<stem>.txt "
        "(enables offline field-subset re-scoring without re-running the VLM).",
    )
    parser.add_argument(
        "--oracle",
        action="store_true",
        help="Feed the structurer a PERFECT GT-rendered transcript instead of the "
        "reader's (structurer-ceiling probe for the attribution audit).",
    )
    parser.add_argument(
        "--score-only",
        default=None,
        metavar="DIR",
        help="Re-score generations saved earlier by --save-outputs (reads DIR/<stem>.txt); "
        "loads no model and runs no inference. Isolates scorer/normalizer changes.",
    )
    args = parser.parse_args(argv[1:])
    if args.score_only and args.save_outputs:
        parser.error("--score-only reads saved generations; --save-outputs would rewrite them.")
    if args.score_only and args.adapter:
        parser.error("--score-only never loads a model, so --adapter has no effect.")

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
    if args.label:
        label = args.label
    elif args.score_only:
        label = "score-only"
    elif args.oracle:
        label = "oracle"
    else:
        label = "finetuned" if adapter_dir else "zero-shot"
    max_tokens = args.max_tokens or cfg.eval_max_tokens

    def _oracle_text(rec) -> str:  # noqa: ANN001 — InvoiceRecord; ready ⇒ gt is set
        assert rec.gt is not None
        return render_oracle_transcript(rec.gt)

    if args.score_only:
        report = score_saved_outputs(
            subset,
            Path(args.score_only),
            structurer_model=cfg.structurer_model,
            label=label,
        )
    else:
        report = evaluate_structurer(
            subset,
            structurer_model=cfg.structurer_model,
            structuring_prompt=prompt,
            adapter_dir=adapter_dir,
            max_tokens=max_tokens,
            label=label,
            save_outputs_dir=Path(args.save_outputs) if args.save_outputs else None,
            reader_text_fn=_oracle_text if args.oracle else None,
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
