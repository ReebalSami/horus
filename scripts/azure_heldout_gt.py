"""Read the held-out Belege with Azure Document Intelligence — GT channel 2 (ADR-061).

Channel 1 (the ADR-060 vision judge) has read all 39 documents. On Tier A its values can be
graded against each PDF's own embedded characters. On Tier B — 12 documents with no text
layer, plus one whose text layer belongs to a covering email page — **nothing** can grade it:
`0 / 338` asserted cells have a deterministic warrant. A single unverifiable reading is
exactly what produced the retracted 0.5692.

So Tier B needs a second reading that fails *differently*. `prebuilt-invoice` is a specialist
(dedicated OCR plus an invoice-trained field model) rather than a generalist VLM, which is
the entire reason it was chosen: agreement between two systems that share a failure mode is
worth very little.

**Runs over all 39 documents by default, not just Tier B.** The judge asserts 752 Tier A
cells against the draft's 360, and most of that gain is judge-only — one channel's opinion
about which field a printed string belongs to. The printed-evidence gate proves such a string
is on the page but cannot prove its *assignment*, so a judge-only cell stays single-channel
on the question that matters and cannot be auto-accepted. A second reading converts it. The
corpus is ~65 page-images against F0's 500 pages/month, so covering Tier A costs nothing and
removes hundreds of cells from the author's desk.

**Per-page PNGs, never PDFs.** F0 truncates a document at 2 pages and rejects files over
4 MB. One corpus PDF is 4.3 MB — and it is Tier B, so it cannot be skipped. Submitting one
rasterized page per request dissolves both caps at once. Images come from
`prepare_judge_images`, the same preparation channel 1 used, so any difference between the
two readings is the model rather than the pixels.

Nothing is overwritten: readings land in `data/self-collected/_azure/`, the live `gt/` tree is
untouched, and everything stays inside the git-ignored private tree (ADR-040). Values are
never printed — stdout carries counts and field NAMES only, so a terminal transcript is safe
to paste.

Usage:
    uv run python scripts/azure_heldout_gt.py --dry-run          # selection + quota, no calls
    uv run python scripts/azure_heldout_gt.py --ids belege-en-email-001
    uv run python scripts/azure_heldout_gt.py --tier-b           # where channel 2 is decisive
    uv run python scripts/azure_heldout_gt.py --all              # all 39 (default)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.env_file import load_env_file  # noqa: E402
from horus.eval.azure_invoice import (  # noqa: E402
    AZURE_MODEL_ID,
    AzureCoverage,
    AzureReading,
    coverage_summary,
    merge_page_groups,
    merge_page_readings,
    not_covered_fields,
    read_analyzed_document,
    read_groups,
    unmapped_azure_fields,
)
from horus.eval.heldout import HeldoutItem, load_heldout_index  # noqa: E402
from horus.eval.judge_images import prepare_judge_images  # noqa: E402
from horus.eval.printed_evidence import extract_text_layer  # noqa: E402
from horus.eval.rasterize import rasterize_pdf  # noqa: E402
from horus.finetune.dataset import (  # noqa: E402
    DEFAULT_HELDOUT_CORPUS_ROOT,
    DEFAULT_HELDOUT_RASTER_CACHE,
)

DEFAULT_AZURE_DIR = DEFAULT_HELDOUT_CORPUS_ROOT / "_azure"

ENDPOINT_VAR = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
KEY_VAR = "AZURE_DOCUMENT_INTELLIGENCE_KEY"

#: F0 allows 20 calls/minute. Pacing to just under that is cheaper than discovering the limit
#: as a burst of 429s and retry-storming into it — a throttled retry still consumes quota.
F0_CALLS_PER_MINUTE = 20
MIN_SECONDS_BETWEEN_CALLS = 60.0 / F0_CALLS_PER_MINUTE

#: F0's documented monthly page allowance. Used only to state headroom in the dry run.
F0_PAGES_PER_MONTH = 500


@dataclass
class DocumentResult:
    """One invoice's merged channel-2 reading, plus what the run learned along the way."""

    invoice_id: str
    readings: dict[str, AzureReading]
    groups: dict[str, list[dict[str, str | None]]]
    n_images: int
    unmapped: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)


