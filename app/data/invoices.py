"""Resolve an invoice's page image(s) and raw model transcript for the explorer.

Page images are rendered from the source PDF via the project's own `rasterize_pdf`
(disk-cached, so repeat views are instant) with each approach's own rasterizer
settings — the app shows the exact image the pipeline saw. Raw transcripts are read
from the (git-ignored, local-only) archive the runs wrote, located by the
``<model_slug>__<invoice_stem>.txt`` convention. Every lookup degrades gracefully to
"unavailable" when a file is missing (e.g. on a fresh clone or in CI).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from horus.eval.rasterize import rasterize_pdf


def find_pdf(corpus_root: Path, invoice_stem: str) -> Path | None:
    """Locate an invoice PDF: the canonical FX path first, then a corpus-wide search."""
    direct = corpus_root / "XML-Rechnung" / "FX" / f"{invoice_stem}.pdf"
    if direct.is_file():
        return direct
    if corpus_root.is_dir():
        matches = sorted(corpus_root.rglob(f"{invoice_stem}.pdf"))
        if matches:
            return matches[0]
    return None


def page_images(corpus_root: Path, invoice_stem: str, *, dpi: int, cache_dir: Path) -> list[Path]:
    """Rasterize every page of the invoice PDF to cached PNGs; empty list if unavailable."""
    pdf = find_pdf(corpus_root, invoice_stem)
    if pdf is None:
        return []
    try:
        return rasterize_pdf(pdf, dpi=dpi, cache_dir=cache_dir)
    except Exception:  # noqa: BLE001 — corrupt/locked PDF → no preview rather than a crash
        return []


def transcript_path(transcript_dir: Path, model_id: str, invoice_stem: str) -> Path | None:
    """Find the archived transcript for a (model, invoice), or None if absent."""
    slug = model_id.lower().replace("/", "__")
    direct = transcript_dir / f"{slug}__{invoice_stem}.txt"
    if direct.is_file():
        return direct
    if transcript_dir.is_dir():
        for candidate in sorted(transcript_dir.glob(f"*__{invoice_stem}.txt")):
            if candidate.name.lower().startswith(slug):
                return candidate
    return None


def load_transcript_body(path: Path) -> str | None:
    """Return the transcript body (page-separated text), or None if unreadable."""
    from horus.eval.transcripts import parse_transcript

    try:
        _model_id, _invoice_stem, body = parse_transcript(path)
    except OSError, ValueError:
        return None
    return body


def last_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort parse of the last balanced ``{...}`` object in ``text``.

    Structurer outputs end each page with a JSON object; this lifts the final one
    (used only for the non-scored ``purpose_summary`` demo touch).
    """
    end = text.rfind("}")
    while end != -1:
        depth = 0
        for i in range(end, -1, -1):
            char = text[i]
            if char == "}":
                depth += 1
            elif char == "{":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[i : end + 1])
                    except json.JSONDecodeError:
                        break
                    return obj if isinstance(obj, dict) else None
        end = text.rfind("}", 0, end)
    return None


def purpose_summary(body: str) -> str | None:
    """Extract the model's one-line ``purpose_summary`` from a structurer transcript."""
    obj = last_json_object(body)
    if obj is None:
        return None
    value = obj.get("purpose_summary")
    return value if isinstance(value, str) and value.strip() else None
