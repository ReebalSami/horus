---
source_url: "https://matplotlib.org/"
source_title: "Matplotlib — Visualization with Python"
source_author: "Matplotlib Development Team"
source_date: ""
retrieved_date: "2026-05-25"
extracted_concepts: []
tags: ["matplotlib", "static-visualization", "python-library", "publication-grade", "pyplot", "primary-tooling", "adr-024"]
archived_pdf: ""
status: stub
---

Matplotlib — comprehensive library for creating static, animated, and interactive visualizations in Python. License: BSD-compatible (matplotlib license). Quarto's default Python figure backend per `https://quarto.org/docs/computations/python.html`. Already transitive in HORUS via `mlx-vlm` deps (verified 2026-05-25 in `uv.lock`); ADR-024 promotes its status from incidental dependency to ratified visualization-stack member, and seaborn is added on top.

**Role in HORUS (per ADR-024)** — static editorial figures for thesis-appendix print. Renders to SVG (preferred, vector) or PNG in Quarto HTML output; renders to PDF (vector) in Quarto PDF output. Configurable per-figure via the standard `plt.figure(figsize=...)`, `plt.rcParams[...]`, and `plt.savefig(...)` API. The editorial aesthetic per Q5 of the EDA plan = FT/NYT-influenced muted palette, large clean typefaces, sparing color, baked-in annotations, self-explanatory captions.

**Configuration patterns in HORUS EDA notebooks**:

- `plt.style.use("seaborn-v0_8-paper")` — base editorial style
- `plt.rcParams["font.family"] = "DejaVu Sans"` — Quarto default; renders consistently in HTML + PDF
- `plt.rcParams["font.size"] = 11` — thesis-appendix readable
- `plt.rcParams["axes.spines.top"] = False` + `plt.rcParams["axes.spines.right"] = False` — minimalist editorial
- `plt.savefig(..., dpi=300, bbox_inches="tight")` — implicit in Quarto's figure capture

**Use pattern**: every EDA finding gets a static matplotlib/seaborn figure with annotation; Quarto auto-captures them via the cell-level `#| label: fig-<id>` + `#| fig-cap: "..."` metadata; cross-references via `@fig-<id>` in surrounding markdown.

**Documentation entry points**:
- Pyplot API: `https://matplotlib.org/stable/api/pyplot_summary.html`
- Style sheets: `https://matplotlib.org/stable/gallery/style_sheets/style_sheets_reference.html`
- Configuration (`rcParams`): `https://matplotlib.org/stable/users/explain/customizing.html`
- Quarto integration (cell metadata for figures): `https://quarto.org/docs/computations/python.html#figure-options`

Used together with seaborn (`docs/sources/tools/seaborn.md`) for the higher-level dataframe-aware API. matplotlib remains the underlying renderer; seaborn calls into matplotlib for layout + drawing.
