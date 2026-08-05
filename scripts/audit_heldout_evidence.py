"""Tier the held-out corpus and audit its ground truth against printed evidence.

This is the reproducible replacement for the ad-hoc measurements that produced the
Tier A / Tier B split. Those numbers are now load-bearing — they justify retracting a
published score — so they must be re-derivable by command rather than quoted from a chat
log.

Two questions, answered separately because they have different kinds of answer:

1. **Which documents can be settled deterministically?** A born-digital PDF carries the
   issuer's own embedded character codes, so a value either appears in them or does not.
   A scanned PDF carries no text layer at all, and for those the previous drafter had no
   input whatsoever — every value it produced for them was invented.

2. **Does the current draft GT survive the printed-evidence gate?** Per cell, not per
   document, because "this invoice is 80 % right" is not actionable while "this cell is
   unevidenced" is.

Deliberately NOT a pass/fail gate on the corpus: the report's purpose is to size and
locate the work, and a single aggregate number would hide exactly the per-cell detail the
review step needs.

Privacy: invoice field values are private (ADR-040). Values are written only into the
git-ignored corpus tree; stdout carries counts and field NAMES only, so a terminal
transcript is safe to paste.

Usage:
    uv run python scripts/audit_heldout_evidence.py
    uv run python scripts/audit_heldout_evidence.py --ids belege-en-email-001
    uv run python scripts/audit_heldout_evidence.py --gt-source judge
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.eval.heldout import load_heldout_index  # noqa: E402
from horus.eval.printed_evidence import (  # noqa: E402
    EvidenceResult,
    EvidenceStatus,
    TextLayer,
    check_gt_document,
    extract_text_layer,
)
from horus.finetune.dataset import DEFAULT_HELDOUT_CORPUS_ROOT  # noqa: E402

#: Presentation order for cells needing review, most alarming first. A fabricated value
#: outranks a merely weak match, and `FOUND` is included (and last) because a weak match
#: still needs a second opinion — omitting it here previously crashed the renderer.
_REVIEW_ORDER: tuple[EvidenceStatus, ...] = (
    EvidenceStatus.NOT_FOUND,
    EvidenceStatus.UNPARSEABLE,
    EvidenceStatus.NO_TEXT_LAYER,
    EvidenceStatus.EXEMPT,
    EvidenceStatus.NULL_CLAIM,
    EvidenceStatus.FOUND,
)


def _review_rank(status: EvidenceStatus) -> int:
    """Sort rank for review presentation; unknown statuses sort last rather than raise."""
    try:
        return _REVIEW_ORDER.index(status)
    except ValueError:
        return len(_REVIEW_ORDER)


#: Below this share of asserted cells evidenced, a text layer is not the invoice's own.
#:
#: `belege-de-email-014` is the motivating case: 102 extractable words, but only 3 of 17
#: asserted cells evidenced, while its GT is internally consistent (594,37 + 112,93 =
#: 707,30). The text layer belongs to a covering email page, not the invoice. Treating
#: "has words" as "is settleable" would route it down the deterministic path where nothing
#: can actually settle it.
LOW_YIELD_THRESHOLD = 0.5

#: Yield is only meaningful once GT asserts enough cells to be a sample rather than noise.
MIN_ASSERTED_FOR_YIELD = 5


@dataclass
class InvoiceAudit:
    """One invoice's tier assignment and per-cell gate verdicts."""

    invoice_id: str
    language: str
    channel: str
    layer: TextLayer
    results: list[EvidenceResult]
    gt_present: bool

    @property
    def evidence_yield(self) -> float | None:
        """Share of asserted cells the text layer evidences; None when GT asserts too few."""
        if len(self.asserted) < MIN_ASSERTED_FOR_YIELD:
            return None
        return len(self.proven) / len(self.asserted)

    @property
    def text_layer_authoritative(self) -> bool:
        """Whether this PDF's text layer can actually settle this invoice's values.

        A text layer may exist and still be the wrong text layer — a covering page, a
        mail body, a footer template. Presence is necessary but not sufficient, and the
        observable difference is that an authoritative layer evidences most of what GT
        asserts while an unrelated one evidences almost none of it.

        Low yield could in principle mean "bad GT" rather than "bad text layer"; both
        conclusions route the document to the same place (the second channel), so the
        ambiguity costs nothing operationally and is not worth guessing about.
        """
        if not self.layer.exists:
            return False
        yield_ = self.evidence_yield
        return yield_ is None or yield_ >= LOW_YIELD_THRESHOLD

    @property
    def tier(self) -> str:
        """`A` deterministically settleable; `A?` text layer present but not authoritative;
        `B` no text layer at all.
        """
        if not self.layer.exists:
            return "B"
        return "A" if self.text_layer_authoritative else "A?"

    @property
    def asserted(self) -> list[EvidenceResult]:
        """Cells where GT claims a value — the ones that can be right or wrong."""
        return [r for r in self.results if r.value is not None]

    @property
    def proven(self) -> list[EvidenceResult]:
        return [r for r in self.asserted if r.is_proven]

    @property
    def unevidenced(self) -> list[EvidenceResult]:
        """Asserted values with no printed evidence — the retraction's actual population."""
        return [
            r
            for r in self.asserted
            if r.status in {EvidenceStatus.NOT_FOUND, EvidenceStatus.NO_TEXT_LAYER}
        ]


