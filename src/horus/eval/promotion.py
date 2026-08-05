"""Promote adjudicated cells into a signed-off held-out GT document (ADR-062).

`adjudication` decides which cells carry a warrant and which need an author. This module is
the other half: it turns those decisions plus the author's answers into the answer key the
held-out evaluation actually grades against, and it stores **why every cell is believed**
next to the value itself.

Three properties are load-bearing.

**Provenance lives inside the document, never in a sidecar.** A warrant kept in a separate
file desyncs from the value it warrants the first time one of them is edited. `provenance` is
a sibling of `fields` in the same JSON object, so a value cannot travel without its reason.

**A promoted document is written to `_promoted/`, not over `gt/`.** The `gt/` tree is the
superseded text-layer draft, and it is still one of the three channels adjudication reads. If
promotion overwrote it, the next adjudication run would feed the answer key back in as an
"independent" channel and manufacture agreement with itself. Keeping the draft frozen also
preserves the record of what produced the retracted 0.5692 (ADR-011: supersede, never delete).

**Verification is gated on completeness, not on a checkbox.** `verified` can only be set when
every escalated cell has an author answer. The retraction happened because a GT was treated as
verified while nobody had looked; a flag the author can tick over an unfinished document
reproduces exactly that failure.

`build_groundtruth_from_json` reads `fields` / `vat_breakdown` / `skonto` / `line_items` and
ignores everything else, so `schema_version: 2` and `provenance` are invisible to the scorer
and published ZUGFeRD figures cannot move.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from horus.eval.adjudication import ProvenanceClass
from horus.eval.ground_truth import FIELDS

__all__ = [
    "PROMOTED_DIRNAME",
    "PROMOTED_SCHEMA_VERSION",
    "CellProvenance",
    "PromotionStatus",
    "decisions_from_promoted",
    "load_promoted",
    "promoted_path",
    "promotion_document",
    "promotion_status",
    "save_promoted",
]

#: Sub-directory of the corpus root holding one promoted `<id>.gt.json` per invoice.
#: Deliberately NOT `gt/` — see the module docstring on channel independence.
PROMOTED_DIRNAME: Final[str] = "_promoted"

#: Bumped from `GT_SCHEMA_VERSION = 1` because the document gains a `provenance` block.
#: Additive, so a v1 reader still finds everything it looks for.
PROMOTED_SCHEMA_VERSION: Final[int] = 2

#: `provenance.decided_by` for a cell an author answered themselves.
DECIDED_BY_AUTHOR: Final[str] = "author"

#: `provenance.decided_by` for a cell promoted on its adjudicated warrant alone.
DECIDED_BY_ADJUDICATION: Final[str] = "adjudication"


@dataclass(frozen=True)
class CellProvenance:
    """Why one promoted cell is believed."""

    key: str
    provenance: str
    decided_by: str
    channels: tuple[str, ...] = ()
    evidenced_channels: tuple[str, ...] = ()
    matched_text: str | None = None
    rank: str | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "class": self.provenance,
            "decided_by": self.decided_by,
            "channels": list(self.channels),
            "evidenced_channels": list(self.evidenced_channels),
            "matched_text": self.matched_text,
            "escalated_as": self.rank,
            "note": self.note,
        }


@dataclass(frozen=True)
class PromotionStatus:
    """How far one document's sign-off has got."""

    invoice_id: str
    total: int
    auto_accepted: int
    escalated: int
    decided: int

    @property
    def pending(self) -> int:
        return self.escalated - self.decided

    @property
    def complete(self) -> bool:
        """Whether every escalated cell has an author answer.

        The gate on `verified`. An incomplete document can still be saved — partial progress
        must survive a closed browser tab — it just cannot claim verification.
        """
        return self.pending == 0


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell_key(cell: Mapping[str, Any]) -> str:
    return str(cell.get("key", ""))


def _is_escalated(cell: Mapping[str, Any]) -> bool:
    """Whether this manifest cell needs an author.

    Reads `auto_accepted` rather than re-deriving it from `rank`, so the manifest stays the
    single source of truth for what was accepted and this module cannot drift from the
    combiner that produced it.
    """
    return not bool(cell.get("auto_accepted", False))


def promotion_status(
    cells: Sequence[Mapping[str, Any]], decisions: Mapping[str, object]
) -> PromotionStatus:
    """Count where one document stands, without building the document.

    Args:
        cells: the manifest's `cells` list for one invoice.
        decisions: `{field_key: value}` author answers. A key present with `None` is a
            decision — "absent on this invoice" — and counts as answered. A key that is
            simply missing has not been looked at.
    """
    escalated = [cell for cell in cells if _is_escalated(cell)]
    answered = sum(1 for cell in escalated if _cell_key(cell) in decisions)
    return PromotionStatus(
        invoice_id="",
        total=len(cells),
        auto_accepted=len(cells) - len(escalated),
        escalated=len(escalated),
        decided=answered,
    )


