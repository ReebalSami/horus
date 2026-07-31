# ADR-055: Thesis Manuscript Authoring Setup

> **Note on numbering**: this record was authored as **ADR-054** on
> `feat/thesis-writing-setup` (2026-06-28). In parallel, `feat/structurer-finetune`
> independently claimed 054 for the thesis-endgame decision and landed on `main`
> first, so this record was renumbered to **055** when its branch rebased onto that
> merge. The renumber changed no substance. This is the post-hoc-renumber fallback
> prescribed by the ADR numbering protocol for concurrent-branch collisions.

|              |                                                                   |
| ------------ | ----------------------------------------------------------------- |
| **Status**   | Accepted (amended 2026-07-31 — see amendment below)               |
| **Date**     | 2026-06-28                                                        |
| **Deciders** | Reebal Sami (author); Cascade (`thesis-writing-setup`)            |
| **Milestone**| Thesis writing (`writeup` phase, `.windsurf/phases.yaml`)         |
| **Refs**     | ADR-054 (thesis endgame + scope freeze — governs what the manuscript may claim) |
| **Supersedes** | —                                                               |

## Context

Thesis writing begins. The manuscript needs a home, a document format, a
language, a reproducible build, and a disciplined way to pull experimental
results in from the repository. The decision is taken **now** (before drafting)
so structure and tooling do not churn mid-write.

The thesis frame is the locked **brainstorm v2** (three layers: extraction →
knowledge graph → analytical query; supervisor Prof. Dr. Dennis Säring;
pre-registered hypotheses H1–H6, H8). The legacy
`Master-Thesis/PLAN_THESIS.md` + `CLAUDE.md` describe a **superseded**
Donut/GraphRAG era and are explicitly NOT followed.

## Current-state survey

- **FH Wedel template** (`github.com/fh-wedel/thesis-template`): LaTeX,
  KOMA-Script `scrreprt`, `biblatex` + `biber` (alphabetic), German by default;
  ships a title page, statutory declaration, listings setup, and the FH logo.
- **Repo conventions**: all ADRs + docs are in English; Quarto is already used
  for the EDA book (ADR-024/025); TeX Live is installed locally (`latexmk`,
  `pdflatex`, `biber` on `PATH`); results live in MLflow + `eval/` reports +
  saved transcripts; held-out datasheet tooling exists (ADR-040).
- **Source archive**: `docs/sources/` already holds verified stubs for the core
  literature (berghaus-2025, cai-2025, han-2025, kim-2022-donut,
  huang-2022-layoutlmv3, ibm-2025-granite-docling, livathinos-2025-docling,
  poznanski-2025-olmocr2, kerr-1998-harking, gebru-2018-datasheets,
  zugferd-corpus, bstbk-2026-ki-faq).

## Options considered

### Location
1. **In-repo `thesis/`** (chosen) — manuscript co-located with code + results;
   figures/tables generated straight from the repo; single history.
2. Separate `Master-Thesis` repo — clean separation but constant cross-repo
   friction syncing results into prose; rejected.
3. New standalone repo — same friction as (2) plus a fresh history; rejected.

### Format
1. **LaTeX via the FH template** (chosen) — institution-blessed layout, precise
   typography, `\input`-able generated tables; the expected format for an FH
   Wedel thesis.
2. Quarto → PDF — already in the repo, but reproducing the FH template's exact
   layout in Quarto is wasted effort; rejected as the manuscript format (Quarto
   stays for the EDA book).
3. Quarto draft + LaTeX final — double-maintenance; rejected.

### Language
1. **English** (chosen) — matches the entire repo (ADRs, code, docs), the
   literature, and broadens readership; FH Wedel permits English theses. German
   legal terms kept inline (babel `ngerman` secondary).
2. German — closer to the audience's daily language but diverges from the repo
   and the field's vocabulary; rejected. A German `Kurzfassung` alongside the
   English abstract is left as an open option.

