"""Reader pass — produce Granite transcripts for invoices that lack one (issue #55).

The structurer fine-tune consumes the reader's (Granite's) transcript text. The pilot-13
cohort run only transcribed the 26 wired `XML-Rechnung` invoices; the other ~120 GT-bearing
ZUGFeRD invoices (`ZUGFeRDv1/`, `ZUGFeRDv2/`) have no transcript. This module runs the reader
over those, writing transcripts **byte-compatible with the cached 26** — same rasterizer, DPI,
prompt, max_tokens, header, and `===== PAGE N =====` separators — so the structurer sees ONE
consistent input distribution (no train/serve skew between the wired 26 and the new 120).

It reuses the harness primitives (`rasterize_pdf` + `_extract_and_concat` + `_model_slug`) and
faithfully replicates the harness's transcript-write block (`_score_one_tuple` step 1-3); it does
NOT score or touch MLflow — these are training INPUTS, not runs. Resumable by construction: an
invoice that already has a transcript is skipped (unless ``overwrite``), so a long run can be
chunked / re-invoked safely (`long-running-foreground`).

Refs: ADR-014 (rasterizer + transcript format), ADR-038/034 (Arm-B reader→structurer),
ADR-009 (Granite manifest entry), plan `~/.windsurf/plans/horus-finetune-structurer-55a1c3.md`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from horus.eval.harness import _extract_and_concat, _model_slug
from horus.eval.rasterize import rasterize_pdf
from horus.finetune.dataset import (
    DEFAULT_READER_MODEL,
    DEFAULT_TRANSCRIPT_DIR,
    InvoiceRecord,
)
from horus.vlm_extractor import COHORT_MANIFEST, get_extractor

__all__ = ["ReaderPassConfig", "run_reader_pass"]

_LOGGER = logging.getLogger(__name__)

# pilot-13's rasterizer settings (pilot-13.yaml) — reused so the new transcripts
# share the cached page renders + match the 26 wired invoices exactly.
_DEFAULT_RASTER_CACHE = Path("data/raw/smoke/multipage")
_DEFAULT_DPI = 300


@dataclass(frozen=True)
class ReaderPassConfig:
    """Knobs for the reader pass (defaults mirror pilot-13's Granite reader)."""

    reader_model: str = DEFAULT_READER_MODEL
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR
    raster_cache_dir: Path = _DEFAULT_RASTER_CACHE
    dpi: int = _DEFAULT_DPI


@dataclass
class ReaderPassResult:
    """Outcome of a reader pass."""

    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)


def _transcript_header(
    *,
    model_id: str,
    invoice_stem: str,
    n_pages: int,
    dpi: int,
    n_errors: int,
    total_seconds: float,
    prompt: str,
) -> str:
    """Replicate the harness transcript header (`_score_one_tuple`) verbatim."""
    prompt_preview = prompt.replace("\n", " ").replace("\t", " ")[:80]
    return (
        f"# Multi-page transcript (ADR-014 PR(c))\n"
        f"# Model:    {model_id}\n"
        f"# Invoice:  {invoice_stem}\n"
        f"# Pages:    {n_pages}\n"
        f"# DPI:      {dpi}\n"
        f"# Errors:   {n_errors}/{n_pages}\n"
        f"# Extract:  {total_seconds:.2f}s total\n"
        f"# Adapter:  regex\n"
        f"# Prompt:   {prompt_preview}\n"
        f"\n"
    )


def run_reader_pass(
    records: list[InvoiceRecord],
    *,
    config: ReaderPassConfig | None = None,
    overwrite: bool = False,
    limit: int | None = None,
    stems: set[str] | None = None,
) -> ReaderPassResult:
    """Transcribe every GT-bearing record lacking a transcript with the reader model.

    Streams per-invoice progress to stdout (`long-running-foreground`). Skips invoices
    whose transcript already exists in ``config.transcript_dir`` (unless ``overwrite``),
    making the pass resumable — the existence check is against the OUTPUT dir, so a
    bake-off pass into a fresh dir re-transcribes invoices that have a canonical
    transcript elsewhere. ``limit`` caps the number transcribed this invocation
    (spike-first discipline); ``stems`` restricts to a subset (e.g. the sealed val split).

    Returns a `ReaderPassResult` with written / skipped / failed stems.
    """
    cfg = config or ReaderPassConfig()
    manifest = COHORT_MANIFEST[cfg.reader_model]
    prompt: str = manifest["prompt_template"]
    max_tokens: int = manifest["max_tokens"]
    reader_slug = _model_slug(cfg.reader_model)

    targets: list[InvoiceRecord] = []
    result = ReaderPassResult()
    for rec in records:
        if not rec.has_gt:
            continue
        if stems is not None and rec.stem not in stems:
            continue
        out_path = cfg.transcript_dir / f"{reader_slug}__{rec.stem}.txt"
        if out_path.exists() and not overwrite:
            result.skipped.append(rec.stem)
            continue
        targets.append(rec)
    if limit is not None:
        targets = targets[:limit]

    print(
        f"Reader pass: {cfg.reader_model} over {len(targets)} invoice(s) "
        f"(prompt={prompt!r} max_tokens={max_tokens} dpi={cfg.dpi}); "
        f"{len(result.skipped)} already transcribed.",
        flush=True,
    )
    if not targets:
        return result

    # Any cohort extractor works as a reader — the protocol (load/extract/unload) is
    # framework-agnostic; MinerU2.5 (transformers-MPS) is a first-class bake-off candidate.
    extractor = get_extractor(cfg.reader_model)

    cfg.transcript_dir.mkdir(parents=True, exist_ok=True)
    extractor.load()
    try:
        for idx, rec in enumerate(targets, start=1):
            try:
                page_pngs = rasterize_pdf(
                    rec.pdf_path,
                    dpi=cfg.dpi,
                    cache_dir=cfg.raster_cache_dir,
                    image_format="png",
                )
                concatenated, per_page = _extract_and_concat(
                    extractor, page_pngs, prompt=prompt, max_tokens=max_tokens
                )
                n_errors = sum(1 for r in per_page if not r.is_ok)
                header = _transcript_header(
                    model_id=cfg.reader_model,
                    invoice_stem=rec.stem,
                    n_pages=len(page_pngs),
                    dpi=cfg.dpi,
                    n_errors=n_errors,
                    total_seconds=sum(r.extract_seconds for r in per_page),
                    prompt=prompt,
                )
                out_path = cfg.transcript_dir / f"{reader_slug}__{rec.stem}.txt"
                out_path.write_text(header + concatenated, encoding="utf-8")
                result.written.append(rec.stem)
                print(
                    f"  [{idx}/{len(targets)}] {rec.stem}: "
                    f"{len(page_pngs)} page(s), {n_errors} err -> {out_path.name}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001 — per-invoice robustness; one bad PDF must not abort
                result.failures.append((rec.stem, f"{type(exc).__name__}: {exc}"))
                print(
                    f"  [{idx}/{len(targets)}] {rec.stem}: FAILED {type(exc).__name__}: {exc}",
                    flush=True,
                )
    finally:
        try:
            extractor.unload()
        except Exception as exc:  # noqa: BLE001 — cleanup is best-effort
            _LOGGER.warning("reader unload() failed: %s", exc)

    print(
        f"Reader pass done: {len(result.written)} written, "
        f"{len(result.failures)} failed, {len(result.skipped)} skipped.",
        flush=True,
    )
    return result
