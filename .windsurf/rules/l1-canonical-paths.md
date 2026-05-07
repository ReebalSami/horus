---
trigger: always_on
description: Windsurf reads global skills, workflows, and rules from `~/.codeium/windsurf/`, NOT from `~/.windsurf/`. Global workflows live at `~/.codeium/windsurf/global_workflows/` (per ADR-016). Never author L1 components under `~/.windsurf/` — that path is invisible to Windsurf.
sources_consulted:
  - cascade-system/docs/decisions/ADR-014-l1-canonical-storage-paths.md (own) — migration record that established the canonical paths
  - cascade-system/docs/decisions/ADR-016-workflow-canonical-path-correction.md (own) — corrects the workflow path from `workflows/` to `global_workflows/`
  - https://docs.windsurf.com/llms-full.txt chunks 348,353,363 (upstream — skill and workflow storage location tables)
adapted_for:
  - L1 global rule (always-on meta-rule about where L1 itself lives)
  - This long-form exists for completeness of the archive; the canonical path table is in ADR-014 + ADR-016
  - Kept intentionally brief because the full rationale lives in the two ADRs
---

# L1 canonical paths

The authoritative path table for all L1 components. This rule's purpose is to ensure every Cascade session has the correct paths top-of-mind.

## Canonical paths (per ADR-014 + ADR-016)

| Component | Canonical global path | Notes |
|---|---|---|
| **Skills** | `~/.codeium/windsurf/skills/<name>/SKILL.md` | Multi-file. Windsurf-discovered. Invoked via `@<name>`. |
| **Workflows** | `~/.codeium/windsurf/global_workflows/<name>.md` | Single-file each. Windsurf-discovered. Invoked via `/<name>`. |
| **Rules (concise/active)** | `~/.codeium/windsurf/memories/global_rules.md` | Single file, ≤6,000 chars, always-on. The LAW. |
| **Rules (long-form/reference)** | `~/Projects/cascade-system/docs/rules/<name>.md` | Full frontmatter + rationale. Not auto-loaded. |
| **Rules (per-project)** | `<project>/.windsurf/rules/<name>.md` | Workspace-scoped. Loaded by Windsurf at project scope. |
| **Contracts** | `~/.windsurf/contracts/<name>.md` | Agent-internal; NOT Windsurf-loaded. Consumed by skills explicitly. |
| **Templates** | `~/.windsurf/templates/{<type>,_shared}/` | Agent-internal; consumed by `/start-project`. |

## Deprecated paths (do not use)

- `~/.windsurf/skills/` — Windsurf does NOT scan this
- `~/.windsurf/workflows/` — Windsurf does NOT scan this
- `~/.windsurf/rules/` — Windsurf does NOT scan this
- `~/.codeium/windsurf/workflows/` — wrong path; use `global_workflows/` (per ADR-016)

## Provenance

Long-form rationale, migration record, and alternatives considered: ADR-014 + ADR-016 in `~/Projects/cascade-system/docs/decisions/`.

This rule was added to the archive during the Sprint 2 prep verification session as the `l1-canonical-paths` section existed in `global_rules.md` but had no corresponding archive file — a `@verify-l1` step 7 orphan detection finding.
