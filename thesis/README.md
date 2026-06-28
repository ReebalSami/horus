# HORUS — Master Thesis manuscript

LaTeX sources for the HORUS master thesis (FH Wedel, SS26), adapted from the FH
Wedel thesis template to **English**. Authoring decision:
`../docs/decisions/ADR-054-thesis-authoring-setup.md`. Phase tracker:
`../docs/prompts/stages/05-writeup.md`.

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
│   ├── 00-abstract.tex
│   └── 01-introduction.tex … 10-conclusion.tex
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
- **Acronyms**: define in `preamble/acronyms.tex`; use `\ac{KEY}`. Do **not** use
  `\ac` in `00-abstract.tex` — it precedes the acronym list in document order.
- **Cross-references**: `\label{ch:...}` / `\ref{...}`.
- **Results integration**: numbers are **never hand-copied**. Figures are exported
  to `figures/` (`\includegraphics`) and tables to `tables/` (`\input`), generated
  from the repo (MLflow runs / `eval/` reports). See ADR-054.

## Status

Chapters 1–4 drafted/scaffolded, 5 partial, 6–10 scaffolded; green build verified
(26 pp). Per-chapter status: `../docs/prompts/stages/05-writeup.md` §2.

## TODO before submission

- Fill the title-page placeholders (`preamble/titlepage.tex`).
- Verify the declaration + AI-clause wording against FH Wedel Richtlinie 3.0
  (`preamble/declaration.tex`).
- Confirm citation style + whether a German `Kurzfassung` is required.
- Reconcile `references.bib` metadata against the `../docs/sources/` stubs.
