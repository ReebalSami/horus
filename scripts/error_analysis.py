"""Per-field error analysis for a (model, invoice) pair — ADR-028 evidence.

Read-only, **offline**. Reuses the cached multi-page transcripts in
``docs/sources/transcripts-multipage/`` + the canonical adapter
(``horus.eval.adapters.to_predicted_dict_multipage``) + the scorer — **no
re-inference**. For a given model + invoice, it prints a per-field table:

    field | BT | outcome | ground truth | predicted

so the F1 numbers can be inspected field-by-field — the actual extracted
string against the factur-x ground-truth value — demystifying what micro-F1
means in practice (which fields are TP, which are FN, and why).

This is the **regeneration path** for ADR-028 Amendment 1's "Worked example"
tables. It deliberately reuses ``scripts.rescore``'s transcript parser and GT
cache so its numbers are bit-identical to the offline A/B re-score
(``make adapter-iterate``) — no parser drift.

Usage:
    uv run python scripts/error_analysis.py \\
        --model opendatalab/MinerU2.5-Pro-2604-1.2B \\
        --invoices EN16931_Einfach,XRECHNUNG_Einfach

    # All invoices the model has a transcript for (omit --invoices):
    uv run python scripts/error_analysis.py --model opendatalab/MinerU2.5-Pro-2604-1.2B

Output is GitHub-flavoured Markdown (renders cleanly in a terminal and pastes
verbatim into an ADR). Per `horus-config-discipline` this is a diagnostic
inspector (not an experiment), so it takes plain CLI flags rather than a YAML
config — same class as ``scripts/inspect_pilot_13.py``.

Refs: ADR-028 (the fix this substantiates), ADR-016 (the offline re-score
substrate it mirrors), ADR-027 (the metric definitions), ADR-013 (the scorer).
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

# `from scripts import rescore` requires the repo root on sys.path when this
# file is run directly (`uv run python scripts/error_analysis.py` puts the
# `scripts/` dir on sys.path[0], not the repo root). Same repo-root-insertion
# pattern as `scripts/compute_probe_verdict.py`. The `horus.*` imports below
# resolve via the editable install regardless.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.config import EvalConfig  # noqa: E402
from horus.eval import adapters  # noqa: E402
from horus.eval.ground_truth import FIELDS  # noqa: E402
from horus.eval.scorer import FieldResult, InvoiceFieldScores, score  # noqa: E402
from scripts import rescore  # noqa: E402

# Outcome glyphs ordered for the per-invoice tally line.
_OUTCOME_ORDER = ("TP", "FP", "FN", "TN", "EXCLUDED")


def _gt_cell(fr: FieldResult) -> str:
    """Render the ground-truth side of one field for the table.

    Distinguishes the three GT states the scorer's truth table cares about:
    absent (field not in the XML), present-but-empty, and present-with-content.
    """
    if not fr.gt_present:
        return "_(absent)_"
    if fr.gt_normalized == "":
        return "_(present, empty)_"
    if fr.gt_normalized is None:
        return "_(present, normalizer-rejected)_"
    return f"`{fr.gt_normalized}`"


def _pred_cell(fr: FieldResult) -> str:
    """Render the predicted side of one field for the table."""
    if fr.predicted_normalized is None:
        return "_(not extracted)_"
    if fr.predicted_normalized == "":
        return "_(empty string)_"
    return f"`{fr.predicted_normalized}`"


def _tally(inv: InvoiceFieldScores) -> str:
    """Build a 'TP n / FP n / ...' summary line from the per-field outcomes."""
    counts = {key: 0 for key in _OUTCOME_ORDER}
    for fr in inv.per_field.values():
        counts[fr.outcome] = counts.get(fr.outcome, 0) + 1
    return " / ".join(f"{key} {counts[key]}" for key in _OUTCOME_ORDER)


def render_invoice(inv: InvoiceFieldScores) -> str:
    """Render one (model, invoice) scoring as a Markdown section + per-field table.

    Fields are listed in `FIELDS` registry order (= EN16931 BT order) so the
    table is stable across runs and matches the ADR's field ordering.
    """
    lines: list[str] = []
    model_short = inv.model_id.split("/")[-1]
    lines.append(f"#### {model_short} × {inv.invoice_id}")
    lines.append("")
    lines.append(
        f"micro-F1 **{inv.micro_f1:.4f}** · presence-conditional F1 "
        f"{inv.presence_conditional_f1:.4f} · {_tally(inv)}"
    )
    lines.append("")
    lines.append("| field | BT | outcome | ground truth | predicted |")
    lines.append("|---|---|---|---|---|")
    for key in FIELDS:
        fr = inv.per_field.get(key)
        if fr is None:
            continue
        lines.append(
            f"| `{key}` | {fr.bt_code} | {fr.outcome} | {_gt_cell(fr)} | {_pred_cell(fr)} |"
        )
    lines.append("")
    return "\n".join(lines)


def analyze(
    *,
    model_id: str,
    invoices: set[str] | None,
    transcripts_dir: Path,
    corpus_root: Path,
) -> list[InvoiceFieldScores]:
    """Score every matching (model, invoice) transcript and return the results.

    Mirrors `rescore.rescore_transcripts` exactly (same parser, same GT cache,
    same multipage adapter, same `score()` call) so the per-field outcomes are
    identical to the offline A/B re-score — only the presentation differs.
    """
    if not transcripts_dir.is_dir():
        raise FileNotFoundError(f"Transcripts dir not found: {transcripts_dir}")
    if not corpus_root.is_dir():
        raise FileNotFoundError(f"Corpus root not found: {corpus_root}")

    # Route rescore's GT-cache progress prints to stderr so this script's
    # stdout stays pure Markdown (paste-ready into the ADR).
    with contextlib.redirect_stdout(sys.stderr):
        gt_cache = rescore._build_gt_cache(corpus_root)
    transcript_paths = sorted(transcripts_dir.glob("*.txt"))

    out: list[InvoiceFieldScores] = []
    for tp in transcript_paths:
        try:
            tp_model, invoice_stem, body = rescore._parse_transcript(tp)
        except ValueError:
            continue
        if tp_model != model_id:
            continue
        if invoices is not None and invoice_stem not in invoices:
            continue
        gt = gt_cache.get(invoice_stem)
        if gt is None:
            print(f"  WARN: no factur-x GT for {invoice_stem!r}; skipping", file=sys.stderr)
            continue

        per_page_texts = rescore._split_per_page_texts(body)
        predicted = adapters.to_predicted_dict_multipage(per_page_texts, tp_model)
        inv = score(
            predicted,
            gt,
            cfg=EvalConfig(),
            invoice_id=invoice_stem,
            model_id=tp_model,
        )
        out.append(inv)

    out.sort(key=lambda s: s.invoice_id)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="error_analysis",
        description=(
            "Per-field GT-vs-predicted error analysis for a (model, invoice) pair, "
            "from cached transcripts (offline, no VLM). ADR-028 evidence regeneration."
        ),
    )
    parser.add_argument(
        "--model",
        required=True,
        metavar="MODEL_ID",
        help="Model id exactly as recorded in the transcript '# Model:' header "
        "(e.g., opendatalab/MinerU2.5-Pro-2604-1.2B).",
    )
    parser.add_argument(
        "--invoices",
        default=None,
        metavar="A,B,...",
        help="Comma-separated invoice stems (e.g., EN16931_Einfach,XRECHNUNG_Einfach). "
        "Default: every invoice the model has a transcript for.",
    )
    parser.add_argument(
        "--transcripts-dir",
        default=str(rescore.DEFAULT_TRANSCRIPTS_DIR),
        help=f"Directory of saved transcripts (default: {rescore.DEFAULT_TRANSCRIPTS_DIR}).",
    )
    parser.add_argument(
        "--corpus-root",
        default=str(rescore.DEFAULT_CORPUS_ROOT),
        help=f"ZUGFeRD corpus root for factur-x GT (default: {rescore.DEFAULT_CORPUS_ROOT}).",
    )
    args = parser.parse_args(argv[1:])

    invoices: set[str] | None = None
    if args.invoices:
        invoices = {s.strip() for s in args.invoices.split(",") if s.strip()}

    results = analyze(
        model_id=args.model,
        invoices=invoices,
        transcripts_dir=Path(args.transcripts_dir),
        corpus_root=Path(args.corpus_root),
    )

    if not results:
        print(
            f"No transcripts matched model={args.model!r} "
            f"invoices={sorted(invoices) if invoices else '<all>'}.",
            file=sys.stderr,
        )
        return 1

    print(f"## Per-field error analysis — {args.model}")
    print()
    print(
        "Offline re-score of cached transcripts (no VLM). Outcomes: **TP** correct, "
        "**FP** value invented on an absent field, **FN** present field missed or "
        "mis-read, **TN** correctly left empty, **EXCLUDED** out-of-truth-table. "
        "MONEY/DATE/CODE use exact-match-on-normalized; only seller/buyer name use ANLS\\*."
    )
    print()
    for inv in results:
        print(render_invoice(inv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
