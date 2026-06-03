"""Extract an Invoice — run ONE method live on an uploaded invoice (ADR-039).

The one end-user page that is NOT read-only: upload an invoice (PDF or image),
pick a method, click **Read**, and the chosen pipeline runs live on this machine.
There is no ground truth for an uploaded file, so this page shows the extraction
for **human-eye review only** — it never scores. The three research pages stay
read-only (ADR-036 §D); this is the bounded exception ratified in ADR-039.

Two methods (the regex baseline is deferred): **Method A** (single-shot — Gemma
reads the page image and writes the fields) and **Method B** (read-then-structure
— Granite transcribes, then Gemma structures). Models load once per session via
`st.cache_resource`. Prompts + model IDs + token budgets are read from the arm
configs + `COHORT_MANIFEST` (never hard-coded). Pages render at the 300-DPI
evaluation resolution so the demo reflects measured behaviour.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from app.components import cards, field_table, theme
from app.data import approaches as approach_data
from app.data.approaches import Approach
from horus.eval import live
from horus.eval.live import LiveResult
from horus.vlm_extractor import COHORT_MANIFEST, MLXVLMExtractor, get_extractor

# Scratch dir for the uploaded file + its rendered pages (gitignored under
# data/raw/smoke/). Each upload writes a uniquely-named temp file, so the
# rasterizer's mtime cache never serves a stale render for a different upload.
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "smoke" / "app-live"

# The two AI methods offered on this page (ADR-039), best/winner first.
_METHOD_KEYS = ("arm_b", "arm_a")

st.title("Extract an Invoice")
st.caption("Upload an invoice, choose a method, and read it live on this machine.")

st.markdown(
    f"<div style='background:{theme.PANEL};border:1px solid {theme.HAIRLINE};"
    f"border-left:3px solid {theme.GOLD};border-radius:0.5rem;padding:0.6rem 0.9rem;"
    f"font-size:0.9rem;color:{theme.MUTED}'>"
    f"<b style='color:{theme.INK}'>Visual review only — no ground truth.</b> "
    "This page runs the model live on your uploaded file and shows what it extracted. "
    "There is no known-correct answer for an arbitrary invoice, so nothing here is "
    "scored — read the values against the page image yourself."
    "</div>",
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def _loaded_extractor(model_id: str) -> MLXVLMExtractor:
    """Load a model once per session (shared across clicks); never unloaded here.

    Keyed by `model_id`, so Method B's Granite + Gemma load once each and Method A
    reuses the same Gemma. All live methods are MLX (ADR-039) — a non-MLX model
    would lack the text-only `extract_text` path, so we fail loudly.
    """
    extractor = get_extractor(model_id)
    if not isinstance(extractor, MLXVLMExtractor):
        raise RuntimeError(
            f"The live demo expects an MLX model; {model_id!r} resolves to "
            f"{type(extractor).__name__}."
        )
    extractor.load()
    return extractor


def _max_tokens(model_id: str) -> int:
    """The model's decode budget from the cohort manifest (e.g. Granite 1536)."""
    return int(COHORT_MANIFEST[model_id]["max_tokens"])


def _structuring_prompt(approach: Approach) -> str:
    """The arm's structuring/single-shot prompt (from config); guard against a gap."""
    if not approach.prompt:
        raise RuntimeError(
            f"approach {approach.key!r} has no prompt override in its config — "
            "cannot run the live method without it."
        )
    return approach.prompt


def _extract(approach: Approach, upload_path: Path) -> LiveResult:
    """Dispatch to the chosen live pipeline, loading (cached) models as needed."""
    pages = live.prepare_pages(upload_path, cache_dir=_CACHE_DIR)
    structurer = _loaded_extractor(approach.model_id)
    if approach.key == "arm_a":
        return live.run_single_shot(
            pages,
            extractor=structurer,
            prompt=_structuring_prompt(approach),
            max_tokens=_max_tokens(approach.model_id),
        )
    reader_id = approach.reader_model_id
    if reader_id is None:  # defensive — arm_b always sets a reader
        raise RuntimeError(f"approach {approach.key!r} has no reader_model_id for Method B.")
    reader = _loaded_extractor(reader_id)
    return live.run_read_then_structure(
        pages,
        reader=reader,
        structurer=structurer,
        reader_prompt=str(COHORT_MANIFEST[reader_id]["prompt_template"]),
        structuring_prompt=_structuring_prompt(approach),
        reader_max_tokens=_max_tokens(reader_id),
        structuring_max_tokens=_max_tokens(approach.model_id),
    )


def _render_pages(paths: list[Path]) -> None:
    cards.section_heading("Page image", "Exactly what the model saw (rendered at 300 DPI)")
    if not paths:
        st.info("No page image to show.")
        return
    if len(paths) == 1:
        st.image(str(paths[0]), use_container_width=True)
        return
    for index, tab in enumerate(st.tabs([f"Page {i + 1}" for i in range(len(paths))])):
        with tab:
            st.image(str(paths[index]), use_container_width=True)


def _render(result: LiveResult, approach: Approach) -> None:
    cards.render_kpi_row(
        [
            {
                "label": "Method",
                "value": approach.short_name,
                "sub": approach.display_name,
                "accent": approach.accent_hex,
            },
            {
                "label": "Pages",
                "value": str(len(result.page_image_paths)),
                "sub": "in this invoice",
            },
            {
                "label": "Model load",
                "value": f"{result.load_seconds:.0f}s",
                "sub": "once per session",
            },
            {
                "label": "Read time",
                "value": f"{result.extract_seconds:.0f}s",
                "sub": "this invoice",
            },
        ]
    )

    image_col, side_col = st.columns([2, 3], gap="large")
    with image_col:
        _render_pages(result.page_image_paths)
    with side_col:
        if result.purpose_summary:
            st.markdown(
                f"<div style='background:{theme.PANEL};border-left:3px solid {theme.TEAL};"
                f"border-radius:0.4rem;padding:0.5rem 0.8rem;margin:0.2rem 0 0.6rem;"
                f"font-size:0.92rem'><b>What this invoice is for:</b> "
                f"{result.purpose_summary}</div>",
                unsafe_allow_html=True,
            )
        cards.section_heading(
            "Extracted fields", "What the model found — visual review only, not scored"
        )
        field_table.render_value_table(result.fields)
        if result.reader_transcript is not None:
            with st.expander("Reader transcript (the text the structurer received)"):
                st.code(result.reader_transcript, language="text")


def _run() -> None:
    approaches = {approach.key: approach for approach in approach_data.load_approaches()}

    method_key = st.radio(
        "Method",
        options=_METHOD_KEYS,
        format_func=lambda key: f"{approaches[key].short_name} — {approaches[key].display_name}",
        horizontal=True,
    )
    approach = approaches[method_key]
    st.caption(approach.description)

    uploaded = st.file_uploader("Invoice (PDF or image)", type=["pdf", "png", "jpg", "jpeg"])
    read = st.button("Read", type="primary", disabled=uploaded is None)
    if not read or uploaded is None:
        return

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded.name).suffix.lower() or ".pdf"
    with tempfile.NamedTemporaryFile(dir=_CACHE_DIR, suffix=suffix, delete=False) as handle:
        handle.write(uploaded.getvalue())
        upload_path = Path(handle.name)

    try:
        with st.spinner("Reading the invoice… (the first run loads the model and is slower)"):
            result = _extract(approach, upload_path)
    except Exception as exc:  # noqa: BLE001 — surface any failure cleanly, never crash the page
        st.error(f"Extraction failed: {exc}")
        return

    _render(result, approach)


_run()
