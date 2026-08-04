#!/usr/bin/env python3
"""Diff two structurer eval reports field-by-field.

The re-baseline companion to `scripts/finetune_evaluate.py`. Scorer- and
normalizer-level changes (ADR-058's sign-folding + `tax_rate` backfill) must be
measured as a *delta against frozen generations*, otherwise a representation fix
is indistinguishable from a model change. This script makes that delta explicit:

    uv run python scripts/compare_eval_reports.py <before.json> <after.json>

It reads the JSON emitted by `finetune_evaluate.py --out`, so it works for any
pair of arms (oracle / zero-shot / fine-tuned) and any pair of runs (pre-fix vs
post-fix, zero-shot vs adapter).

Reported per field:

* ``F1`` before → after, with the signed delta
* the TP/FP/FN/TN/EXCLUDED counts on both sides, so a moved field can be traced
  to *which* outcome bucket changed (an FN→TP move is a real fix; an FN→EXCLUDED
  move is a scope change and must be justified separately)
* ``NEW`` / ``GONE`` markers for fields that gained or lost signal-bearing
  outcomes entirely — the case the per-field reporting defect hid

Exit code is always 0: this is a reporting tool, not a gate.

Note reports written before the ADR-058 accumulator refactor carry no
``per_field_f1`` / ``per_field_outcomes`` keys at all, so comparing against one
shows every field as ``NEW``. Re-derive the older side with ``--score-only``
(which loads no model) rather than reading a pre-refactor JSON.

References: ADR-058 (the fixes being measured, and the per-field reporting defect
that motivated honest before/after accounting — see
``eval/per-field-reporting-audit.md``), ADR-059 (the oracle-label correction),
ADR-013 (scorer contract).
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


def _counts(report: dict[str, Any], key: str, outcomes_key: str) -> dict[str, int]:
    """Return the five outcome counts for one field/cell (zero-filled when absent)."""
    raw = report.get(outcomes_key, {}).get(key, {})
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

    # Three surfaces, same diff shape. The group ones matter because
    # `mean_overall_micro_f1` pools flat fields AND group cells: diffing only the
    # flat surface can show the headline moving with no visible cause (ADR-059).
    for noun, f1_key, outcomes_key in (
        ("fields", "per_field_f1", "per_field_outcomes"),
        ("repeating groups", "per_group_f1", "per_group_outcomes"),
        ("group cells", "per_group_cell_f1", "per_group_cell_outcomes"),
    ):
        lines.extend(_diff_section(before, after, noun, f1_key, outcomes_key))
    return lines


def _diff_section(
    before: dict[str, Any],
    after: dict[str, Any],
    noun: str,
    f1_key: str,
    outcomes_key: str,
) -> list[str]:
    """Diff one per-key F1 surface (flat fields, groups, or group cells)."""
    b_f1: dict[str, float] = before.get(f1_key, {})
    a_f1: dict[str, float] = after.get(f1_key, {})
    if not b_f1 and not a_f1:
        # Reports written before this surface existed simply omit it; saying so is
        # more useful than printing an empty section that implies "no change".
        return [f"{noun}: not recorded in either report", ""]

    lines: list[str] = []
    changed: list[tuple[float, str, str]] = []
    unchanged: list[str] = []

    for key in sorted(set(b_f1) | set(a_f1)):
        b_val, a_val = b_f1.get(key), a_f1.get(key)
        b_cnt = _counts(before, key, outcomes_key)
        a_cnt = _counts(after, key, outcomes_key)

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

    lines.append(f"changed {noun} ({len(changed)})")
    if changed:
        for _, _, row in sorted(changed, key=lambda item: (item[0], item[1])):
            lines.append(row)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"unchanged {noun} ({len(unchanged)}): {', '.join(unchanged) or '(none)'}")
    lines.append("")
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
