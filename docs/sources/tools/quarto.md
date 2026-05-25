---
source_url: "https://quarto.org/"
source_title: "Quarto — An open-source scientific and technical publishing system"
source_author: "Posit, PBC (RStudio)"
source_date: ""
retrieved_date: "2026-05-25"
extracted_concepts: []
tags: ["quarto", "scientific-publishing", "pandoc", "jupyter-kernel", "html-pdf-rendering", "cross-references", "primary-tooling", "adr-024"]
archived_pdf: ""
status: stub
---

Quarto — open-source scientific and technical publishing system from Posit (RStudio's parent company). Built on Pandoc + Jupyter kernels (Python/R/Julia/Observable JS). License: MIT. Renders authored content into HTML (single-page or multi-chapter book), PDF (LaTeX or Typst engine), Word, EPUB, and RevealJS slides from a single source. Native first-class affordances for thesis-grade output: cross-references via `@fig-id` / `@sec-id` / `@eq-id`, citations via `[@key]` against `references.bib`, code-folding via `code-fold: true`, figure captions, page numbers, table-of-contents, footnotes.

**Role in HORUS (per ADR-024)** — rendering layer ON TOP of the existing jupytext+papermill source-of-truth (per `notebook-discipline` L3 rule). Quarto reads jupytext `.py:percent` files directly via `quarto render <file>.py` (per https://quarto.org/docs/computations/render-scripts.html); no `.qmd` wrapper needed. The new `make eda CFG=...` Makefile target chains jupytext-sync + Quarto execute + render to produce ONE archived HTML book + ONE PDF per EDA notebook (issue #46). Solves the user-stated "HTML gets messy fast" concern by replacing many sibling nbconvert outputs with one cross-referenced book. Plotly interactive figures embed natively via Jupyter Widgets (`https://quarto.org/docs/interactive/widgets/jupyter.html`); matplotlib/seaborn static figures render via the default Python figure backend. PDF output gracefully drops Plotly interactivity (static fallback emitted automatically).

**Installation** — Quarto CLI is a separate binary (~80 MB, written in Rust + ships with Deno). On macOS dev machines: `brew install quarto`. Linux dev machines (none currently in scope) would use the official tarball at `https://quarto.org/docs/get-started/`. Pinned version >= 1.7 for native script-rendering of jupytext files (1.4+ added the feature; 1.7+ matured it). CI per ADR-023 does NOT install Quarto — rendering happens on dev machine only; rendered HTML/PDF are gitignored.

**Documentation entry points**:
- Get-started (Python): `https://quarto.org/docs/get-started/hello/jupyter.html`
- Render scripts (jupytext `.py:percent` source): `https://quarto.org/docs/computations/render-scripts.html`
- Python computations: `https://quarto.org/docs/computations/python.html`
- Parameters (`-P key:value`): `https://quarto.org/docs/computations/parameters.html`
- Cross-references: `https://quarto.org/docs/authoring/cross-references.html`
- Jupyter Widgets (Plotly integration): `https://quarto.org/docs/interactive/widgets/jupyter.html`
- Project config (`_quarto.yml`): `https://quarto.org/docs/projects/quarto-projects.html`
- Books format: `https://quarto.org/docs/books/`

**Alternative renderers considered + rejected in ADR-024**: nbconvert HTML alone (sibling-files-messy problem persists); marimo as full notebook replacement (disrupts `notebook-discipline` mid-thesis); Streamlit/Dash dashboards (transient, not archival); pure matplotlib + nbconvert (loses interactivity).
