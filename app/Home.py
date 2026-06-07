"""HORUS observability dashboard — entry point (`streamlit run app/Home.py`, or `make app`).

Bootstraps the import path (Streamlit puts the entry-script directory on `sys.path`,
not the repo root), sets the page config + brand logo, then declares the multipage
navigation with `st.navigation` and runs the selected page. The Overview landing is
rendered by `render_overview` below; the two analytical surfaces live in `app/views/`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402 — must follow the sys.path bootstrap above

from app import loaders  # noqa: E402
from app.components import cards, theme  # noqa: E402
from app.data import approaches as approach_data  # noqa: E402
from app.data import mlflow_store  # noqa: E402
from app.data.approaches import Approach  # noqa: E402
from app.data.metrics import ApproachMetrics  # noqa: E402

_BRAND = _REPO_ROOT / "app" / "assets" / "brand"
_EYE = _BRAND / "eye-of-horus.png"
_WORDMARK = _BRAND / "horus-wordmark.png"

st.set_page_config(
    page_title="HORUS — Observability",
    page_icon=str(_EYE) if _EYE.is_file() else "\U0001f441",
    layout="wide",
    initial_sidebar_state="expanded",
)

if _EYE.is_file():
    st.logo(str(_EYE), size="large")


def render_overview() -> None:
    """The Overview landing: brand hero, headline accuracy, and where to go next."""
    left, right = st.columns([1, 5], vertical_alignment="center")
    with left:
        if _EYE.is_file():
            st.image(str(_EYE), width=120)
    with right:
        if _WORDMARK.is_file():
            st.image(str(_WORDMARK), width=240)
        st.markdown(
            f"<div style='font-size:1.02rem;color:{theme.MUTED};margin-top:0.2rem'>"
            "Hybrid OCR-free Reading &amp; Understanding System — privacy-first invoice "
            "intelligence for German tax &amp; accounting. This is the read-only "
            "observability surface: see exactly how each extraction approach performs, "
            "field by field."
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    if not mlflow_store.store_exists():
        st.warning(
            "No local results found (`mlflow.db` is absent at the repo root). Run an "
            "approach first — e.g. `make pilot-13 CFG=configs/pilot-13.yaml,"
            "configs/baseline-regex.yaml` then `make arm-b CFG=configs/pilot-13.yaml,"
            "configs/arm-b.yaml` — then reload.",
            icon="\u26a0\ufe0f",
        )
        return

    approaches = approach_data.load_approaches()
    metrics_by_key = {approach.key: loaders.load_metrics(approach.key) for approach in approaches}
    n_invoices = max((m.n_invoices for m in metrics_by_key.values()), default=0)

    cards.section_heading(
        "Headline accuracy",
        "Overall field accuracy (micro-F1, 0–1) on the development set — recomputed "
        "live from the saved per-field scores.",
    )
    cards.render_kpi_row(
        [
            {
                "label": approach.short_name,
                "value": (
                    f"{metrics_by_key[approach.key].overall_f1:.2f}"
                    if metrics_by_key[approach.key].n_invoices
                    else "—"
                ),
                "sub": approach.model_label,
                "accent": approach.accent_hex,
            }
            for approach in approaches
        ]
    )

    _render_headline_narrative(approaches, metrics_by_key)
    st.write("")
    cards.dev_caveat(n_invoices)

    st.divider()
    cards.section_heading("Where to go next")
    nav_left, nav_right = st.columns(2)
    with nav_left:
        st.page_link(
            "views/invoice_explorer.py",
            label="**Invoice Explorer** — inspect one invoice field by field",
            icon="\U0001f50d",
        )
        st.caption("Page image, raw output, extracted fields, colour-coded verdict per field.")
    with nav_right:
        st.page_link(
            "views/approach_comparison.py",
            label="**Approach Comparison** — the three methods head to head",
            icon="\u2696\ufe0f",
        )
        st.caption("Accuracy, presence, grouping, invention rate — and where each method breaks.")


def _render_headline_narrative(
    approaches: tuple[Approach, ...],
    metrics_by_key: dict[str, ApproachMetrics],
) -> None:
    """One honest sentence naming the strongest approach + the no-invention fact."""
    scored = [a for a in approaches if metrics_by_key[a.key].n_invoices]
    if not scored:
        return
    best = max(scored, key=lambda a: metrics_by_key[a.key].overall_f1)
    best_metrics = metrics_by_key[best.key]
    invented = (
        "and invented nothing"
        if best_metrics.spurious_rate == 0.0
        else f"with a {best_metrics.spurious_rate:.0%} invention rate"
    )
    st.markdown(
        f"<div style='font-size:0.98rem;color:{theme.INK};margin-top:0.6rem'>"
        f"<b>{best.display_name}</b> ({best.short_name}) leads at "
        f"<b>{best_metrics.overall_f1:.2f}</b> overall field accuracy {invented} on this set."
        "</div>",
        unsafe_allow_html=True,
    )


_overview = st.Page(render_overview, title="Overview", icon="\U0001f3e0", default=True)
_extract = st.Page("views/live_extraction.py", title="Extract an Invoice", icon="\u2728")
_explorer = st.Page("views/invoice_explorer.py", title="Invoice Explorer", icon="\U0001f50d")
_comparison = st.Page(
    "views/approach_comparison.py", title="Approach Comparison", icon="\u2696\ufe0f"
)
_review = st.Page("views/heldout_review.py", title="Ground Truth Review", icon="\U0001f4dd")

_navigation = st.navigation(
    {
        "HORUS": [_overview],
        "Try it": [_extract],
        "Evaluation": [_explorer, _comparison],
        "Held-out set": [_review],
    }
)
_navigation.run()
