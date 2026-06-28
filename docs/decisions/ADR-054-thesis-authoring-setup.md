# ADR-054: Thesis Manuscript Authoring Setup

|              |                                                                   |
| ------------ | ----------------------------------------------------------------- |
| **Status**   | Accepted                                                          |
| **Date**     | 2026-06-28                                                        |
| **Deciders** | Reebal Sami (author); Cascade (`thesis-writing-setup`)            |
| **Milestone**| Thesis writing (`writeup` phase, `.windsurf/phases.yaml`)         |
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
