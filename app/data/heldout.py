"""Data layer for the Ground-Truth Review page (held-out Belege set; ADR-040).

Streamlit-free, unit-testable helpers that bridge `horus.eval.heldout` to the
review page: list the indexed invoices, load a draft answer key for editing, render
the page image(s), and save a (verified) answer key back to disk. Everything here
operates under the git-ignored `data/self-collected/**` tree — this is the one
WRITE surface in the app (the research pages stay read-only; ADR-036/039), because
producing ground truth is inherently an annotation task.

`verified` is authoritative in the per-invoice GT file (what the page writes); on
save we also refresh the cached `verified` flag in `index.json` so the loader +
datasheet stay in sync without a separate re-index run.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from horus.eval.ground_truth import REPEATING_GROUPS
from horus.eval.heldout import (
    INDEX_FILENAME,
    HeldoutItem,
    gt_document,
    load_heldout_index,
)
from horus.eval.rasterize import rasterize_pdf

# Repo root: app/data/heldout.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = _REPO_ROOT / "data" / "self-collected"

# Page-image render cache (gitignored — lives under the private data tree).
_PAGE_CACHE = CORPUS_ROOT / "_pagecache"

# The evaluation rasterization resolution (matches configs/pilot-13.yaml + live.py).
EVAL_DPI = 300


def corpus_root() -> Path:
    """Absolute path to the held-out corpus root."""
    return CORPUS_ROOT


def repeating_subkeys(group_key: str) -> list[str]:
    """Ordered sub-field keys for a repeating group (the review grid's columns)."""
    return list(REPEATING_GROUPS[group_key][1].keys())


def _clean_rows(
    rows: Sequence[Mapping[str, object]] | None,
) -> list[dict[str, str | None]] | None:
    """Strip + null-blank each cell; drop fully-empty rows; `None` if nothing remains."""
    if not rows:
        return None
    cleaned: list[dict[str, str | None]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        cells: dict[str, str | None] = {
            str(key): (str(value).strip() if value is not None and str(value).strip() else None)
            for key, value in row.items()
        }
        if any(value is not None for value in cells.values()):
            cleaned.append(cells)
    return cleaned or None


def list_items() -> list[HeldoutItem]:
    """All indexed held-out invoices (empty if the set hasn't been indexed yet)."""
    return load_heldout_index(CORPUS_ROOT)


def load_draft(item: HeldoutItem) -> dict[str, object]:
    """Load the editable draft document for one invoice (or a blank document).

    Returns the full GT document shape (`{"fields": {...}, "verified": ..., ...}`).
    If no draft file exists yet, returns a blank document with all fields `None`.
    """
    if item.gt_path.is_file():
        data = json.loads(item.gt_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("fields", {})
            return data
    return gt_document(
        invoice_id=item.id,
        language=item.language,
        channel=item.channel,
        fields={},
        drafted_by="cascade",
        verified=False,
    )


def save_draft(
    item: HeldoutItem,
    *,
    fields: dict[str, str | None],
    verified: bool,
    notes: str = "",
    drafted_by: str = "cascade",
    vat_breakdown: Sequence[Mapping[str, object]] | None = None,
    skonto: Sequence[Mapping[str, object]] | None = None,
    line_items: Sequence[Mapping[str, object]] | None = None,
) -> Path:
    """Write the (verified) answer key for one invoice + refresh the index flag.

    Empty/whitespace-only field values are stored as `None` (honest absence); the
    same applies per-cell to the repeating-group rows, and fully-empty rows are
    dropped. The GT file's `verified` is authoritative; `index.json`'s cached flag
    is updated to match so the loader + datasheet need no separate re-index.
    """
    cleaned: dict[str, str | None] = {
        key: (value.strip() if isinstance(value, str) and value.strip() else None)
        for key, value in fields.items()
    }
    doc = gt_document(
        invoice_id=item.id,
        language=item.language,
        channel=item.channel,
        fields=cleaned,
        vat_breakdown=_clean_rows(vat_breakdown),
        skonto=_clean_rows(skonto),
        line_items=_clean_rows(line_items),
        drafted_by=drafted_by,
        verified=verified,
        verified_date=datetime.now(UTC).strftime("%Y-%m-%d") if verified else None,
        notes=notes,
    )
    item.gt_path.parent.mkdir(parents=True, exist_ok=True)
    item.gt_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    _refresh_index_verified(item.id, verified)
    return item.gt_path


def page_images(item: HeldoutItem) -> list[Path]:
    """Rasterize the invoice's pages to cached PNGs (empty list if unavailable)."""
    if not item.pdf_path.is_file():
        return []
    try:
        return rasterize_pdf(item.pdf_path, dpi=EVAL_DPI, cache_dir=_PAGE_CACHE)
    except Exception:  # noqa: BLE001 — a corrupt/locked PDF yields no preview, not a crash
        return []


def progress() -> tuple[int, int]:
    """Return `(n_verified, n_total)` across the indexed set."""
    items = list_items()
    return sum(1 for item in items if item.verified), len(items)


def _refresh_index_verified(invoice_id: str, verified: bool) -> None:
    """Update the cached `verified` flag for one id in index.json (best-effort)."""
    index_path = CORPUS_ROOT / INDEX_FILENAME
    if not index_path.is_file():
        return
    data = json.loads(index_path.read_text(encoding="utf-8"))
    changed = False
    for entry in data.get("items", []):
        if isinstance(entry, dict) and entry.get("id") == invoice_id:
            entry["verified"] = verified
            changed = True
            break
    if changed:
        index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
