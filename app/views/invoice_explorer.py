"""Invoice Explorer — inspect one invoice, for one method, field by field.

Pick a method + invoice; see the page image the model saw, a colour-coded verdict
for every field (extracted value vs. ground truth), the raw model output, the
structured extraction, and — optionally — all three methods side by side on the
same invoice. Read-only: everything is loaded from results that already exist.
"""

from __future__ import annotations

from collections import Counter

import streamlit as st

from app import loaders
from app.components import cards, field_table, theme
from app.data import approaches as approach_data
from app.data import fields as field_meta
from app.data import mlflow_store
from app.data.results import InvoiceRun
from horus.eval.scorer import FieldResult

st.title("Invoice Explorer")
st.caption("Inspect a single invoice field by field — extracted value, ground truth, and verdict.")


def _run() -> None:
    if not mlflow_store.store_exists():
        st.warning("No local results found (`mlflow.db` is absent). Run an approach first.")
        return

    approaches = approach_data.load_approaches()
    approach_by_key = {approach.key: approach for approach in approaches}
    keys = [approach.key for approach in approaches]
    default_index = keys.index("arm_b") if "arm_b" in keys else 0

    method_labels = {
        key: f"{approach_by_key[key].short_name} · {approach_by_key[key].display_name}"
        for key in keys
    }
    method_key = st.sidebar.selectbox(
        "Method",
        options=keys,
        index=default_index,
        format_func=lambda key: method_labels[key],
    )
    approach = approach_by_key[method_key]

    runs = loaders.load_runs(method_key)
    if not runs:
        st.warning(
            f"No runs found for **{approach.short_name}** "
            f"(experiment `{approach.experiment_name}`). Has this approach been run?"
        )
        return

    invoice_id = st.sidebar.selectbox("Invoice", options=sorted(runs), index=0)
    st.sidebar.markdown("---")
    st.sidebar.markdown(theme.legend_html(), unsafe_allow_html=True)

    run = runs[invoice_id]
    _render_header(approach.display_name, approach.model_label, run)

    image_col, side_col = st.columns([2, 3], gap="large")
    with image_col:
        _render_pages(method_key, invoice_id)
    with side_col:
        _render_side(method_key, approach, run, invoice_id)

    st.divider()
    cards.section_heading("Per-field verdict", "Extracted value vs. ground truth, scored")
    if run.field_results:
        field_table.render_field_table(run.field_results)
    else:
        st.info("No per-field scores were saved for this run.")

    st.divider()
    if st.toggle("Compare all three methods on this invoice", value=False):
        _render_compare_all(invoice_id)


def _render_header(method_name: str, model_label: str, run: InvoiceRun) -> None:
    counts = Counter(result.outcome for result in run.field_results)
    cards.render_kpi_row(
        [
            {
                "label": "Field accuracy",
                "value": f"{run.micro_f1:.2f}",
                "sub": f"{method_name} · {run.profile or 'invoice'}",
                "accent": theme.GOLD,
            },
            {
                "label": "Correct",
                "value": str(counts.get("TP", 0)),
                "sub": "matched ground truth",
                "accent": theme.outcome_style("TP").color,
            },
            {
                "label": "Invented",
                "value": str(counts.get("FP", 0)),
                "sub": "value where none exists",
                "accent": theme.outcome_style("FP").color,
            },
            {
                "label": "Missed",
                "value": str(counts.get("FN", 0)),
                "sub": "ground-truth value not found",
                "accent": theme.outcome_style("FN").color,
            },
        ]
    )
    st.caption(f"Model: `{model_label}` · run `{run.run_id[:10]}` · status {run.status}")


def _render_pages(method_key: str, invoice_id: str) -> None:
    cards.section_heading("Page image", "Exactly what the model saw")
    image_paths = loaders.load_page_images(method_key, invoice_id)
    if not image_paths:
        st.info("Page image unavailable (the source PDF is not on this machine).")
        return
    if len(image_paths) == 1:
        st.image(image_paths[0], use_container_width=True)
        return
    for index, tab in enumerate(st.tabs([f"Page {i + 1}" for i in range(len(image_paths))])):
        with tab:
            st.image(image_paths[index], use_container_width=True)


def _render_side(
    method_key: str, approach: approach_data.Approach, run: InvoiceRun, invoice_id: str
) -> None:
    transcript = loaders.load_transcript(method_key, run.model_id, invoice_id)
    summary = _purpose_summary(transcript)
    if summary:
        st.markdown(
            f"<div style='background:{theme.PANEL};border-left:3px solid {theme.TEAL};"
            f"border-radius:0.4rem;padding:0.5rem 0.8rem;margin:0.3rem 0;font-size:0.9rem'>"
            f"<b>What this invoice is for:</b> {summary}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Structured extraction (what the model produced)", expanded=True):
        st.json(_extracted_dict(run, summary))

    with st.expander("Raw model output"):
        if transcript:
            st.code(transcript, language="text")
        else:
            st.caption("Transcript unavailable — no local file for this run.")

    if approach.reader_model_id:
        reader_transcript = loaders.load_transcript(
            method_key, approach.reader_model_id, invoice_id
        )
        with st.expander("Reader transcript (the text the structurer received)"):
            if reader_transcript:
                st.code(reader_transcript, language="text")
            else:
                st.caption("Reader transcript unavailable on this machine.")


def _render_compare_all(invoice_id: str) -> None:
    cards.section_heading(
        "All three methods on this invoice",
        "Same invoice, same fields — how each method's verdict differs",
    )
    per_approach: dict[str, dict[str, FieldResult]] = {}
    columns: list[tuple[str, str]] = []
    for approach in approach_data.load_approaches():
        runs = loaders.load_runs(approach.key)
        run = runs.get(invoice_id)
        if run is None:
            continue
        per_approach[approach.key] = {result.english_key: result for result in run.field_results}
        columns.append((approach.key, approach.short_name))
    if columns:
        field_table.render_comparison_matrix(per_approach, columns)
    else:
        st.info("This invoice is not present in the other methods' runs.")


def _extracted_dict(run: InvoiceRun, summary: str | None) -> dict[str, object]:
    extracted: dict[str, object] = {key: None for key in field_meta.FIELD_ORDER}
    for result in run.field_results:
        extracted[result.english_key] = result.predicted_normalized
    if summary:
        return {"purpose_summary": summary, **extracted}
    return extracted


def _purpose_summary(transcript: str | None) -> str | None:
    if not transcript:
        return None
    from app.data.invoices import purpose_summary

    return purpose_summary(transcript)


_run()
