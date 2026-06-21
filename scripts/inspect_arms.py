"""Per-field + per-group error analysis for the structurer arms (ADR-038/042/044/045).

Read-only, **offline**, **deterministic**. The structurer-arm sibling of
``scripts/error_analysis.py`` (which targets the regex/reader multipage adapter):
this inspector re-scores the SAVED Arm-A / Arm-B structured outputs in
``docs/sources/transcripts-arm{,s}-dev/`` through the EXACT runner path
(``structurer.to_predicted_dict_multipage`` + ``to_predicted_groups_multipage``
+ ``score(predicted_groups=...)``), so its per-cell outcomes are bit-identical to
what ``src/horus/eval/arm_b.py`` computed — no re-inference, no parser drift.

Purpose: separate **genuine model misses** from **ruler artifacts** (GT or scorer
bugs). For every (arm, invoice) it prints:

  - the flat 34-field table: field | BT | outcome | ground truth | predicted
  - the repeating-group cell tables (vat_breakdown / skonto / line_items)
  - the flat micro-F1 + the ADR-042 overall_micro_f1 (flat + groups) + tally

Usage:
    uv run python scripts/inspect_arms.py --arm b
    uv run python scripts/inspect_arms.py --arm a --invoices EN16931_Rabatte
    uv run python scripts/inspect_arms.py --arm b --non-tp-only   # only show misses

Per ``horus-config-discipline`` this is a diagnostic inspector (not an
experiment), so it takes plain CLI flags rather than a YAML config — same class
as ``scripts/error_analysis.py`` / ``scripts/inspect_pilot_13.py``.

Refs: ADR-038 (the arms), ADR-042 (repeating-group scoring), ADR-043/044/045
(the ruler fixes this audits), ADR-013/027 (scorer + metrics).
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.config import EvalConfig  # noqa: E402
from horus.eval import structurer  # noqa: E402
from horus.eval.ground_truth import FIELDS  # noqa: E402
from horus.eval.scorer import FieldResult, InvoiceFieldScores, score  # noqa: E402
from horus.eval.transcripts import (  # noqa: E402
    build_gt_cache,
    parse_transcript,
    split_per_page_texts,
)

_DEFAULT_STRUCTURER = "google/gemma-4-E4B-it"
_DEFAULT_CORPUS_ROOT = REPO_ROOT / "data/raw/german/zugferd-corpus"
_ARM_DIRS = {
    "a": REPO_ROOT / "docs/sources/transcripts-arm-a-dev",
    "b": REPO_ROOT / "docs/sources/transcripts-arms-dev",
}
_OUTCOME_ORDER = ("TP", "FP", "FN", "TN", "EXCLUDED")


def _gt_cell(fr: FieldResult) -> str:
    if not fr.gt_present:
        return "_(absent)_"
    if fr.gt_normalized == "":
        return "_(present, empty)_"
    if fr.gt_normalized is None:
        return "_(present, excluded/normalizer-rejected)_"
    return f"`{fr.gt_normalized}`"


def _pred_cell(fr: FieldResult) -> str:
    if fr.predicted_normalized is None:
        return "_(not extracted)_"
    if fr.predicted_normalized == "":
        return "_(empty string)_"
    return f"`{fr.predicted_normalized}`"


def _tally(per_field: dict[str, FieldResult]) -> str:
    counts = {key: 0 for key in _OUTCOME_ORDER}
    for fr in per_field.values():
        counts[fr.outcome] = counts.get(fr.outcome, 0) + 1
    return " / ".join(f"{key} {counts[key]}" for key in _OUTCOME_ORDER)


def _field_rows(per_field: dict[str, FieldResult], *, non_tp_only: bool) -> list[str]:
    rows: list[str] = []
    for key in FIELDS:
        fr = per_field.get(key)
        if fr is None:
            continue
        if non_tp_only and fr.outcome == "TP":
            continue
        rows.append(
            f"| `{key}` | {fr.bt_code} | {fr.outcome} | {_gt_cell(fr)} | {_pred_cell(fr)} |"
        )
    return rows


def render_invoice(inv: InvoiceFieldScores, *, non_tp_only: bool) -> str:
    lines: list[str] = []
    model_short = inv.model_id.split("/")[-1]
    lines.append(f"### {model_short} × {inv.invoice_id}")
    lines.append("")
    lines.append(
        f"flat micro-F1 **{inv.micro_f1:.4f}** · overall (flat+groups) "
        f"**{inv.overall_micro_f1:.4f}** · presence-cond F1 "
        f"{inv.presence_conditional_f1:.4f} · spurious {inv.spurious_emission_rate:.3f}"
    )
    lines.append(f"flat tally: {_tally(inv.per_field)}")
    lines.append("")
    lines.append("| field | BT | outcome | ground truth | predicted |")
    lines.append("|---|---|---|---|---|")
    field_rows = _field_rows(inv.per_field, non_tp_only=non_tp_only)
    lines.extend(field_rows or ["| _(all flat fields TP)_ | | | | |"])
    lines.append("")

    for group_key, gr in inv.repeating.items():
        if gr.n_gt_rows == 0 and gr.n_pred_rows == 0:
            continue
        lines.append(
            f"**{group_key}** — F1 {gr.f1:.3f} "
            f"(gt_rows={gr.n_gt_rows} pred_rows={gr.n_pred_rows} matched={gr.n_matched_rows})"
        )
        cells = [c for c in gr.cell_results if not (non_tp_only and c.outcome == "TP")]
        if cells:
            lines.append("")
            lines.append("| cell | outcome | ground truth | predicted |")
            lines.append("|---|---|---|---|")
            for c in cells:
                lines.append(
                    f"| `{c.english_key}` | {c.outcome} | {_gt_cell(c)} | {_pred_cell(c)} |"
                )
        lines.append("")
    return "\n".join(lines)


def analyze(
    *,
    arm: str,
    invoices: set[str] | None,
    structurer_model: str,
    corpus_root: Path,
    non_tp_only: bool,
) -> list[InvoiceFieldScores]:
    transcripts_dir = _ARM_DIRS[arm]
    if not transcripts_dir.is_dir():
        raise FileNotFoundError(f"Arm-{arm} transcripts dir not found: {transcripts_dir}")
    if not corpus_root.is_dir():
        raise FileNotFoundError(f"Corpus root not found: {corpus_root}")

    with contextlib.redirect_stdout(sys.stderr):
        gt_cache = build_gt_cache(corpus_root)

    out: list[InvoiceFieldScores] = []
    for tp in sorted(transcripts_dir.glob("*.txt")):
        try:
            tp_model, invoice_stem, body = parse_transcript(tp)
        except ValueError:
            continue
        if tp_model != structurer_model:
            continue
        if invoices is not None and invoice_stem not in invoices:
            continue
        gt = gt_cache.get(invoice_stem)
        if gt is None:
            print(f"  WARN: no factur-x GT for {invoice_stem!r}; skipping", file=sys.stderr)
            continue

        per_page = split_per_page_texts(body)
        predicted = structurer.to_predicted_dict_multipage(per_page, tp_model)
        predicted_groups = structurer.to_predicted_groups_multipage(per_page, tp_model)
        inv = score(
            predicted,
            gt,
            cfg=EvalConfig(),
            invoice_id=invoice_stem,
            model_id=tp_model,
            predicted_groups=predicted_groups,
        )
        out.append(inv)

    out.sort(key=lambda s: s.invoice_id)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect_arms",
        description=(
            "Per-field + per-group GT-vs-predicted audit for the structurer arms, "
            "from saved outputs (offline, deterministic, no VLM)."
        ),
    )
    parser.add_argument("--arm", required=True, choices=("a", "b"), help="Which arm to audit.")
    parser.add_argument(
        "--invoices",
        default=None,
        metavar="A,B,...",
        help="Comma-separated invoice stems. Default: every invoice with a saved output.",
    )
    parser.add_argument("--structurer", default=_DEFAULT_STRUCTURER, help="Structurer model id.")
    parser.add_argument("--corpus-root", default=str(_DEFAULT_CORPUS_ROOT))
    parser.add_argument(
        "--non-tp-only",
        action="store_true",
        help="Show only non-TP fields/cells (the misses) — the audit-focused view.",
    )
    args = parser.parse_args(argv[1:])

    invoices: set[str] | None = None
    if args.invoices:
        invoices = {s.strip() for s in args.invoices.split(",") if s.strip()}

    results = analyze(
        arm=args.arm,
        invoices=invoices,
        structurer_model=args.structurer,
        corpus_root=Path(args.corpus_root),
        non_tp_only=args.non_tp_only,
    )
    if not results:
        print(
            f"No saved outputs matched arm={args.arm!r} structurer={args.structurer!r}.",
            file=sys.stderr,
        )
        return 1

    print(f"## Arm {args.arm.upper()} per-field audit — {args.structurer}")
    print()
    overall = [inv.overall_micro_f1 for inv in results]
    print(f"{len(results)} invoices · mean overall_micro_f1 {sum(overall) / len(overall):.4f}")
    print()
    for inv in results:
        print(render_invoice(inv, non_tp_only=args.non_tp_only))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
