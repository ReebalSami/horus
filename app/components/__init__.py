"""Reusable Streamlit UI components for the observability dashboard.

`theme` holds the brand + colour-blind-safe outcome palette (the single source of
truth for data-encoding colour); `cards`, `field_table`, and `charts` render the
KPI tiles, the colour-coded per-field verdict table, and the comparison figures.
Rendering helpers are kept thin; the figure builders in `charts` are pure functions
so they can be unit-tested without a running Streamlit server.
"""
