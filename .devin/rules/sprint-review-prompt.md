---
trigger: model_decision
description: When a GitHub milestone closes (or `phases.yaml` indicates a phase boundary with a milestone), suggest invoking `@sprint-review` for that milestone before continuing work. Never auto-invoke.
sources_consulted:
  - cascade-system plan `~/.windsurf/plans/cascade-project-system-cac5f9.md` §3.8 (sprint review heartbeat)
  - phase-taxonomy contract `~/.windsurf/contracts/phase-taxonomy.md` (M1.3) §5.3 reader contract
  - portfolio-website (own, browsed) — no analog
  - obra/superpowers, mattpocock/skills (browsed) — no analog
adapted_for:
  - Windsurf rule frontmatter (model_decision activation)
  - Pairs with `@sprint-review` (M1.9) — this rule prompts; the skill runs
  - Phase-taxonomy contract: `phases[].milestone` is the trigger field
---

# Sprint-review prompt

When Cascade observes that a GitHub milestone tied to the active project has just transitioned to `closed`, surface a one-line prompt to run `@sprint-review` before continuing.

## Fire conditions

The rule activates when **any** of these is observed in the assistant's working context:

1. A milestone in the active repo is now `state: closed` and the previous reading had it `state: open`.
2. `/run-phase` (M1.5) reaches step 8 (milestone check) and finds the named milestone closed.
3. `@sync-github` (M1.8) detects that all issues under a milestone are closed but the milestone itself is still open — followed by closing it.
4. The user explicitly says "milestone X is done" or similar.

## Behavior

Surface inline in the next assistant turn:

> Milestone `&lt;name&gt;` closed. Run `@sprint-review` for this milestone before moving on?

Do **not** auto-invoke. The user (or Cascade itself, conversationally) opens it explicitly. The rule's job is to surface the heartbeat moment.

## Suppression

If the user declines for this milestone (e.g., "skip review, continue"), suppress further fires for the same milestone in this conversation. Reset on next session.

If the milestone has already been reviewed (a retro file exists at `<project>/docs/retros/<milestone-slug>.md` with `Status: closed`), don't fire — the review already happened.

## Interaction with other rules

- **`bidirectional-learning-pipe`**: between sprint reviews, learnings flow into the queue. The sprint-review-prompt is the moment those learnings get drained.
- **`plan-drift-watcher`**: if drift was detected during the sprint, recommend running `/recalibrate` *before* `@sprint-review` so the review has a coherent picture.
- **`no-time-estimates`**: never phrase the prompt with time language ("you've been on this for X days"). The trigger is event-based (milestone closure).

## Provenance

Plan ref: §3.8. Phase-taxonomy reader contract §5.3. Issue: `ReebalSami/cascade-system#10`.
