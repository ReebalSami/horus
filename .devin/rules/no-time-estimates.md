---
trigger: always_on
description: Forbids time-based language in plans, estimates, and progress communication. Discrete event-based language only.
---

# No time estimates

NEVER use time-based language when planning, estimating, or describing work:

- "takes 3 days", "should be done by Friday", "this sprint takes a week"
- "soon", "later", "in a few hours", "after a while"
- Calendar dates as deadlines or completion targets
- Hours/days/weeks/months as units of estimation

ALWAYS use discrete, event-based language:

- sprint, milestone, phase, step, iteration, cycle, stage, wave, pass, round, checkpoint, chapter, epic, story
- "after milestone X", "next sprint", "when criterion Y holds", "once `<gate>` passes"

A sprint takes as long as it takes. **Done is defined by milestone completion + retrospective written**, never by time elapsed.

This applies in: plans, PRDs, ADRs, retros, GitHub issues/comments, chat responses to the user, code comments — everywhere.

When the user asks "how long will this take?" — reframe to: "what's the next milestone, and what gates does it require?"

Source: User-defined principle, locked in `~/.windsurf/plans/cascade-project-system-cac5f9.md` §1.
