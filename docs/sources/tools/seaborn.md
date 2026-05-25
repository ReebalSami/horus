---
source_url: "https://seaborn.pydata.org/"
source_title: "seaborn: statistical data visualization"
source_author: "Michael Waskom and contributors"
source_date: ""
retrieved_date: "2026-05-25"
extracted_concepts: []
tags: ["seaborn", "statistical-visualization", "python-library", "matplotlib-based", "primary-tooling", "adr-024"]
archived_pdf: ""
status: stub
---

seaborn — statistical visualization library built on top of matplotlib (`docs/sources/tools/matplotlib.md`). License: BSD-3-Clause. PyPI: `seaborn` 0.13.x line stable through 2025; Python ≥3.8. Adds a high-level dataframe-aware API on top of matplotlib's lower-level pyplot interface: dataframe-input plotting (`sns.heatmap(df)`, `sns.histplot(data=df, x=col)`, `sns.boxplot(data=df, x=cat, y=val)`), curated palettes (`sns.color_palette("muted")` aligns with FT/NYT-influenced editorial aesthetic per Q5 of the ADR-024 EDA plan), categorical-aware faceting (`sns.FacetGrid` for per-flavor / per-profile breakdowns), and built-in statistical estimators (KDE, regression, ECDF).

**Role in HORUS (per ADR-024)** — high-level dataframe-aware visualization API for the editorial-static thesis figures. matplotlib remains the renderer; seaborn is the ergonomic layer that turns the corpus_index dataframe into figures with one call. Issue #46 EDA's expected use:

- `sns.heatmap(presence_df, ...)` — 16-field × 151-PDF presence heatmap (static version; Plotly version sits in the Interactive Explorer section per Q5 hybrid)
- `sns.histplot(data=corpus_df, x="page_count", hue="flavor", multiple="stack")` — page-count distribution faceted by flavor
- `sns.barplot(data=field_presence_df, x="field", y="presence_rate")` — per-field presence-rate bar chart
- `sns.FacetGrid(data=corpus_df, col="profile", row="generator")` — multi-variant breakdowns

**Configuration patterns in HORUS EDA notebooks**:

- `sns.set_theme(style="white", palette="muted", context="paper", font_scale=1.05)` — editorial paper context
- `sns.despine()` — remove top/right axis spines (minimalist)
- `sns.color_palette("muted")` — 10-color muted palette, FT/NYT-influenced

**Documentation entry points**:
- Tutorial overview: `https://seaborn.pydata.org/tutorial.html`
- API reference: `https://seaborn.pydata.org/api.html`
- Color palettes: `https://seaborn.pydata.org/tutorial/color_palettes.html`
- Themes / styles: `https://seaborn.pydata.org/tutorial/aesthetics.html`
- GitHub: `https://github.com/mwaskom/seaborn`

**Why seaborn AND matplotlib both?** matplotlib alone is verbose for dataframe-aware operations (manual `ax.bar(...)` calls + manual color management + manual legend logic); seaborn alone wraps matplotlib but doesn't expose every customization knob. Standard practice: seaborn for the figure structure + palette, drop to matplotlib (`fig, ax = plt.subplots()` + `sns.heatmap(..., ax=ax)` + `ax.set_title(...)`) for fine control over axes / annotations / titles. Both libraries are stable and complementary; ADR-024 ratifies them as a pair.
