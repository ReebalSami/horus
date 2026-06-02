"""Streamlit-cached loaders bridging the pure data layer to the pages.

Thin `@st.cache_data` wrappers so MLflow reads, artifact downloads, metric pooling,
and PDF rasterization happen once per (argument set) per session and are shared
across pages. All heavy lifting lives in the (Streamlit-free, unit-tested) data
layer; this module only adds caching + small convenience shaping.
"""

from __future__ import annotations

import streamlit as st

from app.data import approaches as approach_data
from app.data import invoices, metrics, results
from app.data.metrics import ApproachMetrics
from app.data.results import InvoiceRun


@st.cache_data(show_spinner="Loading results…")
def load_runs(approach_key: str) -> dict[str, InvoiceRun]:
    """All per-invoice runs for an approach's latest parent run (cached)."""
    return results.load_invoice_runs(approach_data.get_approach(approach_key))


@st.cache_data(show_spinner=False)
def load_metrics(approach_key: str, invoice_ids: tuple[str, ...] | None = None) -> ApproachMetrics:
    """Pooled metrics for an approach, optionally restricted to a set of invoices."""
    runs = load_runs(approach_key)
    if invoice_ids is None:
        selected = [run for run in runs.values() if run.is_finished]
    else:
        selected = [runs[i] for i in invoice_ids if i in runs and runs[i].is_finished]
    return metrics.pool_metrics([run.field_results for run in selected])


@st.cache_data(show_spinner=False)
def load_page_images(approach_key: str, invoice_stem: str) -> list[str]:
    """Rasterized page image paths for an invoice (cached on disk by the rasterizer)."""
    approach = approach_data.get_approach(approach_key)
    paths = invoices.page_images(
        approach.corpus_root,
        invoice_stem,
        dpi=approach.raster_dpi,
        cache_dir=approach.raster_cache_dir,
    )
    return [str(path) for path in paths]


@st.cache_data(show_spinner=False)
def load_transcript(approach_key: str, model_id: str, invoice_stem: str) -> str | None:
    """Raw archived transcript body for a (model, invoice), or None if unavailable."""
    approach = approach_data.get_approach(approach_key)
    path = invoices.transcript_path(approach.transcript_dir, model_id, invoice_stem)
    return invoices.load_transcript_body(path) if path is not None else None
