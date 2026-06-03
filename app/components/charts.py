"""Pure Plotly figure builders for the comparison page.

No Streamlit dependency — each function takes plain data and returns a
`plotly.graph_objects.Figure`, so the figures can be unit-tested headless. All
figures share a restrained editorial layout (transparent background to sit on the
warm canvas, minimal gridlines, brand-coloured series).
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from app.components import theme

_AXIS = {
    "showgrid": True,
    "gridcolor": theme.HAIRLINE,
    "zeroline": False,
    "linecolor": theme.HAIRLINE,
}


def _base_layout(title: str, *, height: int = 360) -> dict[str, Any]:
    return {
        "title": {"text": title, "font": {"size": 16, "color": theme.INK}},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": theme.FONT_STACK, "color": theme.INK, "size": 13},
        "margin": {"l": 12, "r": 12, "t": 52, "b": 44},
        "height": height,
        "legend": {
            "orientation": "h",
            "yanchor": "top",
            "y": -0.16,
            "xanchor": "center",
            "x": 0.5,
        },
    }


def grouped_metric_bar(
    metric_labels: list[str],
    series: list[tuple[str, str, list[float]]],
    *,
    title: str = "Headline accuracy by approach",
) -> go.Figure:
    """Grouped bar of higher-is-better F1 metrics. `series` = (name, colour, values)."""
    fig = go.Figure()
    for name, color, values in series:
        fig.add_bar(
            name=name,
            x=metric_labels,
            y=values,
            marker_color=color,
            text=[f"{v:.2f}" for v in values],
            textposition="outside",
            textfont={"size": 12},
        )
    layout = _base_layout(title)
    layout["barmode"] = "group"
    layout["yaxis"] = {**_AXIS, "range": [0, 1.08], "title": {"text": "F1 (0–1)"}}
    layout["xaxis"] = {**_AXIS, "showgrid": False}
    fig.update_layout(**layout)
    return fig


def invention_rate_bar(
    names: list[str],
    colors: list[str],
    rates: list[float],
    *,
    title: str = "Invention rate (lower is better)",
) -> go.Figure:
    """Horizontal bar of the spurious-emission (hallucination) rate per approach."""
    fig = go.Figure(
        go.Bar(
            x=rates,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{r:.1%}" for r in rates],
            textposition="outside",
        )
    )
    layout = _base_layout(title, height=240)
    layout["xaxis"] = {**_AXIS, "range": [0, max(rates + [0.05]) * 1.25], "tickformat": ".0%"}
    layout["yaxis"] = {**_AXIS, "showgrid": False}
    fig.update_layout(**layout)
    return fig


def per_type_bar(
    type_labels: list[str],
    series: list[tuple[str, str, list[float]]],
    *,
    title: str = "Accuracy by field type",
) -> go.Figure:
    """Grouped bar of per-field-type F1 across approaches (where each method struggles)."""
    fig = go.Figure()
    for name, color, values in series:
        fig.add_bar(
            name=name,
            x=type_labels,
            y=values,
            marker_color=color,
            text=[f"{v:.2f}" for v in values],
            textposition="outside",
            textfont={"size": 11},
        )
    layout = _base_layout(title)
    layout["barmode"] = "group"
    layout["yaxis"] = {**_AXIS, "range": [0, 1.08], "title": {"text": "F1 (0–1)"}}
    layout["xaxis"] = {**_AXIS, "showgrid": False}
    fig.update_layout(**layout)
    return fig


def per_label_heatmap(
    field_labels: list[str],
    approach_names: list[str],
    matrix: list[list[float | None]],
    *,
    title: str = "Per-field F1 — where each approach breaks",
) -> go.Figure:
    """Field × approach F1 heatmap (rows = fields, columns = approaches)."""
    fig = go.Figure(
        go.Heatmap(
            z=matrix,
            x=approach_names,
            y=field_labels,
            zmin=0.0,
            zmax=1.0,
            colorscale=theme.SEQUENTIAL_SCALE,
            colorbar={"title": {"text": "F1"}, "thickness": 12},
            hovertemplate="%{y} · %{x}: F1=%{z:.2f}<extra></extra>",
        )
    )
    layout = _base_layout(title, height=max(360, 22 * len(field_labels) + 120))
    layout["xaxis"] = {"side": "top", "tickangle": 0}
    layout["yaxis"] = {"autorange": "reversed"}
    fig.update_layout(**layout)
    return fig
