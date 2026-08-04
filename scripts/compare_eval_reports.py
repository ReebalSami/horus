#!/usr/bin/env python3
"""Diff two structurer eval reports field-by-field.

The re-baseline companion to `scripts/finetune_evaluate.py`. Scorer- and
normalizer-level changes (ADR-058's sign-folding + `tax_rate` backfill) must be
measured as a *delta against frozen generations*, otherwise a representation fix
is indistinguishable from a model change. This script makes that delta explicit:

    make eval-compare BEFORE=<old.json> AFTER=<new.json>

It reads the JSON emitted by `finetune_evaluate.py --out`, so it works for any
pair of arms (oracle / zero-shot / fine-tuned) and any pair of runs (pre-fix vs
post-fix, zero-shot vs adapter).

Reported per field:

* ``F1`` before → after, with the signed delta
* the TP/FP/FN/TN/EXCLUDED counts on both sides, so a moved field can be traced
  to *which* outcome bucket changed (an FN→TP move is a real fix; an FN→EXCLUDED
  move is a scope change and must be justified separately)
* ``NEW`` / ``GONE`` markers for fields that gained or lost signal-bearing
  outcomes entirely — the case ADR-057's reporting defect hid

Exit code is always 0: this is a reporting tool, not a gate.

References: ADR-058 (the fixes being measured), ADR-057 (the per-field reporting
defect that motivated honest before/after accounting), ADR-013 (scorer contract).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_BUCKETS = ("TP", "FP", "FN", "TN", "EXCLUDED")


def _load(path: Path) -> dict[str, Any]:
    """Load an eval report JSON, failing loudly with the offending path."""
    if not path.is_file():
        raise SystemExit(f"eval report not found: {path}")
    with path.open(encoding="utf-8") as fh:
        report: dict[str, Any] = json.load(fh)
    return report


def _counts(report: dict[str, Any], key: str) -> dict[str, int]:
    """Return the five outcome counts for one field (zero-filled when absent)."""
    raw = report.get("per_field_outcomes", {}).get(key, {})
    return {bucket: int(raw.get(bucket, 0)) for bucket in _BUCKETS}


def _fmt_counts(counts: dict[str, int]) -> str:
    """Render outcome counts compactly, omitting empty buckets."""
    parts = [f"{bucket}={counts[bucket]}" for bucket in _BUCKETS if counts[bucket]]
    return " ".join(parts) if parts else "(none)"


def _fmt_f1(value: float | None) -> str:
    """Render an F1, distinguishing 'untested' from a genuine 0.000."""
    return "  --  " if value is None else f"{value:.3f}"


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Build the human-readable comparison lines for two reports."""
    lines: list[str] = []

    b_label = before.get("label") or before.get("structurer_model") or "before"
    a_label = after.get("label") or after.get("structurer_model") or "after"

    lines.append(f"BEFORE : {b_label}  ({before.get('n_ok')} ok / {before.get('n_failed')} failed)")
    lines.append(f"AFTER  : {a_label}  ({after.get('n_ok')} ok / {after.get('n_failed')} failed)")
    lines.append("")

    lines.append("headline metrics")
    for metric in (
        "mean_overall_micro_f1",
        "mean_micro_f1",
        "mean_presence_conditional_f1",
        "mean_spurious_emission_rate",
    ):
        b_val, a_val = before.get(metric), after.get(metric)
        if b_val is None or a_val is None:
            continue
        delta = a_val - b_val
        arrow = "→" if abs(delta) >= 5e-5 else "="
        lines.append(f"  {metric:<32} {b_val:.4f} {arrow} {a_val:.4f}   ({delta:+.4f})")
    lines.append("")

    b_f1: dict[str, float] = before.get("per_field_f1", {})
    a_f1: dict[str, float] = after.get("per_field_f1", {})

    changed: list[tuple[float, str, str]] = []
    unchanged: list[str] = []

    for key in sorted(set(b_f1) | set(a_f1)):
        b_val, a_val = b_f1.get(key), a_f1.get(key)
        b_cnt, a_cnt = _counts(before, key), _counts(after, key)

        if b_val is None:
            marker = "NEW "
        elif a_val is None:
            marker = "GONE"
        elif abs(a_val - b_val) < 5e-5:
            marker = ""
        else:
            marker = "MOVE"

        if not marker and b_cnt == a_cnt:
            unchanged.append(key)
            continue

        delta = 0.0 if b_val is None or a_val is None else a_val - b_val
        row = (
            f"  {marker:<4} {key:<28} {_fmt_f1(b_val)} → {_fmt_f1(a_val)}  ({delta:+.3f})\n"
            f"       {'before:':<8} {_fmt_counts(b_cnt)}\n"
            f"       {'after:':<8} {_fmt_counts(a_cnt)}"
        )
        # Sort worsening first, then improvements by magnitude — regressions must
        # be the first thing a reader sees.
        changed.append((delta, key, row))

    lines.append(f"changed fields ({len(changed)})")
    if changed:
        for _, _, row in sorted(changed, key=lambda item: (item[0], item[1])):
            lines.append(row)
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(f"unchanged fields ({len(unchanged)}): {', '.join(unchanged) or '(none)'}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diff two structurer eval reports field-by-field.",
    )
    parser.add_argument("before", type=Path, help="baseline eval report JSON")
    parser.add_argument("after", type=Path, help="new eval report JSON")
    args = parser.parse_args()

    for line in compare(_load(args.before), _load(args.after)):
        print(line, flush=True)


if __name__ == "__main__":
    main()
