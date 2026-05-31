"""Saved-transcript + ground-truth loading — shared offline-scoring I/O.

Canonical home for the transcript-archive reader + factur-x GT cache that any
offline-scoring consumer needs. Lifted out of ``scripts/rescore.py`` (ADR-016)
so the adapter A/B re-scorer AND the read-quality ceiling diagnostic
(``scripts/reading_ceiling.py``, ADR-030) share ONE transcript parser rather
than duplicating it (DRY; one place to fix if the archive format drifts).

The saved-transcript format (produced by ``harness`` per ADR-014 PR(c)):

    # Multi-page transcript (ADR-014 PR(c))
    # Model:    <model_id>           <- canonical HF id, original case
    # Invoice:  <invoice_stem>       <- PDF stem, no extension
    # Pages:    <N>
    # ... (more `# ` comment header lines)
    <blank line>
    ===== PAGE 1 =====
    <page-1 raw VLM text>
    ===== PAGE 2 =====
    <page-2 raw VLM text>
    ...

Public API:

    parse_transcript(path) -> (model_id, invoice_stem, body)
    split_per_page_texts(body) -> list[str]
    build_gt_cache(corpus_root) -> dict[invoice_stem, GroundTruth]

Refs: ADR-014 (transcript archive format), ADR-016 (rescore.py origin of this
logic), ADR-030 (reading-ceiling diagnostic — second consumer), ADR-012
(GroundTruth parser this caches), ADR-010 (factur-x extraction route).
"""

from __future__ import annotations

import re
from pathlib import Path

from horus.eval.ground_truth import GroundTruth
from horus.eval.harness import (
    _PAGE_SEPARATOR_RE,
    _extract_groundtruth_via_facturx,
    _list_paired_invoices,
)

__all__ = [
    "HEADER_LINE_RE",
    "build_gt_cache",
    "parse_transcript",
    "split_per_page_texts",
]

# Per-transcript header lines:
#   # Multi-page transcript (ADR-014 PR(c))
#   # Model:    <model_id>
#   # Invoice:  <invoice_stem>
#   # Pages:    <N>
#   ...
#   <blank line>
#   ===== PAGE 1 =====
#   ...
HEADER_LINE_RE: re.Pattern[str] = re.compile(r"^# (Model|Invoice):\s+(.+)$")


def parse_transcript(path: Path) -> tuple[str, str, str]:
    """Parse a saved transcript file into ``(model_id, invoice_stem, body)``.

    Reads the ``# Model:`` / ``# Invoice:`` header lines and returns the body
    starting at the first non-comment, non-empty line. ``body`` is the
    multi-page concatenation *with* the ``===== PAGE N =====`` separator lines
    intact (call :func:`split_per_page_texts` to get the per-page list the
    multipage adapter API expects, per ADR-019 W3.1).

    Args:
        path: path to a ``*.txt`` transcript in the archive layout above.

    Returns:
        ``(model_id, invoice_stem, body)``.

    Raises:
        ValueError: if the ``# Model:`` / ``# Invoice:`` header or the body is
            missing (malformed transcript).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    model_id: str | None = None
    invoice_stem: str | None = None
    body_start: int | None = None
    for i, line in enumerate(lines):
        m = HEADER_LINE_RE.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key == "Model":
                model_id = val
            elif key == "Invoice":
                invoice_stem = val
        # Body starts at the first non-comment, non-empty line.
        if not line.startswith("#") and line.strip() != "" and body_start is None:
            body_start = i
            break
    if model_id is None or invoice_stem is None or body_start is None:
        raise ValueError(f"Transcript {path} missing Model:/Invoice: header or body")
    body = "\n".join(lines[body_start:])
    return model_id, invoice_stem, body


def split_per_page_texts(body: str) -> list[str]:
    """Split a transcript body into per-page texts (inverse of harness concat).

    Splits on the canonical ``===== PAGE N =====`` separator line (matched via
    :data:`harness._PAGE_SEPARATOR_RE`), strips each chunk, and drops empty
    chunks (the body typically starts with a separator, producing an empty
    leading split element).

    Args:
        body: the transcript body from :func:`parse_transcript` (3rd element).

    Returns:
        list of per-page text strings, source order preserved, stripped,
        empty pages excluded. Feeds ``adapter.to_predicted_dict_multipage``.
    """
    chunks = _PAGE_SEPARATOR_RE.split(body)
    return [c.strip() for c in chunks if c.strip()]


def build_gt_cache(corpus_root: Path) -> dict[str, GroundTruth]:
    """Extract the CII ground truth for every paired invoice via factur-x.

    One-shot cache keyed by PDF stem so repeated scoring passes don't re-parse
    the same embedded XML. Invoices whose PDF has no factur-x attachment are
    skipped with a WARNING line (per ADR-010 the factur-x route is canonical;
    a missing attachment is a corpus anomaly, not a hard error).

    Streams progress to stdout (``flush=True``) per ``long-running-foreground``.

    Args:
        corpus_root: ZUGFeRD corpus root; paired-invoice discovery walks it via
            :func:`harness._list_paired_invoices`.

    Returns:
        ``dict[invoice_stem, GroundTruth]``.
    """
    cache: dict[str, GroundTruth] = {}
    pairs = _list_paired_invoices(corpus_root)
    print(f"Building GT cache from {len(pairs)} paired invoices...", flush=True)
    for pdf_path, _cii_sidecar in pairs:
        gt = _extract_groundtruth_via_facturx(pdf_path)
        if gt is None:
            print(f"  WARN: {pdf_path.stem} has no factur-x GT; skipping", flush=True)
            continue
        cache[pdf_path.stem] = gt
    print(f"  GT cache: {len(cache)} invoices loaded.", flush=True)
    return cache
