"""Promotion of adjudicated cells into a signed-off held-out GT document (ADR-062).

Hermetic: manifest cells are hand-built dicts in the shape `review_heldout_gt.py` emits, so
no corpus, no credentials, no PDFs.

The cases that matter are the ones where a plausible shortcut would rebuild the exact failure
this pipeline exists to undo: keeping a channel's proposal for a cell nobody reviewed, letting
`verified` be ticked over an unfinished document, or promoting over the draft channel that
adjudication still reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from horus.eval.adjudication import ProvenanceClass
from horus.eval.ground_truth import FIELDS
from horus.eval.heldout import build_groundtruth_from_json
from horus.eval.promotion import (
    PROMOTED_DIRNAME,
    PROMOTED_SCHEMA_VERSION,
    decisions_from_promoted,
    load_promoted,
    promoted_path,
    promotion_document,
    promotion_status,
    save_promoted,
)


def cell(
    key: str,
    *,
    value: str | None = None,
    auto_accepted: bool = True,
    provenance: str = ProvenanceClass.TEXT_LAYER_PROVEN.value,
    rank: str | None = None,
    readings: list[dict[str, Any]] | None = None,
    agreeing: list[str] | None = None,
    evidenced: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    """One manifest cell in the shape the review script writes."""
    return {
        "key": key,
        "value": value,
        "auto_accepted": auto_accepted,
        "provenance": provenance,
        "rank": rank,
        "readings": readings or [],
        "agreeing_channels": agreeing or [],
        "evidenced_channels": evidenced or [],
        "matched_text": value,
        "note": note,
    }


def build(
    cells: list[dict[str, Any]],
    decisions: dict[str, object] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return promotion_document(
        invoice_id="belege-de-email-001",
        language="german",
        channel="email",
        cells=cells,
        decisions=decisions or {},
        **kwargs,
    )


# ---------------------------------------------------------------------------
# What lands in `fields`
# ---------------------------------------------------------------------------


def test_auto_accepted_cells_carry_their_adjudicated_value() -> None:
    doc = build([cell("invoice_number", value="R-1", agreeing=["judge", "draft"])])
    assert doc["fields"]["invoice_number"] == "R-1"
    assert doc["provenance"]["invoice_number"]["class"] == ProvenanceClass.TEXT_LAYER_PROVEN.value
    assert doc["provenance"]["invoice_number"]["decided_by"] == "adjudication"


def test_an_unreviewed_escalation_is_null_not_the_proposed_value() -> None:
    """The single most important behaviour here.

    An escalated cell arrives with a proposed value attached. Keeping it because it is
    conveniently there would produce an answer key nobody checked that looks reviewed — the
    retracted 0.5692 in one line of code.
    """
    doc = build(
        [
            cell(
                "seller_name",
                value="Nordkap (GmbH & Co KG)",
                auto_accepted=False,
                provenance=ProvenanceClass.AUTHOR_ADJUDICATED.value,
                rank="nested-readings",
            )
        ]
    )
    assert doc["fields"]["seller_name"] is None
    assert doc["provenance"]["seller_name"]["escalated_as"] == "nested-readings"
    assert doc["provenance"]["seller_name"]["decided_by"] == "adjudication"


def test_an_answered_escalation_takes_the_authors_value() -> None:
    doc = build(
        [
            cell(
                "seller_name",
                value="NORDKAP",
                auto_accepted=False,
                provenance=ProvenanceClass.AUTHOR_ADJUDICATED.value,
                rank="nested-readings",
            )
        ],
        {"seller_name": "Nordkap (GmbH & Co KG)"},
    )
    assert doc["fields"]["seller_name"] == "Nordkap (GmbH & Co KG)"
    assert doc["provenance"]["seller_name"]["decided_by"] == "author"
    assert doc["provenance"]["seller_name"]["escalated_as"] == "nested-readings"


def test_an_author_can_decide_that_a_field_is_absent() -> None:
    """`None` is an answer, not a missing answer.

    Without this the author could never resolve a cell by saying "the invoice does not print
    it", which is the correct outcome for a channel that hallucinated a value.
    """
    doc = build(
        [cell("delivery_date", value="01.03.2024", auto_accepted=False, rank="null-disputed")],
        {"delivery_date": None},
    )
    assert doc["fields"]["delivery_date"] is None
    assert doc["provenance"]["delivery_date"]["decided_by"] == "author"


def test_an_author_answer_supersedes_the_gate_verdict() -> None:
    """A cell the author decided is `author-adjudicated`, even if the gate proved the string.

    The gate proves presence, never assignment; once a human has ruled on assignment, that
    is what the cell rests on and the record should say so.
    """
    doc = build(
        [
            cell(
                "seller_vat_id",
                value="DE111111111",
                auto_accepted=False,
                provenance=ProvenanceClass.TEXT_LAYER_PROVEN.value,
                rank="single-channel-proven",
                evidenced=["judge"],
            )
        ],
        {"seller_vat_id": "DE222222222"},
    )
    entry = doc["provenance"]["seller_vat_id"]
    assert entry["class"] == ProvenanceClass.AUTHOR_ADJUDICATED.value
    assert entry["evidenced_channels"] == ["judge"]


def test_every_registered_field_is_present_in_the_document() -> None:
    """An absent key must never be ambiguous between "not on the invoice" and "not looked at"."""
    doc = build([cell("invoice_number", value="R-1")])
    assert list(doc["fields"]) == list(FIELDS)
    assert set(doc["provenance"]) == set(FIELDS)


def test_a_field_missing_from_the_manifest_is_recorded_as_such() -> None:
    doc = build([cell("invoice_number", value="R-1")])
    entry = doc["provenance"]["seller_name"]
    assert entry["class"] == ProvenanceClass.NULL_CLAIM.value
    assert "manifest" in entry["note"]


# ---------------------------------------------------------------------------
# The verification gate
# ---------------------------------------------------------------------------


def test_verified_is_refused_while_an_escalation_is_unanswered() -> None:
    """A flag the author can tick over an unfinished document is how the retraction happened."""
    doc = build(
        [
            cell("invoice_number", value="R-1"),
            cell("seller_name", value="X", auto_accepted=False, rank="conflict-none-evidenced"),
        ],
        verified=True,
    )
    assert doc["verified"] is False
    assert doc["verified_date"] is None
    assert doc["sign_off"]["pending"] == 1


def test_verified_is_granted_once_every_escalation_is_answered() -> None:
    doc = build(
        [
            cell("invoice_number", value="R-1"),
            cell("seller_name", value="X", auto_accepted=False, rank="conflict-none-evidenced"),
        ],
        {"seller_name": "ACME GmbH"},
        verified=True,
    )
    assert doc["verified"] is True
    assert doc["verified_date"] is not None
    assert doc["sign_off"]["pending"] == 0


def test_partial_progress_is_saveable_without_claiming_verification() -> None:
    """A closed browser tab must not cost the author their work."""
    doc = build(
        [
            cell("seller_name", value="X", auto_accepted=False, rank="null-disputed"),
            cell("buyer_name", value="Y", auto_accepted=False, rank="null-disputed"),
        ],
        {"seller_name": "ACME GmbH"},
        verified=False,
    )
    assert doc["fields"]["seller_name"] == "ACME GmbH"
    assert doc["fields"]["buyer_name"] is None
    assert doc["verified"] is False


def test_status_counts_an_explicit_absence_as_decided() -> None:
    cells = [cell("delivery_date", auto_accepted=False, rank="null-disputed")]
    assert promotion_status(cells, {}).pending == 1
    assert promotion_status(cells, {"delivery_date": None}).complete


def test_status_ignores_decisions_for_cells_that_were_never_escalated() -> None:
    cells = [cell("invoice_number", value="R-1")]
    status = promotion_status(cells, {"invoice_number": "R-OVERRIDE"})
    assert status.escalated == 0
    assert status.complete


# ---------------------------------------------------------------------------
# On-disk shape and round-trip
# ---------------------------------------------------------------------------


def test_promotion_writes_beside_the_draft_never_over_it() -> None:
    """`gt/` is still a channel adjudication reads; overwriting it would fake agreement."""
    assert PROMOTED_DIRNAME != "gt"
    root = Path("/tmp/does-not-need-to-exist")
    assert promoted_path(root, "belege-de-email-001").parent.name == PROMOTED_DIRNAME


def test_the_scorer_reads_a_promoted_document_unchanged(tmp_path: Path) -> None:
    """`provenance` and `schema_version: 2` must be invisible to the scoring path.

    If they were not, published ZUGFeRD figures computed through the same reader would move.
    """
    doc = build(
        [cell("invoice_number", value="R-1"), cell("grand_total_amount", value="1.234,56")],
        line_items=[{"name": "Widget", "line_amount": "20,00"}],
    )
    path = save_promoted(tmp_path, doc)
    assert path == promoted_path(tmp_path, "belege-de-email-001")

    gt = build_groundtruth_from_json(path)
    assert gt.header["invoice_number"].raw_value == "R-1"
    assert gt.header["grand_total_amount"].normalized_value == "1234.56"
    assert gt.line_items is not None
    assert len(gt.line_items) == 1


def test_a_saved_document_declares_schema_version_two(tmp_path: Path) -> None:
    save_promoted(tmp_path, build([cell("invoice_number", value="R-1")]))
    on_disk = json.loads(promoted_path(tmp_path, "belege-de-email-001").read_text())
    assert on_disk["schema_version"] == PROMOTED_SCHEMA_VERSION
    assert on_disk["drafted_by"] == "adjudication"


def test_load_promoted_is_none_before_sign_off_starts(tmp_path: Path) -> None:
    assert load_promoted(tmp_path, "belege-de-email-001") is None


def test_a_sign_off_session_resumes_from_disk(tmp_path: Path) -> None:
    cells = [
        cell("invoice_number", value="R-1"),
        cell("seller_name", value="X", auto_accepted=False, rank="conflict-none-evidenced"),
    ]
    save_promoted(tmp_path, build(cells, {"seller_name": "ACME GmbH"}))
    reloaded = load_promoted(tmp_path, "belege-de-email-001")
    assert reloaded is not None
    resumed = decisions_from_promoted(reloaded)
    # Only the author's own answers come back — an adjudicated value must not be laundered
    # into a decision by a save/load cycle.
    assert resumed == {"seller_name": "ACME GmbH"}


def test_a_corrupt_promoted_file_reads_as_absent(tmp_path: Path) -> None:
    path = promoted_path(tmp_path, "belege-de-email-001")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_promoted(tmp_path, "belege-de-email-001") is None
