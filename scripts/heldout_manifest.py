#!/usr/bin/env python3
"""heldout_manifest.py — index + sanitized datasheet for the Belege held-out set (ADR-040).

Two modes (issue #78 / HND-5):

  index      Scan data/self-collected/<language>/<channel>/*.pdf, assign STABLE
             sanitized ids (belege-<de|en>-<email|scan>-NNN), compute sha256 +
             page count, and (re)write `<corpus_root>/index.json`. Extracts a PDF
             attachment from any `.eml` first. LOCAL-ONLY output: index.json lives
             under the git-ignored data tree (it carries real source filenames).
             Idempotent: existing ids are preserved (read back from index.json) so
             adding invoices never renumbers the frozen set.

  datasheet  Read index.json + the verified GT files and write a SANITIZED markdown
             datasheet (counts, language/channel mix, page distribution, per-field
             presence rate, and the id↔sha256 freeze table). NO source filenames and
             NO field values — safe to git-track under docs/. This is the public,
             reproducible record of the private set + its freeze hashes.

Usage:
    uv run python scripts/heldout_manifest.py index
    uv run python scripts/heldout_manifest.py datasheet \\
        --out docs/architecture/belege-heldout-datasheet.md

Privacy (ADR-040): the invoices, their GT, and index.json NEVER enter git
(`data/self-collected/**` is ignored in full). Only the datasheet is tracked, and
it is sanitized by construction (this script emits ids + hashes + aggregates only).
"""

from __future__ import annotations

import argparse
import email
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from email import policy
from pathlib import Path

