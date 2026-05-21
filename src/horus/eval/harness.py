"""Cohort orchestration harness — `(model × invoice) → MLflow nested run` per ADR-014.

Top-level entry point: `run_cohort(cfg)`. Iterates over the cohort × ZUGFeRD-corpus
cross-product, rasterizes each PDF to multi-page PNGs (per ADR-014 §5.1, pypdfium2 @
300 DPI), runs each model on each page, concatenates per-page outputs (Strategy α per
ADR-014 §5.2), extracts ground truth via `factur-x` (NOT sidecar route per ADR-012
Probe 5), scores with PR(b)'s scorer, and logs every (model, invoice) tuple as a
nested MLflow run under a single parent. Resume-safe: ctrl-c → re-invoke → harness
picks up where it left off via `mlflow.search_runs` lookup.

Architecture (single-orchestrator design):

  Parent MLflow run: `pilot-13-full` (or as overridden in `cohort.parent_run_name`)
  ├── Nested: <model_id=A, invoice_id=I1>  — per-field JSON + transcript artifact
  ├── Nested: <model_id=A, invoice_id=I2>
  ├── …
  ├── Nested: <model_id=B, invoice_id=I1>
  └── …
  Parent artifacts:
    - cohort_heatmap.png         (rows = working_models, cols = 16 FIELDS, cells = mean ANLS*)
    - cohort_summary.json        (per-profile + pooled micro/macro F1 table)

Multi-page strategy (α per ADR-014 §5.2 — the model-agnostic baseline):

  Each PDF page is rasterized to a PNG. The harness calls `extractor.extract(page_png)`
  once per page (single-image-per-call — preserves ADR-009 evidence-base contract).
  The per-page outputs are concatenated with `===== PAGE N =====` separators into a
  single text string, then passed to PR(b)'s adapter pipeline (preprocess →
  to_predicted_dict → score). The separator is stripped before Layer 1 preprocessing
  by `_strip_page_separators` so it doesn't leak into adapter heuristics.

XRECHNUNG GT route (per ADR-012 Probe 5):

  All 26 ZUGFeRD fixtures (22 EN16931 + 4 XRECHNUNG) use `factur-x.get_xml_from_pdf` to
  extract the PDF-embedded XML attachment — NOT the FeRD-shipped `.cii.xml` sidecar.
  For EN16931 fixtures the two routes are byte-equivalent. For XRECHNUNG fixtures the
  sidecars carry 2024-11-15 dates (FeRD-substituted) while the embedded XML carries the
  original 2018-era dates (silent F1 corruption hazard if sidecar were used). The
  harness tags every nested run with `xml_route=facturx` to make this auditable.

Resume safety (per ADR-014 §5.3):

  Each (model, invoice) is an atomic unit. On re-invoke, the harness queries
  `mlflow.search_runs(filter="tags.model_id=… AND tags.invoice_id=… AND status='FINISHED'",
  experiment_ids=[exp])` and skips any nested run that has already completed. Effect:
  ctrl-c → re-invoke `make pilot-13` → harness re-uses the existing parent run and
  loops over only the unfinished (model, invoice) tuples. Toggle via
  `cfg.cohort.resume_on_existing_run` (default True).

Failure mode (per ADR-014 §5.4):

  Per-(model, invoice) exceptions are caught and logged as `status=FAILED` + `error_type`
  tag on the nested run; the harness continues with the next invoice. Per-model
  `load()` failure tags every invoice for that model with `skip_reason=load_failed`
  and moves to the next model. The 3 ADR-009 errored models (DeepSeek-OCR-2,
  Qwen3-VL-4B-Instruct, Molmo-7B-D) are simply absent from `cfg.cohort.working_models`
  — they aren't hard-excluded by code; they just aren't requested.

Refs:
  - ADR-014 §"Decision + integration thoughts" (this module's enabling ADR — forthcoming)
  - ADR-013 §"Decision" + PR(b) scorer (the downstream scoring contract)
  - ADR-012 §"Probe 5" (the XRECHNUNG sidecar drift hazard this module mitigates)
  - ADR-011 §"Decision" + MLflowTracker (the tracking contract)
  - ADR-009 Amendment 1 (the 10-model cohort substrate; 7 working models)
  - ADR-007 (per-model longest_edge=2048 internal resize — unchanged by 300 DPI rasterization)
  - `.windsurf/rules/horus-config-discipline.md` (knobs live in YAML, not in `.py`)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from horus.config import ExperimentConfig
from horus.eval import adapters as adapters_regex
from horus.eval import adapters_json
from horus.eval.ground_truth import FIELDS, GroundTruth, parse_cii_xml
from horus.eval.rasterize import rasterize_pdf
from horus.eval.scorer import InvoiceFieldScores, score
from horus.vlm_extractor import COHORT_MANIFEST, ExtractionResult, get_extractor

if TYPE_CHECKING:
    import matplotlib.figure

__all__ = ["HarnessRunResult", "run_cohort"]

_LOGGER = logging.getLogger(__name__)

# Page-separator pattern. The chosen prefix `===== PAGE` is unlikely to collide with
# any cohort model's output format (DocTags use `<page_header>`, MinerU uses `<nl>`,
# plain markdown uses `#` / `##`). The separator is stripped from concatenated text
# before adapter Layer 1 runs (it's a transcript-archive aid, not a model-text feature).
_PAGE_SEPARATOR_FMT = "===== PAGE {page} ====="
_PAGE_SEPARATOR_RE = re.compile(r"^={5}\s+PAGE\s+\d+\s+={5}\s*$", flags=re.MULTILINE)


# ===========================================================================
# Public result type
# ===========================================================================


@dataclass(frozen=True)
class HarnessRunResult:
    """Aggregate result for one parent cohort run.

    Returned by `run_cohort()`. Captures the state needed by the CLI runner
    + writeup author to report "what happened" without re-querying MLflow.
    """

    parent_run_id: str
    n_models_attempted: int
    n_models_loaded: int  # successfully loaded (load() didn't raise)
    n_skipped_resume: int  # (model, invoice) skipped because already-FINISHED
    n_completed: int  # (model, invoice) scored to FINISHED in THIS invocation
    n_failed: int  # (model, invoice) errored in THIS invocation
    n_invoices_total: int  # number of distinct invoices in the sweep
    cohort_micro_f1_pooled: float
    cohort_micro_f1_en16931: float
    cohort_micro_f1_xrechnung: float
    per_field_heatmap: dict[str, dict[str, float]] = field(default_factory=dict)


# ===========================================================================
# Internal — corpus discovery
# ===========================================================================


def _list_paired_invoices(
    corpus_root: Path,
    *,
    prefix: str | None = None,
) -> list[tuple[Path, Path]]:
    """Return `(pdf_path, cii_sidecar_path)` pairs for every PDF in `<corpus_root>/XML-Rechnung/FX/`
    whose name matches a sidecar in `<corpus_root>/XML-Rechnung/CII/`.

    Mirrors the production-code-side of `tests.conftest._list_paired_invoices`. The
    sidecars are NOT used for GT parsing (per ADR-012 Probe 5 — the harness uses the
    PDF-embedded factur-x XML for all 26 fixtures); the sidecar list is the pairing
    discriminator only ("if a sidecar exists, treat the PDF as a paired ZUGFeRD invoice").

    Args:
        corpus_root: Repo-relative or absolute path to the ZUGFeRD corpus root
            (e.g., `data/raw/german/zugferd-corpus`). Must contain
            `XML-Rechnung/{FX,CII}/` sub-directories.
        prefix: Optional PDF-stem prefix filter. `"EN16931_"` returns the 22
            EN16931-profile invoices; `"XRECHNUNG_"` returns the 4 XRECHNUNG-
            profile ones; `None` (default) returns all 26.

    Returns:
        Sorted list of `(pdf_path, cii_sidecar_path)` tuples. Empty if the
        corpus directories don't exist or no pairs are found.
    """
    fx_dir = corpus_root / "XML-Rechnung" / "FX"
    cii_dir = corpus_root / "XML-Rechnung" / "CII"
    if not fx_dir.is_dir() or not cii_dir.is_dir():
        return []

    pairs: list[tuple[Path, Path]] = []
    for pdf_path in sorted(fx_dir.glob("*.pdf")):
        if prefix is not None and not pdf_path.stem.startswith(prefix):
            continue
        sidecar = cii_dir / f"{pdf_path.stem}.cii.xml"
        if sidecar.is_file():
            pairs.append((pdf_path, sidecar))
    return pairs


def _invoice_profile(pdf_stem: str) -> str:
    """Return `"EN16931"` or `"XRECHNUNG"` based on the PDF stem prefix.

    Used for the per-profile aggregation split (per ADR-014 §5.5).
    """
    if pdf_stem.startswith("EN16931_"):
        return "EN16931"
    if pdf_stem.startswith("XRECHNUNG_"):
        return "XRECHNUNG"
    return "UNKNOWN"


# ===========================================================================
# Internal — GT extraction (factur-x route, per ADR-012 Probe 5)
# ===========================================================================


def _extract_groundtruth_via_facturx(pdf_path: Path) -> GroundTruth | None:
    """Extract the GT via the PDF-embedded factur-x XML attachment.

    NOT the sidecar route — per ADR-012 Probe 5, FeRD-shipped `.cii.xml` sidecars for
    XRECHNUNG fixtures carry 2024-11-15 dates while the PDF-embedded XML carries the
    original 2018-era dates. Using the sidecar route would silently corrupt the DATE
    field F1 for XRECHNUNG invoices.

    Returns None if the PDF has no factur-x attachment (e.g., a Hetzner PDF).
    Callers MUST handle None — typically by skipping the invoice + logging a
    warning tag.
    """
    import facturx  # noqa: PLC0415 — defer heavy import

    pdf_bytes = pdf_path.read_bytes()
    name, xml_bytes = facturx.get_xml_from_pdf(
        pdf_bytes,
        check_xsd=False,
        check_schematron=False,
    )
    if not name or not xml_bytes:
        return None
    return parse_cii_xml(xml_bytes)


# ===========================================================================
# Internal — multi-page extraction + concatenation (Strategy α per ADR-014 §5.2)
# ===========================================================================


def _extract_and_concat(
    extractor: Any,  # VLMExtractor Protocol — Any to avoid forward-ref issues
    page_pngs: list[Path],
    *,
    prompt: str,
    max_tokens: int,
) -> tuple[str, list[ExtractionResult]]:
    """Run `extractor.extract()` once per page; concatenate with page separators.

    The extractor's contract is single-image-per-call (per ADR-009). For multi-page
    invoices this function loops over the rasterized pages, calls extract() once per
    page, and concatenates the outputs into a single text string with `===== PAGE N =====`
    separators. The separator string is chosen to NOT collide with any cohort model's
    output format (see `_PAGE_SEPARATOR_FMT` module comment).

    Per-page extraction is independent: if page 3 errors, pages 1-2 still contribute.
    The returned text combines successful pages only (errored pages contribute an empty
    string + their separator header for transcript-archive traceability).

    Returns:
        `(concatenated_text, per_page_results)` — the second element is the list of
        per-page `ExtractionResult` objects so the caller can log per-page latencies
        + error counts.
    """
    chunks: list[str] = []
    per_page_results: list[ExtractionResult] = []

    for i, page_png in enumerate(page_pngs, start=1):
        result = extractor.extract(image_path=page_png, prompt=prompt, max_tokens=max_tokens)
        per_page_results.append(result)
        separator = _PAGE_SEPARATOR_FMT.format(page=i)
        chunks.append(separator)
        chunks.append(result.text)  # empty string on error; that's fine

    concatenated = "\n".join(chunks)
    return concatenated, per_page_results


def _strip_page_separators(text: str) -> str:
    """Remove `===== PAGE N =====` separator lines from concatenated text.

    Called before adapter Layer 1 (`preprocess`) so the separators don't leak into
    per-model heuristics (e.g., MinerU's table-detection or DocTags structural
    parsing). The separators are preserved in the archived transcript file (which is
    what humans + future debugging inspect); only the scorer-input is stripped.
    """
    return _PAGE_SEPARATOR_RE.sub("", text)


# ===========================================================================
# Internal — MLflow resume-safety
# ===========================================================================


def _find_finished_nested_run(
    *,
    experiment_id: str,
    parent_run_id: str,
    model_id: str,
    invoice_id: str,
) -> str | None:
    """Query MLflow for a previously-FINISHED nested run matching the given (model, invoice).

    Returns the existing run_id if found, else None. The harness skips already-FINISHED
    nested runs to make the cohort sweep interruptible (per ADR-014 §5.3).

    Filter semantics: the parent_run_id is matched via the implicit `mlflow.parentRunId`
    tag that MLflow sets on nested runs; combined with `tags.model_id` + `tags.invoice_id`
    this is unique per (model, invoice) under one parent.

    Returns None if `mlflow.search_runs` raises (transient backend issue, missing
    experiment, etc.) — letting the harness fall back to re-running rather than
    failing the whole sweep.
    """
    import mlflow  # noqa: PLC0415 — defer heavy import

    try:
        # `mlflow.parentRunId` is the MLflow built-in tag for nested-run hierarchies.
        filter_string = (
            f"tags.mlflow.parentRunId = '{parent_run_id}' "
            f"AND tags.model_id = '{model_id}' "
            f"AND tags.invoice_id = '{invoice_id}' "
            f"AND status = 'FINISHED'"
        )
        # `output_format="list"` returns `list[mlflow.entities.Run]` instead of the
        # pandas-DataFrame default. List is cleaner for index-by-zero + mypy-friendly.
        runs = mlflow.search_runs(
            experiment_ids=[experiment_id],
            filter_string=filter_string,
            max_results=1,
            output_format="list",
        )
        if not runs:
            return None
        return str(runs[0].info.run_id)
    except Exception:  # noqa: BLE001 — never crash the sweep on a search hiccup
        _LOGGER.warning(
            "search_runs failed for (%s, %s); will re-run rather than skip",
            model_id,
            invoice_id,
        )
        return None


# ===========================================================================
# Internal — single (model, invoice) scoring atomic unit
# ===========================================================================


def _score_single_invoice(
    *,
    model_id: str,
    pdf_path: Path,
    extractor: Any,  # VLMExtractor — already loaded
    prompt: str,
    max_tokens: int,
    raster_cache_dir: Path,
    raster_dpi: int,
    raster_format: str,
    transcript_archive_dir: Path,
    gt: GroundTruth,
    eval_cfg: Any,  # EvalConfig | None — None falls back to scorer's defaults
    adapter_module: Any = adapters_regex,  # ADR-018: adapters_regex (default) | adapters_json
) -> tuple[InvoiceFieldScores, str, list[ExtractionResult]]:
    """Score one (model, invoice) tuple end-to-end.

    Pipeline:
      1. Rasterize PDF to N page PNGs (cached).
      2. For each page: extractor.extract(page_png) → ExtractionResult.
      3. Concat per-page text with `===== PAGE N =====` separators (archive-friendly).
      4. Strip separators → preprocess (Layer 1) → to_predicted_dict (Layer 2).
      5. score(predicted_dict, gt) → InvoiceFieldScores.
      6. Save concatenated text to transcript archive (`<dir>/<model_slug>__<stem>.txt`).

    Returns:
        `(scores, transcript_text, per_page_results)`. The transcript_text is what
        was saved to disk (with separators preserved); the score was computed against
        the separator-stripped version.

    Raises:
        Propagates rasterization + GT-parse failures. VLM extraction failures are
        caught inside the per-page loop and surface as empty-text page contributions
        (NOT raised — they're observed-but-not-fatal).
    """
    invoice_stem = pdf_path.stem

    # 1. Rasterize (cached, idempotent on resume).
    page_pngs = rasterize_pdf(
        pdf_path,
        dpi=raster_dpi,
        cache_dir=raster_cache_dir,
        image_format=raster_format,
    )

    # 2 + 3. Per-page extract + concat.
    concatenated, per_page_results = _extract_and_concat(
        extractor, page_pngs, prompt=prompt, max_tokens=max_tokens
    )

    # Archive the concatenated transcript BEFORE scoring (so even a scoring-side
    # exception doesn't lose the raw VLM output).
    transcript_archive_dir.mkdir(parents=True, exist_ok=True)
    model_slug = _model_slug(model_id)
    transcript_path = transcript_archive_dir / f"{model_slug}__{invoice_stem}.txt"
    # ADR-018: surface the prompt's first 80 chars in the transcript header so
    # reviewers can verify which arm (uniform / native+json / default) a given
    # transcript came from. Single-line replacement of newlines / tabs prevents
    # multi-line prompts from breaking the comment shape.
    prompt_preview = prompt.replace("\n", " ").replace("\t", " ")[:80]
    adapter_mode_tag = "json" if adapter_module is adapters_json else "regex"
    transcript_header = (
        f"# Multi-page transcript (ADR-014 PR(c))\n"
        f"# Model:    {model_id}\n"
        f"# Invoice:  {invoice_stem}\n"
        f"# Pages:    {len(page_pngs)}\n"
        f"# DPI:      {raster_dpi}\n"
        f"# Errors:   {sum(1 for r in per_page_results if not r.is_ok)}/{len(per_page_results)}\n"
        f"# Extract:  {sum(r.extract_seconds for r in per_page_results):.2f}s total\n"
        f"# Adapter:  {adapter_mode_tag}\n"
        f"# Prompt:   {prompt_preview}\n"
        f"\n"
    )
    transcript_path.write_text(transcript_header + concatenated, encoding="utf-8")

    # 4. Per-page parse + merge via the multipage adapter API.
    #    ADR-019 Wave 3.1: replaces the `_strip_page_separators(concatenated) →
    #    preprocess → to_predicted_dict` chain that silently dropped per-page-valid
    #    JSON shapes (Gemma-4 unfenced 2-dict concat per B1; GLM-OCR fence-bias
    #    asymmetry per B2; Granite decoder-loop dict-repetition per B3). The
    #    multipage API parses each page independently and merges with
    #    first-non-None-wins (page 1 dominant per ADR-012 tristate semantics);
    #    defends against page-2 hallucinations (e.g., olmOCR Arm B page 2's
    #    "Joghurt Banane" leaking into seller_name).
    #
    #    Both adapters (regex `adapters` + json `adapters_json`) expose the same
    #    `to_predicted_dict_multipage(per_page_texts, model_id)` signature per
    #    the parity test in tests/test_adapters_json.py
    #    ::test_public_surface_signature_parity_with_adapters.
    per_page_texts = [r.text for r in per_page_results]
    predicted_dict = adapter_module.to_predicted_dict_multipage(per_page_texts, model_id)

    # 5. Score.
    scores = score(
        predicted_dict,
        gt,
        cfg=eval_cfg,
        invoice_id=invoice_stem,
        model_id=model_id,
    )

    return scores, concatenated, per_page_results


# ===========================================================================
# Internal — cohort heatmap rendering
# ===========================================================================


def _render_cohort_heatmap(
    aggregate: dict[str, dict[str, float]],
    *,
    title: str,
) -> matplotlib.figure.Figure:
    """Render per-(model, field) ANLS-mean heatmap as a matplotlib Figure.

    Rows: model_ids in `aggregate.keys()` order (caller passes ordered dict).
    Cols: 16 FIELDS in canonical FieldType-clustered order (STRING → CODE → DATE → MONEY).
    Cells: mean ANLS* score across all invoices for that (model, field). NaN cells
    (model produced 0 valid scores for a field) render as the colormap's "bad" color.

    Colormap: viridis (perceptually uniform; print-friendly; ColorBrewer-compatible).
    Annotations: cell-value text overlay at >=0.5 (per-cell legibility; under-0.5
    is too dark for readable annotation against viridis).
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415 — defer heavy import
    import numpy as np  # noqa: PLC0415

    model_ids = list(aggregate.keys())
    field_keys = list(FIELDS.keys())  # FIELDS is dict[str, FieldSpec]; keys are field names
    n_models = len(model_ids)
    n_fields = len(field_keys)

    matrix = np.full((n_models, n_fields), np.nan, dtype=np.float64)
    for i, model_id in enumerate(model_ids):
        per_field = aggregate.get(model_id, {})
        for j, fk in enumerate(field_keys):
            if fk in per_field:
                matrix[i, j] = per_field[fk]

    fig, ax = plt.subplots(figsize=(max(8, n_fields * 0.7), max(4, n_models * 0.5)))
    cmap = plt.get_cmap("viridis")
    cmap.set_bad(color="lightgrey")  # NaN = no valid scores rendered
    im = ax.imshow(matrix, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")

    # Tick labels: short model_id stems on Y, full field keys on X.
    ax.set_xticks(np.arange(n_fields))
    ax.set_xticklabels(field_keys, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(np.arange(n_models))
    ax.set_yticklabels([_model_slug(m) for m in model_ids], fontsize=8)

    # Cell annotations at >=0.5 (legibility — viridis is too dark below this).
    for i in range(n_models):
        for j in range(n_fields):
            val = matrix[i, j]
            if not np.isnan(val) and val >= 0.5:
                ax.text(
                    j,
                    i,
                    f"{val:.2f}",
                    ha="center",
                    va="center",
                    color="white" if val < 0.75 else "black",
                    fontsize=7,
                )

    ax.set_title(title)
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Mean ANLS* / TP-rate across corpus", fontsize=9)
    fig.tight_layout()
    return fig


# ===========================================================================
# Internal — utility helpers
# ===========================================================================


def _model_slug(model_id: str) -> str:
    """Convert canonical HF model_id to a filesystem-safe slug.

    Example: `ibm-granite/granite-docling-258M-mlx` → `ibm-granite__granite-docling-258m-mlx`.
    Used for transcript filenames + per-model nested-run names.
    """
    return model_id.replace("/", "__").lower()


def _aggregate_per_field_scores(
    per_invoice: dict[str, dict[str, list[float]]],
) -> dict[str, dict[str, float]]:
    """Reduce `model_id → field_key → [scores]` to `model_id → field_key → mean(scores)`.

    Empty score lists produce NaN (handled by `_render_cohort_heatmap`'s `set_bad`).
    """
    aggregate: dict[str, dict[str, float]] = {}
    for model_id, field_scores in per_invoice.items():
        aggregate[model_id] = {}
        for fk, scores in field_scores.items():
            if scores:
                aggregate[model_id][fk] = sum(scores) / len(scores)
    return aggregate


def _filter_models(
    working_models: list[str],
    *,
    subset: list[str] | None,
) -> list[str]:
    """Filter `cohort.working_models` by an optional subset (preserving working-models order)."""
    if subset is None:
        return list(working_models)
    subset_set = set(subset)
    unknown = subset_set - set(working_models)
    if unknown:
        raise ValueError(
            f"--models contains entries not in cohort.working_models: {sorted(unknown)}"
        )
    return [m for m in working_models if m in subset_set]


def _filter_invoices(
    pairs: list[tuple[Path, Path]],
    *,
    subset: list[str] | None,
) -> list[tuple[Path, Path]]:
    """Filter paired invoices by an optional list of PDF stems.

    Strict matching: every stem in `subset` MUST match a pair in the corpus. Per
    ADR-016 + `CohortConfig.invoice_subset` field docstring — unmatched entries
    raise at harness boot (no silent skips). This catches typos in dev-overlay
    YAML before any model loads or compute is spent (fail-fast discipline).
    """
    if subset is None:
        return pairs
    subset_set = set(subset)
    available_stems = {pdf.stem for pdf, _ in pairs}
    unmatched = subset_set - available_stems
    if unmatched:
        raise ValueError(
            f"invoice_subset contains {len(unmatched)} entries not found in the "
            f"corpus: {sorted(unmatched)}. "
            f"Available stems: {sorted(available_stems)[:10]}… "
            f"(of {len(available_stems)} total). "
            f"Check the CLI INVOICES= or cohort.invoice_subset YAML field."
        )
    matched = [(pdf, cii) for pdf, cii in pairs if pdf.stem in subset_set]
    if not matched:
        # Defense in depth — if all entries matched the unmatched check above but
        # filtering still produced 0, the corpus discovery is broken. Should be
        # unreachable, but raise rather than return [].
        raise ValueError(
            f"invoice_subset matched 0 fixtures despite all entries present in "
            f"the corpus. This indicates a discovery bug. subset={sorted(subset_set)}"
        )
    return matched


def _snapshot_mps_driver_alloc_mb_or_none(extractor: Any) -> float | None:
    """Return `torch.mps.driver_allocated_memory()` in MB, or None when not applicable.

    Backend-aware: only fires for `transformers-mps` extractors. MLX-path
    extractors get their peak via `GenerationResult.peak_memory` and do NOT
    need this snapshot. Per ADR-017 §"Decision 2 (D2.A)": this is the
    snapshot-based approach to the PyTorch MPS peak-memory gap
    (`torch.mps` has no `max_memory_allocated`-equivalent, see
    pytorch/pytorch#104188). Documented limitation: snapshot misses
    transient peak during `model.generate()` itself; captures steady-state
    post-load weights + activation residue.

    Returns None when:

    - Extractor's `backend_name` is not `"transformers-mps"` (no-op for MLX
      / PaddleOCR / GLM-OCR backends).
    - `torch` cannot be imported (defensive — torch is a runtime dep, but
      future deployments may exclude it for MLX-only setups).
    - `torch.backends.mps.is_available()` is False (CI, non-Apple-Silicon
      dev hosts).
    - The snapshot call itself raises (transient PyTorch issue; non-fatal).

    Callers MUST treat None as "skip MPS-specific metrics for this tuple".

    Refs:
      - PyTorch MPS API docs: `torch.mps.driver_allocated_memory()` returns
        the driver-managed memory total (includes cache). The closest
        approximation to "actual GPU usage" available on MPS.
      - ADR-017 §"Decision 2": rationale for snapshot-over-sampler.
    """
    if getattr(extractor, "backend_name", None) != "transformers-mps":
        return None
    try:
        import torch  # noqa: PLC0415 — defer heavy import

        if not torch.backends.mps.is_available():
            return None
        # driver_allocated_memory returns bytes; convert to MB (matches the
        # MLflow metric naming `perf.mps_*_alloc_mb`).
        return torch.mps.driver_allocated_memory() / (1024.0 * 1024.0)
    except Exception:  # noqa: BLE001 — non-fatal; let harness log without MPS metrics
        return None


# ===========================================================================
# Public orchestrator
# ===========================================================================


# Per ADR-016: canonical "production" MLflow experiment names that MUST NEVER
# receive a `dev_only=true` run. The dev_only forcing function (per
# brainstorm v2 §2 No-HARKing + NeurIPS Paper Checklist) blocks any dev-tier
# config from polluting the canonical thesis-reporting experiment.
#
# Expand when new canonical experiments land (e.g., post-fine-tuning).
_CANONICAL_PRODUCTION_EXPERIMENTS: frozenset[str] = frozenset({"pilot-13-full"})


def run_cohort(
    cfg: ExperimentConfig,
    *,
    invoice_subset: list[str] | None = None,
    model_subset: list[str] | None = None,
) -> HarnessRunResult:
    """Run the full (cohort × corpus) cross-product → MLflow nested runs → cohort heatmap.

    Per-(model, invoice) atomic unit (per ADR-014 §"Architecture"):

      1. Resume check: skip if a FINISHED nested run already exists with matching tags.
      2. Rasterize PDF (cached, mtime-invalidated).
      3. Extract VLM output per page → concat via `_extract_and_concat`.
      4. Extract GT via `extract_via_facturx` (NOT sidecar — per ADR-012 Probe 5).
      5. Adapter Layer 1 (preprocess) + Layer 2 (to_predicted_dict) → predicted_dict.
      6. Score → `InvoiceFieldScores`.
      7. Log nested MLflow run with tags + metrics + per_field_scores.json + transcript.txt.

    Per-model lifecycle: `extractor.load()` once → loop over invoices → `extractor.unload()`
    before next model. Loading order: `transformers-first` (preserves the
    `mlx_vlm`-monkey-patches-transformers contamination caveat documented in
    `horus.vlm_extractor`).

    Failure handling:
      - Per-(model, invoice) exceptions → log `status=FAILED` + `error_type` tag,
        continue to next invoice.
      - Per-model `load()` failure → log every invoice for that model as
        `skip_reason=load_failed`, continue with next model.

    Args:
        cfg: Loaded ExperimentConfig (Pydantic-validated). MUST have `cfg.cohort` +
            `cfg.rasterizer` non-None.
        invoice_subset: Optional list of PDF stems to restrict the sweep to. None =
            all paired invoices in the corpus.
        model_subset: Optional list of model_ids to restrict the sweep to. None =
            all `cfg.cohort.working_models`. Subset entries MUST be in
            `cfg.cohort.working_models` (raises ValueError otherwise).

    Returns:
        `HarnessRunResult` summarizing the run (parent_run_id, counts, F1 numbers,
        per-field heatmap dict).

    Raises:
        ValueError: if `cfg.cohort` or `cfg.rasterizer` is None.
        ValueError: if `invoice_subset` or `model_subset` contains unknown entries.
    """
    import mlflow  # noqa: PLC0415

    # ----- 1. Validate config -----
    if cfg.cohort is None:
        raise ValueError("cfg.cohort is None — run_cohort requires a CohortConfig")
    if cfg.rasterizer is None:
        raise ValueError("cfg.rasterizer is None — run_cohort requires a RasterizerConfig")
    cohort_cfg = cfg.cohort
    raster_cfg = cfg.rasterizer
    eval_cfg = cfg.eval  # may be None — score() handles defaults

    # Per ADR-016: dev_only=true configs MUST NOT target a canonical production
    # experiment. Forcing function against accidentally HARKing on the thesis-
    # reported numbers. Fail fast — before any model loads.
    if cohort_cfg.dev_only and cfg.mlflow.experiment_name in _CANONICAL_PRODUCTION_EXPERIMENTS:
        raise ValueError(
            f"dev_only=true config refuses to log to canonical production "
            f"experiment {cfg.mlflow.experiment_name!r}. Use a distinct "
            f"experiment_name (e.g., 'pilot-13-dev') in mlflow.experiment_name. "
            f"Per ADR-016 HARKing-prevention forcing function. "
            f"Canonical production experiments: {sorted(_CANONICAL_PRODUCTION_EXPERIMENTS)}"
        )

    # ----- 2. Resolve cohort + corpus -----
    # CLI > YAML > full-corpus precedence per ADR-016. The CLI `invoice_subset`
    # kwarg (e.g., `INVOICES=...` on `make pilot-13`) wins; falls through to
    # the declarative `cohort.invoice_subset` YAML field; falls through to None
    # (= all paired invoices in the corpus).
    effective_invoice_subset = (
        invoice_subset if invoice_subset is not None else cohort_cfg.invoice_subset
    )
    pairs = _list_paired_invoices(cohort_cfg.corpus_root)
    pairs = _filter_invoices(pairs, subset=effective_invoice_subset)
    models = _filter_models(cohort_cfg.working_models, subset=model_subset)

    if not pairs:
        raise ValueError(
            f"Found 0 paired invoices under {cohort_cfg.corpus_root}. "
            f"Expected `<corpus_root>/XML-Rechnung/{{FX,CII}}/`."
        )

    _LOGGER.info(
        "run_cohort: %d models × %d invoices = %d (model, invoice) tuples",
        len(models),
        len(pairs),
        len(models) * len(pairs),
    )

    # ----- 3. Set up MLflow parent run -----
    mlflow.set_experiment(cfg.mlflow.experiment_name)
    experiment = mlflow.get_experiment_by_name(cfg.mlflow.experiment_name)
    if experiment is None:
        raise RuntimeError(
            f"MLflow experiment {cfg.mlflow.experiment_name!r} unexpectedly missing "
            "after set_experiment — check tracking_uri configuration."
        )
    experiment_id = experiment.experiment_id

    # ----- 4. Aggregation accumulators -----
    per_field_scores_acc: dict[str, dict[str, list[float]]] = {m: {} for m in models}
    per_profile_outcomes: dict[str, dict[str, int]] = {
        "EN16931": {"tp": 0, "fp": 0, "fn": 0},
        "XRECHNUNG": {"tp": 0, "fp": 0, "fn": 0},
        "POOLED": {"tp": 0, "fp": 0, "fn": 0},
    }
    n_models_loaded = 0
    n_skipped_resume = 0
    n_completed = 0
    n_failed = 0
    parent_run_id: str = ""

    # Cached for tagging across all nested runs (parent + per-(model, invoice)).
    # Stringified to match MLflow's tag-value-is-str contract; lowercase for
    # cross-tool consistency with how Python bool repr (`True`/`False`) renders.
    dev_only_tag_value = str(cohort_cfg.dev_only).lower()

    # ----- 5. Parent run + nested loop -----
    with mlflow.start_run(run_name=cohort_cfg.parent_run_name) as parent_run:
        parent_run_id = parent_run.info.run_id

        # Parent tags from config
        for key, value in cfg.mlflow.run_tags.items():
            mlflow.set_tag(key, value)
        mlflow.set_tag("n_models", str(len(models)))
        mlflow.set_tag("n_invoices", str(len(pairs)))
        mlflow.set_tag("resume_enabled", str(cohort_cfg.resume_on_existing_run))
        mlflow.set_tag("dev_only", dev_only_tag_value)
        # ADR-018: surface the adapter dispatch on the parent run so MLflow
        # search_runs can filter on it (e.g., `tags.adapter_mode = 'json'` to
        # find probe runs without re-iterating nested-run tags).
        mlflow.set_tag("adapter_mode", cohort_cfg.adapter_mode)
        mlflow.log_param("seed", cfg.seed)
        mlflow.log_param("dpi", raster_cfg.dpi)
        if eval_cfg is not None:
            mlflow.log_param("anls_threshold", eval_cfg.anls_threshold)

        # ADR-017 (issue #52) — parent-level MPS ceiling. Constant per host;
        # logged once so the inspector can compute `pct_of_ceiling = peak /
        # ceiling` without per-tuple duplication. Silent NOOP on hosts
        # without MPS (CI, non-Apple-Silicon dev machines). The `try/except`
        # also swallows the case where torch is importable but MPS-init
        # fails (e.g., headless macOS env). Per `know-your-hardware`: M1 Pro
        # 16 GB returns ~10-12 GB ceiling — the OS reserves the rest for
        # system processes.
        try:
            import torch  # noqa: PLC0415 — defer heavy import

            if torch.backends.mps.is_available():
                mps_ceiling_gb = torch.mps.recommended_max_memory() / 1e9
                mlflow.log_metric("perf.mps_recommended_max_gb", mps_ceiling_gb)
        except Exception:  # noqa: BLE001 — non-fatal; harness continues
            pass

        print(
            f"[harness] parent_run_id={parent_run_id} models={len(models)} invoices={len(pairs)}",
            flush=True,
        )

        # Per-model loop
        for model_idx, model_id in enumerate(models, start=1):
            print(
                f"[harness] [model {model_idx}/{len(models)}] loading {model_id} ...",
                flush=True,
            )

            manifest_entry = COHORT_MANIFEST[model_id]
            # ADR-018: per-model prompt override map (cohort.prompt_template_override)
            # falls through to COHORT_MANIFEST defaults for models not present in the
            # override dict. Partial-coverage dicts (some models, not all) are valid;
            # the cross-field validator on CohortConfig already rejected unknown keys
            # at boot, so a `.get(model_id, default)` here is safe and intentional.
            prompt_override = cohort_cfg.prompt_template_override or {}
            prompt = prompt_override.get(model_id, manifest_entry["prompt_template"])
            max_tokens = manifest_entry["max_tokens"]

            extractor = get_extractor(model_id)
            load_failed = False
            try:
                extractor.load()
                n_models_loaded += 1
            except Exception as exc:  # noqa: BLE001 — capture install/load failures
                load_failed = True
                print(
                    f"[harness] [model {model_idx}/{len(models)}] LOAD FAILED: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            # Per-invoice loop
            for inv_idx, (pdf_path, _cii_path) in enumerate(pairs, start=1):
                invoice_stem = pdf_path.stem
                profile = _invoice_profile(invoice_stem)

                # Resume check
                if cohort_cfg.resume_on_existing_run:
                    existing = _find_finished_nested_run(
                        experiment_id=experiment_id,
                        parent_run_id=parent_run_id,
                        model_id=model_id,
                        invoice_id=invoice_stem,
                    )
                    if existing is not None:
                        n_skipped_resume += 1
                        print(
                            f"[harness]   [{inv_idx}/{len(pairs)}] {invoice_stem}: "
                            f"SKIP (resume; run_id={existing[:8]})",
                            flush=True,
                        )
                        continue

                if load_failed:
                    # Log a skipped nested run so the heatmap accounting is consistent.
                    with mlflow.start_run(
                        run_name=f"{_model_slug(model_id)}__{invoice_stem}",
                        nested=True,
                    ):
                        mlflow.set_tag("model_id", model_id)
                        mlflow.set_tag("invoice_id", invoice_stem)
                        mlflow.set_tag("profile", profile)
                        mlflow.set_tag("xml_route", "facturx")
                        mlflow.set_tag("dev_only", dev_only_tag_value)
                        mlflow.set_tag("skip_reason", "load_failed")
                        mlflow.end_run(status="FAILED")
                    n_failed += 1
                    continue

                # Score the (model, invoice) atomic unit.
                try:
                    gt = _extract_groundtruth_via_facturx(pdf_path)
                    if gt is None:
                        with mlflow.start_run(
                            run_name=f"{_model_slug(model_id)}__{invoice_stem}",
                            nested=True,
                        ):
                            mlflow.set_tag("model_id", model_id)
                            mlflow.set_tag("invoice_id", invoice_stem)
                            mlflow.set_tag("profile", profile)
                            mlflow.set_tag("xml_route", "facturx")
                            mlflow.set_tag("dev_only", dev_only_tag_value)
                            mlflow.set_tag("error_type", "no_facturx_attachment")
                            mlflow.end_run(status="FAILED")
                        n_failed += 1
                        continue

                    # ADR-017 §D2.A — MPS driver-allocated memory snapshot
                    # (pre). Returns None for non-MPS backends (MLX path
                    # uses GenerationResult.peak_memory instead).
                    mps_pre_alloc_mb = _snapshot_mps_driver_alloc_mb_or_none(extractor)

                    t_start = time.perf_counter()
                    # ADR-018: dispatch adapter module via cohort.adapter_mode
                    # (Literal["regex", "json"]). Binary dispatch — NOT a
                    # pluggable framework. At exactly 2 variants this stays under
                    # ADR-016 supersession trigger #3 ("past 2 variants").
                    adapter_module = (
                        adapters_json
                        if cohort_cfg.adapter_mode == "json"
                        else adapters_regex
                    )
                    scores, _transcript, per_page = _score_single_invoice(
                        model_id=model_id,
                        pdf_path=pdf_path,
                        extractor=extractor,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        raster_cache_dir=raster_cfg.cache_dir,
                        raster_dpi=raster_cfg.dpi,
                        raster_format=raster_cfg.image_format,
                        transcript_archive_dir=cohort_cfg.transcript_archive_dir,
                        gt=gt,
                        eval_cfg=eval_cfg,
                        adapter_module=adapter_module,
                    )
                    elapsed = time.perf_counter() - t_start

                    # ADR-017 §D2.A — MPS driver-allocated memory snapshot
                    # (post). The pre+post pair lets the inspector report
                    # both the steady-state (post-load weights + activation
                    # residue) and the delta (activation footprint during
                    # the extract call).
                    mps_post_alloc_mb = _snapshot_mps_driver_alloc_mb_or_none(extractor)

                    # Nested run logging
                    with mlflow.start_run(
                        run_name=f"{_model_slug(model_id)}__{invoice_stem}",
                        nested=True,
                    ):
                        mlflow.set_tag("model_id", model_id)
                        mlflow.set_tag("invoice_id", invoice_stem)
                        mlflow.set_tag("profile", profile)
                        mlflow.set_tag("xml_route", "facturx")
                        mlflow.set_tag("dev_only", dev_only_tag_value)
                        mlflow.set_tag("adapter_mode", cohort_cfg.adapter_mode)
                        mlflow.set_tag("pages", str(len(per_page)))
                        mlflow.set_tag("page_errors", str(sum(1 for r in per_page if not r.is_ok)))

                        mlflow.log_metric("micro_f1", scores.micro_f1)
                        mlflow.log_metric("macro_f1", scores.macro_f1)
                        mlflow.log_metric("micro_precision", scores.micro_precision)
                        mlflow.log_metric("micro_recall", scores.micro_recall)
                        mlflow.log_metric("extract_seconds_total", elapsed)
                        extract_seconds_pages_total = sum(r.extract_seconds for r in per_page)
                        mlflow.log_metric(
                            "extract_seconds_pages",
                            extract_seconds_pages_total,
                        )

                        # ADR-017 (issue #52, Amendment 1) — per-tuple perf metrics.
                        # All values are aggregates of per-page ExtractionResult
                        # fields (populated by the extractors in Chunk 1).
                        #
                        # Amendment 1 (post-merge research): the original
                        # design logged a single `perf.generation_tps_mean`
                        # computed as `total_gen_tokens / extract_seconds`,
                        # claimed to match Artificial Analysis methodology.
                        # Web-verified AA methodology
                        # (`docs/sources/tools/artificial-analysis-methodology.md`):
                        # AA "Output Speed" is DECODE-ONLY tokens-per-second,
                        # measured AFTER the first token arrives (excludes
                        # prompt encoding). The original formula computed
                        # END-TO-END TPS, not decode-only — a scientific
                        # correctness bug under the AA-claimed name. Amendment
                        # 1 splits the metric into two with explicit semantics:
                        #
                        #   * `perf.decode_tps_mean` — decode-only (matches AA
                        #     "Output Speed"). Computed as
                        #     `total_gen_tokens / total_decode_seconds`, where
                        #     `decode_seconds_per_page = gen_tokens / generation_tps`.
                        #     Only available when extractors expose decode-only
                        #     tps in `ExtractionResult.generation_tps` (MLX-VLM
                        #     path via `GenerationResult.generation_tps`).
                        #     For Transformers-MPS path, `generation_tps = 0.0`
                        #     per vlm_extractor.py — decode-only is unmeasurable
                        #     via public `transformers.generate(...)` API.
                        #     When no page exposes decode tps, this metric is
                        #     0.0 and `tags.decode_tps_available` is "false".
                        #
                        #   * `perf.inference_tps_mean` — end-to-end (system
                        #     throughput including prompt encoding). Computed
                        #     as `total_gen_tokens / extract_seconds_pages_total`.
                        #     Always computable for any backend that reports
                        #     `extract_seconds` + `generation_tokens`.
                        #
                        # Both metrics answer DIFFERENT questions
                        # ("how fast does the model decode?" vs "what
                        # end-to-end throughput does the user see?") and
                        # both are scientifically meaningful. The thesis
                        # H4 latency-efficiency comparison cites the AA-
                        # canonical `decode_tps` for cross-backend model-
                        # speed claims and `inference_tps` for user-facing
                        # latency claims.
                        #
                        # `perf.peak_memory_gb`: max across pages. For
                        # MLX-VLM path, populated from per-page
                        # `peak_memory_gb` (`mx.get_peak_memory()` — true
                        # peak). For Transformers-MPS path, per-page is
                        # 0.0 by design and the post-snapshot of
                        # `torch.mps.driver_allocated_memory()` overrides
                        # below (snapshot-based stand-in per ADR-017 §D2.A
                        # + pytorch/pytorch#104188 workaround).
                        ok_pages_results = [r for r in per_page if r.is_ok]
                        total_gen_tokens = sum(r.generation_tokens for r in per_page)
                        total_chars = sum(r.output_len_chars for r in per_page)

                        # Decode-only TPS: only includes pages where the
                        # extractor exposed `generation_tps > 0` (MLX-VLM
                        # path). Per-page decode_seconds = gen_tokens /
                        # gen_tps. Time-weighted aggregation per AA
                        # methodology.
                        decode_eligible = [
                            r
                            for r in per_page
                            if r.generation_tokens > 0 and r.generation_tps > 0.0
                        ]
                        if decode_eligible:
                            total_decode_seconds = sum(
                                r.generation_tokens / r.generation_tps for r in decode_eligible
                            )
                            total_decode_tokens = sum(r.generation_tokens for r in decode_eligible)
                            decode_tps_mean = (
                                total_decode_tokens / total_decode_seconds
                                if total_decode_seconds > 0.0
                                else 0.0
                            )
                            decode_tps_available = True
                        else:
                            decode_tps_mean = 0.0
                            decode_tps_available = False

                        # End-to-end TPS: total tokens / total extract wall-
                        # clock. Includes prompt encoding + decode + post-
                        # processing. Always computable when extract_seconds
                        # > 0 and tokens > 0.
                        if total_gen_tokens > 0 and extract_seconds_pages_total > 0.0:
                            inference_tps_mean = total_gen_tokens / extract_seconds_pages_total
                        else:
                            inference_tps_mean = 0.0

                        chars_per_sec = (
                            total_chars / extract_seconds_pages_total
                            if extract_seconds_pages_total > 0.0
                            else 0.0
                        )
                        peak_mem_gb_max = max(
                            (r.peak_memory_gb for r in per_page if r.peak_memory_gb > 0.0),
                            default=0.0,
                        )
                        # ADR-017 §D2.A — Transformers-MPS path: per-page
                        # peak_memory_gb is 0.0 by design (no
                        # `torch.mps.max_memory_allocated` equivalent per
                        # pytorch/pytorch#104188). The post-snapshot of
                        # `torch.mps.driver_allocated_memory()` is the
                        # snapshot-based stand-in: captures steady-state
                        # weights + activation residue. Misses transient
                        # peak during model.generate(); documented limitation
                        # surfaced in the inspector + README + thesis writeup.
                        if mps_post_alloc_mb is not None:
                            peak_mem_gb_max = mps_post_alloc_mb / 1024.0
                        mlflow.log_metric("perf.generation_tokens_total", float(total_gen_tokens))
                        mlflow.log_metric("perf.decode_tps_mean", decode_tps_mean)
                        mlflow.log_metric("perf.inference_tps_mean", inference_tps_mean)
                        mlflow.set_tag(
                            "perf.decode_tps_available",
                            "true" if decode_tps_available else "false",
                        )
                        mlflow.log_metric("perf.output_len_chars_total", float(total_chars))
                        mlflow.log_metric("perf.chars_per_sec", chars_per_sec)
                        mlflow.log_metric("perf.peak_memory_gb", peak_mem_gb_max)
                        mlflow.log_metric("perf.pages_extracted_ok", float(len(ok_pages_results)))
                        # ADR-017 §D2.A — MPS-only metrics: pre + post + delta.
                        # Only logged when the backend is `transformers-mps`
                        # AND MPS is available (else `_snapshot_mps_driver_alloc_mb_or_none`
                        # returned None and we skip per ADR-017 §D2.A).
                        if mps_pre_alloc_mb is not None and mps_post_alloc_mb is not None:
                            mlflow.log_metric("perf.mps_pre_alloc_mb", mps_pre_alloc_mb)
                            mlflow.log_metric("perf.mps_post_alloc_mb", mps_post_alloc_mb)
                            mlflow.log_metric(
                                "perf.mps_delta_mb",
                                mps_post_alloc_mb - mps_pre_alloc_mb,
                            )

                        # Per-field score metrics + JSON artifact
                        for fk, fr in scores.per_field.items():
                            mlflow.log_metric(f"field.{fk}.score", fr.score)
                        mlflow.log_dict(
                            asdict(scores),
                            artifact_file="per_field_scores.json",
                        )

                    # Aggregation
                    for fk, fr in scores.per_field.items():
                        per_field_scores_acc[model_id].setdefault(fk, []).append(fr.score)
                        if fr.outcome == "TP":
                            per_profile_outcomes[profile]["tp"] += 1
                            per_profile_outcomes["POOLED"]["tp"] += 1
                        elif fr.outcome == "FP":
                            per_profile_outcomes[profile]["fp"] += 1
                            per_profile_outcomes["POOLED"]["fp"] += 1
                        elif fr.outcome == "FN":
                            per_profile_outcomes[profile]["fn"] += 1
                            per_profile_outcomes["POOLED"]["fn"] += 1
                        # TP/FP/FN counted; TN/EXCLUDED drop from F1 denominators

                    n_completed += 1
                    print(
                        f"[harness]   [{inv_idx}/{len(pairs)}] {invoice_stem}: "
                        f"micro_f1={scores.micro_f1:.3f} pages={len(per_page)} ({elapsed:.1f}s)",
                        flush=True,
                    )

                except Exception as exc:  # noqa: BLE001 — per-invoice errors are non-fatal
                    n_failed += 1
                    with mlflow.start_run(
                        run_name=f"{_model_slug(model_id)}__{invoice_stem}",
                        nested=True,
                    ):
                        mlflow.set_tag("model_id", model_id)
                        mlflow.set_tag("invoice_id", invoice_stem)
                        mlflow.set_tag("profile", profile)
                        mlflow.set_tag("xml_route", "facturx")
                        mlflow.set_tag("dev_only", dev_only_tag_value)
                        mlflow.set_tag("error_type", type(exc).__name__)
                        mlflow.log_param("error_message", str(exc)[:500])
                        mlflow.end_run(status="FAILED")
                    print(
                        f"[harness]   [{inv_idx}/{len(pairs)}] {invoice_stem}: "
                        f"FAILED: {type(exc).__name__}: {exc}",
                        flush=True,
                    )

            # Unload model between models (OOM accumulation guard).
            try:
                if not load_failed:
                    extractor.unload()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("unload() failed for %s: %s", model_id, exc)

        # ----- 6. Parent-level aggregation -----
        aggregate = _aggregate_per_field_scores(per_field_scores_acc)

        cohort_pooled = _micro_f1_from_counts(per_profile_outcomes["POOLED"])
        cohort_en = _micro_f1_from_counts(per_profile_outcomes["EN16931"])
        cohort_xr = _micro_f1_from_counts(per_profile_outcomes["XRECHNUNG"])

        mlflow.log_metric("cohort_micro_f1_pooled", cohort_pooled)
        mlflow.log_metric("cohort_micro_f1_en16931", cohort_en)
        mlflow.log_metric("cohort_micro_f1_xrechnung", cohort_xr)

        cohort_summary = {
            "n_models_attempted": len(models),
            "n_models_loaded": n_models_loaded,
            "n_invoices_total": len(pairs),
            "n_completed": n_completed,
            "n_failed": n_failed,
            "n_skipped_resume": n_skipped_resume,
            "cohort_micro_f1_pooled": cohort_pooled,
            "cohort_micro_f1_en16931": cohort_en,
            "cohort_micro_f1_xrechnung": cohort_xr,
            "per_profile_outcomes": per_profile_outcomes,
            "per_field_heatmap": aggregate,
        }
        mlflow.log_dict(cohort_summary, artifact_file="cohort_summary.json")

        # Cohort heatmap — only render if there's data (resume-only runs may have 0 completed).
        if any(per_field_scores_acc[m] for m in models):
            title = (
                f"{cohort_cfg.parent_run_name} — per-field ANLS* (rows = models, cols = 16 fields)"
            )
            fig = _render_cohort_heatmap(aggregate, title=title)
            mlflow.log_figure(fig, "cohort_heatmap.png")

    return HarnessRunResult(
        parent_run_id=parent_run_id,
        n_models_attempted=len(models),
        n_models_loaded=n_models_loaded,
        n_skipped_resume=n_skipped_resume,
        n_completed=n_completed,
        n_failed=n_failed,
        n_invoices_total=len(pairs),
        cohort_micro_f1_pooled=cohort_pooled,
        cohort_micro_f1_en16931=cohort_en,
        cohort_micro_f1_xrechnung=cohort_xr,
        per_field_heatmap=aggregate,
    )


def _micro_f1_from_counts(counts: dict[str, int]) -> float:
    """Compute micro-F1 from {tp, fp, fn} integer counts. Returns 0.0 on (0, 0, 0)."""
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    denom = 2 * tp + fp + fn
    if denom == 0:
        return 0.0
    return 2 * tp / denom
