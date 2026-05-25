# ADR-024 — EDA visualization stack (Quarto + Plotly + matplotlib/seaborn)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-25 |
| **Milestone** | Issue #46 EDA on ZUGFeRD corpus (experiment phase) |
| **Authored by** | Cascade D issue #46 EDA planning session (`~/.windsurf/plans/eda-zugferd-9c4a5b.md` Q2 lock) |
| **Supersession trigger** | See `## Supersession trigger` below |

## Context

Issue #46 mandates a descriptive-only EDA on the 151-PDF ZUGFeRD corpus (per the locked plan at `~/.windsurf/plans/eda-zugferd-9c4a5b.md`). The user's stated visualization-quality bar in that planning session: *"I need some good visualisations of EDA. they have to be very nice, attractive and designed on expert creative levels. Also we need to decide how to do them and what to use like html (usually gets messy fast and hard to return to them when they are too many) or are there better modern approaches out there..."*

Existing notebook toolchain (per `~/Projects/horus/.windsurf/rules/notebook-discipline.md` L3 + ADR-016): jupytext `.py:percent` source-of-truth → papermill execution → `*.executed.ipynb` build artifact (gitignored). The papermill output renders to HTML via `jupyter nbconvert` IF needed, but:

1. **One HTML file per notebook** — the user's "messy HTML files" concern. EDAs of the size we're authoring (11 sections, ~10 charts) accumulate sibling artifacts that drift across the project.
2. **No cross-references** — `@fig-N`, `@sec-name`, `@eq-stddev` are not first-class in nbconvert HTML.
3. **No PDF export** — thesis-defense reproducibility (per `horus-decision-discipline` + brainstorm v2 §0 lock #9 *"scientific correctness over speed"*) needs a print-ready archived deliverable. nbconvert's PDF path goes through LaTeX with no native figure-caption / page-numbering / citation conventions.
4. **No code-folding / page-numbering / figure-caption / table-of-contents conventions** — these are publication-grade affordances that academic readers expect.

The gap is real: an EDA artifact intended to land in the thesis appendix needs publication-grade rendering, not just notebook export. The toolchain layer that closes this gap (without disrupting the existing source-of-truth) is the decision this ADR ratifies.

## Decision

Adopt the following stack as the rendering + visualization layer **on top of** the existing jupytext+papermill source-of-truth (per `notebook-discipline`):

1. **Quarto** (Posit, https://quarto.org/) — the rendering engine. Reads jupytext `.py:percent` directly via `quarto render <file>.py`; produces HTML + PDF + (optionally) Word + EPUB from one source. Native cross-references, citations, page numbering, figure captions, code-folding, table-of-contents, multi-format output. v1.7+ supports script rendering via the percent-format directly per `https://quarto.org/docs/computations/render-scripts.html`.
2. **Plotly** (https://plotly.com/python/) — interactive figures. Native Quarto integration via Jupyter Widgets per `https://quarto.org/docs/interactive/widgets/jupyter.html`. Hover tooltips, drill-down, brushing/linking. Plotly's `plotly_white` template aligns with the editorial-aesthetic ask (Q5 of the EDA plan).
3. **matplotlib** (https://matplotlib.org/) + **seaborn** (https://seaborn.pydata.org/) — static editorial figures for thesis-appendix print. matplotlib is already transitive via `mlx-vlm` deps (verified via `uv pip list | grep -i matplotlib`); seaborn is new. FT/NYT-influenced palette (muted, sparing color, large clean type, baked-in annotations).

### Source-of-truth flow (new vs existing)

| Stage | Tool | Source | Output | Tracked in git? |
|---|---|---|---|---|
| 1. Author | jupytext (existing) | `.py:percent` editor | `experiments/eda-zugferd.py` | YES (source-of-truth) |
| 2. Execute | Quarto (NEW) | `.py:percent` script | inline kernel state | (transient) |
| 3. Render HTML | Quarto (NEW) | inline state | `experiments/eda-zugferd.html` | NO (build artifact, gitignored) |
| 4. Render PDF | Quarto (NEW) | inline state | `experiments/eda-zugferd.pdf` | NO (build artifact, gitignored) |
| (optional) | papermill (existing) | `.py:percent` script | `experiments/eda-zugferd.executed.ipynb` | NO (existing pattern, gitignored) |

The existing `make experiment NB=... CFG=...` target (jupytext+papermill flow) is **untouched**. The new `make eda CFG=...` target is **additive** — it invokes Quarto to render the EDA notebook into an HTML book + PDF. Both pipelines coexist: papermill remains the canonical batch-parameterization runner for cohort sweeps (pilot-13, structured-probe overlays, etc.); Quarto becomes the canonical thesis-grade-artifact renderer for descriptive EDAs.

### Hybrid aesthetic (Q5 of EDA plan)

Per the locked plan answer to Q5 = C (hybrid):

- **Static figures** (matplotlib/seaborn) — every finding gets a thesis-appendix-ready figure with FT/NYT-influenced palette: muted color, large clean type, key annotations baked in, self-explanatory caption. These survive the PDF export.
- **Interactive figures** (Plotly) — heatmaps and per-flavor breakdowns get a Plotly version in a separate `## Interactive Explorer` section in the HTML output. PDF export gracefully drops interactivity (Quarto's documented behavior; static fallback emitted).
- The HTML book carries both; the PDF carries only the static set.

## Current-state survey

Dated 2026-05-25. Sources consulted via `context7` MCP (`mcp2_resolve-library-id` then `mcp2_query-docs` for `/quarto-dev/quarto-web`) + `search_web` for the marimo-vs-Quarto landscape.

- **Quarto v1.8** (`https://quarto.org/`, retrieved 2026-05-25) — open-source scientific publishing system from Posit (RStudio's parent company). Built on Pandoc + Jupyter kernels. Supports Python, R, Julia, Observable JS. Output formats: HTML (single page or multi-chapter book), PDF (LaTeX or Typst engine), Word, EPUB, RevealJS slides. License: MIT. Cross-references via `@fig-id` / `@sec-id` / `@eq-id` syntax. Citations via `[@key]` against `references.bib`. Code-folding via `code-fold: true` cell metadata. Native Plotly support in HTML output via Jupyter Widgets. Script rendering for `.py:percent` files via `https://quarto.org/docs/computations/render-scripts.html` — confirmed Quarto reads jupytext source directly without a `.qmd` wrapper.
- **Plotly Python v6.x** (`https://plotly.com/python/`, retrieved 2026-05-25) — interactive Python visualization. Apache 2.0 license. Native Quarto integration; `plotly.io.show(fig)` or `fig.show()` in a Quarto cell renders interactive HTML widget in HTML output, static fallback in PDF. `plotly_white` and `plotly_dark` templates ship in-box. PyPI: `plotly` 6.x line stable since late 2025; Python ≥3.9 supported.
- **matplotlib v3.10+** (`https://matplotlib.org/`, retrieved 2026-05-25) — already transitive via `mlx-vlm` (verified 2026-05-25 in current `uv.lock`). Static rendering, publication-grade. Quarto's default Python figure backend per `https://quarto.org/docs/computations/python.html`.
- **seaborn v0.13+** (`https://seaborn.pydata.org/`, retrieved 2026-05-25) — statistical visualization built on matplotlib. BSD-3 license. Adds: high-level dataframe-aware API (`sns.heatmap`, `sns.histplot`, `sns.boxplot`), curated palettes (`sns.color_palette("muted")` aligns with editorial aesthetic), categorical-aware faceting (`sns.FacetGrid`). PyPI: `seaborn` 0.13.x line stable through 2025; Python ≥3.8 supported.
- **marimo v0.10+** (`https://marimo.io/`, retrieved 2026-05-25) — reactive Python notebook stored as plain `.py`. Apache 2.0. Replaces jupyter+jupytext+papermill+streamlit in one tool. Reactive cell graph, deterministic execution, built-in package management. Considered as Option C in `## Options considered`; rejected for HORUS scope.
- **Existing precedent** — Berghaus et al. 2025 (cited in brainstorm v2 §7.1) and an increasing share of academic ML papers in 2025 use Quarto for thesis publication. Posit's `https://posit.co/blog/announcing-quarto-a-new-scientific-and-technical-publishing-system/` documents the design intent (Pandoc-based, kernel-agnostic). The `quarto4research` ecosystem project (`https://github.com/elenlefoll/quarto4research`) curates thesis-grade templates.

### Existing HORUS toolchain anchors

- **jupytext** (existing per `notebook-discipline` L3 rule + `pyproject.toml` `[dependency-groups] dev`) — source-of-truth for experiments, `.py:percent` format, paired with `.ipynb` build artifact.
- **papermill** (existing per `horus-config-discipline` + `pyproject.toml` `[dependency-groups] dev`) — parameterized batch-execution of jupytext-paired notebooks. ONE param `cfg_path` per `horus-config-discipline`.
- **mlx-vlm + transformers + factur-x + ...** (existing per ADR-007/008/010) — runtime deps already pulling matplotlib transitively.
- **CI scope per ADR-023** — `.github/workflows/ci.yml` runs `make lint` + `make typecheck` + `make test` only. NOT `make eda`. Rendering happens on the dev machine.

## Options considered

| # | Option | Pros | Cons | Verdict |
|---|---|---|---|---|
| 1 | **Quarto + Plotly + matplotlib/seaborn** (chosen) | Solves "HTML messy" via single rendered book + PDF; thesis-grade output by design (cross-refs, citations, page-numbers, figure captions); composes with existing `notebook-discipline` (renders `.py:percent` directly); widely used in 2025 academic publishing; ADR-walkable per `horus-decision-discipline`; PDF export is first-class | Adds 1 binary dep (Quarto CLI ~80 MB, `brew install quarto` on dev machine) + 2 Python deps (`plotly` + `seaborn`); CI does NOT render (rendering is dev-machine-only per ADR-023's lint+typecheck+test scope) | **Chosen** |
| 2 | jupytext + Plotly only (no Quarto), nbconvert HTML | Zero new tooling; works with existing pipeline | Many sibling HTML files persist; no auto-PDF; no cross-references; no thesis-grade format affordances; doesn't address user's stated "messy HTML" concern | Rejected — addresses none of the gap |
| 3 | Switch to marimo (reactive notebook) | Reproducible by design; replaces jupyter+jupytext+papermill+streamlit | Disrupts `notebook-discipline` mid-thesis (would require rule rewrite + L3 template update + retrofit of existing experiments); thesis-grade publication output less mature than Quarto's (page-numbering, citations, captions are not first-class); mid-thesis tooling change is risky | Rejected — disruption cost exceeds benefit at this phase; revisit at next-project-kickoff |
| 4 | Streamlit / Dash dashboard | Rich interactivity for exploration | Transient artifact (server-bound); not archival; not thesis-citable; PDF export requires manual screenshot pipeline | Rejected — wrong tool category for an archival deliverable |
| 5 | YData Profiling auto-report (`pandas-profiling` successor) | One-line tabular profile generation | Generic; not custom-narrative; not tuned to document-corpus EDA shape (designed for tabular CSV); zero control over thesis-appendix layout | Considered as a complement (not substitute); deferred — if useful for a quick first-pass, can be added in a follow-up ADR. NOT adopted in this ADR. |
| 6 | Pure matplotlib + nbconvert (no Plotly, no Quarto) | Zero new tooling; static-only is simpler | Loses interactive exploration affordance (hover-on-heatmap-shows-PDF-name); same nbconvert HTML-messy problem as Option 2 | Rejected — Plotly's interactivity is genuinely useful for the 16-field × N-PDF heatmap |

**Chosen: Option 1.** Reasons (in priority order):

1. **Directly addresses the user's stated concern** — single rendered HTML book + single PDF, not many sibling HTML files.
2. **Thesis-grade output is first-class** — cross-references, citations, page-numbers, figure captions, code-folding ship out-of-the-box with no custom rendering layer.
3. **Composes with `notebook-discipline`** — `.py:percent` stays source-of-truth; Quarto reads it directly via `quarto render`. No source format change.
4. **Hybrid-aesthetic feasible** — both static (matplotlib/seaborn for thesis figures) and interactive (Plotly for exploration) coexist in the HTML output; PDF gracefully drops interactivity.
5. **ADR-walkable supersession path** — if Quarto upstream becomes problematic, migration to a successor renderer is a pure tooling swap (source-of-truth doesn't change). This is the same supersession-discipline shape as ADR-007/008's dual-track choices.
6. **Marimo (Option 3) is genuinely compelling** — but adopting it now requires rewriting `notebook-discipline` and retrofitting existing experiments. The cost/benefit at this thesis phase doesn't pencil; revisit at next-project-kickoff.

## Decision + integration thoughts

### Dependency additions

- `pyproject.toml` `[project] dependencies` — add `plotly>=6.0,<7.0` and `seaborn>=0.13,<0.14`. matplotlib is already transitive (verified via `uv pip list`). Both are runtime deps (NOT dev-only) because experiment notebooks import them at execution time.
- Quarto CLI binary — installed on dev machine via `brew install quarto` (macOS, per `know-your-hardware`). Linux dev machines (none currently in scope) would use the official tarball. Pinned via `quarto --version` reproducibility check at the top of the EDA notebook (warning emitted if version <1.7).
- `pyproject.toml` `[tool.uv]` — no extras needed; Quarto detects the project Python via the `python3` resolver + `.python-version` (consistent with ADR-023's setup-uv pattern in CI; here it's just local).

### `make eda` Makefile target

```makefile
# Render an EDA notebook to HTML + PDF via Quarto.
# Source: experiments/<slug>.py (jupytext :percent)
# Outputs: experiments/<slug>.html + experiments/<slug>.pdf (gitignored)
# Requires: brew install quarto + uv sync
.PHONY: eda
eda:
	@if [ -z "$(NB)" ]; then echo "Usage: make eda NB=experiments/<slug>.py CFG=configs/<slug>.yaml"; exit 1; fi
	@if [ -z "$(CFG)" ]; then echo "Usage: make eda NB=experiments/<slug>.py CFG=configs/<slug>.yaml"; exit 1; fi
	@quarto --version >/dev/null 2>&1 || (echo "ERROR: Quarto CLI not found. Install via 'brew install quarto'."; exit 1)
	uv run quarto render $(NB) --to html --execute -P cfg_path:$(CFG)
	uv run quarto render $(NB) --to pdf  --execute -P cfg_path:$(CFG)
```

Quarto's `-P key:value` flag passes parameters into the Jupyter kernel as `cfg_path` per `https://quarto.org/docs/computations/parameters.html`, matching the `horus-config-discipline` "ONE papermill parameter `cfg_path`" contract.

### `_quarto.yml` project config

Lives at the repo root (Quarto project-level config). Minimal shape:

```yaml
project:
  type: default
  output-dir: experiments
  render:
    - "experiments/*.py"

format:
  html:
    theme: cosmo
    toc: true
    toc-depth: 3
    code-fold: true
    code-tools: true
    fig-format: svg
    fig-cap-location: bottom
  pdf:
    documentclass: scrartcl
    toc: true
    toc-depth: 3
    fig-cap-location: bottom
    fig-format: pdf

execute:
  echo: true
  warning: false
  freeze: auto
```

`freeze: auto` re-executes only when the `.py` source changes, matching the `notebook-discipline` "executed artifacts are transient" intent. The `cosmo` theme is Quarto's clean editorial default per Bootswatch; FT/NYT palette via per-cell matplotlib/seaborn configuration (NOT a global theme override).

### `.gitignore` additions

Per `notebook-discipline` (`*.executed.ipynb` already gitignored), extend to:

```gitignore
# Quarto build artifacts (per ADR-024)
experiments/*.html
experiments/*.pdf
experiments/.quarto/
/_freeze/
```

The `_freeze/` directory is Quarto's execution cache (per `freeze: auto`) — also a build artifact.

### Interaction with existing components

- **`notebook-discipline` (L3 rule)** — UNTOUCHED. Source-of-truth remains jupytext `.py:percent`. Quarto is a renderer alongside papermill, not a replacement. The rule's "Cascade-authored content is `.py` only" clause continues to apply: Quarto reads `.py` directly; we never author `.qmd`.
- **`horus-config-discipline` (L2 rule)** — UNTOUCHED. The `cfg_path` parameter contract holds; Quarto's `-P cfg_path:<path>` syntax delivers it.
- **ADR-016 (fast-dev config + adapter-iterate)** — UNAFFECTED. EDA notebook is not adapter-rescore work; the `dev_only` config-discipline tier separation is orthogonal.
- **ADR-023 (CI pipeline)** — UNAFFECTED. CI does NOT run `make eda`. CI runs lint+typecheck+test; rendering happens on dev machine. Rendered HTML/PDF are gitignored, so they don't appear in PRs.
- **`horus-source-archival` (L2 rule)** — APPLIED. This ADR ships 4 source-archival stubs (Quarto, Plotly, matplotlib, seaborn) per the rule's "every cited tool" clause.
- **Issue #46** — this ADR is the foundation for the EDA notebook authored as the next step. Issue #46 closes when the EDA artifact lands; this ADR closes the toolchain prerequisite.

### Reusability beyond the EDA notebook

The stack is **not specific to the ZUGFeRD EDA**. Any future thesis-grade artifact (e.g., results-chapter cross-model comparison, supervisor-meeting progress slide deck via Quarto's RevealJS format, methods-chapter pipeline diagram with computed parameters, weekly progress retros if formal output is wanted) can use the same `make eda` target. The pattern composes with the existing `make experiment` flow without conflict.

## Source archival

Per `horus-source-archival` (L2). Stubs authored alongside this ADR, live under `docs/sources/tools/`:

| Tool | Source | Stub path |
|---|---|---|
| Quarto | `https://quarto.org/` | `docs/sources/tools/quarto.md` |
| Plotly | `https://plotly.com/python/` | `docs/sources/tools/plotly.md` |
| matplotlib | `https://matplotlib.org/` | `docs/sources/tools/matplotlib.md` |
| seaborn | `https://seaborn.pydata.org/` | `docs/sources/tools/seaborn.md` |

Frontmatter format = Obsidian-clipper-compatible per ADR-002 (`source_url` / `source_title` / `source_author` / `retrieved_date` / `tags` / `archived_pdf` / `status`). Each stub carries 1–2 paragraphs of HORUS-relevance commentary citing this ADR.

## Supersession trigger

This ADR is superseded if any of the following hold:

1. **Quarto upstream becomes unmaintained** (Posit deprioritizes the project; release cadence stalls >6 months; CVE backlog accumulates) AND a clean alternative exists. Low-risk; Posit's commitment is structural (Quarto is core to RStudio's content-publishing positioning).
2. **Quarto's PDF rendering breaks for our specific needs** (LaTeX engine bugs that block thesis-quality output AND no clean Typst-engine workaround) AND a successor renderer ships with comparable cross-ref / citation / figure-caption affordances.
3. **`notebook-discipline` rewrites to marimo** (or another reactive notebook) — at that point `.py:percent` ceases to be the source-of-truth and Quarto's render-scripts path no longer applies. Triggers a new ADR for the visualization stack on the new substrate.
4. **Thesis-defense reproducibility requires CI-rendered EDA artifacts** (e.g., supervisor or thesis committee asks for an "official" rendered version that doesn't depend on the dev machine). Would require Quarto in the CI workflow + a new ADR amending ADR-023's CI scope. This is an evolution, not a supersession of THIS ADR; ADR-024 stays valid.
5. **A successor stack lands with materially better thesis-grade output** for our use case — at which point a new ADR-NNN would document the swap with a migration note here.

The substrate this ADR ratifies (jupytext source + Quarto renderer + Plotly interactive + matplotlib/seaborn static) is expected to remain stable through thesis defense (2026-08-25). Reassessment happens at the next thesis-grade-artifact authoring milestone or at any of the 5 triggers above.