### Build tooling
1. **`latexmk` (pdflatex + biber)** (chosen) — standard; handles the multi-pass
   + biber dependency automatically; wrapped as `make thesis`.
2. `tectonic` — single-binary, but not installed and adds a toolchain dependency
   where TeX Live already works; rejected.
3. Manual `pdflatex` / `biber` invocations — error-prone; rejected.

### Results integration
1. **Generated assets** (chosen) — figures exported to `thesis/figures/` (PDF)
   and tables to `thesis/tables/` (`.tex`, `\input`); numbers never hand-copied.
   The generation pipeline is wired as results land.
2. Hand-copied numbers — rejected outright (drift + transcription error +
   non-reproducible; violates `make-sure-it-works`).

## Decision + integration thoughts

Adopt the FH Wedel LaTeX template **adapted to English** under a new top-level
**`thesis/`** directory, built with **`latexmk`** via **`make thesis`** →
`thesis/_build/main.pdf`.

- **Layout**: `thesis/main.tex` orchestrates; `preamble/` (header, title page,
  declaration, acronyms), `chapters/` (`00`–`10`), `appendix/`, `references.bib`,
  `latexmkrc`, `images/` (FH logo), `figures/` + `tables/` (generated).
- **Adaptations from the template**: babel `main=english,ngerman`; `lmodern`
  (was `ae`); listings trimmed to python/json; `\graphicspath` → `images/` +
  `figures/`; `\addbibresource{references.bib}`.
- **Declaration**: adds the mandatory **AI-disclosure clause** (current FH Wedel
  Richtlinie) — the upstream template predates it; AI-tool usage also gets a
  dedicated appendix.
- **Build containment**: `latexmkrc` sets `out_dir=_build` and pre-creates
  `_build/{preamble,chapters,appendix}` (latexmk + `-output-directory` does not
  auto-create `\include` subdirs). `.gitignore` excludes `thesis/_build/`;
  `make thesis-clean` wipes it.
- **Chapter structure** mirrors brainstorm v2: ch.1–4 (intro / background /
  related-work / methodology) drafted from existing research + ADRs; ch.5
  (extraction) is the deepest-built layer (partial); ch.6–7 (KG / query) are
  scaffolds pending that work; ch.8 (system) partial; ch.9–10 stubbed.
  **→ superseded by the 2026-07-31 amendment below** (ADR-054's scope freeze
  removed the KG / query work from thesis scope, so those chapters can never be
  filled).
- **`thesis/` as a new top-level dir** invokes the `clean-project-structure`
  ADR-exception (a new top-level path requires an ADR) — this ADR is that record.
- **Citations**: `references.bib` keys are backed by existing `docs/sources/`
  stubs; bib metadata is reconciled against those verified stubs during the
  writeup wave (entries currently flagged `approx.`).

## Source archival

Per `horus-source-archival`, the institutional sources this ADR cites:

- **FH Wedel thesis template** → `docs/sources/tools/fh-wedel-thesis-template.md`
  (stub).
- **FH Wedel thesis Richtlinie / Leitfaden (incl. AI-disclosure requirement)** →
  `docs/sources/legal/fh-wedel-thesis-richtlinie.md` (stub).
- LaTeX build toolchain (`latexmk`, `biblatex` / `biber`, KOMA-Script) —
  ubiquitous build tooling; cited inline by canonical URL and treated like
  `make` / `git` (no per-tool stub), consistent with repo practice.
- Literature cited in `references.bib` — already archived under
  `docs/sources/{papers,datasets,legal}/`.

## Supersession trigger

Revisit if: FH Wedel mandates a specific template version incompatible with this
setup; the supervisor requires German as the manuscript language; the build
moves to CI (a `thesis` CI job would *extend*, not supersede, this ADR); or the
manuscript outgrows a single-repo layout.

## Consequences

- **+** One source of truth; results flow repo → prose without copy; reproducible
  `make thesis`; institution-correct layout; English consistency; AI-disclosure
  compliant.
