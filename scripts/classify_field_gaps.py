#!/usr/bin/env python3
"""Classify every flat field's F1 loss by CAUSE: prompt gap, reading gap, or neither.

Step 1 of ADR-064's ordering rule, at *field* granularity. ADR-064 forbids handing a
prompt-fixable gap to a LoRA — otherwise the fine-tune is credited with gains a free
prompt edit would have produced. Discharging that rule requires knowing, per field,
whether a weak score is something the prompt could fix. This script answers that from
two eval reports that already exist, with no model inference:

    uv run python scripts/classify_field_gaps.py \\
        --reader data/finetune/eval-zeroshot-qwen-adr059-val.json \\
        --oracle data/finetune/eval-oracle-adr059-val.json

The two arms differ in ONE thing: the oracle arm is fed a perfect GT-rendered
transcript, the reader arm the real reader's text (`finetune_evaluate --oracle`). So:

* **A field at ceiling on perfect text has an adequate prompt.** The model found and
  mapped the value whenever it was rendered under the registry's own label, so the prompt
  is not what it is losing to on real reader text. Adding glossary text cannot help, and
  ADR-048 + ADR-053 both measured *added* glossary text as net-negative — so "hands off"
  is an action, not an absence of one. Note what this does NOT say: it is not a claim that
  the reader failed to transcribe the value. Most such losses are values that ARE in the
  transcript and were not mapped (ADR-066 measured 56 of 84 flat FNs as readable) — that
  residue is the fine-tune's target, not the prompt's. Use
  `scripts/finetune_attribution.py`'s per-field FN-readability split to tell the two apart.
* **A field below ceiling on perfect text has a residual cause that is NOT reading.**
  It is a prompt gap, a GT/renderer bug, or a scorer bug. Which one needs the
  per-invoice instrument: `scripts/check_oracle_transcript_labels.py <field>`. This
  script's job is to say *which fields are worth running it on*, so the expensive
  manual step runs on the few fields that can move rather than all 34.

Why this is not `compare_eval_reports.py` or `finetune_attribution.py`: the former is a
*temporal* before/after delta on one arm, the latter pools outcomes into three coarse
clusters (legacy-16 / new-flat / group:*). Neither answers "for THIS field, is the
prompt the cause?" — which is the only question ADR-064 asks.

Scope is the flat registry. Repeating-group cells are deliberately excluded: ADR-053
measured glossing them as net-negative and they are not scored on the held-out set
(ADR-063), so there is no prompt decision to make about them here.

The escalation commands this prints name a directory of saved generations, and that
directory must belong to the SAME arm as ``--oracle`` or the per-invoice diagnostic
reports what a different run emitted. ``data/finetune/`` holds two near-identically
named oracle dirs and the obvious-looking one is the wrong one:

* ``oracle-adr059-fixed-outputs`` -> flat 0.9743 / pooled 0.9719 =
  ``eval-oracle-adr059-val.json``, the CANONICAL arm and this script's default.
* ``oracle-adr059-outputs`` -> flat 0.9735 / pooled 0.9218 =
  ``eval-oracle-adr059-nocolon-val.json``, an ABLATION. Do not use it here.

Verified by re-scoring each with ``finetune_evaluate.py --score-only`` (loads no model)
and matching the means against the reports. ADR-058 Finding 4 is the precedent for
taking this seriously: a diagnostic silently read a superseded reader lineage because
the canonical choice lived only in a config file.

Exit code is always 0 — a reporting instrument, not a gate.

Refs: ADR-064 (the ordering rule), ADR-058 + ADR-059 (the arms and the prompt surface),
ADR-048 + ADR-053 (measured cost of over-glossing), ADR-054 (the LoRA gate this
precedes).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NamedTuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from horus.eval.ground_truth import FIELDS  # noqa: E402

_BUCKETS = ("TP", "FP", "FN", "TN", "EXCLUDED")

#: An oracle F1 at or above this counts as "prompt proven adequate". Tied to the split
#: size rather than picked for roundness: on 29 val invoices a field present on nearly
#: all of them scores 0.982 with exactly ONE miss (28 TP / 1 FN), so 0.98 is the
#: threshold for "at most a single miss on perfect input". Below it the model missed
#: twice or more with the value plainly in front of it, which is a comprehension-level
#: finding rather than noise.
ORACLE_ADEQUATE_F1 = 0.98

#: Minimum number of signal errors (FN+FP) on the perfect-text arm before a field is
#: escalated as a prompt candidate. Count, not ratio, because F1 on a small denominator
#: is dominated by sample size: `billing_period_start` is present on 3 val invoices, so a
#: single miss reads as 0.800 and looks alarming while being one data point. The prompt
#: gaps ADR-058 actually found looked nothing like that — BT-107 and BT-108 scored 0.000
#: on perfect text, emitting null for every present cell. Requiring two errors keeps the
#: escalation list to fields where the model demonstrably could not see the value, which
#: matters because the remedy (more glossary text) was measured net-NEGATIVE in ADR-048
#: and ADR-053. Single-error fields are reported as `marginal`, not hidden.
MIN_ORACLE_ERRORS = 2

#: F1 differences below this are rounding, not movement (matches
#: `compare_eval_reports._diff_section`).
EPSILON = 5e-5


class Verdict(NamedTuple):
    """One field's cause classification."""

    field: str
    bt_code: str
    reader_f1: float | None
    oracle_f1: float | None
    verdict: str
    note: str

    @property
    def gap(self) -> float:
        """How much the reader arm gives up against its own ceiling."""
        if self.reader_f1 is None or self.oracle_f1 is None:
            return 0.0
        return self.oracle_f1 - self.reader_f1


