"""Collapse the held-out cells to the minimum needing author eyes (ADR-062).

Three channels have now read all 39 documents: the text-layer draft, the ADR-060 vision
judge, and the ADR-061 Azure channel. Together they assert on the order of 1,100 cells.
Reviewing all of them by hand is not a plan; reviewing none of them is what produced the
retracted 0.5692.

This script runs the adjudication combiner over every document and emits two artefacts:

- `_review/manifest.json` — machine-readable, consumed by the Streamlit sign-off page.
- `_review/sheet.md` — human-readable, ranked worst-first, with page context per cell.

and prints the **collapse ratio**: total cells, auto-accepted, escalated, split by tier and
by provenance class. That number is the deliverable of this phase.

The Tier A / Tier B split is reported separately throughout, because a single blended
percentage would hide the thing that matters: Tier A cells can be backed by the document's
own bytes, and Tier B cells never can.

Values are written only into the git-ignored corpus tree. Stdout carries counts and field
NAMES only (ADR-040), so the terminal output is safe to paste.

Usage:
    uv run python scripts/review_heldout_gt.py
    uv run python scripts/review_heldout_gt.py --ids belege-de-scan-010
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.eval.adjudication import (  # noqa: E402
    CellDecision,
    ChannelReading,
    EscalationRank,
    ProvenanceClass,
    adjudicate_cell,
    collapse_summary,
    escalated,
    group_row_counts,
)
from horus.eval.azure_invoice import AzureCoverage  # noqa: E402
from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS  # noqa: E402
from horus.eval.heldout import HeldoutItem, load_heldout_index  # noqa: E402
from horus.eval.printed_evidence import TextLayer, extract_text_layer  # noqa: E402
from horus.finetune.dataset import DEFAULT_HELDOUT_CORPUS_ROOT  # noqa: E402

#: Channel directories, in the order their opinions are listed in the sheet.
#: `draft` is the superseded text-layer GT — retained as a channel because where it AGREES
#: with an independent reader that agreement is still information, even though it is not
#: trusted on its own (it is the channel that produced the retraction).
CHANNEL_DIRS: tuple[tuple[str, str], ...] = (
    ("judge", "_judge/gt"),
    ("azure", "_azure/gt"),
    ("draft", "gt"),
)

#: Characters of text-layer context to show around a match in the sheet.
CONTEXT_WINDOW = 60


@dataclass
class DocumentReview:
    """One invoice's adjudication outcome."""

    invoice_id: str
    tier: str
    decisions: list[CellDecision]
    group_counts: dict[str, dict[str, int]]

    @property
    def escalations(self) -> list[CellDecision]:
        return escalated(self.decisions)


def _load_channel(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _coverage_from(document: Mapping[str, Any]) -> dict[str, bool]:
    """Per-field `can this channel express it` from an ADR-061 coverage block.

    Only the Azure channel writes one. Absent block means every field is expressible, which
    is the right default for the two channels that read the whole schema.
    """
    raw = document.get("azure_coverage")
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) != AzureCoverage.NOT_COVERED.value for key, value in raw.items()}


def _context_for(layer: TextLayer, matched: str | None) -> str | None:
    """A window of raw text around the matched rendering, for the sheet.

    Lets the author confirm a value in the sheet itself instead of opening the PDF. Tier B
    has no text layer, so this is None there and the page image is the only recourse.
    """
    if not matched or not layer.exists:
        return None
    dense_needle = "".join(matched.split()).casefold()
    if not dense_needle:
        return None
    collapsed = " ".join(layer.raw.split())
    haystack = collapsed.casefold()
    position = haystack.find(matched.casefold())
    if position < 0:
        # The match was found in the densified haystack, so it may be split by spaces in
        # the raw text; fall back to locating the first token.
        first = matched.split()[0] if matched.split() else matched
        position = haystack.find(first.casefold())
        if position < 0:
            return None
    start = max(0, position - CONTEXT_WINDOW)
    end = min(len(collapsed), position + len(matched) + CONTEXT_WINDOW)
    return ("…" if start else "") + collapsed[start:end] + ("…" if end < len(collapsed) else "")


