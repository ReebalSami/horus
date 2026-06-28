---
source_url: "https://github.com/fh-wedel/thesis-template"
source_title: "FH Wedel Thesis LaTeX Template"
source_author: "Fachhochschule Wedel"
source_date: ""
retrieved_date: "2026-06-28"
extracted_concepts: ["KOMA-Script scrreprt", "biblatex/biber alphabetic", "FH Wedel title page", "Eidesstattliche Erklärung", "listings setup"]
tags: ["latex", "template", "thesis", "fh-wedel"]
archived_pdf: ""
status: stub
---

# FH Wedel Thesis LaTeX Template

KOMA-Script (`scrreprt`) LaTeX template provided by FH Wedel for student theses.
Ships a title page, the statutory declaration (Eidesstattliche Erklärung),
`biblatex` + `biber` (alphabetic) bibliography setup, a `listings` configuration,
and the FH logo.

## Why cited in HORUS

Base template adapted to **English** for the thesis manuscript under `thesis/`;
see `docs/decisions/ADR-054-thesis-authoring-setup.md`. A local copy lives at
`/Users/reebal/Projects/FH-Wedel/SS26/Master-Thesis/anmeldung-und-richtlinien/thesis-template-master/`.

## Notes

- Adaptations: babel `main=english,ngerman`; `lmodern` (was `ae`); listings
  trimmed to python/json; bibliography bound to `thesis/references.bib`.
- The upstream declaration predates the current AI-disclosure requirement (added
  in HORUS; see `docs/sources/legal/fh-wedel-thesis-richtlinie.md`).
