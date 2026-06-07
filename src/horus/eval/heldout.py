"""Held-out Belege test set — manual-JSON ground truth + set discovery (ADR-040).

The held-out test set (issue #78 / HND-5) is HORUS's private corpus of ~40 REAL
invoices the author collected (German + English; email-native PDFs + phone-scans).
Unlike the synthetic ZUGFeRD corpus — whose ground truth `parse_cii_xml` extracts
automatically from the PDF-embedded factur-x XML — real invoices carry no embedded
XML, so their ground truth is **hand-authored** (drafted by a model, then verified
field-by-field by the author against the source document; the human verification is
the scientific anchor, per ADR-040 §"Decision").

This module is the held-out counterpart of the ZUGFeRD GT/discovery path:

  - `build_groundtruth_from_mapping` / `build_groundtruth_from_json` — the
    **JSON → `GroundTruth` route**, parallel to `ground_truth.parse_cii_xml`. It
    produces the *identical* `GroundTruth` shape the scorer already consumes
    (`scorer.score(predicted, gt, …)` works unchanged), so the held-out set grades
    with the exact same instrument as the synthetic set. Per-field locale repair is
    delegated to `schema.validate_and_repair` (the one validate/repair home, ADR-035)
    so a hand-typed German value (`1.234,56` / `15.01.2024` / `19 %`) canonicalizes
    byte-identically to a correct model prediction.
  - `load_heldout_index` / `HeldoutItem` — discovery over the flat self-collected
    layout, parallel to `harness._list_paired_invoices`. The set is defined by a
    single `index.json` at the corpus root (the frozen-set manifest); absence of
    that file yields `[]` so corpus-dependent tests auto-skip (ADR-023 pattern).
  - `build_gt_cache` — id → `GroundTruth` one-shot cache, parallel to
    `transcripts.build_gt_cache`.

Privacy (ADR-040 §"Decision"): every path here operates on files under
`data/self-collected/**`, which is git-ignored in full — invoices, the GT JSON, and
`index.json` NEVER enter version control. Only sanitized, non-identifying artifacts
(the datasheet + this code + synthetic-fixture tests) are tracked. This module
imports nothing that would serialize private content into a tracked location.

GT JSON document shape (one file per invoice, under `<corpus_root>/gt/<id>.gt.json`):

    {
      "schema_version": 1,
      "id": "belege-de-email-001",
      "language": "german",            # german | english
      "channel": "email",             # email | iphone-pdf-scan
      "drafted_by": "cascade",        # provenance of the DRAFT (verified by author)
      "verified": true,                # author confirmed every field vs. source
      "verified_date": "2026-06-07",
      "notes": "",
      "fields": { <the 19 FIELDS keys>: "<as printed>" | null }
    }

`null` (or a missing key / empty string) means the field is **absent** on the
invoice (`is_present=False`) — the honesty contract: a held-out GT never invents a
value the document does not carry.

Refs: ADR-040 (this module's ratifying ADR — held-out test set + GT methodology +
privacy + circularity guard), ADR-035 (`validate_and_repair` / the canonical
schema), ADR-037 (19-field scoring scope), ADR-012/013 (`GroundTruth` + scorer
contract this reproduces), ADR-023 (corpus-absent auto-skip), ADR-034 (held-out
eval strategy this set serves).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from horus.eval.ground_truth import FIELDS, GroundTruth, GroundTruthField
from horus.eval.schema import validate_and_repair

__all__ = [
    "GT_DIRNAME",
    "GT_SCHEMA_VERSION",
    "INDEX_FILENAME",
    "HeldoutItem",
    "build_groundtruth_from_json",
    "build_groundtruth_from_mapping",
    "build_gt_cache",
    "empty_gt_fields",
    "gt_document",
    "load_heldout_index",
]

# The frozen-set manifest filename at the corpus root (lists every invoice + its
# sanitized id, source path, sha256, and GT path). Local-only (under the
# git-ignored data tree); the tracked datasheet is its sanitized projection.
INDEX_FILENAME = "index.json"

# Sub-directory (relative to the corpus root) holding one `<id>.gt.json` per invoice.
GT_DIRNAME = "gt"

# Bumped only on a breaking change to the GT JSON document shape.
GT_SCHEMA_VERSION = 1

# Provenance sentinel stored in `GroundTruthField.xpath`. The CII route records the
# XPath that produced a field; the manual route has none, so this marks the record
# as hand-authored (the scorer ignores `xpath`; this is for audit/debug only).
_MANUAL_GT_PROVENANCE = "manual-json"


def empty_gt_fields() -> dict[str, None]:
    """Return a fresh `{english_key: None}` dict over exactly the 19 scored `FIELDS`.

    The all-absent starting point for a new GT draft (every field honestly null
    until populated). Keyed in `FIELDS` declaration order.
    """
    return dict.fromkeys(FIELDS)


def gt_document(
    *,
    invoice_id: str,
    language: str,
    channel: str,
    fields: Mapping[str, str | None],
    drafted_by: str = "cascade",
    verified: bool = False,
    verified_date: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Assemble a canonical GT JSON document (the on-disk shape, see module docstring).

    `fields` is merged onto `empty_gt_fields()` so the result always carries exactly
    the 19 `FIELDS` keys (unknown keys are dropped; missing keys stay `None`). Used
    by the drafting pass and the dashboard review page so both write byte-consistent
    files that `build_groundtruth_from_json` round-trips.
    """
    merged: dict[str, str | None] = {key: None for key in FIELDS}
    merged.update({key: value for key, value in fields.items() if key in merged})
    return {
        "schema_version": GT_SCHEMA_VERSION,
        "id": invoice_id,
        "language": language,
        "channel": channel,
        "drafted_by": drafted_by,
        "verified": verified,
        "verified_date": verified_date,
        "notes": notes,
        "fields": merged,
    }