def review_document(item: HeldoutItem, corpus: Path) -> DocumentReview | None:
    """Adjudicate one invoice across every channel that has read it."""
    channels: dict[str, dict[str, Any]] = {}
    coverage: dict[str, dict[str, bool]] = {}
    for name, subdir in CHANNEL_DIRS:
        document = _load_channel(corpus / subdir / f"{item.id}.gt.json")
        if document is None:
            continue
        channels[name] = document
        channel_coverage = _coverage_from(document)
        if channel_coverage:
            coverage[name] = channel_coverage

    if not channels:
        return None

    layer = extract_text_layer(item.pdf_path) if item.pdf_path.is_file() else None
    if layer is None:
        return None
    tier = "A" if layer.exists else "B"

    decisions: list[CellDecision] = []
    for key in FIELDS:
        readings = [
            ChannelReading(
                channel=name,
                value=_as_text((document.get("fields") or {}).get(key)),
                covered=coverage.get(name, {}).get(key, True),
                confidence=(document.get("azure_confidence") or {}).get(key),
            )
            for name, document in channels.items()
        ]
        decisions.append(adjudicate_cell(key, readings, layer))

    group_counts = {group: group_row_counts(channels, group) for group in REPEATING_GROUPS}
    return DocumentReview(item.id, tier, decisions, group_counts)


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _manifest_cell(decision: CellDecision, layer_context: str | None) -> dict[str, Any]:
    return {
        "key": decision.key,
        "policy": decision.policy.value,
        "provenance": decision.provenance.value,
        "rank": decision.rank.label if decision.rank else None,
        "rank_order": decision.rank.value if decision.rank else None,
        "auto_accepted": decision.auto_accepted,
        "value": decision.value,
        "readings": [
            {
                "channel": r.channel,
                "value": r.value,
                "covered": r.covered,
                "confidence": r.confidence,
            }
            for r in decision.readings
        ],
        "evidenced_channels": list(decision.evidenced_channels),
        "agreeing_channels": list(decision.agreeing_channels),
        "matched_text": decision.matched_text,
        "context": layer_context,
        "note": decision.note,
    }


def build_manifest(reviews: Sequence[DocumentReview], corpus: Path) -> dict[str, Any]:
    """The machine-readable artefact the Streamlit sign-off page consumes."""
    documents: list[dict[str, Any]] = []
    for review in reviews:
        item_layer = None
        pdf = corpus / "pdf" / f"{review.invoice_id}.pdf"
        if pdf.is_file():
            item_layer = extract_text_layer(pdf)
        cells = [
            _manifest_cell(
                decision,
                _context_for(item_layer, decision.matched_text) if item_layer else None,
            )
            for decision in review.decisions
        ]
        documents.append(
            {
                "id": review.invoice_id,
                "tier": review.tier,
                "summary": collapse_summary(review.decisions),
                "escalated_keys": [d.key for d in review.escalations],
                "group_row_counts": review.group_counts,
                "cells": cells,
            }
        )
    all_decisions = [d for review in reviews for d in review.decisions]
    return {
        "schema_version": 1,
        "channels": [name for name, _ in CHANNEL_DIRS],
        "summary": collapse_summary(all_decisions),
        "documents": documents,
    }


def _render_sheet(reviews: Sequence[DocumentReview], manifest: Mapping[str, Any]) -> str:
    """The human-readable ranked sheet."""
    summary = manifest["summary"]
    lines: list[str] = [
        "# Held-out ground truth — adjudication sheet",
        "",
        "Generated by `scripts/review_heldout_gt.py` (ADR-062). Ranked worst-first: an "
        "unevidenced assertion nothing contradicts is the most dangerous cell there is, "
        "because it looks exactly like a good one.",
        "",
        "## Collapse ratio",
        "",
        f"- **All cells**: {summary['total']} — {summary['auto_accepted']} auto-accepted "
        f"({summary['auto_accepted'] / max(summary['total'], 1):.1%}), "
        f"{summary['escalated']} escalated",
        f"- **Asserted cells only** (excluding {summary['null_claims']} cells no channel "
        f"claimed a value for): {summary['asserted_total']} — "
        f"{summary['asserted_auto_accepted']} auto-accepted "
        f"({summary['asserted_auto_accepted'] / max(summary['asserted_total'], 1):.1%}), "
        f"{summary['asserted_escalated']} escalated",
        "",
        "The second figure is the honest one. Roughly half an invoice's schema is "
        "legitimately absent, and counting undisputed absences as collapsed work inflates "
        "the first.",
        "",
        "### By provenance class",
        "",
        "A cell can carry the strongest class and still be escalated — a printed value only "
        "one channel assigned to the field is `text-layer-proven` but unconfirmed on "
        "assignment.",
        "",
        "| Class | Cells | Accepted without review |",
        "|---|---:|---:|",
    ]
    for provenance in ProvenanceClass:
        lines.append(
            f"| `{provenance.value}` | {summary[provenance.value]} "
            f"| {summary[f'{provenance.value}/accepted']} |"
        )
    lines += ["", "### By escalation rank (worst first)", "", "| Rank | Cells |", "|---|---:|"]
    for rank in EscalationRank:
        lines.append(f"| {rank.value}. `{rank.label}` | {summary[rank.label]} |")

    lines += ["", "## Cells needing a decision", ""]
    for review in reviews:
        escalations = review.escalations
        if not escalations:
            continue
        lines += [
            f"### `{review.invoice_id}` (Tier {review.tier}) — "
            f"{len(escalations)} of {len(review.decisions)} cells",
            "",
        ]
        by_key = {
            cell["key"]: cell
            for document in manifest["documents"]
            if document["id"] == review.invoice_id
            for cell in document["cells"]
        }
        for decision in escalations:
            cell = by_key.get(decision.key, {})
            rank_label = decision.rank.label if decision.rank else "?"
            lines.append(f"- **`{decision.key}`** — {rank_label} · {decision.note}")
            for reading in decision.readings:
                if not reading.covered:
                    lines.append(f"  - `{reading.channel}`: *(cannot express this field)*")
                elif reading.value is None:
                    lines.append(f"  - `{reading.channel}`: *(nothing found)*")
                else:
                    confidence = (
                        f" (conf {reading.confidence:.2f})"
                        if reading.confidence is not None
                        else ""
                    )
                    evidenced = (
                        " **[printed]**" if reading.channel in decision.evidenced_channels else ""
                    )
                    lines.append(
                        f"  - `{reading.channel}`: `{reading.value}`{confidence}{evidenced}"
                    )
            context = cell.get("context")
            if context:
                lines.append(f"  - page text: …{context}…")
            lines.append("")

        mismatched = {
            group: counts
            for group, counts in review.group_counts.items()
            if len(set(counts.values())) > 1
        }
        if mismatched:
            lines.append("  Row-count disagreement (readers segmented the table differently):")
            for group, counts in mismatched.items():
                rendered = ", ".join(f"{name}={n}" for name, n in counts.items())
                lines.append(f"  - `{group}`: {rendered}")
            lines.append("")
    return "\n".join(lines) + "\n"