def _load_gt(path: Path) -> tuple[Mapping[str, object], Mapping[str, Sequence[Mapping]], bool]:
    """Load a GT document's fields and groups; report whether the file existed."""
    if not path.is_file():
        return {}, {}, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, {}, False
    fields = data.get("fields", {})
    groups = {name: data.get(name, []) or [] for name in ("vat_breakdown", "skonto", "line_items")}
    return (fields if isinstance(fields, dict) else {}), groups, True


def audit_invoice(item, gt_path: Path) -> InvoiceAudit:
    """Extract the text layer and run every GT cell through the printed-evidence gate."""
    layer = extract_text_layer(item.pdf_path)
    fields, groups, present = _load_gt(gt_path)
    return InvoiceAudit(
        invoice_id=item.id,
        language=item.language,
        channel=item.channel,
        layer=layer,
        results=check_gt_document(fields, groups, layer),
        gt_present=present,
    )


def render_report(audits: list[InvoiceAudit], gt_source: str) -> str:
    """Per-cell markdown report for the review step. Contains PRIVATE values."""
    lines = [
        f"# Held-out GT — printed-evidence audit (`{gt_source}` GT)",
        "",
        "PRIVATE — contains invoice field values. Git-ignored tree; never commit.",
        "",
        "`proven` = the value appears in the PDF's own embedded text layer, so it cannot "
        "be a fabrication. It does NOT prove the value was filed under the right field — "
        "assignment is settled by the independent vision channel.",
        "",
    ]
    for audit in sorted(audits, key=lambda a: (a.tier, a.invoice_id)):
        lines += [
            f"## `{audit.invoice_id}` — Tier {audit.tier} "
            f"({audit.language}/{audit.channel}, {audit.layer.word_count} words)",
            "",
        ]
        if not audit.gt_present:
            lines += ["No GT file for this invoice.", ""]
            continue
        lines.append(
            f"- asserted **{len(audit.asserted)}** cells, "
            f"proven **{len(audit.proven)}**, unevidenced **{len(audit.unevidenced)}**"
        )
        lines.append("")
        flagged = [r for r in audit.asserted if not r.is_proven]
        if not flagged:
            lines += ["Every asserted cell is deterministically evidenced.", ""]
            continue
        lines += ["| cell | GT value | verdict | matched |", "|---|---|---|---|"]
        for result in sorted(flagged, key=lambda r: (_review_rank(r.status), r.key)):
            lines.append(
                f"| `{result.key}` | {result.value} | {result.status.value}"
                f"{' (weak)' if result.weak else ''} | {result.matched or ''} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def print_summary(audits: list[InvoiceAudit]) -> None:
    """Counts and field names only — safe for a terminal transcript."""
    tier_a = [a for a in audits if a.tier == "A"]
    tier_weak = [a for a in audits if a.tier == "A?"]
    tier_b = [a for a in audits if a.tier == "B"]

    print("\nCorpus tiering (by usable printed evidence, not mere text-layer presence)", flush=True)
    print(f"  Tier A  — authoritative text layer      : {len(tier_a):>3} docs", flush=True)
    print(f"  Tier A? — text layer present, low yield : {len(tier_weak):>3} docs", flush=True)
    print(f"  Tier B  — NO text layer                 : {len(tier_b):>3} docs", flush=True)
    if tier_weak:
        print(
            "          (A? needs the second channel too — the layer is not the invoice's)",
            flush=True,
        )

    for label, group in (("Tier A", tier_a), ("Tier A?", tier_weak), ("Tier B", tier_b)):
        if not group:
            continue
        asserted = sum(len(a.asserted) for a in group)
        proven = sum(len(a.proven) for a in group)
        unevidenced = sum(len(a.unevidenced) for a in group)
        print(f"\n{label} — draft GT under the gate", flush=True)
        print(f"  asserted cells     : {asserted:>4}", flush=True)
        print(f"  proven             : {proven:>4}", flush=True)
        print(f"  unevidenced        : {unevidenced:>4}", flush=True)

    unparseable = [r for a in audits for r in a.results if r.status is EvidenceStatus.UNPARSEABLE]
    if unparseable:
        print(
            f"\nGT values not parseable as their declared type: {len(unparseable)}",
            flush=True,
        )
        for result in unparseable[:10]:
            print(f"  {result.key}", flush=True)

    print("\nPer-invoice (asserted / proven / unevidenced)", flush=True)
    for audit in sorted(audits, key=lambda a: (a.tier, a.invoice_id)):
        marker = "" if audit.tier == "A" else "  <- no deterministic source"
        print(
            f"  {audit.tier:<2} {audit.invoice_id:<24} "
            f"{len(audit.asserted):>3} / {len(audit.proven):>3} / "
            f"{len(audit.unevidenced):>3}{marker}",
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit_heldout_evidence",
        description="Tier the held-out corpus and audit GT against printed evidence.",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_HELDOUT_CORPUS_ROOT)
    parser.add_argument(
        "--gt-source",
        default="draft",
        choices=["draft", "judge"],
        help="Which GT to audit: the live draft tree, or the judge's output.",
    )
    parser.add_argument("--ids", nargs="+", default=None, help="Audit these ids only.")
    parser.add_argument("--report", type=Path, default=None, help="Override report path.")
    args = parser.parse_args(argv)

    items = load_heldout_index(args.corpus)
    if not items:
        print(f"No held-out index at {args.corpus / 'index.json'}.", file=sys.stderr)
        return 1
    if args.ids:
        by_id = {item.id: item for item in items}
        unknown = [i for i in args.ids if i not in by_id]
        if unknown:
            print(f"Unknown ids: {', '.join(unknown)}", file=sys.stderr)
            return 1
        items = [by_id[i] for i in args.ids]

    judge_gt_dir = args.corpus / "_judge" / "gt"
    audits: list[InvoiceAudit] = []
    for item in items:
        gt_path = item.gt_path if args.gt_source == "draft" else judge_gt_dir / f"{item.id}.gt.json"
        audits.append(audit_invoice(item, gt_path))
        print(f"  audited {item.id}", flush=True)

    missing = [a.invoice_id for a in audits if not a.gt_present]
    if missing:
        print(
            f"\nNo `{args.gt_source}` GT for {len(missing)} invoice(s): "
            f"{', '.join(missing[:5])}{' …' if len(missing) > 5 else ''}",
            flush=True,
        )

    print_summary(audits)

    report_path = args.report or (args.corpus / "_audit" / f"evidence-{args.gt_source}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(audits, args.gt_source), encoding="utf-8")
    print(f"\nPer-cell report (PRIVATE) -> {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