- **−** A new top-level dir; contributors need TeX Live/MacTeX for `make thesis`
  (documented; not required for the Python toolchain); bib metadata needs a
  verification pass before submission.
- **Neutral**: Quarto remains for the EDA book; the two coexist.

---

## Amendment 2026-07-31 — scope-freeze alignment + formal-compliance corrections

**Status**: amendment to the *Decision* section's chapter-structure bullet and to
the formal front/back-matter. Supplements; the location / format / language /
build-tooling / results-integration decisions above are unchanged and stay in force.

**Trigger**: ADR-054 (authored after this record, landed first) froze thesis scope
to Layer 1 — the knowledge-graph and analytical-query layers, the cloud comparison
arm, and template-shift move to future work. The June chapter skeleton was built
*before* that freeze and therefore carried two chapters ("Knowledge Graph",
"Analytical Query") that can never be filled, plus a research question spanning all
three layers. Reviewing the manuscript against the FH Wedel Richtlinie in the same
pass surfaced three further formal defects.

### 1. Chapter map reshaped to the frozen scope

The three-layer vision is retained as a **System Design** chapter (it motivates the
architecture and is honest: this was the design, and the foundation layer was built
and evaluated properly), while the unbuilt layers move into a substantial
**Limitations and Future Work** chapter. No empty chapters remain.

| # | Chapter | Source |
|---|---|---|
| 1 | Introduction | rewritten (softened legal framing, OCR-free naming note, honest hypothesis reporting) |
| 2 | Background | June scaffold |
| 3 | Related Work | June scaffold + `docs/sources/papers/` |
| 4 | System Design | **new** — three-layer architecture; Layer 1 in depth; Layers 2–3 as design-only with an explicit not-evaluated statement |
| 5 | Methodology | June `04-methodology` |
| 6 | Results | June `05-extraction`, widened to the full Layer-1 result set |
| 7 | Implementation and Prototype | June `08-system` |
| 8 | Discussion | June `09-discussion` |
| 9 | Limitations and Future Work | **new** — absorbs June `06-knowledge-graph` + `07-query` + ADR-054's descoped list |
| 10 | Conclusion | June `10-conclusion` |

### 2. Part order corrected to the Richtlinie

The June `main.tex` placed the abstract **before** the table of contents. The
Richtlinie fixes the order as: cover → (confidentiality note) → contents → list of
figures → list of tables → list of abbreviations → body → appendix → bibliography →
statutory declaration. The abstract is the first body element, so it now follows the
abbreviations list. Side benefit: `\ac{}` acronym macros are legal in the abstract
again (the June workaround of spelling terms out is removed).

### 3. Statutory declaration replaced with the verbatim required wording

The June text paraphrased the AI-disclosure requirement in a separate paragraph. The
Richtlinie prescribes one sentence with the AI clause **inline**; that exact wording
(plus the template's "not previously submitted / not published" sentence) is now
used verbatim. The appendix continues to document the extent of AI-tool use.

### 4. Personal data on the title page

Decided with the author (2026-07-31): the author's name, **Matriculation number**,
and the **examiners' names** are committed normally — the repo is public but none of
this is sensitive, and the May redaction of the supervisor's surname applied to
repo prose, not to a title page that must legally carry it. **No postal address
appears in the manuscript at all** (added by hand before printing only if an
examiner requires it). No git-ignored private-include mechanism is introduced —
rejected as unnecessary machinery for two public-by-nature values.

### 5. Writing-model note (non-binding, operational)

Chapter drafting runs on **Claude Opus 5 at high/xhigh reasoning effort** (released
2026-07-24: Fable-5-class intelligence at half the token price, and the current
leader on independent agentic-knowledge-work benchmarks, which is the closest public
proxy for long-horizon document authoring). Planning / decision sessions stay on the
session's own model. Recorded for reproducibility of the authoring process, not as a
technical dependency — the manuscript is plain LaTeX with no model in its build path.
