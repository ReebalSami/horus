---
trigger: always_on
description: Whenever Cascade encounters an insight, friction note, pattern, or anti-pattern during project work, capture it to the appropriate review queue using a standardized format. The queue is drained by `@sprint-review` (M1.9), which decides which items merit L1 promotion.
sources_consulted:
  - cascade-system plan `~/.windsurf/plans/cascade-project-system-cac5f9.md` §3.4 (bidirectional learning), §3.8 (sprint review)
  - cascade-system queue `~/Projects/cascade-system/queue/pending-review.md` (existing format precedent)
  - portfolio-website (own, browsed) — informal learning capture; not as structured
  - obra/superpowers, mattpocock/skills (browsed) — no learning-pipe analog
adapted_for:
  - Windsurf rule frontmatter (always_on; ambient capture across all conversations)
  - Pairs with `@sprint-review` (M1.9) — this rule captures; the skill drains
  - Pairs with `@update-horizontal` (M1.10) — promoted items end up there
---

# Bidirectional learning pipe

Capture worth-remembering observations into a review queue at the moment they appear. The queue is drained periodically by `@sprint-review`. This rule is the ambient capture mechanism.

## What counts as worth capturing

- **Pattern** — a way of doing something that worked unexpectedly well, that other projects could borrow
- **Anti-pattern** — a way of doing something that backfired; future Cascades should avoid
- **Friction** — a recurring annoyance that suggests an L1 gap (missing skill, unclear rule, ambiguous contract)
- **Trade-off insight** — a moment where a real choice was made and the reasoning is worth preserving
- **Tooling discovery** — a non-obvious capability of an MCP, library, or platform that future work could leverage

What does **not** count:

- Trivial observations ("commit succeeded")
- Single-use facts ("the user prefers blue")
- Anything already captured in an ADR (write the ADR; don't double-log)

## Where to capture

Two queues exist; pick the right one:

| Queue | When to use |
|---|---|
| `<project>/docs/retros/<milestone>.md` (in-progress retro, "Learnings" section) | Insight is project-local — pertains only to the current vertical / template / domain |
| `~/Projects/cascade-system/queue/pending-review.md` | Insight is cross-project — likely warrants an L1 rule/skill/contract update |

When unsure, capture to the project-local retro **and** flag it for cross-project consideration:

```
- **Insight**: ...
- **Source**: ...
- **Cross-project candidate**: yes — surface to meta-repo queue at next @sprint-review
```

## Capture format (standardized)

The format matches `~/Projects/cascade-system/queue/pending-review.md` so items can be lifted verbatim:

```markdown
- **Insight**: &lt;1-line statement&gt;
- **Source**: &lt;conversation-id, commit-sha, issue-number, or filesystem path&gt;
- **Project**: &lt;project name; "cascade-system" if meta-repo&gt;
- **Cascade**: &lt;A | B | C | D — which Cascade observed it&gt;
- **Date observed**: &lt;YYYY-MM-DD&gt;
- **Proposed L1 change**: &lt;optional; only if obvious&gt;
- **Project-local action**: &lt;optional; only if obvious&gt;
```

## Behavior

When an insight surfaces during a working session:

1. **Capture inline** — write the entry to the appropriate queue (project retro or meta-queue).
2. **Surface briefly** in the conversation:

   > Captured: &lt;1-line insight&gt; → &lt;queue file path&gt;.

3. **Don't disrupt the flow** — capture is a side action, not a context switch. After capturing, continue the user's current task.

## Anti-patterns

- **Double-capture** — same insight in queue + ADR + retro is noise. Pick one canonical location.
- **Capture-as-procrastination** — capturing should take seconds. If an insight needs paragraphs, it's an ADR, not a queue item.
- **Empty queue items** — every entry has at least Insight + Source + Date. Skipping fields = log it later, not now.
- **Auto-promotion to L1** — promotion is an `@sprint-review` decision, never automatic from this rule.

## Interaction with other rules

- **`document-as-you-go`**: ADRs are for decisions; this rule is for observations that aren't decisions yet. ADR > queue item if a decision was made.
- **`no-quantity-over-shape`**: don't measure the queue ("47 entries this sprint!"). Drain it; that's the metric.
- **`be-honest-direct-critical`**: capture friction even when it's about the user's preferences or process. Soft language defeats the pipe.

## Provenance

Plan ref: §3.4 (bidirectional learning), §3.8. Issue: `ReebalSami/cascade-system#10`.