#: Verdicts in the order a reader should care about them. `prompt-candidate` and
#: `label-mapping` are the only ones that authorize a prompt edit.
VERDICT_ORDER = (
    "label-mapping",
    "prompt-candidate",
    "marginal",
    "reading-gap",
    "closed",
    "untested",
)

_ACTIONABLE = frozenset({"label-mapping", "prompt-candidate"})


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"eval report not found: {path}")
    with path.open(encoding="utf-8") as fh:
        report: dict[str, Any] = json.load(fh)
    return report


def _counts(report: dict[str, Any], key: str) -> dict[str, int]:
    raw = report.get("per_field_outcomes", {}).get(key, {})
    return {bucket: int(raw.get(bucket, 0)) for bucket in _BUCKETS}


def _signal(counts: dict[str, int]) -> int:
    """Gradable outcomes. TN and EXCLUDED carry no information about the prompt."""
    return counts["TP"] + counts["FP"] + counts["FN"]


def classify_field(
    key: str,
    bt_code: str,
    reader_f1: float | None,
    oracle_f1: float | None,
    reader_counts: dict[str, int],
    oracle_counts: dict[str, int],
    *,
    adequate_f1: float = ORACLE_ADEQUATE_F1,
    min_oracle_errors: int = MIN_ORACLE_ERRORS,
) -> Verdict:
    """Assign one field's cause verdict. Pure, so the rules are testable."""
    oracle_signal = _signal(oracle_counts)
    reader_signal = _signal(reader_counts)
    oracle_errors = oracle_counts["FN"] + oracle_counts["FP"]

    if oracle_signal == 0 and reader_signal == 0:
        return Verdict(
            key,
            bt_code,
            reader_f1,
            oracle_f1,
            "untested",
            f"no gradable cells on either arm (TN={oracle_counts['TN']}); an F1 of 0.000 "
            "here is undefined, not a failure",
        )

    if oracle_signal == 0:
        return Verdict(
            key,
            bt_code,
            reader_f1,
            oracle_f1,
            "untested",
            "no gradable cells on the perfect-text arm, so it sets no ceiling to compare against",
        )

    if oracle_f1 is None:
        return Verdict(
            key, bt_code, reader_f1, oracle_f1, "untested", "perfect-text arm reports no F1"
        )

    # The oracle arm scoring BELOW the reader arm is the strongest prompt signal there
    # is: identical model, identical instruction, and the perfect page does worse. The
    # only difference is the wording the oracle page prints, so the model is losing on
    # label→key mapping. ADR-059 saw exactly this when the oracle label changed from
    # schema jargon to the corpus's own wording.
    if reader_f1 is not None and reader_f1 - oracle_f1 > EPSILON:
        return Verdict(
            key,
            bt_code,
            reader_f1,
            oracle_f1,
            "label-mapping",
            f"perfect text scores BELOW reader text ({oracle_f1:.3f} < {reader_f1:.3f}) — the "
            "model maps the oracle page's label worse than the reader's own wording",
        )

    if oracle_f1 < adequate_f1 and oracle_errors >= min_oracle_errors:
        return Verdict(
            key,
            bt_code,
            reader_f1,
            oracle_f1,
            "prompt-candidate",
            f"{oracle_counts['FN']} FN + {oracle_counts['FP']} FP with the value in plain "
            "text — cause is prompt, GT/renderer, or scorer; escalate per-invoice",
        )

    if oracle_f1 < adequate_f1:
        return Verdict(
            key,
            bt_code,
            reader_f1,
            oracle_f1,
            "marginal",
            f"a single error on perfect text ({oracle_counts['FN']} FN + "
            f"{oracle_counts['FP']} FP over {oracle_signal} gradable cells) — too thin to "
            "justify perturbing a prompt whose additions measured net-negative",
        )

    if reader_f1 is not None and oracle_f1 - reader_f1 > EPSILON:
        return Verdict(
            key,
            bt_code,
            reader_f1,
            oracle_f1,
            "reading-gap",
            f"prompt proven adequate at {oracle_f1:.3f}; glossary text cannot recover the "
            f"{oracle_f1 - reader_f1:.3f} it gives up on real text. Whether that residue is "
            "an unreadable value or a readable-but-unmapped one is a separate question — see "
            "finetune_attribution.py's per-field FN-readability split",
        )

    return Verdict(
        key,
        bt_code,
        reader_f1,
        oracle_f1,
        "closed",
        f"at ceiling on both arms ({oracle_f1:.3f}); nothing to repair",
    )