def _print_tier_table(reviews: Sequence[DocumentReview]) -> None:
    """Collapse ratio split by tier — a blended number would hide the point."""
    print(f"\n  {'TIER':<6} {'DOCS':>5} {'ASSERTED':>8} {'AUTO':>7} {'ESCALATED':>10} {'RATIO':>7}")
    for tier in ("A", "B"):
        tier_reviews = [r for r in reviews if r.tier == tier]
        if not tier_reviews:
            continue
        decisions = [d for r in tier_reviews for d in r.decisions]
        summary = collapse_summary(decisions)
        ratio = summary["asserted_auto_accepted"] / max(summary["asserted_total"], 1)
        print(
            f"  {tier:<6} {len(tier_reviews):>5} {summary['asserted_total']:>7} "
            f"{summary['asserted_auto_accepted']:>7} "
            f"{summary['asserted_escalated']:>10} {ratio:>6.1%}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="review_heldout_gt",
        description="Collapse held-out cells to the minimum needing author eyes (ADR-062).",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_HELDOUT_CORPUS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--ids", nargs="+", default=None)
    args = parser.parse_args(argv)

    items = load_heldout_index(args.corpus)
    if not items:
        print(f"No held-out index at {args.corpus / 'index.json'}.", file=sys.stderr)
        return 1
    if args.ids:
        wanted = set(args.ids)
        items = [item for item in items if item.id in wanted]
        if not items:
            print("No matching ids.", file=sys.stderr)
            return 1

    reviews: list[DocumentReview] = []
    for item in sorted(items, key=lambda i: i.id):
        review = review_document(item, args.corpus)
        if review is None:
            print(f"  {item.id}: no channel readings on disk — skipped", flush=True)
            continue
        reviews.append(review)

    if not reviews:
        print("Nothing to adjudicate.", file=sys.stderr)
        return 1

    manifest = build_manifest(reviews, args.corpus)
    out_dir = args.out_dir or (args.corpus / "_review")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "sheet.md").write_text(_render_sheet(reviews, manifest), encoding="utf-8")

    summary = manifest["summary"]
    print(f"\nAdjudicated {len(reviews)} document(s) across {len(CHANNEL_DIRS)} channels.")
    print(
        f"\nCOLLAPSE RATIO (asserted cells): {summary['asserted_auto_accepted']} of "
        f"{summary['asserted_total']} auto-accepted "
        f"({summary['asserted_auto_accepted'] / max(summary['asserted_total'], 1):.1%}); "
        f"{summary['asserted_escalated']} need an author."
    )
    print(
        f"  (all {summary['total']} cells incl. {summary['null_claims']} undisputed "
        f"absences: {summary['auto_accepted']} accepted "
        f"({summary['auto_accepted'] / max(summary['total'], 1):.1%}) — the wider "
        "denominator flatters the result, so the asserted figure leads.)"
    )
    _print_tier_table(reviews)

    print("\n  Provenance (cells in class / accepted without review):")
    for provenance in ProvenanceClass:
        count = summary[provenance.value]
        if count:
            accepted = summary[f"{provenance.value}/accepted"]
            print(f"    {provenance.value:<22} {count:>5} / {accepted:>5}")

    print("\n  Escalations by rank (worst first):")
    for rank in EscalationRank:
        count = summary[rank.label]
        if count:
            print(f"    {rank.value}. {rank.label:<26} {count:>5}")

    field_hotspots = Counter(decision.key for review in reviews for decision in review.escalations)
    if field_hotspots:
        print("\n  Most-escalated fields:")
        for key, count in field_hotspots.most_common(8):
            print(f"    {key:<28} {count:>4} document(s)")

    print(f"\nWrote {out_dir / 'manifest.json'} and {out_dir / 'sheet.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
