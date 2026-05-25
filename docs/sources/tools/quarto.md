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

## Books format details (ADR-025)

ADR-025 extends ADR-024's single-notebook scope into a multi-chapter Quarto Book covering all 7 datasets in `data/raw/`. The Books format (`https://quarto.org/docs/books/`) is Quarto's standard for multi-chapter scientific reports, inheriting from Pandoc + bookdown lineage.

**Project type**: `_quarto.yml` declares `project.type: book` (instead of ADR-024's `default`); a `book:` section lists chapters in order. Each chapter is a separate `.py:percent` (jupytext) or `.qmd` file. Quarto compiles the chapters into a single navigable HTML book at `_book/index.html` (with sidebar TOC, chapter numbers, search) and a single PDF at `_book/<title>.pdf`.

**Cross-references across chapters**: `@sec-id` / `@fig-id` / `@tbl-id` / `@eq-id` syntax resolves across chapter boundaries (per `https://quarto.org/docs/authoring/cross-references.html`). Links between chapters use standard `[link text](other-chapter.qmd#section-id)` syntax.

**Required files**: `index.qmd` (preface; HTML home page) + at least one chapter; conventionally `references.qmd` for the bibliography. Appendices declared via `book.appendices:` list (separate from `book.chapters:`).

**Numbering**: chapters are auto-numbered; sections per chapter are auto-numbered; `.unnumbered` class on a heading opts out (e.g., `# Preface {.unnumbered}` for the index file). `number-depth: N` (top-level format option, NOT under `book:`) controls section-numbering depth.

**Books-specific docs entry points**:
- Books overview: `https://quarto.org/docs/books/`
- Book structure: `https://quarto.org/docs/books/book-structure.html`
- Book output formats (HTML / PDF / EPUB): `https://quarto.org/docs/books/book-output.html`
- Cross-references in books: `https://quarto.org/docs/authoring/cross-references.html`

**HORUS Book scaffold (per ADR-025)**:
- `index.qmd` (preface; scope; methodology overview)
- 7 chapter notebooks (`experiments/01-zugferd.py` through `experiments/07-inv-cdip-tobacco.py`)
- 1 cross-corpus synthesis chapter (`experiments/08-cross-corpus.py`)
- 1 consolidated Datasheets-for-Datasets appendix (`experiments/A1-datasheets.qmd`)
- 1 references / bibliography (`experiments/references.qmd`)
- Output: `_book/index.html` (HTML book) + `_book/Horus-EDA.pdf` (PDF) — both gitignored as build artifacts.
