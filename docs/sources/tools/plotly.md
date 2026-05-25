---
source_url: "https://plotly.com/python/"
source_title: "Plotly Python Open Source Graphing Library"
source_author: "Plotly Technologies Inc."
source_date: ""
retrieved_date: "2026-05-25"
extracted_concepts: []
tags: ["plotly", "interactive-visualization", "python-library", "jupyter-widgets", "quarto-integration", "primary-tooling", "adr-024"]
archived_pdf: ""
status: stub
---

Plotly — open-source Python graphing library for interactive web-native visualizations. License: MIT (Python library) / proprietary (Plotly Cloud SaaS, NOT used by HORUS). PyPI: `plotly` 6.x line stable since late 2025; Python ≥3.9. Built on plotly.js (D3.js + WebGL); produces self-contained interactive HTML widgets (no server required for rendering). Express API (`plotly.express` for one-line dataframe-aware plotting) + Graph Objects API (`plotly.graph_objects` for full control).

**Role in HORUS (per ADR-024)** — interactive figure layer for the EDA visualization stack. Issue #46 EDA produces a 16-field × 151-PDF presence heatmap that benefits from hover-to-see-PDF-name interactivity (Q5 hybrid recommendation in the EDA plan). Plotly figures render natively in Quarto HTML output via Jupyter Widgets (`https://quarto.org/docs/interactive/widgets/jupyter.html`); PDF export gracefully falls back to static images (Quarto's documented behavior). Templates: `plotly_white` (clean editorial baseline aligned with FT/NYT-influenced palette per Q5); `plotly_dark` (available but not used).

**Use pattern in HORUS**:

- Static thesis-appendix figures → matplotlib/seaborn (per `docs/sources/tools/matplotlib.md` + `docs/sources/tools/seaborn.md`)
- Interactive in-session exploration figures (heatmaps, per-flavor breakdowns, per-field drill-downs) → Plotly
- Both coexist in the rendered HTML book; PDF carries only the static set

The split is intentional per the ADR-024 hybrid aesthetic: thesis appendix needs print-ready, self-contained figures with curated palettes; in-session exploration benefits from hover/drill-down; Quarto handles both in one source.

**Documentation entry points**:
- Python library overview: `https://plotly.com/python/`
- Plotly Express (high-level): `https://plotly.com/python/plotly-express/`
- Graph Objects (low-level): `https://plotly.com/python/graph-objects/`
- Templates / themes: `https://plotly.com/python/templates/`
- Heatmaps: `https://plotly.com/python/heatmaps/`
- GitHub: `https://github.com/plotly/plotly.py`

**Alternative interactive libraries considered + rejected in ADR-024**: Bokeh (similar capability, smaller Quarto integration footprint, less common in 2025 academic publishing); Altair (declarative grammar of graphics, considered but rejected because the editorial-static figures we want for thesis are best done in matplotlib/seaborn — adding Altair would create a third visualization stack); HoloViews (well-suited for large datasets but our 151-PDF corpus is small).
