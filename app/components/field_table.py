"""The colour-coded per-field verdict table + the three-approach comparison matrix.

Both render `pandas` frames through `st.dataframe` with a Styler that tints each
verdict cell using the colour-blind-safe outcome palette (paired with a glyph +
word, never colour alone). The frames are built by pure helpers so they can be
asserted on in tests without a running Streamlit server.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import theme
from app.data import fields as field_meta
from horus.eval.scorer import FieldResult


def _fit_height(n_rows: int) -> int:
    """Pixel height that shows all rows without an internal scrollbar (capped)."""
    return min(40 + 36 * n_rows, 760)


def _verdict_text(outcome: str) -> str:
    style = theme.outcome_style(outcome)
    return f"{style.glyph}  {style.label}"


def _cell_css(outcome: str) -> str:
    style = theme.outcome_style(outcome)
    return f"background-color:{style.tint};color:{style.color};font-weight:600"


def build_field_dataframe(results: list[FieldResult]) -> tuple[pd.DataFrame, list[str]]:
    """Build the per-field display frame + a parallel list of outcomes (for styling)."""
    by_key = {result.english_key: result for result in results}
    rows: list[dict[str, object]] = []
    outcomes: list[str] = []
    for key in field_meta.FIELD_ORDER:
        result = by_key.get(key)
        if result is None:
            rows.append(
                {
                    "Field": field_meta.label(key),
                    "Verdict": "— not scored",
                    "Extracted": "—",
                    "Ground truth": "—",
                    "Score": None,
                    "German": field_meta.german_label(key),
                }
            )
            outcomes.append("EXCLUDED")
            continue
        gt = result.gt_normalized if (result.gt_present and result.gt_normalized) else "—"
        rows.append(
            {
                "Field": field_meta.label(key),
                "Verdict": _verdict_text(result.outcome),
                "Extracted": result.predicted_normalized or "—",
                "Ground truth": gt,
                "Score": round(float(result.score), 2),
                "German": field_meta.german_label(key),
            }
        )
        outcomes.append(result.outcome)
    return pd.DataFrame(rows), outcomes


def render_field_table(results: list[FieldResult]) -> None:
    """Render the colour-coded per-field verdict table for one (model, invoice)."""
    frame, outcomes = build_field_dataframe(results)
    styler = frame.style.apply(
        lambda _column: [_cell_css(outcome) for outcome in outcomes],
        subset=["Verdict"],
        axis=0,
    )
    st.dataframe(
        styler,
        hide_index=True,
        use_container_width=True,
        height=_fit_height(len(frame)),
        column_config={
            "Field": st.column_config.TextColumn("Field", width="medium"),
            "Verdict": st.column_config.TextColumn("Verdict", width="small"),
            "Extracted": st.column_config.TextColumn("Extracted", width="medium"),
            "Ground truth": st.column_config.TextColumn("Ground truth", width="medium"),
            "Score": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
            "German": st.column_config.TextColumn("German", width="small"),
        },
    )


def build_comparison_matrix(
    per_approach_results: dict[str, dict[str, FieldResult]],
    approaches: list[tuple[str, str]],
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Build the field × approach verdict matrix + per-column outcomes (for styling).

    `per_approach_results` maps approach key → {english_key: FieldResult};
    `approaches` is an ordered list of (approach key, column label).
    """
    rows: list[dict[str, object]] = []
    column_outcomes: dict[str, list[str]] = {label: [] for _key, label in approaches}
    for key in field_meta.FIELD_ORDER:
        row: dict[str, object] = {"Field": field_meta.label(key)}
        for approach_key, label in approaches:
            result = per_approach_results.get(approach_key, {}).get(key)
            outcome = result.outcome if result is not None else "EXCLUDED"
            row[label] = _verdict_text(outcome)
            column_outcomes[label].append(outcome)
        rows.append(row)
    return pd.DataFrame(rows), column_outcomes


def render_comparison_matrix(
    per_approach_results: dict[str, dict[str, FieldResult]],
    approaches: list[tuple[str, str]],
) -> None:
    """Render the field × approach verdict matrix (one invoice, all approaches)."""
    frame, column_outcomes = build_comparison_matrix(per_approach_results, approaches)
    styler = frame.style
    for _approach_key, label in approaches:
        outcomes = column_outcomes[label]
        styler = styler.apply(
            lambda _column, outs=outcomes: [_cell_css(outcome) for outcome in outs],
            subset=[label],
            axis=0,
        )
    st.dataframe(styler, hide_index=True, use_container_width=True, height=_fit_height(len(frame)))
