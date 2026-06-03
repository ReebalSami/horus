"""Live single-method extraction for the end-user demo page (ADR-039).

Pure orchestration over the existing inference primitives for the Streamlit
"upload -> pick a method -> Read" page. Runs ONE chosen method live on an
uploaded invoice and returns the extracted fields for **human-eye review** —
there is no ground truth for an uploaded file, so this module **never scores**
and **never touches MLflow**. It is deliberately NOT ``arm_b.run_arm_b`` (that
reads cached transcripts, scores against ground truth, and logs MLflow runs).

Two methods (ADR-039; the regex baseline is deferred):

  - **Method A (single-shot):** image -> Gemma -> JSON, per page, merged.
  - **Method B (read-then-structure):** image -> Granite -> text -> Gemma -> JSON.

The ``run_*`` functions take ALREADY-LOADED extractors (the Streamlit layer caches
them via ``st.cache_resource``), plus the prompts + token budgets the caller reads
from ``configs/arm-{a,b}.yaml`` + ``COHORT_MANIFEST`` — nothing is hard-coded here
(``horus-config-discipline``). They are pure (paths in, data out) so they
unit-test with a mocked extractor and no model load.

Refs: ADR-039 (this module), ADR-038 (the two arms + ``build_structuring_input``),
ADR-035 (``InvoiceFields.to_full_dict`` — 19 scored fields + ``purpose_summary``),
ADR-014 (``rasterize_pdf`` at the 300-DPI evaluation resolution), ADR-009
(``COHORT_MANIFEST`` prompts + ``max_tokens``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from horus.eval.rasterize import rasterize_pdf
from horus.eval.schema import PURPOSE_SUMMARY_KEY
from horus.eval.structurer import build_structuring_input, to_full_dict
from horus.vlm_extractor import DEFAULT_MAX_TOKENS, ExtractionResult

__all__ = [
    "EVAL_DPI",
    "IMAGE_SUFFIXES",
    "ImageExtractor",
    "LiveResult",
    "TextExtractor",
    "prepare_pages",
    "run_read_then_structure",
    "run_single_shot",
]

# The rasterization resolution the evaluation pipeline uses (configs/pilot-13.yaml
# `rasterizer.dpi`). The live page renders at the SAME DPI so the demo faithfully
# reflects measured performance — a lower-resolution preview would give the model
# less to read than during evaluation (ADR-039 §Options E).
EVAL_DPI = 300

# Upload suffixes treated as a ready-to-read single page image (no rasterization).
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})


class ImageExtractor(Protocol):
    """The minimal surface Method A + the Method B reader need: image-in extraction.

    ``MLXVLMExtractor`` satisfies this structurally; tests pass a fake with the
    same shape (no model load).
    """

    def extract(
        self, image_path: Path, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> ExtractionResult: ...


class TextExtractor(Protocol):
    """The minimal surface the Method B structurer needs: text-only extraction."""

    def extract_text(
        self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> ExtractionResult: ...


@dataclass(frozen=True)
class LiveResult:
    """One live extraction outcome for the demo page (no score — there is no GT)."""

    method: str
    # The full 20-key dict: the 19 scored fields + the non-scored `purpose_summary`
    # (``InvoiceFields.to_full_dict`` shape). Values are canonical strings or None.
    fields: dict[str, str | None]
    page_image_paths: list[Path]
    load_seconds: float
    extract_seconds: float
    # Method B only: the reader's (Granite's) transcript — the interesting middle
    # artifact the structurer consumed. None for single-shot.
    reader_transcript: str | None = None

    @property
    def purpose_summary(self) -> str | None:
        """The non-scored one-line 'what is this invoice for' summary (or None)."""
        return self.fields.get(PURPOSE_SUMMARY_KEY)


def prepare_pages(upload_path: Path, *, cache_dir: Path, dpi: int = EVAL_DPI) -> list[Path]:
    """Resolve an uploaded file to a list of page-image paths.

    A PDF is rasterized to one PNG per page at ``dpi`` (the evaluation resolution,
    disk-cached); an uploaded image (png/jpg/jpeg) is already a single page and is
    returned unchanged.
    """
    if upload_path.suffix.lower() in IMAGE_SUFFIXES:
        return [upload_path]
    return rasterize_pdf(upload_path, dpi=dpi, cache_dir=cache_dir)


def _require_text(result: ExtractionResult) -> str:
    """Return the model text, or raise with the captured backend error.

    Extractors never raise past ``.extract()``/``.extract_text()`` — they bundle
    failures into ``ExtractionResult.error``. The live page surfaces that message;
    raising here lets the page's single try/except show it cleanly.
    """
    if not result.is_ok:
        raise RuntimeError(result.error or "extraction failed")
    return result.text


def _merge_full_dicts(per_page: list[dict[str, str | None]]) -> dict[str, str | None]:
    """Merge per-page full dicts with first-non-None-wins (page 1 dominates).

    Mirrors ``structurer.to_predicted_dict_multipage`` semantics (a later page's
    value never overwrites an earlier page's), extended to the full dict (incl.
    ``purpose_summary``) for the demo.
    """
    if not per_page:
        return to_full_dict("")
    merged: dict[str, str | None] = dict(per_page[0])
    for page in per_page[1:]:
        for key, value in page.items():
            if merged.get(key) is None and value is not None:
                merged[key] = value
    return merged


def run_single_shot(
    page_paths: list[Path],
    *,
    extractor: ImageExtractor,
    prompt: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LiveResult:
    """Method A: the structurer reads each page image directly and emits the fields.

    ``extractor`` must already be loaded (the Streamlit layer caches it). Each page
    yields reasoning-then-JSON, parsed via ``structurer.to_full_dict`` and merged
    first-non-None-wins. ``prompt`` + ``max_tokens`` come from the caller (the arm-a
    config override + the manifest), not from this module.
    """
    results = [extractor.extract(page, prompt, max_tokens) for page in page_paths]
    per_page = [to_full_dict(_require_text(result)) for result in results]
    return LiveResult(
        method="arm_a",
        fields=_merge_full_dicts(per_page),
        page_image_paths=list(page_paths),
        load_seconds=results[0].load_seconds if results else 0.0,
        extract_seconds=sum(result.extract_seconds for result in results),
    )


def run_read_then_structure(
    page_paths: list[Path],
    *,
    reader: ImageExtractor,
    structurer: TextExtractor,
    reader_prompt: str,
    structuring_prompt: str,
    reader_max_tokens: int = DEFAULT_MAX_TOKENS,
    structuring_max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LiveResult:
    """Method B: a specialist reader transcribes each page, then the structurer types it.

    The reader (Granite) reads every page image with its native prompt; the page
    transcripts are joined and handed to the structurer (Gemma) as text via
    ``build_structuring_input`` (the same composition the offline Arm-B runner uses).
    Both extractors must already be loaded. The reader transcript is returned so the
    page can show the interesting middle artifact.
    """
    read_results = [reader.extract(page, reader_prompt, reader_max_tokens) for page in page_paths]
    transcript = "\n\n".join(_require_text(result) for result in read_results)
    structuring_input = build_structuring_input(structuring_prompt, transcript)
    struct_result = structurer.extract_text(structuring_input, structuring_max_tokens)
    fields = to_full_dict(_require_text(struct_result))
    reader_load = read_results[0].load_seconds if read_results else 0.0
    return LiveResult(
        method="arm_b",
        fields=fields,
        page_image_paths=list(page_paths),
        load_seconds=reader_load + struct_result.load_seconds,
        extract_seconds=sum(result.extract_seconds for result in read_results)
        + struct_result.extract_seconds,
        reader_transcript=transcript,
    )
