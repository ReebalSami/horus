"""Data bridge for the held-out sign-off page (ADR-062).

Hermetic: the manifest readers are pure functions over dicts, so no corpus is needed.

These are worth testing because their failure mode is silent and dangerous in one direction:
a reader that returns `{}` on a malformed manifest makes the page render "nothing to review",
which is indistinguishable from "everything is settled".
"""

from __future__ import annotations

from typing import Any

import pytest

from app.data import heldout as heldout_data


def test_manifest_documents_are_keyed_by_invoice_id() -> None:
    manifest: dict[str, Any] = {
        "documents": [
            {"id": "belege-de-email-001", "tier": "A"},
            {"id": "belege-de-scan-001", "tier": "B"},
        ]
    }
    assert set(heldout_data.manifest_documents(manifest)) == {
        "belege-de-email-001",
        "belege-de-scan-001",
    }


def test_manifest_entries_without_an_id_are_skipped_not_crashed_on() -> None:
    manifest: dict[str, Any] = {"documents": [{"tier": "A"}, "junk", {"id": "ok"}]}
    assert list(heldout_data.manifest_documents(manifest)) == ["ok"]


def test_a_manifest_without_documents_yields_nothing() -> None:
    assert heldout_data.manifest_documents({}) == {}
    assert heldout_data.manifest_documents({"documents": "not-a-list"}) == {}


def test_manifest_cells_drops_non_object_entries() -> None:
    document: dict[str, Any] = {"cells": [{"key": "invoice_number"}, None, 7]}
    assert heldout_data.manifest_cells(document) == [{"key": "invoice_number"}]


def test_manifest_cells_of_a_document_without_cells_is_empty() -> None:
    assert heldout_data.manifest_cells({}) == []


def test_sign_off_progress_counts_only_escalated_cells() -> None:
    cells: list[dict[str, Any]] = [
        {"key": "invoice_number", "auto_accepted": True},
        {"key": "seller_name", "auto_accepted": False},
        {"key": "buyer_name", "auto_accepted": False},
    ]
    assert heldout_data.sign_off_progress(cells, {}) == (0, 2)
    assert heldout_data.sign_off_progress(cells, {"seller_name": "ACME GmbH"}) == (1, 2)
    # An explicit absence is an answer.
    assert heldout_data.sign_off_progress(cells, {"seller_name": "X", "buyer_name": None}) == (2, 2)


def test_an_unknown_channel_name_is_a_programming_error() -> None:
    """Fail loudly. A typo'd channel returning `None` would look like "that channel has not
    read this invoice", which is a legitimate state and would hide the bug indefinitely."""
    item = heldout_data.list_items()
    probe = item[0] if item else None
    if probe is None:
        pytest.skip("private held-out corpus not present on this machine")
    with pytest.raises(KeyError):
        heldout_data.load_channel_document(probe, "not-a-channel")
