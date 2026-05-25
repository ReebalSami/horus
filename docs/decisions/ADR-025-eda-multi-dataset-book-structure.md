# ADR-025 — EDA scope expansion: multi-dataset Quarto Book + Datasheets-for-Datasets template

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-25 |
| **Milestone** | Issue #46 EDA on full data corpus (experiment phase, ADR-024 extension) |
| **Authored by** | Cascade D EDA-expansion session, plan `~/.windsurf/plans/eda-full-corpus-ed5d97.md` |
| **Extends** | ADR-024 (EDA visualization stack) — visualization-stack decisions inherited verbatim |
| **Supersession trigger** | See `## Supersession trigger` below |

## Context

ADR-024 ratified the visualization stack (Quarto + Plotly + matplotlib/seaborn) for a single-dataset EDA on the 151-PDF ZUGFeRD German corpus. The notebook authored under that ADR — `experiments/eda-zugferd.py` — surfaced a scope gap during user review on 2026-05-25:

> *"What about all the data we downloaded before like when I look at `data/raw/` I see English Korean multi language are they all empty?"* (user, conversation 2026-05-25)

Honest audit of `data/raw/` confirmed the gap: HORUS has **7 datasets totaling ~12,000 documents** on disk, all with full data and verified MANIFESTs:

| Slug | Language | Size | What it is |
|---|---|---|---|
| `zugferd-corpus` | German | 145 MB / 250 files | ZUGFeRD/Factur-X/XRechnung sample corpus (151 PDFs + 88 sidecar XMLs); the only one ADR-024 covers |
| `fatura2-invoices` | English | 343 MB / 4 files | ~10K invoice images with field labels (HF mathieu1256/FATURA2-invoices, CC-BY-4.0) |
| `funsd` | English | 28 MB / 401 files | 200 form/document scans with hand-annotated tokens + bboxes (FUNSD, non-commercial research) |
| `inv-cdip-tobacco` | English | 2 MB / 362 files | 350 tobacco-industry invoice annotations only (Salesforce inv-cdip, CC-BY-NC-4.0; underlying scans intentionally not downloaded per sub-issue #28) |
| `parsee-ai-invoices-example` | English | 46 KB / 3 files | 45 invoice rows in a parquet (HF parsee-ai/invoices-example, MIT) |
| `cord-v2` | Korean | 2.3 GB / 9 files | Korean receipts (HF naver-clova-ix/cord-v2, CC-BY-4.0); 6 parquet files (test + train + validation) |
| `omnidocbench` | Multilingual | 1.5 GB / 1659 files | Mixed document benchmark — invoices + papers + books with OmniDocBench JSON annotations (HF opendatalab/OmniDocBench, custom non-commercial-research license) |

The EDA notebook authored under ADR-024 looks at **1 of 7 datasets**. The user's stated thesis claim — *"VLM-based invoice understanding for tax advisors"* (per `AGENTS.md` top-level definition) — requires characterizing the full data substrate, not just the German subset, because:

1. **The thesis claim is multi-format / multi-standard / multi-language.** A VLM that only handles the modern Factur-X v2 standard would replicate what existing parser libraries already do; the thesis adds value precisely by handling old formats (ZUGFeRDv1 from 2014), photos / scans, weird formats, real consumer invoices.
2. **Cross-dataset comparisons are load-bearing for thesis methodology.** Dataset breadth (which formats? which annotation schemas? which licenses permit which downstream uses?) is a research-design input, not an implementation detail.
3. **The Datasheets-for-Datasets standard (Gebru et al. 2018, arxiv:1803.09010) is the academic gold standard** for documenting datasets used in ML research. Adopting it now (mid-thesis) is cheaper than retrofitting it later (post-defense).
4. **Single-dataset EDA artifacts don't compose** into a thesis appendix. A multi-chapter Book composes naturally; navigation, cross-references, and scope are first-class.

The gap is real: the EDA artifact intended to land in the thesis appendix needs to characterize the **full data substrate**, not just one dataset, with **academically-sound per-dataset documentation**. The structural expansion this ADR ratifies closes that gap without changing the visualization-stack decisions ratified by ADR-024.

## Decision

Expand the EDA artifact from a single-dataset notebook into a **multi-chapter Quarto Book** covering all 7 datasets in `data/raw/`, structured per Quarto's official Book conventions and adopting the **Datasheets-for-Datasets template (Gebru et al. 2018)** for per-dataset documentation. Specifically:

1. **Quarto Book structure** per `https://quarto.org/docs/books/` — `_quarto.yml` extended with `book:` section + chapter list; `index.qmd` (preface) + chapter-per-dataset (`experiments/0X-<slug>.py`) + cross-corpus synthesis chapter (`experiments/08-cross-corpus.py`) + consolidated Datasheets appendix (`experiments/A1-datasheets.qmd`) + bibliography (`experiments/references.qmd`). HTML output is a navigable book at `_book/index.html`; PDF output is a single archived deliverable at `_book/Horus-EDA.pdf`.

2. **Datasheets-for-Datasets template (Gebru et al. 2018)** — every chapter ends with a Datasheet appendix entry covering Gebru's seven canonical sections: Motivation / Composition / Collection process / Preprocessing & cleaning & labeling / Uses / Distribution / Maintenance. The 50+ canonical questions Gebru proposes are answered for each dataset where they apply (with explicit "N/A — see <reason>" for those that don't).

