# ADR-069: `docs/reviews/` subdirectory for manuscript/artifact review records

**Status**: Accepted
**Date**: 2026-08-15
**Refs**: cascade-system ADR-002 (new-top-level-path-requires-ADR precedent), ADR-003 (strict docs structure), `strict-docs-placement` workspace rule

## Context (current-state survey)

A full first-supervisor-style review of the thesis manuscript (`thesis/`) was produced on
2026-08-15: content audit, repo-evidence verification, build/rendered-PDF audit, and web
verification of citations and factual claims. The artifact is a review record — not an ADR
(it decides nothing), not a retro (it is not a milestone retrospective), not a handoff, and
not an eval report (it audits prose, not model output). No canonical directory exists for it,
and `strict-docs-placement` requires an ADR before any new `docs/` category is created.

## Options considered

1. **`docs/reviews/`** — **chosen**. A review is a distinct artifact class with a plausible
   future population (subsequent supervisor passes, external feedback rounds, pre-submission
   audits). One directory, dated filenames, append-only.
2. `eval/` — rejected: `eval/` holds machine-measurement evidence (scoring audits, re-score
   matrices); a prose review of the manuscript does not belong beside them.
3. `docs/retros/` — rejected: retros snapshot closed milestones and are immutable by
   convention (ADR-011 of the meta-repo); a review is iterated on and answered.
4. `thesis/review/` — rejected: `thesis/` is the LaTeX source tree; non-manuscript prose in
   it pollutes the build root (`latexmkrc` globs, `make thesis-clean` blast radius).

## Decision (+ integration thoughts)

Create `docs/reviews/`. Naming: `YYYY-MM-DD-<slug>.md`. Reviews are append-only records:
a later review supersedes by date, never by deletion (mirrors ADR-011 retention). First
occupant: `docs/reviews/2026-08-15-first-supervisor-review.md`.

## Source archival

No external sources; the review itself cites its evidence inline (repo paths, build log,
web-verified citations).

## Supersession trigger

If `/docs-refresh` lands with a different canonical layout for review records, or if the
meta-repo's ADR-003 docs taxonomy adds a review category with a different name, migrate and
supersede.
