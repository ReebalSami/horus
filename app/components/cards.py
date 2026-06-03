"""Branded KPI cards, section headings, and the honest dev-set caveat banner.

Cards take plain strings (not data-layer types) so they stay generic and testable;
pages assemble the values. `kpi_card_html` is pure HTML; the `render_*` helpers do
the Streamlit layout.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import streamlit as st

from app.components import theme


def kpi_card_html(label: str, value: str, sub: str = "", *, accent: str = theme.GOLD) -> str:
    """A single KPI tile as HTML (rounded panel, accent top-rule, big value)."""
    return (
        f"<div style='background:{theme.PANEL};border:1px solid {theme.HAIRLINE};"
        f"border-top:3px solid {accent};border-radius:0.7rem;padding:0.9rem 1.05rem;"
        f"height:100%'>"
        f"<div style='font-size:0.74rem;letter-spacing:.05em;text-transform:uppercase;"
        f"color:{theme.MUTED}'>{label}</div>"
        f"<div style='font-size:1.85rem;font-weight:700;color:{theme.INK};line-height:1.2;"
        f"margin:.12rem 0'>{value}</div>"
        f"<div style='font-size:0.82rem;color:{theme.MUTED}'>{sub}</div>"
        f"</div>"
    )


def render_kpi_row(cards: Sequence[dict[str, Any]]) -> None:
    """Render a row of KPI tiles. Each card dict: label, value, sub?, accent?."""
    columns = st.columns(len(cards))
    for column, card in zip(columns, cards, strict=True):
        with column:
            st.markdown(
                kpi_card_html(
                    card["label"],
                    card["value"],
                    card.get("sub", ""),
                    accent=card.get("accent", theme.GOLD),
                ),
                unsafe_allow_html=True,
            )


def section_heading(title: str, sub: str = "") -> None:
    """A consistent section heading with an optional muted sub-line."""
    st.markdown(
        f"<div style='margin:0.4rem 0 0.2rem'>"
        f"<span style='font-size:1.15rem;font-weight:700;color:{theme.INK}'>{title}</span>"
        + (f"<div style='font-size:0.86rem;color:{theme.MUTED}'>{sub}</div>" if sub else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def dev_caveat(n_invoices: int) -> None:
    """The honest framing shown wherever numbers appear: dev set, not final results."""
    st.markdown(
        f"<div style='background:{theme.PANEL};border:1px solid {theme.HAIRLINE};"
        f"border-left:3px solid {theme.GOLD};border-radius:0.5rem;padding:0.55rem 0.8rem;"
        f"font-size:0.82rem;color:{theme.MUTED}'>"
        f"<b style='color:{theme.INK}'>Development set — {n_invoices} invoices.</b> "
        "These are iteration numbers for error analysis, not the final held-out "
        "test results reported in the thesis."
        "</div>",
        unsafe_allow_html=True,
    )
