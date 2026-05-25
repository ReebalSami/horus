"""Tests for `horus.eda.figures` (ADR-025 Phase A skeleton).

Verifies the styling helper is idempotent + side-effect-only + returns
the expected handle structure. We test behavior, not visual output
(visual fidelity is verified by Quarto-rendered chapters during review).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import plotly.io as pio

from horus.eda.figures import PLOTLY_LAYOUT, StyleHandles, apply_styles


def test_apply_styles_returns_palette_handles() -> None:
    handles = apply_styles()
    assert isinstance(handles, StyleHandles)
    assert len(handles.palette) == 12
    assert len(handles.palette_hex) == 12
    # Each palette entry is RGB triple in [0, 1].
    for r, g, b in handles.palette:
        assert 0.0 <= r <= 1.0
        assert 0.0 <= g <= 1.0
        assert 0.0 <= b <= 1.0
    # Each hex entry is "#rrggbb" form.
    for hex_color in handles.palette_hex:
        assert hex_color.startswith("#")
        assert len(hex_color) == 7


def test_apply_styles_n_colors_is_configurable() -> None:
    handles = apply_styles(n_colors=6)
    assert len(handles.palette) == 6
    assert len(handles.palette_hex) == 6


def test_apply_styles_sets_plotly_default_template() -> None:
    apply_styles(palette_interactive="plotly_white")
    assert pio.templates.default == "plotly_white"
    apply_styles(palette_interactive="plotly_dark")
    assert pio.templates.default == "plotly_dark"
    # Reset for downstream tests.
    apply_styles()


def test_apply_styles_sets_matplotlib_rc_params() -> None:
    apply_styles()
    assert plt.rcParams["font.family"] == ["DejaVu Sans"]
    assert plt.rcParams["axes.titlesize"] == 12.0
    assert plt.rcParams["axes.labelsize"] == 10.0


def test_apply_styles_is_idempotent() -> None:
    handles_a = apply_styles()
    handles_b = apply_styles()
    # Same call twice → same palette (deterministic).
    assert handles_a.palette_hex == handles_b.palette_hex


def test_plotly_layout_is_a_complete_dict() -> None:
    assert "margin" in PLOTLY_LAYOUT
    assert "font" in PLOTLY_LAYOUT
    assert "title" in PLOTLY_LAYOUT
    margin = PLOTLY_LAYOUT["margin"]
    assert isinstance(margin, dict)
    for side in ("t", "l", "r", "b"):
        assert side in margin