def build_groundtruth_from_mapping(fields: Mapping[str, Any]) -> GroundTruth:
    """Build a `GroundTruth` from a hand-authored field mapping (the JSON GT route).

    Produces the same `GroundTruth(header={english_key: GroundTruthField})` shape as
    `parse_cii_xml`, so `scorer.score` consumes it unchanged. For each of the 19
    `FIELDS`:

      - **absent** — key missing, value `None`, or empty/whitespace-only string →
        `is_present=False`, `raw_value=None`, `normalized_value=None` (honest null).
      - **present** — non-empty value → `is_present=True`, `raw_value=<as written>`,
        `normalized_value=<canonical>` via `validate_and_repair` (German/locale
        money/date/rate coercion; ADR-035). A present-but-unparseable value keeps
        `is_present=True` with `normalized_value=None` (audit-preserving; the author
        catches it at review).

    Key matching is case-insensitive (first occurrence wins), mirroring
    `InvoiceFields`'s before-validator so the JSON may use any casing.
    """
    normalized = validate_and_repair(fields)
    lower_to_original: dict[str, str] = {}
    for key in fields:
        lower_to_original.setdefault(str(key).lower(), str(key))

    header: dict[str, GroundTruthField] = {}
    for english_key, spec in FIELDS.items():
        original_key = lower_to_original.get(english_key.lower())
        raw_obj = fields[original_key] if original_key is not None else None
        if raw_obj is None:
            is_present = False
            raw_value: str | None = None
        else:
            raw_value = raw_obj if isinstance(raw_obj, str) else str(raw_obj)
            is_present = raw_value.strip() != ""
            if not is_present:
                raw_value = None
        header[english_key] = GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=raw_value,
            normalized_value=normalized[english_key] if is_present else None,
            xpath=_MANUAL_GT_PROVENANCE,
            is_present=is_present,
        )
    return GroundTruth(header=header)


