"""Audit which held-out answer-key cells the scorer excludes, and why.

The held-out evaluation grades a prediction against a signed-off answer key, and the
scorer has a fourth ground-truth state besides absent / empty / content:
`normalizer_rejected`, which it reports as EXCLUDED — the cell is dropped from the
denominator entirely (`scorer.py` truth table). Two entirely different situations reach
that state through the same `normalized_value is None` encoding:

1. **Ratified neutralisation.** The field opts in via `FieldSpec.neutralize_when_unlocatable`
   AND this invoice's warrant records that no adjudication channel could locate the value
   in the page text. A deliberate, documented decision (ADR-065): scoring a model against
   a value that is not on the page measures the answer key, not the model.

2. **The parser rejected the author's own value.** The cell went through
   `validate_and_repair` and came back `None`, so the signed-off value could not be coerced
   to its declared type. Nobody decided this; it is a silent consequence of a locale-parsing
   gap, and it removes cells the model should have been graded on.

Both are invisible in every aggregate: an excluded cell leaves no trace in F1, precision or
recall, and the corpus-level cell count is reported after exclusion. Only a per-cell pass
separates them, which is what this script is for.

Read-only. Loads each document through `build_groundtruth_from_json` — the same loader the
evaluation uses — and classifies every header cell with the scorer's own `_gt_state`, so this
report cannot drift from what the scorer actually does.

Scope: the registered header fields only. Repeating groups (VAT breakdown, discount rows,
line items) are excluded structurally from the held-out grading, so their cells are not part
of the population this audits.

Privacy: invoice field values are private (ADR-040). Stdout carries counts, field NAMES and
document ids only, so a terminal transcript is safe to paste into a pull request.

Usage:
    uv run python scripts/audit_heldout_exclusions.py
    uv run python scripts/audit_heldout_exclusions.py --ids belege-de-email-001
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from horus.eval.ground_truth import FIELDS  # noqa: E402
from horus.eval.heldout import (  # noqa: E402
    _is_unlocatable_and_neutralized,
    build_groundtruth_from_json,
)
from horus.eval.promotion import PROMOTED_DIRNAME  # noqa: E402
from horus.eval.scorer import _gt_state  # noqa: E402
from horus.finetune.dataset import DEFAULT_HELDOUT_CORPUS_ROOT  # noqa: E402

#: Cause label for an exclusion the project decided on and documented (ADR-065).
CAUSE_RATIFIED = "ratified neutralisation (ADR-065)"

#: Cause label for an exclusion nobody chose: the answer key's own value failed to parse.
CAUSE_PARSER = "answer-key value the parser rejected"


@dataclass(frozen=True)
class ExcludedCell:
    """One header cell the scorer will drop from the denominator."""

    invoice_id: str
    language: str
    channel: str
    field: str
    field_type: str
    cause: str


@dataclass
class DocumentAudit:
    """One document's header-cell state census plus its excluded cells."""

    invoice_id: str
    language: str
    channel: str
    states: Counter[str]
    excluded: list[ExcludedCell]


def audit_document(path: Path) -> DocumentAudit:
    """Classify every registered header cell of one signed-off document."""
    raw: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    invoice_id = str(raw.get("id") or path.name.removesuffix(".gt.json"))
    provenance = raw.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else None
    ground_truth = build_groundtruth_from_json(path)

    states: Counter[str] = Counter()
    excluded: list[ExcludedCell] = []
    for english_key, spec in FIELDS.items():
        gt_field = ground_truth.header.get(english_key)
        if gt_field is None:
            continue
        state = _gt_state(gt_field)
        states[state] += 1
        if state != "normalizer_rejected":
            continue
        cause = (
            CAUSE_RATIFIED if _is_unlocatable_and_neutralized(spec, provenance) else CAUSE_PARSER
        )
        excluded.append(
            ExcludedCell(
                invoice_id=invoice_id,
                language=str(raw.get("language", "?")),
                channel=str(raw.get("channel", "?")),
                field=english_key,
                field_type=spec.field_type,
                cause=cause,
            )
        )
    return DocumentAudit(
        invoice_id=invoice_id,
        language=str(raw.get("language", "?")),
        channel=str(raw.get("channel", "?")),
        states=states,
        excluded=excluded,
    )


def _print_counter(title: str, counts: Counter[str], *, width: int = 38) -> None:
    if not counts:
        return
    print(f"\n{title}", flush=True)
    for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {key:<{width}} {count:>4}", flush=True)


def print_report(audits: list[DocumentAudit]) -> None:
    """Counts, field names and document ids only — safe for a terminal transcript."""
    excluded = [cell for audit in audits for cell in audit.excluded]
    states: Counter[str] = Counter()
    for audit in audits:
        states.update(audit.states)
    graded_cells = sum(states.values())

    print("\nHeld-out answer key — exclusion audit", flush=True)
    print(
        f"\n{len(audits)} documents x {len(FIELDS)} registered header fields "
        f"= {graded_cells} header cells.",
        flush=True,
    )
    print(
        "Repeating groups are out of scope: the held-out evaluation grades header fields only.",
        flush=True,
    )
    print("Counts, field names and document ids only; no field values (ADR-040).", flush=True)

    print("\nHeader cell states (the scorer's own classification)", flush=True)
    for state in ("absent", "present_empty", "present_content", "normalizer_rejected"):
        suffix = "  -> EXCLUDED from scoring" if state == "normalizer_rejected" else ""
        print(f"  {state:<22} {states.get(state, 0):>4}{suffix}", flush=True)

    if not excluded:
        print("\nNo header cell is excluded. Nothing to disclose.", flush=True)
        return

    _print_counter("EXCLUDED cells by cause", Counter(c.cause for c in excluded), width=42)

    for cause in (CAUSE_RATIFIED, CAUSE_PARSER):
        cells = [c for c in excluded if c.cause == cause]
        if not cells:
            continue
        _print_counter(
            f"{cause} — by field",
            Counter(f"{c.field} ({c.field_type})" for c in cells),
        )
        _print_counter(
            f"{cause} — by language / channel",
            Counter(f"{c.language} / {c.channel}" for c in cells),
        )
        _print_counter(
            f"{cause} — by document",
            Counter(c.invoice_id for c in cells),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit_heldout_exclusions",
        description="Audit which held-out answer-key cells the scorer excludes, and why.",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_HELDOUT_CORPUS_ROOT)
    parser.add_argument("--ids", nargs="+", default=None, help="Audit these ids only.")
    args = parser.parse_args(argv)

    promoted_dir = args.corpus / PROMOTED_DIRNAME
    paths = sorted(promoted_dir.glob("*.gt.json"))
    if not paths:
        print(f"No signed-off answer key under {promoted_dir}.", file=sys.stderr)
        return 1
    if args.ids:
        wanted = set(args.ids)
        paths = [p for p in paths if p.name.removesuffix(".gt.json") in wanted]
        if not paths:
            print(f"No signed-off document matches: {', '.join(sorted(wanted))}", file=sys.stderr)
            return 1

    print_report([audit_document(path) for path in paths])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
