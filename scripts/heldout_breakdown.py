"""Break a held-out eval report down by language and acquisition channel (ADR-063).

The corpus-level mean hides the finding that matters: an email-native PDF and a phone
photo of an invoice are different difficulty regimes, and the whole reason the held-out
set records `language/channel` is to keep them separable. A single pooled number would let
a strong result on 29 clean PDFs mask a weak one on 10 scans.

Reads the JSON a `finetune_evaluate.py --out` run wrote, joins it to the corpus index on
the invoice id, and prints group means.

    uv run python scripts/heldout_breakdown.py data/self-collected/_eval/<report>.json

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

DEFAULT_CORPUS_ROOT = Path("data/self-collected")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Path to an eval report JSON.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_ROOT))
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