def classify(
    reader: dict[str, Any],
    oracle: dict[str, Any],
    *,
    adequate_f1: float,
    min_oracle_errors: int = MIN_ORACLE_ERRORS,
) -> list[Verdict]:
    """Classify every flat registry field, ordered by verdict severity then by gap size."""
    reader_f1: dict[str, float] = reader.get("per_field_f1", {})
    oracle_f1: dict[str, float] = oracle.get("per_field_f1", {})

    verdicts = [
        classify_field(
            key,
            spec.bt_code,
            reader_f1.get(key),
            oracle_f1.get(key),
            _counts(reader, key),
            _counts(oracle, key),
            adequate_f1=adequate_f1,
            min_oracle_errors=min_oracle_errors,
        )
        for key, spec in FIELDS.items()
    ]
    return sorted(
        verdicts,
        key=lambda v: (VERDICT_ORDER.index(v.verdict), -v.gap, v.field),
    )


def render(
    verdicts: list[Verdict],
    reader: dict[str, Any],
    oracle: dict[str, Any],
    *,
    oracle_outputs: Path,
) -> list[str]:
    """Markdown-table report, pasteable into an ADR."""

    def headline(report: dict[str, Any]) -> str:
        return (
            f"flat {report.get('mean_micro_f1'):.4f} / "
            f"pooled {report.get('mean_overall_micro_f1'):.4f}"
        )

    lines = [
        f"READER : {reader.get('label')}  ({headline(reader)})",
        f"ORACLE : {oracle.get('label')}  ({headline(oracle)})",
        f"n      : {reader.get('n_ok')} reader / {oracle.get('n_ok')} oracle invoices",
        "",
        "| field | BT | reader F1 | perfect F1 | gap | verdict |",
        "|---|---|---|---|---|---|",
    ]
    for v in verdicts:
        both = v.reader_f1 is not None and v.oracle_f1 is not None
        reader_cell = "  --  " if v.reader_f1 is None else f"{v.reader_f1:.3f}"
        oracle_cell = "  --  " if v.oracle_f1 is None else f"{v.oracle_f1:.3f}"
        gap_cell = f"{v.gap:+.3f}" if both else "  --  "
        lines.append(
            f"| `{v.field}` | {v.bt_code} | {reader_cell} | {oracle_cell} "
            f"| {gap_cell} | {v.verdict} |"
        )

    lines.append("")
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.verdict] = counts.get(v.verdict, 0) + 1
    lines.append("## Verdict counts")
    for name in VERDICT_ORDER:
        if name in counts:
            lines.append(f"  {name:<18} {counts[name]}")
    lines.append("")

    actionable = [v for v in verdicts if v.verdict in _ACTIONABLE]
    lines.append(f"## Escalate these {len(actionable)} field(s) — everything else is hands-off")
    if not actionable:
        lines.append("  (none — no field has a residual loss on perfect text)")
    for v in actionable:
        lines.append(f"  {v.field}  [{v.verdict}]")
        lines.append(f"      {v.note}")
        lines.append(
            f"      uv run python scripts/check_oracle_transcript_labels.py {v.field} "
            f"--outputs {oracle_outputs}"
        )
    lines.append("")

    marginal = [v for v in verdicts if v.verdict == "marginal"]
    lines.append(f"## Recorded but NOT escalated ({len(marginal)} marginal)")
    for v in marginal:
        lines.append(f"  {v.field:<26} {v.note}")
    if not marginal:
        lines.append("  (none)")
    lines.append("")

    lines.append("## Hands-off rationale (reading gaps, largest first)")
    reading = [v for v in verdicts if v.verdict == "reading-gap"]
    for v in reading:
        lines.append(f"  {v.field:<26} {v.note}")
    if not reading:
        lines.append("  (none)")
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reader",
        type=Path,
        default=Path("data/finetune/eval-zeroshot-qwen-adr059-val.json"),
        help="eval report for the arm fed REAL reader transcripts",
    )
    parser.add_argument(
        "--oracle",
        type=Path,
        default=Path("data/finetune/eval-oracle-adr059-val.json"),
        help="eval report for the arm fed PERFECT GT-rendered transcripts",
    )
    parser.add_argument(
        "--adequate-f1",
        type=float,
        default=ORACLE_ADEQUATE_F1,
        help="perfect-text F1 at or above which the prompt counts as proven adequate",
    )
    parser.add_argument(
        "--oracle-outputs",
        type=Path,
        default=Path("data/finetune/oracle-adr059-fixed-outputs"),
        help=(
            "saved generations of the SAME arm as --oracle, used in the escalation "
            "commands. Default reproduces eval-oracle-adr059-val.json; note "
            "oracle-adr059-outputs is the nocolon ablation, not this arm."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/finetune/field-gap-classification-val.json"),
        help="write the machine-readable classification here",
    )
    args = parser.parse_args()

    reader, oracle = _load(args.reader), _load(args.oracle)
    verdicts = classify(reader, oracle, adequate_f1=args.adequate_f1)

    for line in render(verdicts, reader, oracle, oracle_outputs=args.oracle_outputs):
        print(line, flush=True)

    artifact = {
        "reader_report": str(args.reader),
        "oracle_report": str(args.oracle),
        "oracle_outputs": str(args.oracle_outputs),
        "adequate_f1": args.adequate_f1,
        "min_oracle_errors": MIN_ORACLE_ERRORS,
        "fields": [
            {
                "field": v.field,
                "bt_code": v.bt_code,
                "reader_f1": v.reader_f1,
                "oracle_f1": v.oracle_f1,
                "gap": round(v.gap, 4),
                "verdict": v.verdict,
                "note": v.note,
            }
            for v in verdicts
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote artifact -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