def _provenance_for(cell: Mapping[str, Any], *, decided: bool, escalated: bool) -> CellProvenance:
    key = _cell_key(cell)
    adjudicated = str(cell.get("provenance", ProvenanceClass.AUTHOR_ADJUDICATED.value))
    readings = cell.get("readings")
    channels = (
        tuple(str(r.get("channel")) for r in readings if isinstance(r, Mapping))
        if isinstance(readings, Sequence)
        else ()
    )
    evidenced = cell.get("evidenced_channels")
    agreeing = cell.get("agreeing_channels")
    if decided:
        # The author's answer replaces the class outright rather than being recorded
        # alongside it. A cell an author decided is `author-adjudicated` even where the gate
        # had also proved the string, because what makes it trustworthy now is the human
        # judgement about ASSIGNMENT, which the gate cannot supply.
        return CellProvenance(
            key=key,
            provenance=ProvenanceClass.AUTHOR_ADJUDICATED.value,
            decided_by=DECIDED_BY_AUTHOR,
            channels=channels,
            evidenced_channels=tuple(evidenced) if isinstance(evidenced, Sequence) else (),
            matched_text=_as_text(cell.get("matched_text")),
            rank=_as_text(cell.get("rank")),
            note="answered by the author at sign-off",
        )
    return CellProvenance(
        key=key,
        provenance=adjudicated,
        decided_by=DECIDED_BY_ADJUDICATION,
        channels=tuple(agreeing) if isinstance(agreeing, Sequence) else (),
        evidenced_channels=tuple(evidenced) if isinstance(evidenced, Sequence) else (),
        matched_text=_as_text(cell.get("matched_text")),
        rank=_as_text(cell.get("rank")) if escalated else None,
        note=str(cell.get("note", "")),
    )


def promotion_document(
    *,
    invoice_id: str,
    language: str,
    channel: str,
    cells: Sequence[Mapping[str, Any]],
    decisions: Mapping[str, object],
    vat_breakdown: Sequence[Mapping[str, str | None]] | None = None,
    skonto: Sequence[Mapping[str, str | None]] | None = None,
    line_items: Sequence[Mapping[str, str | None]] | None = None,
    verified: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    """Assemble the `schema_version: 2` promoted GT document for one invoice.

    Every registered field appears in `fields`, so an absent key is never ambiguous between
    "absent on the invoice" and "we forgot to look". Cell sourcing:

    - **auto-accepted** — the adjudicated value, with its provenance class carried over.
    - **escalated and answered** — the author's answer, recorded as `author-adjudicated`.
    - **escalated and unanswered** — `None`. An unreviewed escalation must NOT silently keep
      whichever value a channel proposed; that is the exact move that produced a GT nobody
      had checked.

    `verified` is refused unless every escalated cell is answered — a half-finished document
    can be saved, but it cannot claim verification.
    """
    by_key = {_cell_key(cell): cell for cell in cells if _cell_key(cell)}
    status = promotion_status(cells, decisions)

    fields: dict[str, str | None] = {}
    provenance: dict[str, Any] = {}
    for key in FIELDS:
        cell = by_key.get(key)
        if cell is None:
            # The manifest predates a field being registered. Honest null, and the gap is
            # visible in the provenance block rather than looking like a null claim.
            fields[key] = None
            provenance[key] = CellProvenance(
                key=key,
                provenance=ProvenanceClass.NULL_CLAIM.value,
                decided_by=DECIDED_BY_ADJUDICATION,
                note="no channel read this field; absent from the adjudication manifest",
            ).as_dict()
            continue
        escalated = _is_escalated(cell)
        decided = escalated and key in decisions
        if decided:
            fields[key] = _as_text(decisions[key])
        elif escalated:
            fields[key] = None
        else:
            fields[key] = _as_text(cell.get("value"))
        provenance[key] = _provenance_for(cell, decided=decided, escalated=escalated).as_dict()

    return {
        "schema_version": PROMOTED_SCHEMA_VERSION,
        "id": invoice_id,
        "language": language,
        "channel": channel,
        "drafted_by": "adjudication",
        "verified": bool(verified) and status.complete,
        "verified_date": (
            datetime.now(UTC).strftime("%Y-%m-%d") if verified and status.complete else None
        ),
        "notes": notes,
        "fields": fields,
        "provenance": provenance,
        "vat_breakdown": [dict(row) for row in vat_breakdown] if vat_breakdown else None,
        "skonto": [dict(row) for row in skonto] if skonto else None,
        "line_items": [dict(row) for row in line_items] if line_items else None,
        "sign_off": {
            "cells": status.total,
            "auto_accepted": status.auto_accepted,
            "escalated": status.escalated,
            "decided": status.decided,
            "pending": status.pending,
        },
    }


def promoted_path(corpus_root: Path, invoice_id: str) -> Path:
    """Where the promoted answer key for one invoice lives."""
    return corpus_root / PROMOTED_DIRNAME / f"{invoice_id}.gt.json"


def save_promoted(corpus_root: Path, document: Mapping[str, Any]) -> Path:
    """Write a promoted document into the git-ignored corpus tree."""
    invoice_id = str(document.get("id", ""))
    if not invoice_id:
        raise ValueError("promoted document has no id")
    path = promoted_path(corpus_root, invoice_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_promoted(corpus_root: Path, invoice_id: str) -> dict[str, Any] | None:
    """Read a promoted document back, or `None` when sign-off has not started."""
    path = promoted_path(corpus_root, invoice_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def decisions_from_promoted(document: Mapping[str, Any]) -> dict[str, str | None]:
    """Recover the author's answers from a saved promoted document.

    Lets a sign-off session resume: only cells whose provenance says an author decided them
    are returned, so re-opening a document does not silently convert adjudicated values into
    author decisions.
    """
    fields = document.get("fields")
    provenance = document.get("provenance")
    if not isinstance(fields, Mapping) or not isinstance(provenance, Mapping):
        return {}
    return {
        str(key): _as_text(fields.get(key))
        for key, entry in provenance.items()
        if isinstance(entry, Mapping) and entry.get("decided_by") == DECIDED_BY_AUTHOR
    }
