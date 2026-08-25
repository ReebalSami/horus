# ADR-076 — Submission repository presentation

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-25 |
| **Milestone** | submission (delivery) |
| **Relationship** | Bounded by the thesis's AI-usage appendix (appendix E) + statutory declaration; sibling of ADR-074's redaction pass (same HEAD-only tradeoff); companion of ADR-075 (examiner delivery channel) |

## Context

The repository is public and is delivered to the examiners alongside the manuscript. A pre-submission audit found the browsable tree still narrating its own *development workflow* rather than presenting the *research artifact*: internal phase playbooks and working handoffs under `docs/`, a workflow operating guide at the repo root, agent-workspace configuration, machine-local plan paths in docstrings and configs, and READMEs whose bottom halves documented internal tooling loops. None of this is secret — the thesis's AI-usage appendix formally discloses the AI-assisted workflow, per the FH Wedel guidance and as required by the statutory declaration's marking clause — but a submission artifact should read audience-first.

## Current-state survey (2026-08-25)

| Fact | Evidence | Implication |
|---|---|---|
| Appendix E is the declaration's required marking | `thesis/appendix/appendix.tex` (`app:ai-usage`): "This appendix is that marking" | it must not be weakened; repo curation must stay consistent with it |
| Appendix E cites `docs/reviews/` twice | "Multiple review passes, documented under `docs/reviews/`…" | review records must remain tracked |
| Appendix F cites `docs/decisions/` as the reasoning trail | "recorded as numbered architecture decision records (`docs/decisions/`, indexed)" | the ADR corpus must remain tracked and unedited |
| No thesis `.tex` references the internal working docs | grep over `thesis/**` for `docs/prompts`, `docs/handoffs`, `docs/retros`, `AGENTS`, `structure.md` → zero hits | those paths are deletable without touching the frozen manuscript |
| Precedent for HEAD-only cleanup exists | the supervisor-name redaction pass explicitly accepted "clean HEAD, no force-push" | consistent depth choice; no history rewrite |

## Decision

1. **Untouched (disclosure integrity)**: `thesis/appendix/appendix.tex`, `thesis/preamble/declaration.tex`, the entire `docs/decisions/` record corpus (this INDEX row + file excepted, as a new record), and `docs/reviews/` content (only machine-local `~/.windsurf/plans/…` path strings stripped — meaningless outside the author's machine).
2. **Removed from tracking**: `docs/prompts/` (phase playbooks + reviewer prompts), `docs/handoffs/` (working handoffs + index), `docs/retros/` (process retrospectives), `docs/structure.md` (scaffold meta-doc). These are internal working documents; the durable outcomes they produced live in the ADRs, review records, and the manuscript.
3. **Untracked, kept locally**: `AGENTS.md` and `.devin/` via `.gitignore` — workflow configuration for the author's environment, not part of the research artifact.
4. **Reworded, meaning-preserving**: docstrings/comments pointing at now-untracked rule files now point at `configs/README.md` (the public statement of the same discipline); machine-local plan paths and internal milestone tokens removed from living docs, configs, and the dataset-manifest generator + its 7 committed manifests; both READMEs rewritten audience-first (project, quick start, reproduction, examiner access, layout, license).
5. **Not renamed**: the `drafted_by="cascade"` provenance value inside the ground-truth schema and the frozen GT files — it is honest adjudication provenance, disclosed in the methodology chapter, and baked into the frozen corpus (renaming would break byte-identity with the ADR-075 bundle).
6. **Depth: HEAD-only.** History is not rewritten and GitHub PR/issue records remain. The disclosure makes old history *consistent* rather than contradictory; this pass is curation of presentation, not concealment of process — which is also why this decision is itself recorded in the open.

## Alternatives considered

- **History rewrite (force-push a squashed main)** — rejected: GitHub retains PR/issue bodies regardless, every commit-SHA cross-reference in the record corpus breaks, and the earlier redaction pass already established the HEAD-only tradeoff as proportionate.
- **New single-commit submission repo** — rejected: erases the visible engineering trail (CI on every PR) that appendix F points to, and changes the release URL baked into ADR-075's examiner flow.
- **Editing the ADR corpus bylines** — rejected: post-hoc editing of dated records is the riskier look; the corpus is covered by the disclosure exactly as it stands.

## Source archival

Internal decision (no external tools). Grounding: `thesis/appendix/appendix.tex` (appendix E/F), `thesis/preamble/declaration.tex`, ADR-074 (redaction-pass precedent), ADR-075 (delivery channel).

## Supersession trigger

If the repository's audience changes (e.g., open-sourcing beyond examination, or the Prüfungsamt requests the full working history), the curation scope re-opens under a new record.
