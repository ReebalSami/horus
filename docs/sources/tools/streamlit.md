---
source_url: "https://docs.streamlit.io/develop/concepts/multipage-apps"
source_title: "Streamlit — Multipage apps (st.navigation / st.Page)"
source_author: "Snowflake Inc. (Streamlit)"
source_date: ""
retrieved_date: "2026-06-02"
extracted_concepts: []
tags: ["streamlit", "dashboard", "observability", "python-framework", "multipage", "st-navigation", "st-page", "primary-tooling", "adr-036"]
archived_pdf: ""
status: stub
---

Streamlit — open-source Python framework for building interactive data/ML web apps from plain Python scripts. License: Apache-2.0. PyPI: `streamlit` (1.5x line, Python ≥3.9). Runs locally with `streamlit run <entrypoint>.py`; pure-Python (no JS required); reactive re-run-on-interaction execution model with `st.session_state` for persistence and `@st.cache_data` / `@st.cache_resource` for memoization. M1-friendly (CPU-only, no GPU dependency) — fits `know-your-hardware`.

**Modern multipage API (verified via context7, `/streamlit/docs`, 2026-06-02)** — the current idiom is **programmatic navigation**, not the legacy `pages/` directory convention:

```python
import streamlit as st

explorer = st.Page("pages/invoice_explorer.py", title="Invoice Explorer", icon=":material/description:")
compare  = st.Page("pages/approach_comparison.py", title="Approach Comparison", icon=":material/compare:")

pg = st.navigation({"Evaluation": [explorer, compare]})   # dict → sidebar sections
pg.run()
```

- `st.Page(page, title=, icon=, default=)` — declares a page (from a file path or a callable).
- `st.navigation(pages)` — `pages` is a list, or a `dict[section_name, list[st.Page]]` to group pages into labelled sidebar sections (the scalable/modular shape).
- `pg.run()` — runs the selected page from the entry-point script.
- `st.logo(...)`, `st.session_state`, dynamic page-dict assembly (role/state-conditional sections) all supported — the basis for HORUS's "add a page each time we do something" modularity.

**Role in HORUS (per ADR-036)** — the research/eval observability application at top-level `app/`. Read-only data access from MLflow runs (ADR-011) + saved transcripts (`docs/sources/transcripts-*`) + CII ground truth (ADR-012); no model inference or re-scoring in the UI. First increment: **Invoice Explorer** (page image + raw transcript + extracted JSON + GT + colour-coded per-field score) + **Approach Comparison** (Arm A vs Arm B vs regex baseline; reading-ceiling/parser-loss tables). Modular page-registry so new surfaces (fine-tuning tracker, held-out results, the #82 end-user extraction prototype) drop in as new `st.Page`s without restructuring.

**Why Streamlit over alternatives (ADR-036)**:
- **Gradio** — excellent for single-model demo widgets, weaker for a multipage analytical dashboard with custom layout; better suited to the eventual #82 inference demo than to the research surface.
- **Static HTML / Quarto** (ADR-024) — Quarto already owns the *thesis-grade EDA book* (static, citable). The observability need is *interactive* (click an invoice, drill into a field) and *live* (reads the latest MLflow run), which static rendering cannot serve.
- **The existing `textual` TUI** (ADR-026) — terminal-only, live-run-progress-oriented; not a per-invoice inspection/error-analysis surface, and not screenshot-friendly for the thesis.

**Documentation entry points**:
- Multipage concepts: `https://docs.streamlit.io/develop/concepts/multipage-apps`
- `st.navigation`: `https://docs.streamlit.io/develop/api-reference/navigation/st.navigation`
- `st.Page`: `https://docs.streamlit.io/develop/api-reference/navigation/st.page`
- Theming (professional look): `https://docs.streamlit.io/develop/concepts/configuration/theming`
- Caching: `https://docs.streamlit.io/develop/concepts/architecture/caching`
- GitHub: `https://github.com/streamlit/streamlit`
