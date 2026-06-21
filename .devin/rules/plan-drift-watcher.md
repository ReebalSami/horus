---
trigger: model_decision
description: Surfaces drift between the active project's PRD vertical slices, the live GitHub issue/milestone state, and the recent commit log. When drift is observed, recommend invoking `/recalibrate`.
sources_consulted:
  - cascade-system plan `~/.windsurf/plans/cascade-project-system-cac5f9.md` §3.9 (drift detection)
  - cascade-system contract `~/.windsurf/contracts/phase-taxonomy.md` (M1.3) — reader contract for plan-drift-watcher
  - obra/superpowers (browsed) — no analog
  - portfolio-website (own, browsed) — no analog
adapted_for:
  - Windsurf rule frontmatter (model_decision activation; only triggers when project state is in scope)
  - Pairs with `/recalibrate` workflow (M1.7) — this rule signals; the workflow resolves
---

# Plan-drift watcher

A passive monitor that activates whenever Cascade is reading the active project's state and notices a mismatch between three sources of truth:

1. **PRD §11** — `docs/prompts/stages/03-prd.md` vertical slices (the *intent*)
2. **GitHub state** — open + recently-closed issues, milestones, Project v2 cards (the *plan-of-record*)
3. **Recent commits** — last ~20 commits on the active branch (the *actual work*)

When the three diverge, the rule fires.

## Drift signals (each is a fire condition)

| Signal | Definition | Example |
|---|---|---|
| **Scope creep** | An open issue exists that maps to no PRD §11 slice | A bug fix issue that should have been a small ad-hoc task is now a labeled `vertical-slice` |
| **Unreflected work** | Recent commit messages reference work for which no issue exists | `feat: add auth flow` with no auth-related issue |
| **Issue abandonment** | An open issue has had no activity (comment, commit, label change) for an extended event window (e.g., "since the last milestone closed") | Issue from Slice 3 stalled while Slice 5 already shipped |
| **Artifact lag** | PRD's `Date` field predates a substantive design pivot evident in commits or recent issues | Commits show a different architecture than PRD §7 |
| **Milestone-state mismatch** | A milestone's open-issue count is zero but state is `open`, or non-zero but state is `closed` | Stale milestone left open after all work shipped |
| **Phase mismatch** | The latest PRD/brainstorm artifact's phase is later than `phases.yaml` would imply for the current work | Working on `experiment` artifacts but `phases.yaml` says we're still in `spec` |

## Behavior when fired

When this rule activates, surface the drift signal **inline** in the next assistant turn that interacts with project state:

> ⚠ Drift detected: &lt;signal name&gt;. &lt;1-line description.&gt; Run `/recalibrate` to triage.

Do **not** auto-invoke `/recalibrate`. The user opens it explicitly. The rule's job is to notice; the workflow's job is to resolve.

## Suppression

If the user has acknowledged the drift this session (e.g., said "yes I know, ignore for now"), suppress further fires for the same signal during this conversation. Reset on next session.

## Interaction with other rules

- **`no-quantity-over-shape`**: drift signals are a *shape* observation. Don't quantify ("3 drift signals!") unless the count materially helps; describe the shape.
- **`be-honest-direct-critical`**: drift surfaces are direct and unhedged. Don't soften.
- **`make-sure-it-works`**: drift detection itself doesn't replace verification — a passing test suite with PRD drift is still drifted.

## Provenance

Plan ref: `~/.windsurf/plans/cascade-project-system-cac5f9.md` §3.9. Phase-taxonomy reader contract (M1.3) §5.4. Issue: `ReebalSami/cascade-system#8`.