from horus.eval.ground_truth import FIELDS
from horus.eval.heldout import (
    GT_DIRNAME,
    GT_SCHEMA_VERSION,
    INDEX_FILENAME,
    build_gt_cache,
    load_heldout_index,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "data" / "self-collected"

# Source layout: <corpus_root>/<language>/<channel>/*.pdf
_LANGUAGES = ("german", "english")
_CHANNELS = ("email", "iphone-pdf-scan")
_LANG_CODE = {"german": "de", "english": "en"}
_CHANNEL_CODE = {"email": "email", "iphone-pdf-scan": "scan"}


def _sha256(path: Path) -> str:
    """Return the hex sha256 of a file (streamed in 64 KiB chunks)."""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _page_count(path: Path) -> int | None:
    """Return the PDF page count via pypdfium2, or None if it cannot be opened."""
    try:
        import pypdfium2 as pdfium  # noqa: PLC0415 — optional/heavy; defer

        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception as exc:  # noqa: BLE001 — page count is best-effort metadata
        print(f"  WARN: could not read page count for {path.name}: {exc}", flush=True)
        return None


def _extract_pdf_from_eml(eml_path: Path) -> Path | None:
    """Extract the first application/pdf attachment of an .eml to a sibling .pdf.

    Returns the written PDF path, or None when the email carries no PDF attachment
    (e.g. an HTML-only receipt — handled manually / dropped per ADR-040).
    """
    msg = email.message_from_bytes(eml_path.read_bytes(), policy=policy.default)
    for part in msg.walk():
        if part.get_content_type() == "application/pdf":
            payload = part.get_payload(decode=True)
            if isinstance(payload, (bytes, bytearray)):
                out_path = eml_path.with_suffix(".pdf")
                out_path.write_bytes(payload)
                print(f"  extracted PDF attachment: {eml_path.name} -> {out_path.name}", flush=True)
                return out_path
    print(f"  WARN: no PDF attachment in {eml_path.name}; skipping (handle manually).", flush=True)
    return None


def _load_existing_id_map(index_path: Path) -> dict[str, str]:
    """Return {source_relpath: id} from an existing index.json (for stable ids)."""
    if not index_path.is_file():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    return {
        str(item["pdf"]): str(item["id"])
        for item in data.get("items", [])
        if isinstance(item, dict) and "pdf" in item and "id" in item
    }


def _discover_pdfs(corpus_root: Path) -> list[tuple[str, str, Path]]:
    """Return sorted (language, channel, pdf_path) triples; extracts .eml PDFs first."""
    found: list[tuple[str, str, Path]] = []
    for language in _LANGUAGES:
        for channel in _CHANNELS:
            channel_dir = corpus_root / language / channel
            if not channel_dir.is_dir():
                continue
            for eml in sorted(channel_dir.glob("*.eml")):
                extracted = _extract_pdf_from_eml(eml)
                if extracted is not None and not extracted.is_file():  # pragma: no cover
                    continue
            for pdf in sorted(channel_dir.glob("*.pdf")):
                found.append((language, channel, pdf))
    return found


def _next_id(language: str, channel: str, used: set[str]) -> str:
    """Allocate the next free belege-<lang>-<channel>-NNN id not already in `used`."""
    prefix = f"belege-{_LANG_CODE[language]}-{_CHANNEL_CODE[channel]}-"
    n = 1
    while f"{prefix}{n:03d}" in used:
        n += 1
    return f"{prefix}{n:03d}"


def build_index(corpus_root: Path) -> Path:
    """Scan the corpus and (re)write index.json with stable ids + hashes + page counts."""
    index_path = corpus_root / INDEX_FILENAME
    existing = _load_existing_id_map(index_path)
    used_ids = set(existing.values())

    print(f"Scanning {corpus_root} ...", flush=True)
    items: list[dict[str, object]] = []
    for language, channel, pdf in _discover_pdfs(corpus_root):
        rel = str(pdf.relative_to(corpus_root))
        invoice_id = existing.get(rel)
        if invoice_id is None:
            invoice_id = _next_id(language, channel, used_ids)
            used_ids.add(invoice_id)
        gt_rel = f"{GT_DIRNAME}/{invoice_id}.gt.json"
        gt_path = corpus_root / gt_rel
        verified = False
        if gt_path.is_file():
            gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
            verified = bool(gt_data.get("verified", False))
        items.append(
            {
                "id": invoice_id,
                "pdf": rel,
                "source_filename": pdf.name,
                "language": language,
                "channel": channel,
                "pages": _page_count(pdf),
                "sha256": _sha256(pdf),
                "gt": gt_rel,
                "verified": verified,
            }
        )

    items.sort(key=lambda entry: str(entry["id"]))
    index = {
        "name": "belege-heldout-v1",
        "schema_version": GT_SCHEMA_VERSION,
        "created": datetime.now(UTC).strftime("%Y-%m-%d"),
        "frozen": False,
        "corpus_root": str(corpus_root.relative_to(PROJECT_ROOT)),
        "items": items,
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    n_verified = sum(1 for entry in items if entry["verified"])
    print(
        f"  index.json written: {len(items)} invoices ({n_verified} verified). "
        f"[LOCAL-ONLY — git-ignored]",
        flush=True,
    )
    return index_path


def build_datasheet(corpus_root: Path, out_path: Path) -> Path:
    """Write a sanitized, git-trackable datasheet (counts + presence + freeze hashes)."""
    items = load_heldout_index(corpus_root)
    if not items:
        raise SystemExit(
            f"No index found at {corpus_root / INDEX_FILENAME}. Run "
            f"'uv run python scripts/heldout_manifest.py index' first."
        )

    lang_counts = Counter(item.language for item in items)
    channel_counts = Counter(item.channel for item in items)
    page_values = [item.n_pages for item in items if item.n_pages is not None]
    n_verified = sum(1 for item in items if item.verified)

    # Per-field presence over ALL drafted GT (aggregate counts only; no values).
    # Drafts are Cascade-authored, author-verified field-by-field in the review
    # page; the verified count is reported separately so the caveat is explicit.
    gt_cache = build_gt_cache(corpus_root)
    presence: dict[str, int] = dict.fromkeys(FIELDS, 0)
    for gt in gt_cache.values():
        for key, field in gt.header.items():
            if field.is_present:
                presence[key] += 1
    n_drafted = len(gt_cache)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append("# Belege Held-Out Test Set — Datasheet (sanitized)\n")
    lines.append(
        "> Sanitized public record of HORUS's PRIVATE held-out invoice set (issue #78, "
        "ADR-040). Generated by `scripts/heldout_manifest.py datasheet`. Contains ONLY "
        "counts, aggregate field-presence rates, and the id\u2194sha256 freeze table — "
        "**no source filenames, no field values, no invoice content**. The invoices and "
        "their ground truth live under the git-ignored `data/self-collected/**` and are "
        "never committed.\n"
    )
    lines.append(f"- **Generated:** {today}")
    lines.append(f"- **Invoices:** {len(items)}")
    lines.append(f"- **Ground truth drafted:** {n_drafted} / {len(items)}")
    lines.append(f"- **Ground truth author-verified:** {n_verified} / {len(items)}")
    lines.append(f"- **GT schema version:** {GT_SCHEMA_VERSION}\n")

    lines.append("## Composition\n")
    lines.append("| Axis | Value | Count |")
    lines.append("| --- | --- | --- |")
    for language in _LANGUAGES:
        lines.append(f"| Language | {language} | {lang_counts.get(language, 0)} |")
    for channel in _CHANNELS:
        lines.append(f"| Channel | {channel} | {channel_counts.get(channel, 0)} |")
    if page_values:
        page_summary = f"min {min(page_values)} / max {max(page_values)} / total {sum(page_values)}"
        lines.append(f"| Pages | per-invoice | {page_summary} |")
    lines.append("")

    lines.append("## Field-presence rate (drafted GT)\n")
    if n_drafted:
        lines.append(
            f"Across the {n_drafted} drafted invoices ({n_verified} author-verified), "
            "how often each field is present (honest nulls for absent fields):\n"
        )
        lines.append("| Field | Present | Rate |")
        lines.append("| --- | --- | --- |")
        for key in FIELDS:
            count = presence[key]
            rate = count / n_drafted
            lines.append(f"| `{key}` | {count}/{n_drafted} | {rate:.0%} |")
    else:
        lines.append("*(No ground truth drafted yet — re-run after drafting.)*")
    lines.append("")

    lines.append("## Freeze table (id \u2194 sha256)\n")
    lines.append(
        "The sha256 of each source PDF is the freeze proof: any change to an invoice "
        "changes its hash. Filenames are intentionally omitted (private).\n"
    )
    lines.append("| id | pages | sha256 (source PDF) | verified |")
    lines.append("| --- | --- | --- | --- |")
    index_data = json.loads((corpus_root / INDEX_FILENAME).read_text(encoding="utf-8"))
    sha_by_id = {str(e["id"]): str(e.get("sha256", "")) for e in index_data.get("items", [])}
    for item in items:
        pages = item.n_pages if item.n_pages is not None else "?"
        sha = sha_by_id.get(item.id, "")
        lines.append(f"| `{item.id}` | {pages} | `{sha}` | {'yes' if item.verified else 'no'} |")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"  datasheet written: {out_path} ({len(items)} invoices, "
        f"{n_drafted} drafted, {n_verified} verified)."
    )
    return out_path


def _extract_text(pdf_path: Path) -> list[str]:
    """Return the per-page embedded text layer of a PDF (empty strings for image-only pages)."""
    import pypdfium2 as pdfium  # noqa: PLC0415 — heavy; defer

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        pages: list[str] = []
        for i in range(len(pdf)):
            textpage = pdf[i].get_textpage()
            pages.append(textpage.get_text_range())
        return pages
    finally:
        pdf.close()


def dump_text(corpus_root: Path, out_path: Path) -> Path:
    """Dump every indexed invoice's embedded text to ONE local file (drafting aid).

    Writes per-invoice + per-page separated text to `out_path` (under the git-ignored
    data tree) and prints a `(id, pages, chars)` summary sorted low-text-first, so
    image-only scans (near-zero text layer → need vision drafting) are obvious. This
    is a LOCAL inspection aid for ground-truth drafting; it emits no tracked artifact.
    """
    items = load_heldout_index(corpus_root)
    if not items:
        raise SystemExit(
            f"No index found at {corpus_root / INDEX_FILENAME}. Run the `index` mode first."
        )
    blocks: list[str] = []
    summary: list[tuple[str, int, int]] = []
    for item in items:
        pages: list[str] = []
        if item.pdf_path.is_file():
            try:
                pages = _extract_text(item.pdf_path)
            except Exception as exc:  # noqa: BLE001 — extraction failure is non-fatal
                print(f"  WARN: text extraction failed for {item.id}: {exc}", flush=True)
        total_chars = sum(len(p) for p in pages)
        summary.append((item.id, len(pages), total_chars))
        header = (
            f"===== {item.id} | {item.language}/{item.channel} | "
            f"pages={len(pages)} | chars={total_chars} ====="
        )
        body = "\n\n".join(f"--- page {n} ---\n{text.strip()}" for n, text in enumerate(pages, 1))
        blocks.append(f"{header}\n{body}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n\n".join(blocks), encoding="utf-8")
    print(f"  text dumped: {out_path} ({len(items)} invoices) [LOCAL-ONLY]", flush=True)
    print("  id / pages / chars (low-text first = likely image-only scan):", flush=True)
    for inv_id, n_pages, chars in sorted(summary, key=lambda row: row[2]):
        flag = "  <-- low text (scan?)" if chars < 200 else ""
        print(f"    {inv_id:26s} pages={n_pages:2d} chars={chars:6d}{flag}", flush=True)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index + datasheet for the Belege held-out test set (ADR-040).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_index = sub.add_parser("index", help="(re)write index.json (local-only)")
    p_index.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)

    p_sheet = sub.add_parser("datasheet", help="write the sanitized tracked datasheet")
    p_sheet.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    p_sheet.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "docs" / "architecture" / "belege-heldout-datasheet.md",
    )

    p_text = sub.add_parser("text", help="dump per-invoice extracted text (local drafting aid)")
    p_text.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    p_text.add_argument(
        "--out", type=Path, default=DEFAULT_CORPUS_ROOT / "_text" / "all-invoices.txt"
    )

    args = parser.parse_args()
    if args.mode == "index":
        build_index(args.corpus_root)
    elif args.mode == "datasheet":
        build_datasheet(args.corpus_root, args.out)
    elif args.mode == "text":
        dump_text(args.corpus_root, args.out)


if __name__ == "__main__":
    main()
