---
trigger: always_on
description: Forbids prescribing fixed counts of skills, rules, workflows, or other components. Build instances as the work demands.
---

# No quantity over shape

NEVER commit to fixed counts:

- "build 5 skills"
- "create 3 workflows"
- "we need 6 rules"
- "this template requires N phases"

ALWAYS describe **archetypes and patterns**, then build instances as the work demands. If a sprint produces 4 skills, that's fine. If it produces 12, that's fine. **Numbers emerge from need.**

When asked "how many X do we need?", reframe to: "what archetypes of X serve this purpose? we build instances when they're needed."

## Component archetypes (reference)

**Skill archetypes**: interview, artifact-producing, dispatcher, verification, sync, review, documentation, maintenance, meta, stack-specific.

**Workflow archetypes**: orchestrator (e.g., `/start-project`), ritual (e.g., `@sprint-review` entry).

**Rule archetypes**: meta-principle (this one), watcher (drift, capture-signal), enforcer (no-terminal-oneline-scripts), guide (context7-and-docs-first).

These archetypes are open — new ones emerge as the system grows.

Source: User-defined principle, locked in `~/.windsurf/plans/cascade-project-system-cac5f9.md` §1.
