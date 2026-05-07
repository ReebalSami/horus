---
trigger: always_on
description: Project-local enforcement of canonical docs/ placement. Mirrors cascade-system ADR-003 so that every downstream project carries the rule even if global L1 rules aren't loaded.
sources_consulted:
  - cascade-system/docs/decisions/ADR-003-strict-docs-structure.md (own)
  - cascade-system/docs/decisions/ADR-004-shared-scaffold-pattern.md (own)
  - ~/.windsurf/rules/clean-project-structure.md (own, L1)
adapted_for:
  - Per-project propagation (this rule lives in `<project>/.windsurf/rules/`, not L1)
  - Self-contained: works without L1 rules loaded
  - Naming: `strict-docs-placement` is project-flavored; the L1 generic equivalent is `clean-project-structure`
---

# Strict docs placement

Every artifact under `docs/` lives in its canonical subdirectory.

## Allowed at `docs/` root

- `structure.md`
- (project-specific cross-cutting docs only, e.g., `technical.md`, `makefile-manual.md`)

## Required subdirectories

| Path | Holds |
|---|---|
| `docs/architecture/` | `*.excalidraw`, `*.mmd` diagrams |
| `docs/decisions/` | `ADR-NNN-<kebab-slug>.md` records + `INDEX.md` |
| `docs/handoffs/` | `<from-cascade-id>-<topic>.md` cross-session prompts + `INDEX.md` |
| `docs/retros/` | `<milestone-slug>.md` retrospectives |
| `docs/prompts/stages/` | `NN-<phase-slug>.md` per `phases.yaml` |

## Enforcement

- **At write time**: every file write under `docs/` first answers "what's its canonical directory?". If no answer, write an ADR for the new category before writing the file.
- **New top-level path**: requires an ADR. Precedent: cascade-system `ADR-002-handoff-prompts-subdirectory.md`.
- **Misplaced files**: migrated immediately upon detection. Not deferred to a refactor sprint.

## Relationship to L1

The L1 `~/.windsurf/rules/clean-project-structure.md` carries the universal principle. This file is the project-local mirror so the rule survives even if the project is opened in a Cascade without L1 rules loaded (e.g., by another developer, in CI, or in a fresh environment).

## Validators

When `/docs-refresh` lands at L1, it auto-validates placement. Until then, manual.

## Provenance

- Cascade-system ADR-003 codified the universal rule
- ADR-004's `_shared/scaffold/` pattern propagates this file into every project bootstrapped via `/start-project`