def build_groundtruth_from_json(path: Path) -> GroundTruth:
    """Read a `<id>.gt.json` file and build its `GroundTruth` (see module docstring).

    Accepts either the full document shape (`{"fields": {...}, ...}`) or a bare
    field mapping at the top level. Raises `ValueError` if the file is not a JSON
    object or its `fields` is not an object.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"GT file {path} must contain a JSON object; got {type(data).__name__}.")
    fields = data.get("fields", data)
    if not isinstance(fields, Mapping):
        raise ValueError(f"GT file {path} 'fields' must be a JSON object.")
    return build_groundtruth_from_mapping(fields)


@dataclass(frozen=True)
class HeldoutItem:
    """One entry in the held-out set index (`index.json`).

    Attributes:
        id: sanitized stable identifier (e.g. `belege-de-email-001`) — the ONLY
            identifier that may appear in tracked artifacts (the source filename is
            private and stays in the git-ignored index).
        pdf_path: absolute path to the source invoice PDF (under the git-ignored
            data tree).
        gt_path: absolute path to the `<id>.gt.json` answer key.
        language: `german` | `english`.
        channel: acquisition channel — `email` (native-digital) | `iphone-pdf-scan`
            (photographed; the harder real-world degraded case).
        verified: whether the author has confirmed every field against the source.
        n_pages: page count if recorded in the index, else `None`.
    """

    id: str
    pdf_path: Path
    gt_path: Path
    language: str
    channel: str
    verified: bool
    n_pages: int | None = None


def load_heldout_index(corpus_root: Path) -> list[HeldoutItem]:
    """Load the held-out set from `<corpus_root>/index.json`, sorted by id.

    Returns `[]` when the index file is absent — so tests + downstream eval runs
    auto-skip on machines without the private corpus (CI, fresh clones), mirroring
    the ZUGFeRD corpus-absent behaviour (ADR-023). `pdf`/`gt` paths in the index are
    interpreted relative to `corpus_root`.
    """
    index_path = corpus_root / INDEX_FILENAME
    if not index_path.is_file():
        return []
    data = json.loads(index_path.read_text(encoding="utf-8"))
    raw_items = data.get("items", []) if isinstance(data, Mapping) else []
    items: list[HeldoutItem] = []
    for entry in raw_items:
        if not isinstance(entry, Mapping) or "id" not in entry:
            continue
        gt_rel = entry.get("gt") or f"{GT_DIRNAME}/{entry['id']}.gt.json"
        items.append(
            HeldoutItem(
                id=str(entry["id"]),
                pdf_path=corpus_root / str(entry.get("pdf", "")),
                gt_path=corpus_root / str(gt_rel),
                language=str(entry.get("language", "unknown")),
                channel=str(entry.get("channel", "unknown")),
                verified=bool(entry.get("verified", False)),
                n_pages=entry.get("pages"),
            )
        )
    return sorted(items, key=lambda item: item.id)


def build_gt_cache(corpus_root: Path, *, verified_only: bool = False) -> dict[str, GroundTruth]:
    """Build an `{id: GroundTruth}` cache for the held-out set.

    The held-out counterpart of `transcripts.build_gt_cache` (which reads the
    factur-x route). Skips items whose GT file is missing (streams a WARN line). With
    `verified_only=True`, includes only author-verified items — the safe default for
    a real grading run, where unverified drafts must not count.

    Streams progress to stdout (`flush=True`) per `long-running-foreground`.
    """
    cache: dict[str, GroundTruth] = {}
    items = load_heldout_index(corpus_root)
    print(f"Building held-out GT cache from {len(items)} indexed invoices...", flush=True)
    for item in items:
        if verified_only and not item.verified:
            print(f"  WARN: {item.id} is unverified; skipping (verified_only).", flush=True)
            continue
        if not item.gt_path.is_file():
            print(f"  WARN: {item.id} has no GT file at {item.gt_path}; skipping.", flush=True)
            continue
        cache[item.id] = build_groundtruth_from_json(item.gt_path)
    print(f"  Held-out GT cache: {len(cache)} invoices loaded.", flush=True)
    return cache
