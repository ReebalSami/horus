---
trigger: always_on
description: Capture significant decisions as ADRs at the moment of decision, not after. Real-time documentation; surfacing via @docs-refresh.
---

# Document as you go

When a **significant decision** is made — architectural choice, dependency selection, naming convention, trade-off resolution, design pattern adoption — write the ADR **immediately**, not at the end of a phase or sprint.

## Where

`<project-or-meta-repo>/docs/decisions/ADR-NNN-<slug>.md`

NNN = zero-padded sequence (001, 002, …). Slug = kebab-case short title.

## Format (minimal — keep it lean)

```markdown
# ADR-NNN: <Title>

**Status**: Proposed | Accepted | Superseded by ADR-MMM
**Context**: <why this came up now — 1–3 sentences>
**Decision**: <what we chose — be specific>
**Alternatives considered**: <briefly, what we didn't choose and why>
**Consequences**: <what this enables, what it constrains, who it affects>
**Source**: <conversation reference, commit SHA, or chat snippet>
```

## What counts as "significant"

- Choosing one technology over a comparable alternative (Postgres vs SQLite, pnpm vs npm, …)
- Adopting a non-trivial pattern (event sourcing, hexagonal, drift-aware PM, …)
- Trading off two desirable properties (consistency vs availability, simplicity vs flexibility, …)
- Setting a convention that will be repeated (file naming, layout, frontmatter shape, …)
- Cross-cutting choices that affect multiple sprints

## What doesn't

- Bug fixes
- Refactors with no design implication
- Implementation choices fully prescribed by upstream conventions
- Things smaller than "I'll need to remember why I did this in 3 sprints"

## Lifecycle

- **Draft-then-promote** — write a draft (`Status: Proposed`) as soon as the decision surfaces; promote to `Accepted` when used or peer-reviewed.
- **Supersession over deletion** — see `## Retention` below (extended to handoffs and retros per ADR-011).

## Numbering allocation (ADRs)

Per ADR-009. When authoring `ADR-NNN-<slug>.md`:

1. **First** — edit `docs/decisions/INDEX.md` to add a row reserving NNN (even a stub row claims the number). This atomic edit against the file-system is the allocation gate.
2. **Then** — author the `ADR-NNN-<slug>.md` file.
3. **On collision** — if another Cascade lands the same NNN in parallel and your INDEX edit races, renumber your ADR post-hoc with a `Note on numbering` line at the top explaining the renumber, and update INDEX.md accordingly.

Reserve-in-INDEX-first is the default path; post-hoc renumber is the fallback, not the primary protocol. The Sprint 1 concurrent ADR-004 incident (documented in ADR-004 + ADR-005 numbering notes) is the precedent this protocol prevents.

## Retention (all record types)

Per ADR-011. "Supersession over deletion" applies to:

- **ADRs** — mark `Status: Superseded by ADR-MMM`; never delete; cross-link both ways.
- **Handoffs** — when superseded (sprint closes, vertical finishes, fresh Cascade takes over), update `docs/handoffs/INDEX.md` status column (e.g., "superseded — Sprint N closed"); the file stays on disk.
- **Retros** — once `Status: closed`, retros are **immutable**. They are never superseded because each retro snapshots a moment; a new retro adds to the record, never replaces.

Principle: the reasoning trail must be durable. Deletion erases the trail. Retention is cheap; loss is not.

Archive policies (e.g., moving old superseded records into `<dir>/archive/`) require their own ADR if ever adopted.

## Surfacing

`@docs-refresh` (M1.11) indexes ADRs into `docs/decisions/INDEX.md` and regenerates the handoff index, validates placement, and flags empty subdirectories without rationale (per ADR-010). It does not prune superseded records.

Source: User-defined principle, locked in `~/.windsurf/plans/cascade-project-system-cac5f9.md` §1. Amendments per ADR-009 (numbering) and ADR-011 (retention), both from the Sprint 1 hardening batch.
