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
│   ├── titlepage.tex     # FH Wedel title page (placeholders marked <...>)
│   ├── declaration.tex   # Eidesstattliche Erklärung (incl. AI-disclosure clause)
│   └── acronyms.tex      # list of abbreviations (acronym package)
├── chapters/
│   ├── 00-abstract.tex              # first BODY element (after the abbreviations list)
│   ├── 01-introduction.tex
│   ├── 02-background.tex
│   ├── 03-related-work.tex
│   ├── 04-system-design.tex         # three-layer design; Layers 2-3 = design only
│   ├── 05-methodology.tex
│   ├── 06-results.tex               # carries explicit [PENDING] markers
│   ├── 07-implementation.tex
│   ├── 08-discussion.tex
│   ├── 09-limitations-future-work.tex
│   └── 10-conclusion.tex
├── appendix/
│   └── appendix.tex      # metric spec, hypotheses, datasheet, AI-usage, reproducibility
├── images/               # static assets (FH logo)
├── figures/              # GENERATED figures (PDF) — see "Results integration"
└── tables/               # GENERATED tables (.tex, \input) — see "Results integration"
```

## Conventions

- **Language**: English (babel `main=english,ngerman`; German legal terms inline).
- **Citations**: biblatex `alphabetic` + biber. Use `\cite{key}`; keys live in
  `references.bib` and are backed by archived stubs under `../docs/sources/`.
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
  cloud comparison as results. They are design (ch.4) and future work (ch.9).
- **Cross-references**: `\label{ch:...}` / `\ref{...}`.
- **Results integration**: numbers are **never hand-copied**. Figures are exported
  to `figures/` (`\includegraphics`) and tables to `tables/` (`\input`), generated
  from the repo (MLflow runs / `eval/` reports). See ADR-055.
- **Label every number** as diagnostic (in-sample) or sealed (held-out). An
  in-sample number may never be presented as the system's accuracy.

## Status

Chapter map reshaped 2026-07-31 for the scope freeze; introduction rewritten;
green build verified (32 pp, no undefined references or citations). Per-chapter
status: `../docs/prompts/stages/05-writeup.md` §2.

## TODO before submission

- Fill the remaining title-page values marked `<...>` (`preamble/titlepage.tex`):
  Matrikelnummer, university e-mail, second examiner, first examiner's e-mail.
  No postal address is used by decision.
- Get supervisor sign-off on the softened legal framing in ch.1 (the paragraph
  carries a `SUPERVISOR GATE` comment).
- Confirm citation style with the supervisor (the regulation prescribes the
  short-reference method and lets the supervisor's preference override).
- Confirm whether a German `Kurzfassung` is required (stub in `00-abstract.tex`).
- Reconcile `references.bib` metadata against the `../docs/sources/` stubs.
- Replace every `[PENDING]` marker in ch.6 once the reader-selection run lands.
