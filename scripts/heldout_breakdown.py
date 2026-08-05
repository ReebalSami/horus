"""Break a held-out eval report down by language and acquisition channel (ADR-063).

The corpus-level mean hides the finding that matters: an email-native PDF and a phone
photo of an invoice are different difficulty regimes, and the whole reason the held-out
set records `language/channel` is to keep them separable. A single pooled number would let
a strong result on 29 clean PDFs mask a weak one on 10 scans.

Reads the JSON a `finetune_evaluate.py --out` run wrote, joins it to the corpus index on
the invoice id, and prints group means.

    uv run python scripts/heldout_breakdown.py data/self-collected/_eval/<report>.json

With `--outputs <dir>` it additionally re-scores each group from the saved generations to
report the **cell-pooled** F1 alongside the mean-of-per-invoice F1. These answer different
questions and are easy to conflate:

- **Mean of per-invoice F1** — every invoice counts once, whether it carries 12 filled
  fields or 25. Answers *"how well does this go on a typical invoice?"* This is the figure
  the project reports (ADR-027) because the invoice is the unit a practitioner cares about.
- **Cell-pooled F1** — all TP/FP/FN summed across every invoice, then one F1. Field-dense
  invoices pull harder. Answers *"what share of all extracted cells is correct?"*

Neither is a maximum over invoices; both are whole-corpus figures.

Privacy (ADR-040): prints ids, group names, counts and scores only. Never a field value.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from horus.eval.heldout import load_heldout_index  # noqa: E402
from horus.finetune.dataset import build_heldout_records  # noqa: E402
from horus.finetune.evaluate import score_saved_outputs  # noqa: E402

DEFAULT_CORPUS_ROOT = Path("data/self-collected")


def _pooled_f1(per_field_outcomes: dict[str, dict[str, int]]) -> tuple[float, int, int, int]:
    """F1 over every signal-bearing cell in a group: 2TP / (2TP + FP + FN).

    TN and EXCLUDED are omitted on purpose — including them would make the number a
    function of how often fields are absent rather than of how well they are read, the
    defect `eval/per-field-reporting-audit.md` records.
    """
    tp = sum(counts.get("TP", 0) for counts in per_field_outcomes.values())
    fp = sum(counts.get("FP", 0) for counts in per_field_outcomes.values())
    fn = sum(counts.get("FN", 0) for counts in per_field_outcomes.values())
    denominator = 2 * tp + fp + fn
    return (2 * tp / denominator if denominator else 0.0), tp, fp, fn


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Path to an eval report JSON.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_ROOT))
    parser.add_argument(
        "--outputs",
        default=None,
        help="Saved-generations dir. When given, each group is re-scored (no inference) to "
        "report the cell-pooled F1 next to the mean-of-per-invoice F1.",
    )
    parser.add_argument(
        "--metric",
        default="micro_f1",
        choices=("micro_f1", "overall_micro_f1", "presence_conditional_f1"),
        help="Per-invoice metric to average (default: %(default)s, the flat-field score).",
    )
    args = parser.parse_args(argv[1:])

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    per_invoice = report.get("per_invoice") or []
    meta = {item.id: item for item in load_heldout_index(Path(args.corpus))}
    if not meta:
        print(f"no held-out index under {args.corpus}", file=sys.stderr)
        return 1

    groups: dict[str, list[float]] = {}
    languages: dict[str, list[float]] = {}
    channels: dict[str, list[float]] = {}
    unknown: list[str] = []

    for entry in per_invoice:
        if not entry.get("ok"):
            continue
        stem = str(entry.get("stem", ""))
        item = meta.get(stem)
        if item is None:
            unknown.append(stem)
            continue
        value = float(entry.get(args.metric, 0.0))
        groups.setdefault(f"{item.language}/{item.channel}", []).append(value)
        languages.setdefault(item.language, []).append(value)
        channels.setdefault(item.channel, []).append(value)

    label = report.get("label", "<unlabelled>")
    print(f"\n{label} — mean {args.metric} by group\n")
    for title, buckets in (
        ("language / channel", groups),
        ("language", languages),
        ("channel", channels),
    ):
        print(f"  by {title}:")
        for name, values in sorted(buckets.items()):
            spread = f" (min {min(values):.3f})" if len(values) > 1 else ""
            print(f"    {name:28s} n={len(values):3d}  mean={statistics.mean(values):.4f}{spread}")
        print()

    if unknown:
        print(f"  WARN: {len(unknown)} scored invoices are absent from the index: {unknown}")

    if args.outputs:
        _print_pooled(report, Path(args.corpus), Path(args.outputs))
    return 0


def _print_pooled(report: dict[str, object], corpus_root: Path, outputs: Path) -> None:
    """Re-score per group from saved generations and print the cell-pooled F1.

    Re-scores rather than reading the report because the report carries per-field counts
    for the whole corpus only; per-group pooling needs per-group counts. No inference is
    involved, so this is seconds.
    """
    structurer = str(report.get("structurer_model", ""))
    records = [rec for rec in build_heldout_records(corpus_root) if rec.ready]
    by_group: dict[str, list] = {}
    for rec in records:
        by_group.setdefault(rec.subdir, []).append(rec)

    print("  cell-pooled F1 (all TP/FP/FN summed, then one F1):\n")
    rows: list[tuple[str, int, float, int, int, int]] = []
    for name, group in sorted(by_group.items()):
        scored = score_saved_outputs(
            group,
            outputs,
            structurer_model=structurer,
            label=f"pooled:{name}",
            progress=False,
            score_groups=False,
        )
        f1, tp, fp, fn = _pooled_f1(scored.per_field_outcomes)
        rows.append((name, len(group), f1, tp, fp, fn))

    whole = score_saved_outputs(
        records,
        outputs,
        structurer_model=structurer,
        label="pooled:all",
        progress=False,
        score_groups=False,
    )
    f1, tp, fp, fn = _pooled_f1(whole.per_field_outcomes)
    rows.append(("ALL", len(records), f1, tp, fp, fn))

    print()
    for name, n, group_f1, tp, fp, fn in rows:
        # Precision vs recall separates the two failure modes. Leaving a field empty and
        # inventing one are not equally bad for an accounting tool, so the split is
        # reported rather than collapsed into F1.
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        print(
            f"    {name:28s} n={n:3d}  pooled_f1={group_f1:.4f}  "
            f"P={precision:.4f} R={recall:.4f}  TP={tp:4d} FP={fp:3d} FN={fn:3d}"
        )
    print()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
