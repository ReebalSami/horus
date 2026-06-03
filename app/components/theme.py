"""Brand palette + the colour-blind-safe outcome palette (single source of truth).

Chrome colours (canvas, accent, sidebar) live in `.streamlit/config.toml`; this
module owns the DATA-encoding colours so figures and inline verdicts stay in sync.

The outcome palette is the Okabe–Ito colour-blind-safe set recommended by *Nature
Methods* (Wong, 2011, doi:10.1038/nmeth.1618) — deliberately NOT red/green — and
every verdict is shown with a glyph + word as well as colour, so colour is never
the sole signal (WCAG 2.1 success criterion 1.4.1, "Use of Color").
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Brand palette (mirrors the chrome in .streamlit/config.toml) ---
GOLD = "#C9A227"
GOLD_BRIGHT = "#D8B23E"
TEAL = "#0E4D45"
TEAL_DEEP = "#13201D"
SAND = "#F2C879"
INK = "#1A1A1A"
CANVAS = "#FBFAF7"
PANEL = "#F2EEE4"
HAIRLINE = "#E6DFCE"
MUTED = "#6B6256"

FONT_STACK = "Source Sans Pro, system-ui, -apple-system, Segoe UI, sans-serif"


@dataclass(frozen=True)
class OutcomeStyle:
    """How one scorer outcome is shown: colour + glyph + word + plain-language meaning."""

    code: str
    label: str
    glyph: str
    color: str
    tint: str
    description: str


# Okabe–Ito colour-blind-safe encoding for the scorer's five outcomes.
OUTCOMES: dict[str, OutcomeStyle] = {
    "TP": OutcomeStyle("TP", "Correct", "\u2714", "#009E73", "#E2F3EC", "Matched the ground truth"),
    "FP": OutcomeStyle(
        "FP",
        "Invented",
        "\u25b2",
        "#D55E00",
        "#FBE7DA",
        "Emitted a value for a field that is genuinely absent (a hallucination)",
    ),
    "FN": OutcomeStyle(
        "FN",
        "Missed",
        "\u2718",
        "#E69F00",
        "#FCEFD6",
        "A ground-truth value the model did not extract",
    ),
    "TN": OutcomeStyle(
        "TN",
        "Correct (absent)",
        "\u00b7",
        "#7C8389",
        "#EEF0F1",
        "Correctly left empty — nothing present, nothing emitted",
    ),
    "EXCLUDED": OutcomeStyle(
        "EXCLUDED",
        "Excluded",
        "\u2013",
        "#A89F8E",
        "#F0ECE3",
        "Ground truth not gradable for this field (excluded from scoring)",
    ),
}


def outcome_style(outcome: str) -> OutcomeStyle:
    """Return the display style for a scorer outcome (defaults to EXCLUDED if unknown)."""
    return OUTCOMES.get(outcome, OUTCOMES["EXCLUDED"])


# Sequential colour scale for F1 heatmaps (pale sand → gold → deep teal):
# perceptually ordered, on-brand, and colour-blind-safe. Plotly colorscale form.
SEQUENTIAL_SCALE: list[list[float | str]] = [
    [0.0, "#F5EDD9"],
    [0.5, GOLD],
    [1.0, TEAL],
]


def outcome_badge(outcome: str) -> str:
    """Inline HTML badge (glyph + word, colour-coded) for use in `st.markdown`."""
    style = outcome_style(outcome)
    return (
        "<span style='display:inline-block;padding:0.05rem 0.5rem;border-radius:0.5rem;"
        f"background:{style.tint};color:{style.color};font-weight:600;font-size:0.8rem;"
        f"white-space:nowrap'>{style.glyph}&nbsp;{style.label}</span>"
    )


def legend_html() -> str:
    """A compact verdict legend (the colour key) for the explorer."""
    badges = "".join(outcome_badge(code) for code in ("TP", "FP", "FN", "TN"))
    return f"<div style='display:flex;gap:0.4rem;flex-wrap:wrap;align-items:center'>{badges}</div>"
