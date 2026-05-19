# M2D.5 — Mid-phase heartbeat retro (2026-05-19)

**Status**: closed — heartbeat scope drained, L1 promotion landed, follow-on issues queued for Phase 4 of the post-pilot-13 rethink plan.

**Type**: mid-phase heartbeat (not a milestone-close retro — M2D.5 is still in progress). Per `@sprint-review` skill semantics, this is the "drain learnings + decide L1 promotions" pattern applied off the milestone boundary, triggered by the user's explicit request after pilot #13 (`docs/retros/m2d.5-pilot-13-cohort-harness.md` learning #1) and by the post-pilot-13 re-evaluation session.

**Scope** (deliberately narrow):

1. Drain pilot-13 retro learning #1 (log-streaming for long-running commands) → L1 promotion
2. Privacy redaction across both public-facing repos + GitHub issue #17 reframe
3. Brainstorm v2 §12 amendment (supervisor-meeting framing correction)
4. Stage Phase 4 (13 new issues per the rethink plan §5 chronological order)

**NOT in scope**:

- Full M2D.5 close-out (pilot-13 was one of multiple in-flight workstreams; adapter fix #41 + structured-output probe + EDA + fine-tuning all still ahead)
- Pilot-13 retro learning #2 (empirical-probe-per-stage discipline) — deferred to a follow-on heartbeat or full milestone retro; weak L1-promotion signal; consider extending `horus-decision-discipline` first if pattern surfaces on a second project
- `queue/pending-review.md` pre-existing entries (LFS install ordering; audit-trail `.git/` skip; token-economy / no-status-polling) — preserved as uncommitted local-only changes; not drained in this heartbeat (those need their own focused triage cycle)

## Outputs landed in this heartbeat

| Output | Where | Commit / PR |
|---|---|---|
| Redaction of supervisor surname (9 horus files) | `ReebalSami/horus` | PR #43 → `c0aea17` |
| Brainstorm v2 §12 amendment (meeting framing correction) | `ReebalSami/horus` `docs/prompts/stages/02-brainstorm.md` §12 | PR #43 → `c0aea17` |
| Issue #17 rewrite (title + body + `progress-check` label) | `ReebalSami/horus#17` | direct via `mcp3_issue_write` (PR #43 session) |
| Redaction of supervisor surname (handoff) | `ReebalSami/cascade-system` `docs/handoffs/cascade-d-master-thesis.md` | PR #105 → `9e97e07` |
| L1 promotion: `long-running-foreground` rule (long-form) | `ReebalSami/cascade-system` `docs/rules/long-running-foreground.md` | PR #106 → `adef820` |
| L1 promotion: concise law in `global_rules.md` | `~/.codeium/windsurf/memories/global_rules.md` (local-only, no repo) | inline edit during PR #106 session; 5981 chars total (under 6000 budget) |
| Workspace copy of new rule for HORUS sessions | `~/Projects/horus/.windsurf/rules/long-running-foreground.md` | this PR |

## Drain decisions

### Pilot-13 learning #1 — log-streaming → L1 promotion: ACCEPTED

The retro's "Proposed L1 change" was: *"Add to `cascade-system` rule `no-terminal-oneline-scripts.md` (or a new sibling rule): explicit guidance on log-streaming for long-running commands. The current rule covers crash-safety; a sibling rule should cover observability."*

**Decision**: sibling rule (Q9=A of the rethink plan). Rationale:

- Different concern (observability vs crash-safety)
- Different forcing function (visibility vs syntax-safety)
- Cleaner long-term evolution (each rule evolves independently of the other)
- Mirror-pair pattern fits `no-terminal-oneline-scripts` + `/commit` workflow precedent (ADR-013)

**Empirical evidence** triangulated from 3 HORUS sessions:

1. M2D.5 step 3 (dataset acquisition, 2026-05-13) — `huggingface-cli download` parallel-background pattern; per-process progress is the only signal of which dataset is hung. Suppressing to `/dev/null` defeats the parallel pattern.
2. M2D.5 step 5 (ADR-009 PR(b), 2026-05-14) — 6 VLM cohort smokes (5–60 min each); foreground-streaming surfaced model-load failures within seconds; background-poll would have cost ~30 tool calls of "Status: RUNNING" with zero signal.
3. M2D.5 step 7 (pilot-13 cohort sweep, 2026-05-18) — 26 invoices × 7 models = 182 inference calls; streaming per-tuple output let the user observe per-model F1 trend in real-time + catch the MONEY-field FN pattern before sweep completed.

**Sources also consulted** (per `adapt-from-all`):

- `~/.windsurf/handoffs/horus-adr-009-prb-202605141837-coding.md` — user-stated rule re: foreground + live output during cohort smokes (2026-05-14)
- `queue/pending-review.md` 2026-05-13 entry "token-economy / no-status-polling" — sibling principle on token economics of polling
- `cascade-system/docs/rules/no-terminal-oneline-scripts.md` — structural template for sibling rule
- `cascade-system/docs/rules/make-sure-it-works.md` + `cascade-system/docs/rules/know-your-hardware.md` — cross-references

### Pilot-13 learning #2 — empirical-probe-per-stage → L1 promotion: DEFERRED

The retro proposed extending either `horus-decision-discipline` (L2 workspace) or `document-as-you-go` (L1 global) with: *"every multi-step data-pipeline ADR plan should specify ≥ 1 empirical probe per stage before commits land."*

**Decision**: defer L1 promotion until a second project provides corroborating evidence. Rationale (per `no-quantity-over-shape` + `adapt-from-all`): one-project signal is insufficient for global rule promotion; the pattern may be HORUS-specific. Capture remains in `docs/retros/m2d.5-pilot-13-cohort-harness.md` as the canonical project-local record. Re-evaluate at the next horizontal `@sprint-review`.

### Privacy redaction → executed: ACCEPTED

User-requested 2026-05-19 during the post-pilot-13 rethink session. Both public-facing repos (`ReebalSami/horus` + `ReebalSami/cascade-system`) carried the supervisor's surname; scope of redaction set per the rethink plan §6 Q2-A=A (forward-replace only) / Q2-B=A ("supervisor") / Q2-C=C (public repos + issue #17 only).

Git history NOT rewritten — commit messages verified clean (`git log --grep` + `git log --pretty='%H %an %s'` returned 0 matches before redaction). Tradeoff: simplicity + no force-push + no broken SHAs; old commit blobs reachable via specific historical-commit URLs but not via default browsing. See brainstorm §12 amendment for the full rationale.

### Brainstorm v2 §12 amendment → executed: ACCEPTED

Supersedes the §4.1 "First-supervisor-meeting lock" tier and reframes the supervisor's role from a "lock ceremony" to a "routine progress check" per FH-Wedel `Masterarbeit-Leitfaden.md` §9 (*regelmäßiger Austausch*) + modern ML methodology norms (NeurIPS Paper Checklist 2024/2025 + arxiv 2406.14325 + arxiv 2503.08124). H1–H6 pre-registration (timestamped 2026-05-08 in v2 §6) preserved unchanged; what changes is the meta-framing of WHEN/HOW the supervisor sees them, not the hypothesis content.

## What this heartbeat is NOT a substitute for

- **M2D.5 milestone close retro** — when `experiments-validated` milestone closes (after pilot-13 + adapter fix + structured-output evidence + EDA + fine-tuning evidence are all in hand), the full milestone-close retro will integrate this heartbeat's learnings with the post-heartbeat work.
- **Full queue triage** — `cascade-system/queue/pending-review.md` has 4+ uncommitted entries from M2D.5 step 3 that this heartbeat did NOT drain. Those need their own dedicated triage cycle.
- **Cross-vertical horizontal sprint review** — if Cascade A picks up the queue at the next horizontal sprint review, additional L1 promotions may surface (e.g., the LFS install ordering pattern may justify a `python-ml-uv` L3 template extension).

## Next phase

Per the post-pilot-13 rethink plan §8 Phase 4: invoke `@to-issues` adapted-from-brainstorm-and-handoff per `cascade-d-master-thesis.md` §3 amendment 11. Author the 13 new issues per §5 chronological order. Each issue body cites: predecessor (`Blocked by #X`), which H_i it tests (or "exploratory under §4.2"), trigger conditions, acceptance criteria, Project board #6 entry, labels per Q8.

## References

- **Post-pilot-13 rethink plan**: `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §3.5 + §8
- **Source retros**: `docs/retros/m2d.5-pilot-13-cohort-harness.md` (learning #1 drained here; learning #2 deferred)
- **Companion PRs**:
  - `ReebalSami/horus#43` (Phase 1: redact + brainstorm §12 + issue #17 rewrite) — merged as `c0aea17`
  - `ReebalSami/cascade-system#105` (Phase 2: handoff redaction) — merged as `9e97e07`
  - `ReebalSami/cascade-system#106` (Phase 3 cascade-system: long-running-foreground L1 promotion) — merged as `adef820`
- **Source consults** (per `adapt-from-all`): NeurIPS Paper Checklist 2024/2025; arxiv 2406.14325 (Reproducibility in ML-based Research, June 2024); arxiv 2503.08124 (Confirmatory Methodological Research, March 2025); NERVE-ML reproducibility + validity checklist (April 2025); FH-Wedel `Masterarbeit-Leitfaden.md` §9
- **Authoring session**: same Cascade D session as the rethink plan + PRs #43, #105, #106
