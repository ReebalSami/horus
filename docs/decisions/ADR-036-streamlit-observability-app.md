# ADR-036 — Streamlit observability application (modular research/eval dashboard at top-level `app/`)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-02 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (held-out-evaluation strategy session; plan `~/.windsurf/plans/horus-heldout-eval-strategy-d8c53c.md`) |
| **Issue** | NEW "Streamlit observability app" epic (filed during the ADR-034 board reconciliation); relates to #82 (end-user prototype). |
| **Relationship** | Sub-decision of **ADR-034**; supersedes the **ADR-026** TUI as the *analysis* surface; introduces a new top-level `app/` dir (ratified here per `clean-project-structure`). |

## Context

The user's recurring blocker: *"I can't see how it works — there's no frontend."* Error analysis (which fields fail, on which invoices, for which arm) and thesis figures both need a surface that shows, per invoice: the page image, the raw transcript, the extracted JSON, the ground truth, and the per-field score. None of the existing surfaces provide this:

- MLflow UI (ADR-015) shows **run-level metrics**, not per-invoice field-level inspection.
- The `textual` TUI (ADR-026) shows **live cohort-run progress** in the terminal; it is not an analysis/inspection tool and is not screenshot-friendly.
- The reading-ceiling report (ADR-030) is **static markdown**.

The user's requirement (verbatim intent): a **Streamlit** app that is "very good and very scalable from the beginning to cover all the areas of this project," **modular** ("every time we do something we add it easily"), and **professional** ("no amateur stuff"). This ADR ratifies the framework, placement, and architecture; the build is handed to a coding session.

## Current-state survey (2026-06-02)

| Surface | Where | Gap |
|---|---|---|
| MLflow UI | ADR-011/015 (`make mlflow-ui`) | run/metric browsing only; no per-invoice field drill-down |
| TUI dashboard | ADR-026 (`src/horus/cli/`) | terminal live-run progress; not inspection; not screenshottable |
| Reading-ceiling report | ADR-030 (`eval/*.md`) | static; not interactive; one diagnostic only |
| `#82` prototype | issue (planned) | end-user extraction demo (FastAPI+Streamlit+Docker) — product, not research surface |
| Streamlit multipage API | context7 `/streamlit/docs` (verified 2026-06-02) | `st.Page` + `st.navigation(dict)` + `pg.run()` is the current modular idiom; stub `docs/sources/tools/streamlit.md` |

## Options considered

**A — Framework:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Streamlit (chosen)** | pure-Python, fast to build, multipage + session-state + caching, Apache-2.0, M1-friendly, screenshot-friendly | the user explicitly requested it; best fit for a multipage analytical dashboard |
| Gradio | great demo widgets | weaker for multipage custom-layout dashboards; better suited to the eventual #82 inference demo |
| Static HTML | zero-dep, cheap | not interactive (no click-to-drill-into-a-field); cannot read the latest MLflow run live |
| Quarto (ADR-024) | already owns thesis-grade static EDA | static + citable is the EDA book's job; observability needs interactivity + liveness |

**B — Placement:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Top-level `app/` (chosen)** | Streamlit convention (entry script + `pages/`); keeps UI out of the importable `src/horus/` package | a new top-level dir — ratified here per `clean-project-structure` (new top-level path requires an ADR) |
| `src/horus/app/` | inside the package | conflates the library with its UI; awkward for `streamlit run` entrypoint discovery |

**C — Relationship to #82:** the observability app is built **now** (research need); the #82 FastAPI+Docker **end-user** prototype folds in **later** as a page within the same app → one unified, modular app "covering all areas," as requested. Rejected: two separate Streamlit apps (duplication, divergent design).

**D — Data access:** **read-only** from MLflow runs + saved transcripts + CII GT. **No** model inference or re-scoring in the UI (keeps it fast, deterministic, and side-effect-free; recomputation stays in the harness/scripts). Rejected: recompute-in-UI (slow, non-reproducible, couples UI to model loading).

## Decision + integration thoughts

1. **Adopt Streamlit** (`streamlit` dep added by the coding session per `uv-discipline`; source stub `docs/sources/tools/streamlit.md`).
2. **Top-level `app/`**: entry-point `app/Home.py` (calls `st.navigation`), pages under `app/pages/`, reusable widgets under `app/components/`, a read-only data-access layer under `app/data/` (wraps MLflow `search_runs` + transcript/GT loaders from `src/horus/eval`).
3. **Modular multipage** via the verified API: `st.Page(...)` per surface, grouped into `st.navigation({section: [pages]})`; adding a surface = drop a `pages/<x>.py` + register it. First increment:
   - **Invoice Explorer** — pick model/arm/invoice → page image + transcript + extracted JSON + GT + colour-coded per-field score (TP/FP/FN).
   - **Approach Comparison** — Arm A vs Arm B vs regex baseline; reading-ceiling + parser-loss tables (ADR-030), 4-metric surface (ADR-027).
4. **Professional look**: Streamlit theming (`.streamlit/config.toml`) + a consistent layout system + a curated palette (align with the ADR-024 editorial aesthetic); no default-gray blandness.
5. **Read-only**; reads MLflow (ADR-011), transcripts (`docs/sources/transcripts-*`), GT (ADR-012). No GPU, no inference.

**Integration:** reuses `src/horus/eval` loaders + the ADR-027 scorer helpers; the app is a *consumer* of existing artifacts. The ADR-026 TUI stays for live-run progress (not extended); #72/#85 (TUI rollout + crash) close as superseded for the analysis surface (per ADR-034 board reconciliation). Doubles as the **error-analysis + thesis-screenshot** surface.

## Source archival

- **New stub**: `docs/sources/tools/streamlit.md` (Apache-2.0; `st.Page`/`st.navigation` API verified via context7 `/streamlit/docs`, 2026-06-02).
- Internal: ADR-011/015 (MLflow), ADR-026 (TUI superseded), ADR-024 (Quarto boundary), ADR-027 (metrics), ADR-012 (GT), ADR-034 (parent).

## Supersession trigger

Superseded if **any** of:

1. The app outgrows Streamlit's interaction model (e.g., needs real-time multi-user collaboration) → a new ADR ratifies a replacement (e.g., a React/FastAPI SPA).
2. The #82 end-user prototype is built as a *separate* deployable (Docker) rather than folded in as a page → a new ADR records the split and the shared-component boundary.
3. Streamlit's multipage API changes materially → the architecture section is amended (the source stub's API snapshot is the dated reference).

## Consequences

- HORUS gains a per-invoice inspection + approach-comparison surface (the user's "I can't see it" blocker) and an error-analysis + thesis-figure tool.
- New top-level `app/` dir is ratified; the TUI is retired as the analysis surface (#72/#85 close).
- `streamlit` becomes a (dev/app) dependency; the app is read-only and M1-friendly.
- Build handed to a coding session (plan §"Coding-session handoffs"); no code in this ADR.