3. **One YAML config per chapter** per `horus-config-discipline` (L2 rule already in force for `eda-zugferd.yaml`). Each chapter's HARKing safeguards (pre-committed thresholds, descriptive-only scope, hypothesis-shaped patterns routed to an Exploratory Observations log) are baked into its YAML before the EDA runs. No "global EDA config" — chapters are independent.

4. **Shared helpers extracted to `src/horus/eda/`** — corpus walking, figure styling, Datasheet rendering, and per-dataset loaders live in a Python package, not inline in notebooks. Per-dataset loaders share a uniform interface: `walk(cfg) → DataFrame` + dataset-specific helpers. Chapter notebooks contain narrative + cells that call into this package; they do not contain library code.

5. **Local-only rendering during iteration.** `make eda-book` renders the full book to `_book/`; user views via `file://` URL. GitHub Pages deployment deferred to a separate ADR + commit once the Book passes end-to-end review (NOT part of this ADR's scope).

### Source-of-truth flow (ADR-024 inherited; chapter dimension new)

| Stage | Tool | Source | Output | Tracked in git? |
|---|---|---|---|---|
| 1. Author chapter | jupytext (existing) | `.py:percent` editor | `experiments/0X-<slug>.py` | YES (source-of-truth) |
| 2. Author chapter config | YAML editor | `configs/eda-<slug>.yaml` | YES (source-of-truth) | YES |
| 3. Render single chapter | Quarto `make eda` (existing) | `.py:percent` source | `experiments/<slug>.html` + `.pdf` | NO (build artifact, gitignored) |
| 4. Render whole Book | Quarto `make eda-book` (NEW) | `_quarto.yml` book + chapters | `_book/index.html` + `_book/Horus-EDA.pdf` | NO (build artifact, gitignored) |

Both targets coexist: `make eda` is for fast single-chapter iteration; `make eda-book` is for the full Book render.

### Chapter ordering (most-thesis-relevant first)

| # | Chapter | File | Rationale |
|---|---|---|---|
| 0 | Index / preface | `experiments/00-index.qmd` | Scope statement, methodology overview, navigation |
| 1 | ZUGFeRD German corpus | `experiments/01-zugferd.py` | Refactored from `experiments/eda-zugferd.py`; thesis primary substrate |
| 2 | fatura2-invoices | `experiments/02-fatura2.py` | Largest invoice dataset (~10K English with field labels); CC-BY-4.0 |
| 3 | OmniDocBench | `experiments/03-omnidocbench.py` | Broadest format coverage (1659 docs incl. invoices, multi-language); license caveat |
| 4 | FUNSD | `experiments/04-funsd.py` | Small but well-annotated; field-extraction relevance |
| 5 | parsee-ai | `experiments/05-parsee-ai.py` | MIT-licensed comparator; smallest |
| 6 | CORD-v2 | `experiments/06-cord-v2.py` | Korean receipts; OCR-route generality; lower thesis relevance |
| 7 | inv-cdip-tobacco | `experiments/07-inv-cdip-tobacco.py` | Annotations-only (no scans); annotation-schema characterization |
| 8 | Cross-corpus synthesis | `experiments/08-cross-corpus.py` | Master comparison table + decision register (observations only; NOT scope decisions) |
| A1 | Datasheets appendix | `experiments/A1-datasheets.qmd` | Consolidated per-dataset Datasheets-for-Datasets entries |
| Refs | References | `experiments/references.qmd` | Bibliography |

### Per-chapter content template (consistent across all 7 dataset chapters)

1. **§1 — Provenance** (Datasheets §3.1 Motivation): origin, license, retrieval recipe, MANIFEST verification.
2. **§2 — Composition** (Datasheets §3.2): file count, format breakdown, size-on-disk, language, label/annotation type, schema.
3. **§3 — Sample inspection** (Datasheets §3.3): random-sample load + visual; verify `sample_load_passed` claim from MANIFEST holds.
4. **§4 — Distributional properties** (dataset-specific): field-presence rates, value distributions, anomalies, edge cases.
5. **§5 — HORUS-relevance assessment** (NEW; thesis-specific): which thesis evaluation paths can use this dataset (VLM extraction / OCR comparator / fine-tuning training-pool / methodology breadth only / out-of-scope) — descriptive only, NO scope decisions.
6. **§6 — Anomalies & limitations**: license caveats, schema gaps, mislabeled files, missing-by-design subsets.
7. **§7 — Exploratory observations log**: hypothesis-shaped patterns surfaced during inspection, captured per `bidirectional-learning-pipe`.

## Current-state survey

Dated 2026-05-25. Sources consulted via `read_file` of every dataset's MANIFEST.md + README.md, web search for Datasheets-for-Datasets canonical reference, Quarto Books official documentation, and inspection of the existing `eda-zugferd.py` notebook structure.

- **Gebru et al. 2018, *Datasheets for Datasets*** (`https://arxiv.org/abs/1803.09010`, retrieved 2026-05-25) — peer-reviewed paper proposing standardized dataset documentation; widely cited (>3000 citations as of 2025); adopted by major ML conferences (NeurIPS Datasets and Benchmarks Track requires Datasheet-style documentation). Seven canonical sections (Motivation / Composition / Collection / Preprocessing / Uses / Distribution / Maintenance) and ~50 questions per section. Original PDF preserved at `https://arxiv.org/pdf/1803.09010`. Microsoft Research mirror: `https://www.microsoft.com/en-us/research/wp-content/uploads/2019/01/1803.09010.pdf`. License: arXiv standard (perpetual, irrevocable license to distribute).
- **Quarto Books v1.9** (`https://quarto.org/docs/books/`, retrieved 2026-05-25) — multi-chapter scientific report structure inherited from Pandoc + bookdown lineage. `_quarto.yml` `book:` section + chapter list + reference list. Cross-references between chapters are first-class (`@sec-name` resolves across files). HTML output is a navigable book with TOC + chapter numbers + sidebar; PDF output is one archived document. `index.qmd` is required (HTML home page); `references.qmd` conventionally holds the bibliography.
- **Existing `eda-zugferd.py`** (HORUS, on disk 2026-05-25) — 1647-line jupytext `.py:percent` notebook covering 9 sections (corpus walk + per-flavor coverage + page distribution + profile detection + 16-field presence + value distributions + complexity tiers + locale + anomalies + sufficiency report + observations log). Contains substantial inline helper code (filename profile detection, complexity tier assignment, ZUGFeRDv1 namespace detection); refactor target for Phase B of the implementation plan.
- **HORUS dataset MANIFESTs** (`data/raw/<lang>/<slug>/MANIFEST.md`, all 7 verified 2026-05-25 via `read_file`) — every dataset has Obsidian-clipper-compatible frontmatter (slug / language / source_url / license_spdx / commit_sha / file_count / total_bytes / sha256_aggregate / sample_load_passed / acquisition_status). All 7 are `acquisition_status: completed`; all 7 have `sample_load_passed: true` (verified by Cascade D during M2D.5 step 3, issue #12).
- **No prior multi-dataset EDA precedent in HORUS** — issue #46 was originally scoped single-dataset (ZUGFeRD only); ADR-024 inherited that scope. The user's 2026-05-25 feedback (*"this is the whole point of EDA — I want to know everything about the data"*) is the explicit scope-expansion mandate ratified by this ADR.

### Existing HORUS toolchain anchors (all inherited from ADR-024 unchanged)

- **jupytext** — `.py:percent` source-of-truth per `notebook-discipline` L3.
- **Quarto CLI** — installed via `brew install quarto` on dev machine; CI does NOT render per ADR-023's scope.
- **Plotly + matplotlib + seaborn** — visualization stack per ADR-024.
- **Pydantic + PyYAML** — `horus-config-discipline` per ADR-004; `EDAConfig` Pydantic schema in `src/horus/config.py` already validated.
- **CI scope per ADR-023** — `make lint` + `make typecheck` + `make test` only; rendering happens locally.

## Options considered

| # | Option | Pros | Cons | Verdict |
|---|---|---|---|---|
| 1 | **Quarto Book + Datasheets-for-Datasets template** (chosen) | Academic gold standard for dataset documentation; Quarto Books are designed for multi-chapter scientific reports; cross-references between chapters are first-class; modular per-chapter rendering enables fast iteration; composes with existing `notebook-discipline` + `horus-config-discipline`; thesis-grade output by design | Adds 1 cross-cutting refactor (extract helpers from existing notebook into `src/horus/eda/`) + 6 new chapter notebooks + 6 new YAML configs + 6 new loader modules + tests; substantial work | **Chosen** |
| 2 | Single mega-notebook with 7 sequential top-level sections | Simplest navigation (one HTML page); no Book scaffold required | Current notebook is already 1647 lines; adding 6 more datasets at similar depth → ~10K-line monster; hard to maintain, hard to navigate, hard to render incrementally (Quarto's `freeze: auto` is per-document); violates `clean-project-structure` | Rejected — coding-debt magnet |
| 3 | Phased — Book skeleton + 1 priority chapter now, others deferred | Smallest cognitive load per step | Leaves the Book partially-populated mid-thesis; user explicitly stated *"no partial knowledge anymore"* (2026-05-25); deferred chapters become "I'll get to it" debt | Rejected — partial knowledge |
| 4 | Separate standalone EDA notebooks per dataset (no Book) | No Book scaffold; each notebook is independent | No cross-references between datasets; no master comparison view; navigation across artifacts is manual; loses the synthesis chapter that ties findings together | Rejected — sacrifices the cross-corpus comparison that's the whole point of expanding scope |
| 5 | Datasheet-only documentation (no notebooks) | Cheapest; just markdown files | Datasheets answer composition questions but don't produce distributional plots / value-frequency tables / anomaly detection; the EDA's purpose is not just to describe statically but to characterize empirically | Rejected — doesn't replace EDA, it complements it |
| 6 | YData Profiling auto-reports per dataset | One-line tabular profile generation | Designed for tabular CSV; not tuned to document-corpus shape (PDFs / images / annotations); not customizable to the HORUS-relevance §5 framing | Rejected as substitute (same as ADR-024 Option 5); deferred as optional complement if useful for a quick first-pass on a tabular-shape dataset |

**Chosen: Option 1.** Reasons (in priority order):

1. **Adopts the academic standard for dataset documentation** (Datasheets-for-Datasets). Thesis defense quality bar.
2. **Native multi-chapter structure** via Quarto Books — cross-references, master TOC, chapter numbering, navigable HTML book + single archived PDF.
3. **Composes with existing rules** — `notebook-discipline` (jupytext source), `horus-config-discipline` (one YAML per chapter), `clean-project-structure` (helpers in `src/`, narrative in `experiments/`).
4. **Modular iteration** — one chapter at a time; render single-chapter via existing `make eda` for fast feedback; full Book via new `make eda-book` for review milestones.
5. **No partial knowledge** — covers all 7 datasets; the user's explicit mandate.
6. **Refactor cost is one-time** — Phase B of the implementation plan extracts shared helpers from the existing notebook into `src/horus/eda/`; subsequent chapters reuse the extracted helpers without modification.

## Decision + integration thoughts

### Filesystem changes (atomic; verifiable)

| Path | Action | Tracking |
|---|---|---|
| `_quarto.yml` | Extend with `book:` section + chapter list (currently has `format:` only) | git tracked |
| `experiments/00-index.qmd` | NEW — preface, scope, methodology overview, TOC preview | git tracked |
| `experiments/01-zugferd.py` | RENAME from `experiments/eda-zugferd.py` (Phase B) | git tracked |
| `experiments/02-fatura2.py` | NEW (Phase C) | git tracked |
| `experiments/03-omnidocbench.py` | NEW (Phase C) | git tracked |
| `experiments/04-funsd.py` | NEW (Phase C) | git tracked |
| `experiments/05-parsee-ai.py` | NEW (Phase C) | git tracked |
| `experiments/06-cord-v2.py` | NEW (Phase C) | git tracked |
| `experiments/07-inv-cdip-tobacco.py` | NEW (Phase C) | git tracked |
| `experiments/08-cross-corpus.py` | NEW (Phase D) — master comparison + decision register | git tracked |
| `experiments/A1-datasheets.qmd` | NEW — consolidated Datasheets appendix (one section per dataset) | git tracked |
| `experiments/references.qmd` | NEW — bibliography | git tracked |
| `configs/eda-<slug>.yaml` × 6 | NEW (one per dataset added in Phase C) | git tracked |
| `src/horus/eda/__init__.py` | NEW — package marker | git tracked |
| `src/horus/eda/corpus_walk.py` | NEW — shared file-walking helpers | git tracked |
| `src/horus/eda/figures.py` | NEW — shared palette + figure-styling helpers | git tracked |
| `src/horus/eda/datasheet.py` | NEW — Datasheet-template renderer (Gebru §3 schema) | git tracked |
| `src/horus/eda/<slug>_loader.py` × 7 | NEW (one per dataset; ZUGFeRD extracted from existing notebook in Phase B) | git tracked |
| `tests/test_eda_<slug>_loader.py` × 7 | NEW (one per loader) | git tracked |
| `_book/` | NEW build-artifact directory | gitignored |
| `_freeze/` | already gitignored per ADR-024 | gitignored |
| `Makefile` | Add `make eda-book` target alongside existing `make eda` | git tracked |
| `docs/sources/methodology/datasheets-for-datasets.md` | NEW — Gebru et al. 2018 source archival per `horus-source-archival` | git tracked |
| `docs/sources/tools/quarto-books.md` | NEW — Quarto Books docs source archival | git tracked |

### `_quarto.yml` extension

The existing `_quarto.yml` (per ADR-024) is extended with a `book:` section. The `format:` block stays intact:

```yaml
project:
  type: book

book:
  title: "HORUS — Exploratory Data Analysis"
  subtitle: "Multi-dataset characterization of the HORUS thesis substrate"
  author: "Reebal Sami"
  date: today
  date-format: iso
  chapters:
    - experiments/00-index.qmd
    - experiments/01-zugferd.py
    - experiments/02-fatura2.py
    - experiments/03-omnidocbench.py
    - experiments/04-funsd.py
    - experiments/05-parsee-ai.py
    - experiments/06-cord-v2.py
    - experiments/07-inv-cdip-tobacco.py
    - experiments/08-cross-corpus.py
  appendices:
    - experiments/A1-datasheets.qmd
  references: experiments/references.qmd

# format: block (unchanged from ADR-024)
```

The `project.type: default` of ADR-024 changes to `project.type: book` (Quarto's required value for Book projects).

### `make eda-book` Makefile target

```makefile
.PHONY: eda-book
eda-book:
	@quarto --version >/dev/null 2>&1 || (echo "ERROR: Quarto CLI not found. Install via 'brew install quarto'."; exit 1)
	uv run quarto render
	@echo "Rendered: _book/index.html (open via file://$(PWD)/_book/index.html)"
	@echo "Rendered: _book/Horus-EDA.pdf"
```

`uv run quarto render` (no path argument) renders the entire Book project per `_quarto.yml`. The existing `make eda NB=... CFG=...` target (single-chapter render) stays untouched for fast iteration.

### `src/horus/eda/` package shape

```
src/horus/eda/
├── __init__.py           # package marker
├── corpus_walk.py        # walk(root, exclude_patterns) → DataFrame; shared dotfile filter
├── figures.py            # apply_palette(), editorial_style(), interactive_default()
├── datasheet.py          # Datasheet pydantic model + render_to_qmd()
├── zugferd_loader.py     # ZUGFeRD-specific (extracted from current notebook)
├── fatura2_loader.py     # parquet reader + label-schema unpacker
├── omnidocbench_loader.py  # JSON annotation reader + multi-format walker
├── funsd_loader.py       # PNG + JSON pair loader
├── parsee_ai_loader.py   # parquet reader
├── cord_v2_loader.py     # parquet reader (test/train/validation splits)
└── inv_cdip_loader.py    # JSON annotation reader (no underlying scans)
```

Each loader exposes a uniform interface:

```python
def walk(cfg: EDAConfig) -> pd.DataFrame: ...
def load_annotations(row: pd.Series) -> dict: ...
def schema_summary() -> dict: ...
```

Chapters call into these loaders; loaders are tested independently.

### Per-chapter `EDAConfig` Pydantic schema

The existing `EDAConfig` (per ADR-024 + ADR-004) is dataset-agnostic at its root (corpus_root + output_dir + page_count_bins + palette_static + palette_interactive + figure_dpi + complexity + fine_tuning_anchors + expected_min_pdfs + ground_truth_required). Most fields apply uniformly; some (e.g., `complexity`, `ground_truth_required`, `page_count_bins`) are specific to PDF-shaped corpora and don't apply to receipt-shaped (CORD-v2) or annotation-only (inv-cdip-tobacco) datasets.

Phase B of the implementation plan revisits the schema:

- **Stays at root**: `corpus_root`, `output_dir`, `palette_static`, `palette_interactive`, `figure_dpi`, `expected_min_pdfs` (with sensible per-chapter override).
- **Becomes optional / per-chapter**: `complexity`, `ground_truth_required`, `page_count_bins` — applicable only when the chapter's data shape supports them.
- **New per-chapter additions** (where needed): `expected_format_breakdown` (e.g., for OmniDocBench's mixed-format reality), `annotation_schema_version` (e.g., for FUNSD vs inv-cdip-tobacco field-key conventions).

The schema additions are small and stay backward-compatible with `eda-zugferd.yaml`. Tests cover each chapter's config independently.

### HARKing safeguards (inherited; per chapter)

Per ADR-024 + brainstorm v2 §2 + plan §5, every chapter's YAML pre-commits any thresholds the chapter uses BEFORE the EDA runs. Hypothesis-shaped patterns surfaced during inspection go to that chapter's `## §7 — Exploratory observations log` (per `bidirectional-learning-pipe`), NOT into H1–H6.

### Interaction with existing components

- **`notebook-discipline` (L3 rule)** — UNTOUCHED. Source-of-truth remains jupytext `.py:percent` for chapter notebooks. `.qmd` files are used only for index / appendix / references where there's no executable code. Cascade-authored content in chapter notebooks is `.py` only.
- **`horus-config-discipline` (L2 rule)** — UNTOUCHED. The `cfg_path` parameter contract holds per chapter. Each chapter loads its config via `EDAConfig.from_yaml(cfg_path)` at the top.
- **`clean-project-structure` (L1 rule)** — STRENGTHENED. Library code in `src/horus/eda/`; narrative in `experiments/0X-<slug>.py`; configs in `configs/eda-<slug>.yaml`; build artifacts in `_book/` (gitignored). No inline library code in notebooks.
- **`horus-decision-discipline` (L2 rule)** — APPLIED. This ADR follows the 5 mandatory sections (Current-state survey / Options considered / Decision + integration thoughts / Source archival / Supersession trigger).
- **`horus-source-archival` (L2 rule)** — APPLIED. Two new source stubs (Gebru 2018 + Quarto Books).
- **ADR-024** — EXTENDED, not superseded. The visualization-stack decisions (Quarto + Plotly + matplotlib/seaborn) are inherited verbatim. ADR-024 stays valid; its `## Status` row in the INDEX is annotated *"extended by ADR-025"* (per ADR-011 supersession-over-deletion: extension is a forward link, not a replacement).
- **ADR-023 (CI pipeline)** — UNAFFECTED. CI does NOT run `make eda` or `make eda-book`. Rendering happens locally; rendered HTML/PDF are gitignored.
- **Issue #46** — this ADR closes the toolchain prerequisite for the expanded EDA. Issue #46's acceptance criteria (per the original issue body) get reinterpreted under the expanded scope; final closure happens in Phase E.

### Reusability beyond this work

The Quarto Book + Datasheets template is **not specific to this EDA**. Any future thesis-grade multi-dataset artifact (e.g., results-chapter cross-model comparison, methodology-chapter dataset audit, supervisor-meeting Book) can use the same scaffold. The pattern composes with the existing single-notebook `make eda` flow without conflict.

## Source archival

Per `horus-source-archival` (L2) + ADR-002 source-archival taxonomy (`papers/` / `tools/` / `datasets/` / `legal/`):

| Source | Stub path | Action |
|---|---|---|
| Gebru et al. 2018, *Datasheets for Datasets* (arxiv:1803.09010) | `docs/sources/papers/gebru-2018-datasheets-for-datasets.md` | NEW stub |
| Quarto Books format documentation (`https://quarto.org/docs/books/`) | `docs/sources/tools/quarto.md` | EXTEND existing stub with `## Books format details (ADR-025)` section (one-stub-per-tool convention; no separate `quarto-books.md`) |

Frontmatter format = Obsidian-clipper-compatible per ADR-002 (`source_url` / `source_title` / `source_author` / `retrieved_date` / `tags` / `archived_pdf` / `status`). Each stub carries 1–2 paragraphs of HORUS-relevance commentary citing this ADR.

The 7 dataset stubs at `docs/sources/datasets/<slug>.md` (already authored at M2D.5 step 3, issue #12 closure) are the inputs to per-chapter §1 Provenance sections; no new stubs needed there.

## Supersession trigger

This ADR is superseded if any of the following hold:

1. **Datasheets-for-Datasets is replaced by a newer academic standard** (e.g., the OECD "AI Data Cards" or Hugging Face Hub "Dataset Cards" supersede Gebru 2018 in mainstream ML publication norms) AND HORUS thesis defense expects the newer standard. Low-risk in 2026; Datasheets remain canonical.
2. **Quarto Books deprecate or break for our use case** (e.g., LaTeX rendering breaks for the multi-chapter PDF AND no Typst-engine workaround) AND a successor renderer ships with comparable Book affordances. Migration is a tooling swap; the Book content (chapters, configs, loaders) survives.
3. **Scope contracts** (e.g., user decides to drop one or more datasets from scope) — that's an evolution, not supersession; the chapter is removed from `_quarto.yml` and its files archived per ADR-011 supersession-over-deletion. ADR-025 stays valid.
4. **Scope expands further** (e.g., user adds an 8th dataset, or the Belege chapter joins the public Book post-redaction) — that's an evolution; the new chapter is added per the established template. ADR-025 stays valid.
5. **A successor pattern lands** (e.g., a fully reactive notebook system replaces jupytext + Quarto entirely, per ADR-024 supersession trigger #3) — at that point the Book content survives but the rendering substrate changes. New ADR documents the migration.

The substrate this ADR ratifies (Quarto Book + Datasheets template + per-chapter YAML + `src/horus/eda/` package) is expected to remain stable through thesis defense (2026-08-25). Reassessment happens at the next major data-substrate change (e.g., Belege chapter inclusion) or at any of the 5 triggers above.
