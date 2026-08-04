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

`--heldout` swaps the sealed synthetic split for the PRIVATE held-out Belege set of
real invoices (ADR-040) — same structurer, same prompt, same scorer, different data:

    uv run python scripts/finetune_evaluate.py --heldout --label zero-shot \
        --out data/self-collected/_eval/eval-zeroshot-heldout.json

That is the generalization measurement: every number the thesis currently reports comes
from synthetic ZUGFeRD invoices, so a real-invoice score is the only evidence that the
pipeline works on documents it was not built around. `--split` does not apply (the whole
set is held out by construction) and the report label is suffixed `-heldout` so it can
never be confused with a val number.
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
from horus.finetune.dataset import (  # noqa: E402
    DEFAULT_HELDOUT_CORPUS_ROOT,
    DEFAULT_HELDOUT_TRANSCRIPT_DIR,
    build_heldout_records,
    build_records,
    render_oracle_transcript,
)
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

    # Repeating groups. `overall_micro_f1` pools these WITH the flat fields, so
    # without them a group-only regression shows up in the headline with no
    # attributable cause anywhere in the report (ADR-059).
    if report.per_group_f1:
        print("  repeating groups (pooled per-group F1):")
        for key, f1 in sorted(report.per_group_f1.items()):
            c = report.per_group_outcomes.get(key, {})
            n_sig = c.get("TP", 0) + c.get("FP", 0) + c.get("FN", 0)
            print(f"    {f1:.3f}  {key:<32} n={n_sig}")
    if report.per_group_cell_f1:
        print("  weakest group cells (pooled per-cell F1):")
        for key, f1 in sorted(report.per_group_cell_f1.items(), key=lambda kv: kv[1])[:10]:
            c = report.per_group_cell_outcomes.get(key, {})
            n_sig = c.get("TP", 0) + c.get("FP", 0) + c.get("FN", 0)
            print(f"    {f1:.3f}  {key:<32} n={n_sig}")


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
    parser.add_argument(
        "--heldout",
        action="store_true",
        help="Evaluate the private held-out Belege set of REAL invoices (ADR-040) instead "
        "of the sealed synthetic split; --split does not apply.",
    )
    parser.add_argument(
        "--heldout-corpus",
        default=str(DEFAULT_HELDOUT_CORPUS_ROOT),
        help="Held-out corpus root holding index.json (default: %(default)s).",
    )
    parser.add_argument(
        "--heldout-transcripts",
        default=str(DEFAULT_HELDOUT_TRANSCRIPT_DIR),
        help="Held-out reader-transcript dir (default: %(default)s).",
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

    if args.heldout:
        # No split filtering: the entire Belege set is held out by construction, so
        # there is nothing to hold back from it. Transcripts come from the private
        # git-ignored tree rather than the tracked docs/sources/ dir.
        records = build_heldout_records(
            Path(args.heldout_corpus),
            transcript_dir=Path(args.heldout_transcripts),
            reader_model=cfg.reader_model,
        )
        subset = list(records)
    else:
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
    if args.heldout:
        # Suffix unconditionally, including a user-supplied --label: a held-out number
        # and a val number are not comparable, and mixing them up would silently
        # misstate what the thesis claims.
        label = f"{label}-heldout"
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
