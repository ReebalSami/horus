"""Shared figure-styling helpers for EDA chapters (ADR-024 + ADR-025 Phase A skeleton).

This module sets up the editorial palette + typography so every chapter
of the Quarto Book has a consistent visual identity. The hybrid approach
ratified in ADR-024 §"Hybrid aesthetic" splits responsibility:

  - **Static figures** (matplotlib + seaborn) — survive PDF export; FT/NYT-
    influenced muted palette + clean typography + baked-in annotations.
  - **Interactive figures** (Plotly) — HTML-only; drop to static fallbacks
    in PDF gracefully (Quarto's documented behavior).

Per ADR-025, every chapter calls `apply_styles(cfg)` once near the top
of its narrative. The function is idempotent + side-effect-only (mutates
matplotlib's rcParams + Plotly's default template).

Refs: ADR-024 §"Hybrid aesthetic", ADR-025 §"Decision + integration thoughts".
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import plotly.io as pio
import seaborn as sns

# Plotly default layout — applied via `**PLOTLY_LAYOUT` spread into
# `fig.update_layout(...)` calls. Matches the editorial typography of
# the matplotlib stack so PDF static fallbacks are visually consistent.
PLOTLY_LAYOUT: dict[str, object] = {
    "margin": {"t": 60, "l": 60, "r": 20, "b": 60},
    "font": {"family": "DejaVu Sans, sans-serif", "size": 12},
    "title": {"x": 0.0, "xanchor": "left", "font": {"size": 14}},
}


@dataclass(frozen=True)
class StyleHandles:
    """Returned by :func:`apply_styles` so callers can access palette objects.

    The `palette` field is a list of RGB tuples (matplotlib/seaborn-friendly);
    `palette_hex` is the same colors as `#rrggbb` strings (Plotly-friendly).
    Plotly's `color_discrete_sequence` rejects raw RGB tuples (per
    `plotly/_plotly_utils/basevalidators.py`), so the hex form is required
    when targeting the interactive stack.
    """

    palette: list[tuple[float, float, float]]
    palette_hex: list[str]


def apply_styles(
    *,
    palette_static: str = "muted",
    palette_interactive: str = "plotly_white",
    n_colors: int = 12,
) -> StyleHandles:
    """Configure matplotlib + seaborn + Plotly with the HORUS editorial style.

    Args:
        palette_static: seaborn palette name for static figures (matplotlib +
            seaborn). Defaults to "muted" per the FT/NYT-influenced aesthetic
            ratified in ADR-024 Q5=C.
        palette_interactive: Plotly template name. Defaults to "plotly_white"
            (cleanest editorial baseline).
        n_colors: number of categorical colors to materialize from the palette.
            12 is enough for per-flavor / per-profile faceting; chapters with
            more categories can re-derive a longer palette via
            `sns.color_palette(palette_static, n_colors=N)`.

    Returns:
        A :class:`StyleHandles` carrying both the matplotlib-friendly RGB
        palette and the Plotly-friendly hex palette.

    Side effects:
        - Sets seaborn theme (style="white", context="paper", font_scale=1.0).
        - Mutates matplotlib's `plt.rcParams` (font family, sizes, axes spines).
        - Sets `plotly.io.templates.default = palette_interactive`.

    Idempotent: calling twice is safe (later call overwrites earlier settings).
    """
    sns.set_theme(
        style="white",
        context="paper",
        font_scale=1.0,
        rc={
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#333333",
            "xtick.color": "#333333",
            "ytick.color": "#333333",
        },
    )
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 10
    plt.rcParams["xtick.labelsize"] = 9
    plt.rcParams["ytick.labelsize"] = 9
    plt.rcParams["legend.fontsize"] = 9
    plt.rcParams["figure.titlesize"] = 13

    pio.templates.default = palette_interactive

    palette = sns.color_palette(palette_static, n_colors=n_colors)
    palette_hex = palette.as_hex()
    return StyleHandles(palette=list(palette), palette_hex=list(palette_hex))
