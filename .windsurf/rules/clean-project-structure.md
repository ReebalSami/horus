---
trigger: always_on
description: Every artifact lives in its canonical directory. Project root holds only conventional top-level files. New top-level paths require an ADR.
sources_consulted:
  - portfolio-website/.windsurf/rules/clean-project-structure.md (own, primary — heavily adapted)
  - cascade-system/docs/decisions/ADR-003-strict-docs-structure.md (own, structural rule)
  - cascade-system/docs/decisions/ADR-002-handoff-prompts-subdirectory.md (own, precedent)
  - obra/superpowers (browsed, no direct rule analog)
  - mattpocock/skills (browsed, no direct rule analog)
adapted_for:
  - L1 global rule (was L2 portfolio-only with hardcoded subdir list)
  - Stack-agnostic: dropped portfolio-specific layout (`utility/`, `infra/`, `Bewerbung/`, `PORTFOLIO_BUILD_PROMPT.md`)
  - Aligned with ADR-003 (strict-docs-structure) for the meta-repo and downstream projects
  - L3 templates carry stack-specific layout; this rule states the principle only
---

# Clean project structure

Every artifact lives in its canonical directory. Project roots stay clean.

## Universal principle

- **No random files in the project root.** Everything has a proper directory.
- **Conventional root files only.** What counts as "conventional" is L3-template-defined, but typically: `README.md`, `LICENSE`, `.gitignore`, the package/dependency manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, …), the build manifest (`Makefile`, `justfile`, `tsconfig.json`, …), framework configs (`next.config.ts`, `vite.config.ts`, …), and `.env.example`.
- **New top-level files or directories require an ADR** — precedent set by `cascade-system/docs/decisions/ADR-002-handoff-prompts-subdirectory.md`.
- **Private/personal files are gitignored** and never committed (résumés, applications, scratch notes, vault snapshots).

## Universal `docs/` layout

Per `cascade-system/docs/decisions/ADR-003-strict-docs-structure.md`:

```
docs/
├── structure.md
├── architecture/        # *.excalidraw + *.mmd
├── decisions/           # ADR-NNN-<slug>.md
├── handoffs/            # <cascade-id>-<sprint-or-vertical>.md
├── retros/              # <milestone-slug>.md (downstream projects only)
└── prompts/stages/      # NN-<phase-slug>.md
```

Only `structure.md`, `makefile-manual.md`, and `technical.md` are allowed at `docs/` root.

## L3-template layouts

Source code, tests, infrastructure, and stack-specific layout details belong to each L3 template's `scaffold/`, not this rule. Examples:

- `python-ml-uv` → `src/<pkg>/`, `tests/`, `notebooks/`
- (future) `nextjs-app` → `src/`, `tests/`, `e2e/`, `public/`
- (future) `python-pipeline` → `src/`, `dags/`, `tests/`

Stack-specific paths drift across project types; the docs layout doesn't.

## Enforcement

Until `@docs-refresh` (M1.11) automates validation:

- Manual placement discipline at every file write.
- Self-review: when about to place a file, ask "what's its canonical directory?" — if no answer exists, write the ADR first.

Source: portfolio-website (own — generalized; portfolio-specific subdirs and root-file lists removed). Reinforces ADR-002 + ADR-003 from the meta-repo.
