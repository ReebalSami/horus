# HORUS — Master Thesis manuscript

LaTeX sources for the HORUS master thesis (FH Wedel, SS26), adapted from the FH
Wedel thesis template to **English**.

- **Authoring decision**: `../docs/decisions/ADR-055-thesis-authoring-setup.md`
  (authored as 054, renumbered; carries the 2026-07-31 scope-freeze amendment).
- **Scope decision — what may be claimed**:
  `../docs/decisions/ADR-054-thesis-endgame-reader-first-recovery-and-scope-freeze.md`.
- **Phase tracker**: `../docs/prompts/stages/05-writeup.md`.

## Build

```sh
make thesis        # from the repo root -> thesis/_build/main.pdf
make thesis-clean  # remove build artifacts (thesis/_build)
```

Requires a TeX Live / MacTeX install (`latexmk`, `pdflatex`, `biber` on `PATH`) —
**not** part of the Python/uv toolchain. Install MacTeX with
`brew install --cask mactex-no-gui` (then restart the shell or run
`eval "$(/usr/libexec/path_helper)"`).

The build runs `latexmk` (pdflatex + biber, multi-pass) in this directory; see
`latexmkrc`. The PDF and all aux/log/bbl intermediates go to `_build/` (gitignored).

## Structure

```
thesis/
├── main.tex              # document root: \documentclass + structure
├── latexmkrc             # latexmk config (out_dir=_build; pre-creates \include subdirs)
├── references.bib        # bibliography (biblatex/biber; keys backed by docs/sources/)
├── preamble/
│   ├── header.tex        # packages, fonts, listings, biblatex, hyperref, doc-info
│   ├── titlepage.tex     # FH Wedel title page (all fields filled; no placeholders)
│   ├── declaration.tex   # Eidesstattliche Erklärung (incl. AI-disclosure clause)
│   └── acronyms.tex      # list of abbreviations (acronym package)
├── chapters/
│   ├── 00-abstract.tex              # first BODY element (after the abbreviations list)
│   ├── 01-introduction.tex
│   ├── 02-background.tex
│   ├── 03-related-work.tex
│   ├── 04-system-design.tex         # three-layer design; Layers 2-3 = design only
│   ├── 05-methodology.tex
│   ├── 06-measurement-validity.tex  # the instrument-validation chapter (own chapter by design)
│   ├── 07-results.tex
│   ├── 08-implementation.tex
│   ├── 09-discussion.tex
│   ├── 10-limitations.tex
│   ├── 11-future-work.tex
│   └── 12-conclusion.tex
├── appendix/
│   └── appendix.tex      # field registry, hypotheses, datasheet, abandoned metric, AI-usage, reproducibility
├── images/               # static assets (FH logo)
├── figures/              # GENERATED charts (PDF) + hand-authored TikZ diagrams (.tex)
└── tables/               # GENERATED tables (.tex, \input) — see "Results integration"
```

## Conventions

- **Language**: English (babel `main=english,ngerman`; German legal terms inline).
- **Citations**: biblatex `numeric-comp` + biber (`sorting=nty`), rendering `[N]`
  — the first examiner's written instruction in his 2026-08-18 review (registry
  row R02; ADR-074 supersedes the earlier `authoryear` inference; Richtlinie
  defers the short-reference form to the supervisor). Use `\parencite{key}` for
  bracketed citations and `\textcite{key}` when the authors are the sentence's
  subject; keys live in `references.bib` and are backed by archived stubs under
  `../docs/sources/`.
- **Acronyms**: define in `preamble/acronyms.tex`; use `\ac{KEY}` (`\acp{}` for
  plural). Legal everywhere in the body, including the abstract, because the
  abbreviations list now precedes it (required part order).
- **Part order is prescribed** by the university regulation: cover → contents →
  figures → tables → abbreviations → body → appendix → bibliography → statutory
  declaration. Do not move the abstract in front of the contents.
- **The declaration wording is prescribed** — see the warning block in
  `preamble/declaration.tex`. Never paraphrase it; document AI use in the appendix
  instead.
- **Scope guard**: do not claim the knowledge-graph layer, the query layer, or a
  cloud comparison as results. They are design (ch.4) and future work (ch.11).
- **Cross-references**: `\label{ch:...}` / `\ref{...}`.
- **Results integration**: numbers are **never hand-copied**. Figures are exported
  to `figures/` (`\includegraphics`) and tables to `tables/` (`\input`), generated
  from the repo (MLflow runs / `eval/` reports). See ADR-055.
- **Label every number** as diagnostic (in-sample) or sealed (held-out). An
  in-sample number may never be presented as the system's accuracy.

## Status

All thirteen chapters, the abstract and all six appendices are drafted. Applied
review passes, in order: the 2026-08-15 supervisor-review fix plan (evidential
repairs M1--M7, bibliography corrections, missing prose, appendices, formatting);
the 2026-08-16 second pass (seven new figures — every chapter 2--8 carries at
least one visual — duplication trimmed, AI-usage appendix sharpened); the
2026-08-18 examiner review of the interim manuscript, worked as a 38-row registry
(R01--R38: citation style switched to `numeric-comp` per his written instruction,
ADR-074; limitations/future-work split into own chapters; measurement-venue
scoping per ADR-070); and the 2026-08-20 Feinschliff pass. Green build verified:
140 pp, zero unresolved references and citations, zero overfull boxes, 1,265
tests passing. Review records under `../docs/reviews/`.
Per-chapter status: `../docs/prompts/stages/05-writeup.md` §2.

## TODO before submission

- Author read-through of the full PDF: the author signs off every sentence
  (declaration requirement; AI-drafted prose is documented in the AI-usage
  appendix).
- Citation style: resolved — `numeric-comp` per the examiner's written
  instruction (2026-08-18 review, R02; ADR-074). No further nod needed.
- Kurzfassung: deliberately omitted (author decision 2026-08-15, English-only);
  re-confirm with the Prüfungsamt only if its requirement is in doubt.
- Print, sign and date the statutory declaration in the submitted copies.
