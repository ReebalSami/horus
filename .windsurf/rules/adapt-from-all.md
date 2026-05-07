---
trigger: always_on
description: When authoring any L1 skill, rule, or workflow, study multiple sources and cite provenance. Vendor adapted code; never runtime-depend.
---

# Adapt from all, depend on none

When authoring any L1 component (skill, rule, workflow):

## 1. Consult multiple sources

At minimum, before writing a new component, browse:

- `~/Projects/cascade-system/refs/superpowers/` — `obra/superpowers` (skills lifecycle: brainstorming, writing-plans, executing-plans, TDD, debugging, code-review, worktrees, …)
- `~/Projects/cascade-system/refs/mattpocock-skills/` — `mattpocock/skills` (grill-me, to-prd, to-issues, tdd, improve-codebase-architecture)
- `~/Projects/cascade-system/refs/awesome-agent-skills/` and `~/Projects/cascade-system/refs/claude-skills/` — curated ecosystem libraries (200+ skills)
- `~/Projects/portfolio-website/.windsurf/` — battle-tested in production for one full project
- Our own thinking — gaps the above don't cover

## 2. Cite `sources_consulted` in frontmatter

Every authored SKILL.md / rule / workflow includes:

```yaml
sources_consulted:
  - obra/superpowers/skills/<name> (MIT, refs/superpowers/skills/<name>)
  - mattpocock/skills/<category>/<name> (MIT, refs/mattpocock-skills/skills/<category>/<name>)
  - portfolio-website/.windsurf/<path> (own, inspirational)
  - awesome-agent-skills (browsed, no direct adoption)
adapted_for:
  - Windsurf Cascade SKILL.md format
  - Our L1/L2/L3 architecture
  - Our T-shape multi-vertical execution
  - Our adaptive `phases.yaml` contract
```

This makes provenance explicit, lets `@update-horizontal` spot-check upstream changes, and prevents blind copying.

## 3. Vendor — never runtime-depend

Copy adapted code into the canonical L1 location: skills → `~/.codeium/windsurf/skills/<name>/`; workflows → `~/.codeium/windsurf/global_workflows/<name>.md`; rules → dual-stored at `~/Projects/cascade-system/docs/rules/<name>.md` (long-form) + section in `~/.codeium/windsurf/memories/global_rules.md` (concise). **Never** `npx skills@latest add ...` at runtime. **Never** import a third-party skill registry. Upstream changes get reviewed each sprint via `@update-horizontal`.

## 4. Adapt — don't blind-copy

Every authored component is shaped to:

- Windsurf Cascade SKILL.md format (not Claude Code's plugin format)
- Our layered (L0/L1/L2/L3) architecture
- T-shape multi-vertical execution
- Adaptive `phases.yaml` contract (not one-size-fits-all)
- Our drift-aware lifecycle PM agent
- Our cross-project Obsidian memory layer

A component that's a 1:1 paste is a code smell — it means we haven't thought about how it fits.

Source: User-defined principle, locked in `~/.windsurf/plans/cascade-project-system-cac5f9.md` §1, decision #11.
