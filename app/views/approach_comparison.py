"""Approach Comparison — the three extraction methods, head to head.

Pools the four headline metrics LIVE from each method's per-field scores (over the
invoices all methods share, so the comparison is fair), then shows them as KPI
cards, an exact table, comparison charts, a reading-vs-structuring breakdown, and a
per-field heatmap of where each method breaks. Read-only.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import loaders
from app.components import cards, charts
from app.data import approaches as approach_data
from app.data import fields as field_meta
from app.data import mlflow_store
from app.data.approaches import Approach
from app.data.metrics import ApproachMetrics

_TYPE_LABELS = {
    "STRING": "Text",
    "CODE": "Codes / IDs",
    "MONEY": "Money",
    "DATE": "Dates",
    "RATE": "VAT rate",
}
_TYPE_ORDER = ("STRING", "CODE", "MONEY", "DATE", "RATE")

st.title("Approach Comparison")
st.caption("The three extraction methods, measured on the same invoices with the same scorer.")


def _run() -> None:
    if not mlflow_store.store_exists():
        st.warning("No local results found (`mlflow.db` is absent). Run the approaches first.")
        return

    approaches = approach_data.load_approaches()
    runs_by_key = {approach.key: loaders.load_runs(approach.key) for approach in approaches}
    finished = [
        {invoice for invoice, run in runs.items() if run.is_finished}
        for runs in runs_by_key.values()
        if runs
    ]
    common = (
        sorted(set.intersection(*finished)) if len(finished) == len(approaches) and finished else []
    )
    if not common:
        st.warning(
            "The approaches do not yet share a common set of completed invoices, so a fair "
            "comparison is not available. Run each approach over the same invoice subset."
        )
        return

    common_key = tuple(common)
    metrics_by_key = {
        approach.key: loaders.load_metrics(approach.key, common_key) for approach in approaches
    }

    _render_kpis(approaches, metrics_by_key)
    cards.dev_caveat(len(common))

    st.divider()
    _render_metric_table(approaches, metrics_by_key)

    st.divider()
    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        st.plotly_chart(_accuracy_chart(approaches, metrics_by_key), use_container_width=True)
    with chart_right:
        st.plotly_chart(_invention_chart(approaches, metrics_by_key), use_container_width=True)

    st.divider()
    _render_reading_vs_structuring(metrics_by_key)

    st.divider()
    st.plotly_chart(_type_chart(approaches, metrics_by_key), use_container_width=True)

    st.divider()
    cards.section_heading(
        "Per-field accuracy", "Which fields each method gets right (blank = no signal)"
    )
    st.plotly_chart(_heatmap(approaches, metrics_by_key), use_container_width=True)


def _scored(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> list[Approach]:
    return [approach for approach in approaches if metrics_by_key[approach.key].n_invoices]


def _render_kpis(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> None:
    cards.section_heading("Overall accuracy", "Micro-F1 (0–1) and invention rate per method")
    kpi_cards: list[dict[str, str]] = []
    for approach in approaches:
        metric = metrics_by_key[approach.key]
        if not metric.n_invoices:
            continue
        kpi_cards.append(
            {
                "label": f"{approach.short_name} · {approach.display_name}",
                "value": f"{metric.overall_f1:.2f}",
                "sub": f"invents {metric.spurious_rate:.0%} · {approach.model_label}",
                "accent": approach.accent_hex,
            }
        )
    cards.render_kpi_row(kpi_cards)


def _render_metric_table(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> None:
    cards.section_heading(
        "The four metrics", "Exact numbers — hover a column header for what it means"
    )
    rows = [
        {
            "Approach": approach.short_name,
            "Overall accuracy": metrics_by_key[approach.key].overall_f1,
            "Presence accuracy": metrics_by_key[approach.key].presence_f1,
            "Grouping accuracy": metrics_by_key[approach.key].group_f1,
            "Invention rate": metrics_by_key[approach.key].spurious_rate,
        }
        for approach in _scored(approaches, metrics_by_key)
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Approach": st.column_config.TextColumn("Approach", width="medium"),
            "Overall accuracy": st.column_config.NumberColumn(
                "Overall accuracy",
                format="%.2f",
                help="Micro-F1 across every field of every invoice — the headline accuracy.",
            ),
            "Presence accuracy": st.column_config.NumberColumn(
                "Presence accuracy",
                format="%.2f",
                help="F1 over fields that are present (did it capture what's there).",
            ),
            "Grouping accuracy": st.column_config.NumberColumn(
                "Grouping accuracy",
                format="%.2f",
                help="All-or-nothing per business group (seller, buyer, totals).",
            ),
            "Invention rate": st.column_config.NumberColumn(
                "Invention rate",
                format="%.2f",
                help="Values emitted for absent fields; lower is better (0 = never invents).",
            ),
        },
    )


def _accuracy_chart(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> go.Figure:
    series = [
        (
            approach.short_name,
            approach.accent_hex,
            [
                metrics_by_key[approach.key].overall_f1,
                metrics_by_key[approach.key].presence_f1,
                metrics_by_key[approach.key].group_f1,
            ],
        )
        for approach in _scored(approaches, metrics_by_key)
    ]
    return charts.grouped_metric_bar(["Overall", "Presence", "Grouping"], series)


def _invention_chart(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> go.Figure:
    scored = _scored(approaches, metrics_by_key)
    return charts.invention_rate_bar(
        [approach.short_name for approach in scored],
        [approach.accent_hex for approach in scored],
        [metrics_by_key[approach.key].spurious_rate for approach in scored],
    )


def _type_chart(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> go.Figure:
    present = [
        field_type
        for field_type in _TYPE_ORDER
        if any(field_type in metrics_by_key[a.key].per_type_f1 for a in approaches)
    ]
    labels = [_TYPE_LABELS[field_type] for field_type in present]
    series = [
        (
            approach.short_name,
            approach.accent_hex,
            [
                metrics_by_key[approach.key].per_type_f1.get(field_type, 0.0)
                for field_type in present
            ],
        )
        for approach in _scored(approaches, metrics_by_key)
    ]
    return charts.per_type_bar(labels, series)


def _heatmap(
    approaches: tuple[Approach, ...], metrics_by_key: dict[str, ApproachMetrics]
) -> go.Figure:
    scored = _scored(approaches, metrics_by_key)
    field_labels = [field_meta.label(key) for key in field_meta.FIELD_ORDER]
    matrix = [
        [metrics_by_key[approach.key].per_label_f1.get(key) for approach in scored]
        for key in field_meta.FIELD_ORDER
    ]
    return charts.per_label_heatmap(
        field_labels, [approach.short_name for approach in scored], matrix
    )


def _render_reading_vs_structuring(metrics_by_key: dict[str, ApproachMetrics]) -> None:
    cards.section_heading(
        "Reading vs. structuring",
        "What each stage contributes — isolated by holding the other constant",
    )

    def overall(key: str) -> float | None:
        metric = metrics_by_key.get(key)
        return metric.overall_f1 if metric and metric.n_invoices else None

    baseline, arm_a, arm_b = overall("baseline"), overall("arm_a"), overall("arm_b")
    left, right = st.columns(2, gap="large")
    with left:
        if baseline is not None and arm_b is not None:
            st.metric(
                "Value of LLM structuring",
                f"{arm_b:.2f}",
                delta=f"{arm_b - baseline:+.2f} vs. regex baseline",
            )
            st.caption(
                "Same specialist read (Granite); swap the hand-written regex parser for the "
                "Gemma structurer. The gain is what learned structuring buys over brittle rules."
            )
        else:
            st.caption("Need the baseline and Method B to isolate the structuring contribution.")
    with right:
        if arm_a is not None and arm_b is not None:
            st.metric(
                "Value of a specialist reader",
                f"{arm_b:.2f}",
                delta=f"{arm_b - arm_a:+.2f} vs. single-shot",
            )
            st.caption(
                "Same structurer (Gemma); add a specialist reader (Granite) in front instead of "
                "letting the general model read the image itself. The gain is what specialist "
                "reading buys."
            )
        else:
            st.caption("Need Method A and Method B to isolate the reading contribution.")


_run()