def _pace(last_call_at: float | None) -> float:
    """Sleep just enough to respect the per-minute cap; return the new call timestamp."""
    if last_call_at is not None:
        remaining = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - last_call_at)
        if remaining > 0:
            time.sleep(remaining)
    return time.monotonic()


def _analyze_page(client: Any, image_path: Path) -> dict[str, Any]:
    """Analyze ONE page image; return the raw result as plain JSON.

    `bytes_source` rather than `url_source`: a URL would require making a private invoice
    publicly reachable, which ADR-040 forbids. `as_dict()` keeps every consumer on plain
    JSON, which is what lets the mapping layer be tested without credentials.
    """
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

    poller = client.begin_analyze_document(
        AZURE_MODEL_ID, AnalyzeDocumentRequest(bytes_source=image_path.read_bytes())
    )
    payload = poller.result().as_dict()
    return payload if isinstance(payload, dict) else {}


def _first_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The first analyzed document of a result, or `{}`.

    A page with no invoice fields at all (a covering page, a blank verso) yields no
    documents. That is a legitimate outcome, not an error — the merge simply has nothing to
    take from that page.
    """
    documents = payload.get("documents")
    if isinstance(documents, Sequence) and not isinstance(documents, str | bytes):
        for document in documents:
            if isinstance(document, Mapping):
                return dict(document)
    return {}


def _result_warnings(payload: Mapping[str, Any]) -> list[str]:
    """Service warnings, surfaced rather than swallowed.

    A warning on a Tier B scan is diagnostic information about the only reading that
    document will ever have.
    """
    raw = payload.get("warnings")
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        return []
    messages: list[str] = []
    for warning in raw:
        if isinstance(warning, Mapping):
            code = str(warning.get("code", "")).strip()
            message = str(warning.get("message", "")).strip()
            joined = f"{code}: {message}".strip(": ")
            if joined:
                messages.append(joined)
    return messages


def azure_gt_document(result: DocumentResult, *, language: str, channel: str) -> dict[str, object]:
    """Render a channel-2 reading in the `<id>.gt.json` shape.

    `verified` stays False — this is a reading of pixels, which the truth hierarchy ranks
    BELOW the PDF's own embedded characters and below author sign-off. Only author review
    may set it true (ADR-060). This file is never promoted directly; it is one input to
    adjudication.

    `azure_coverage` records, per field, whether Azure had nothing to say or *could* say
    nothing. Collapsing those two would hand a Tier B null a confirmation it never earned.
    """
    uncovered = not_covered_fields()
    notes = (
        f"Azure DI channel 2 over {result.n_images} page image(s). "
        f"{len(uncovered)} field(s) are structurally outside `{AZURE_MODEL_ID}`'s "
        "vocabulary and are recorded as not-covered, which is NOT evidence of absence."
    )
    if result.warnings:
        notes += f" Service warnings: {'; '.join(result.warnings)}"
    return {
        "schema_version": 1,
        "id": result.invoice_id,
        "language": language,
        "channel": channel,
        "drafted_by": f"azure/{AZURE_MODEL_ID}",
        "verified": False,
        "verified_date": None,
        "notes": notes,
        "fields": {key: reading.value for key, reading in result.readings.items()},
        "azure_coverage": {key: reading.coverage.value for key, reading in result.readings.items()},
        "azure_confidence": {
            key: reading.confidence
            for key, reading in result.readings.items()
            if reading.confidence is not None
        },
        "azure_page": {
            key: reading.page for key, reading in result.readings.items() if reading.page
        },
        "vat_breakdown": result.groups.get("vat_breakdown", []),
        "skonto": result.groups.get("skonto", []),
        "line_items": result.groups.get("line_items", []),
    }


def rebuild_from_raw(
    raw_dir: Path, gt_out: Path, by_id: Mapping[str, HeldoutItem], ids: Sequence[str]
) -> tuple[int, set[str]]:
    """Re-derive the channel-2 GT files from archived responses, with ZERO API calls.

    The mapping table is a measured hypothesis (see `audit_azure_vocabulary.py`), so it
    changes whenever the audit finds a field we were discarding — as it did when
    `PaymentDetails[].IBAN` turned out to cover a field previously written off as
    uncoverable. Re-deriving from the archived raw JSON keeps quota spend at zero for what
    is purely a re-interpretation of bytes we already hold, and it makes the raw archive
    load-bearing rather than decorative.

    Returns the number of documents rewritten and the union of unmapped Azure fields seen.
    """
    rewritten = 0
    all_unmapped: set[str] = set()

    for sid in ids:
        raw_path = raw_dir / f"{sid}.json"
        if not raw_path.is_file():
            continue
        try:
            pages = json.loads(raw_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  {sid}: unreadable archive ({exc}) — skipped", flush=True)
            continue
        if not isinstance(pages, list):
            continue

        per_page_readings = []
        per_page_groups = []
        warnings: list[str] = []
        unmapped: set[str] = set()
        for page in pages:
            if not isinstance(page, Mapping):
                continue
            warnings.extend(_result_warnings(page))
            document = _first_document(page)
            if not document:
                continue
            per_page_readings.append(read_analyzed_document(document))
            per_page_groups.append(read_groups(document))
            unmapped |= unmapped_azure_fields(document)

        if not per_page_readings:
            print(f"  {sid}: no analyzed documents in archive — skipped", flush=True)
            continue

        result = DocumentResult(
            invoice_id=sid,
            readings=merge_page_readings(per_page_readings),
            groups=merge_page_groups(per_page_groups),
            n_images=len(pages),
            unmapped=unmapped,
            warnings=warnings,
        )
        all_unmapped |= unmapped
        item = by_id[sid]
        (gt_out / f"{sid}.gt.json").write_text(
            json.dumps(
                azure_gt_document(result, language=item.language, channel=item.channel),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        rewritten += 1
        counts = coverage_summary(result.readings)
        print(
            f"  {sid:<26} {counts[AzureCoverage.VALUE.value]:>2} read, "
            f"{counts[AzureCoverage.NOT_PRESENT.value]:>2} silent, "
            f"{counts[AzureCoverage.NOT_COVERED.value]:>2} not-covered; "
            f"line_items={len(result.groups.get('line_items', []))}",
            flush=True,
        )
    return rewritten, all_unmapped


def _tier_b_ids(items: Sequence[HeldoutItem]) -> list[str]:
    """Ids whose PDF has no usable text layer — where channel 2 is indispensable.

    Uses the same `extract_text_layer` the audit uses, so this selection cannot drift from
    the tiering that justified the retraction. Deliberately the coarse `word_count == 0`
    test: the finer low-yield classification lives in `audit_heldout_evidence.py` and needs
    a GT to measure yield against, which would be circular here. Note this does NOT catch
    the document whose text layer belongs to a covering email page — it has a text layer,
    just not one describing the invoice — which is one more reason the default is `--all`.
    """
    return [
        item.id
        for item in items
        if item.pdf_path.is_file() and not extract_text_layer(item.pdf_path).exists
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="azure_heldout_gt",
        description="Read the held-out set with Azure Document Intelligence (ADR-061).",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_HELDOUT_CORPUS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_AZURE_DIR)
    parser.add_argument("--raster-cache", type=Path, default=DEFAULT_HELDOUT_RASTER_CACHE)
    parser.add_argument("--dpi", type=int, default=300)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="Read every invoice (default).")
    selection.add_argument("--ids", nargs="+", default=None, help="Read these ids only.")
    selection.add_argument(
        "--tier-b",
        action="store_true",
        help="Read only documents with no text layer (where channel 2 is decisive).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show selection, image plan and quota surface; make no API calls.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "Re-derive GT from the archived raw responses with no API calls. Use after "
            "the mapping table changes (see scripts/audit_azure_vocabulary.py)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-read invoices that already have a result on disk (default: skip them).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Read at most N invoices this run; re-run to continue where it stopped.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    items = load_heldout_index(args.corpus)
    if not items:
        print(f"No held-out index at {args.corpus / 'index.json'}.", file=sys.stderr)
        return 1
    by_id = {item.id: item for item in items}
    all_ids = sorted(by_id)

    if args.ids:
        unknown = [i for i in args.ids if i not in by_id]
        if unknown:
            print(f"Unknown ids: {', '.join(unknown)}", file=sys.stderr)
            return 1
        selected = sorted(args.ids)
    elif args.tier_b:
        selected = _tier_b_ids(items)
        print(f"Tier B selection: {len(selected)} document(s) with no text layer.", flush=True)
    else:
        selected = all_ids

    gt_out = args.out_dir / "gt"
    raw_out = args.out_dir / "raw"

    if args.rebuild:
        if not raw_out.is_dir():
            print(f"No archived responses at {raw_out}.", file=sys.stderr)
            return 1
        gt_out.mkdir(parents=True, exist_ok=True)
        print(f"Rebuilding from {raw_out} (no API calls):", flush=True)
        rewritten, rebuilt_unmapped = rebuild_from_raw(raw_out, gt_out, by_id, selected)
        print(f"\nRewrote {rewritten} document(s) from the archive.", flush=True)
        if rebuilt_unmapped:
            print(f"Unmapped Azure field(s): {', '.join(sorted(rebuilt_unmapped))}", flush=True)
        return 0

    if not args.force:
        done = [sid for sid in selected if (gt_out / f"{sid}.gt.json").is_file()]
        if done:
            shown = ", ".join(done[:4]) + (" …" if len(done) > 4 else "")
            print(
                f"Skipping {len(done)} already-read invoice(s) (--force to re-read): {shown}",
                flush=True,
            )
            selected = [sid for sid in selected if sid not in set(done)]
        if not selected:
            print("Nothing left to read.", flush=True)
            return 0

    if args.limit is not None and args.limit < len(selected):
        remaining = len(selected) - args.limit
        selected = selected[: args.limit]
        print(f"Limiting to {args.limit} this run; {remaining} will remain.", flush=True)

    print(f"Selected {len(selected)} of {len(all_ids)} invoice(s):", flush=True)
    image_map: dict[str, list[Path]] = {}
    total_images = 0
    for sid in selected:
        pages = rasterize_pdf(
            by_id[sid].pdf_path, dpi=args.dpi, cache_dir=args.raster_cache, image_format="png"
        )
        prepared = prepare_judge_images(pages, out_dir=args.out_dir / "images" / sid)
        image_map[sid] = [image.path for image in prepared]
        total_images += len(prepared)
        largest = max((image.path.stat().st_size for image in prepared), default=0)
        print(
            f"  {sid:<26} {len(pages)} page(s) -> {len(prepared)} image(s), "
            f"largest {largest / 1024:.0f} KiB",
            flush=True,
        )

    uncovered = not_covered_fields()
    print(
        f"\nRequests this run: {total_images} (1 per page image) = "
        f"{total_images / F0_PAGES_PER_MONTH:.0%} of the F0 {F0_PAGES_PER_MONTH} pages/month "
        f"allowance. Paced at {F0_CALLS_PER_MINUTE}/min ≈ "
        f"{total_images * MIN_SECONDS_BETWEEN_CALLS / 60:.1f} min.",
        flush=True,
    )
    print(
        f"Structurally outside `{AZURE_MODEL_ID}` ({len(uncovered)} of 34 fields, recorded "
        f"as not-covered rather than absent): {', '.join(uncovered)}",
        flush=True,
    )

    injected = load_env_file()
    if injected:
        print(f"Loaded from .env: {', '.join(sorted(injected))}", flush=True)
    endpoint = os.environ.get(ENDPOINT_VAR, "").strip()
    key = os.environ.get(KEY_VAR, "").strip()
    missing = [name for name, value in ((ENDPOINT_VAR, endpoint), (KEY_VAR, key)) if not value]
    if missing:
        print(
            f"Missing credential(s): {', '.join(missing)}. Set them in the git-ignored .env "
            "(setup runbook: scripts/azure/README.md) or export them.",
            file=sys.stderr,
        )
        return 2
    print(f"Endpoint host: {endpoint.split('//')[-1].rstrip('/')} (key present)", flush=True)

    if args.dry_run:
        print("Dry run — no API calls made.", flush=True)
        return 0

    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    gt_out.mkdir(parents=True, exist_ok=True)
    raw_out.mkdir(parents=True, exist_ok=True)

    last_call_at: float | None = None
    all_unmapped: set[str] = set()
    failures: list[str] = []

    for position, sid in enumerate(selected, start=1):
        item = by_id[sid]
        images = image_map[sid]
        print(f"\n[{position}/{len(selected)}] {sid} — {len(images)} request(s)", flush=True)

        per_page_readings = []
        per_page_groups = []
        raw_pages: list[dict[str, Any]] = []
        warnings: list[str] = []
        unmapped: set[str] = set()
        failed = False

        for image_index, image_path in enumerate(images, start=1):
            last_call_at = _pace(last_call_at)
            try:
                payload = _analyze_page(client, image_path)
            except Exception as exc:  # noqa: BLE001 — one page must not abort the corpus
                print(f"    image {image_index}: FAILED — {type(exc).__name__}: {exc}", flush=True)
                failures.append(f"{sid}#{image_index}")
                failed = True
                continue

            raw_pages.append(payload)
            warnings.extend(_result_warnings(payload))
            document = _first_document(payload)
            if not document:
                print(f"    image {image_index}: no invoice fields on this page", flush=True)
                continue

            readings = read_analyzed_document(document)
            per_page_readings.append(readings)
            per_page_groups.append(read_groups(document))
            unmapped |= unmapped_azure_fields(document)
            counts = coverage_summary(readings)
            print(
                f"    image {image_index}: {counts[AzureCoverage.VALUE.value]} field(s) read, "
                f"{counts[AzureCoverage.NOT_PRESENT.value]} silent, "
                f"{counts[AzureCoverage.NOT_COVERED.value]} not-covered",
                flush=True,
            )

        if failed and not per_page_readings:
            print(f"    -> no usable reading for {sid}; not written", flush=True)
            continue

        result = DocumentResult(
            invoice_id=sid,
            readings=merge_page_readings(per_page_readings),
            groups=merge_page_groups(per_page_groups),
            n_images=len(images),
            unmapped=unmapped,
            warnings=warnings,
        )
        all_unmapped |= unmapped

        (raw_out / f"{sid}.json").write_text(
            json.dumps(raw_pages, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        document_json = azure_gt_document(result, language=item.language, channel=item.channel)
        (gt_out / f"{sid}.gt.json").write_text(
            json.dumps(document_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        merged_counts = coverage_summary(result.readings)
        print(
            f"    -> merged: {merged_counts[AzureCoverage.VALUE.value]} field(s) read, "
            f"{merged_counts[AzureCoverage.NOT_PRESENT.value]} silent, "
            f"{merged_counts[AzureCoverage.NOT_COVERED.value]} not-covered; "
            f"line_items={len(result.groups.get('line_items', []))} "
            f"vat_breakdown={len(result.groups.get('vat_breakdown', []))}",
            flush=True,
        )
        if warnings:
            print(f"    !! service warnings: {'; '.join(warnings)}", flush=True)

    print(f"\nWrote channel-2 readings to {gt_out}", flush=True)
    if all_unmapped:
        print(
            "Azure returned field(s) no mapping table consumes — the measured vocabulary "
            f"gap (see AZURE_FIELD_MAP): {', '.join(sorted(all_unmapped))}",
            flush=True,
        )
    else:
        print("No unmapped Azure fields observed.", flush=True)
    if failures:
        print(f"Failed request(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
