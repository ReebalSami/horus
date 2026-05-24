---
trigger: always_on
description: Never `gh issue create` in a repo linked to a GitHub Project v2 board without simultaneously adding the new issue to that Project. Pre-flight checks the project link; on miss, the command MUST include `--project "<title>"` OR be paired immediately with `gh project item-add` (no other tool calls in between). Bare `gh issue create` in project-tracked repos is forbidden. Paired with `/issue-create` workflow as the forcing function and `@sync-github` as the retroactive reconciler.
sources_consulted:
  - cascade-system/docs/decisions/ADR-036-issue-project-assignment-rule.md (own) — codifies this rule + paired workflow + propagation
  - cascade-system/docs/decisions/ADR-018-release-discipline-cluster.md (own) — pattern precedent (rule + active forcing function beats rule-alone for high-blast-radius invariants)
  - cascade-system/docs/decisions/ADR-013-commit-workflow-forcing-function.md (own) — earliest application of the rule+workflow pairing pattern
  - cascade-system/docs/rules/branch-and-pr-required.md (own) — structural template for the "discipline backstop + forcing function" rule shape
  - ~/.codeium/windsurf/skills/sync-github/SKILL.md (own) — retroactive reconciler that pairs with this rule for orphan recovery
  - GitHub CLI `gh project` + `gh issue create --project` flag docs (browse) — canonical add-at-create syntax
  - Empirical incident, HORUS evidence-base audit follow-up, 2026-05-23 (Cascade D filed #62/#63/#64 via bare `gh issue create`, omitting Project v2 board assignment; user-flagged gap → rule promotion)
adapted_for:
  - L1 always_on rule (paired with workspace propagation via `/start-project` step 6a)
  - Cascade tool model: `gh issue create` is the choke point; rule fires on the intent, workflow orchestrates the resolution
  - Repos WITHOUT a linked Project v2 board: rule no-ops; plain `gh issue create` remains allowed (graceful fallback for non-tracked repos)
  - User's project topology: one Project v2 per repo (1:1 mapping; cached project number once known per repo)
  - Pairs with `/issue-create` workflow forcing function (mirrors `no-terminal-oneline-scripts` ↔ `/commit` and `branch-and-pr-required` ↔ `@release-manager` pairings)
---

# issue-project-assignment-required

> **HARD CONSTRAINT**: `gh issue create` in a repo linked to a GitHub Project v2 board is forbidden unless the new issue is simultaneously added to that Project. The add MUST happen at creation time (`--project "<title>"` flag) or as the immediate next tool call (`gh project item-add`) with no other tool calls in between.
>
> This is not a hygiene preference. It is a tracking-integrity invariant. Orphan issues (created but never added to the board) silently drift out of the project's planning view — they exist on the repo but are invisible to `@sync-github`, milestone planning, and any kanban-style triage. The drift surfaced empirically during the HORUS evidence-base audit follow-up (Cascade D, 2026-05-23): three issues filed via bare `gh issue create` sat off-board until user-flagged.

## Pre-flight checklist (run before EVERY `gh issue create` command)

Before issuing any `gh issue create`, self-check:

1. **Does this repo have a linked GitHub Project v2 board?** Resolve once per session and cache:

   ```sh
   gh project list --owner <owner> --format json
   ```

   Look for a project whose title matches the repo's roadmap convention (e.g., `<repo> roadmap`, `<project-name>`). Cache the project number for the remainder of the session.

2. **If NO Project exists** → plain `gh issue create` is fine. Skip the rest of this checklist.

3. **If a Project EXISTS** → the create command MUST satisfy one of:
   - **Atomic path (preferred)**: `gh issue create --project "<title>" --title "<title>" --body-file <body-file> --label <labels>` — single command, atomic on the GitHub side.
   - **Pair path (fallback when `--project` is unavailable or fails)**: `gh issue create ...` immediately followed by `gh project item-add <num> --owner <owner> --url <issue-url>` as the very next tool call. No other tool calls (ls, read_file, status checks, etc.) may interpose between the two.

4. **Verify** the issue appears on the Project board after creation:

   ```sh
   gh project item-list <num> --owner <owner> --format json | grep '"number":<issue-number>'
   ```

   (Optional; `/issue-create` workflow step 5 automates this.)

## Banned patterns

- `gh issue create ...` alone, in a repo where `gh project list --owner <owner>` returns a matching Project (verified or assumed by reasonable repo-convention inference)
- `gh issue create ...` followed by unrelated tool calls (read_file, ls, edit, gh issue view) before the `gh project item-add` follow-up — breaks the "immediate pair" contract and risks the user moving on while the orphan persists
- Skipping the pre-flight `gh project list` check on the assumption that the repo has no Project — verify, don't assume; the call is cheap (sub-second)
- Filing multiple issues in a batch, then "I'll add them to the project at the end" — by then the user has acted on the chat, and the orphan window is open

## Allowed patterns

- `gh issue create --project "<title>" --title "..." --body-file /tmp/<file>.md --label <labels>` — the canonical atomic form
- `gh issue create --title "..." --body-file /tmp/<file>.md ...` immediately followed in the SAME tool-call batch (or as the literal next sequential call) by `gh project item-add <num> --owner <owner> --url <issue-url>` — the pair form
- Plain `gh issue create ...` in repos verified to have NO linked Project board (rare but valid)
- `/issue-create` workflow invocation — handles the resolve+create+verify cycle deterministically

## Forcing function

`/issue-create` workflow is the active forcing function. It:

- Resolves the active repo's owner + name via `gh repo view --json owner,name`
- Calls `gh project list --owner <owner>` to detect a linked Project v2
- If found: invokes `gh issue create --project "<title>" ...` (atomic path)
- If not found: invokes plain `gh issue create ...` (no-op for the Project step)
- Verifies the result via `gh project item-list <num> --owner <owner>` when applicable
- Surfaces the issue URL + project URL to the user

The skill body inlines the pre-flight checklist. Refuses to proceed with bare `gh issue create` when a Project is detected.

`@sync-github` is the retroactive reconciler (paired safety net). It scans for orphan issues (created on the repo but not present on the Project board) and adds them with a flag, surfacing the gap for review. The rule + workflow handles the forward path; `@sync-github` handles the backward sweep.

The rule + workflow + reconciler triangle mirrors the proven patterns:
- `no-terminal-oneline-scripts` rule + `/commit` workflow (ADR-013 — earliest pairing precedent)
- `branch-and-pr-required` rule + `@release-manager` skill + `/branch-*` workflows (ADR-018 — full-cluster pairing precedent)

## Rationale

- **Tracking integrity**: every issue belongs in the planning view from the moment of creation; orphans drift silently
- **Auditability**: the project board IS the planning artifact; off-board issues bypass it
- **Empirical evidence**: the rule was promoted in response to a verified user-flagged gap (HORUS audit follow-up, Cascade D, 2026-05-23, #62/#63/#64 filed off-board)
- **Discipline backstop**: rule + forcing function pattern proven elsewhere (ADR-013 + ADR-018); rules-as-text alone proved insufficient on the same blast-radius class of invariants
- **Graceful fallback**: repos without a Project board are unaffected; the pre-flight `gh project list` check is sub-second and idempotent
- **Solo-dev compatibility**: the user is the only planner; the Project board exists for their own visibility, not for collaborator coordination — making orphan drift even MORE costly (the planner is the only one who can spot the gap)

## Interactions with other rules

- **`no-terminal-oneline-scripts`**: issue bodies with multi-paragraph content MUST be passed via `--body-file <path>` (never `--body "...\n\n..."` with embedded newlines). The `/issue-create` workflow always uses `--body-file`. See ADR-013.
- **`branch-and-pr-required`**: every PR opened in a Project-v2-tracked repo follows the same atomicity principle for PR-to-Project linkage (separately handled by `@release-manager`'s `/branch-push-and-pr` step).
- **`make-sure-it-works`**: after the create-and-add pair, verify the issue appears on the board (cheap GH API call). Don't claim "filed" without confirming both surfaces (repo + project) reflect the issue.
- **`document-as-you-go`**: the addition of THIS rule is itself an ADR (ADR-036) per the rule. Self-applied at promotion time.
- **`bidirectional-learning-pipe`**: the gap that triggered this rule was a Sprint 2 learning. Captured to `queue/pending-review.md` would be the standard path, but in this case the user surfaced it directly during the audit follow-up → L1 promoted without a queue intermediate (acceptable shortcut when the user explicitly initiates the promotion).

## Consequences when violated

If a bare `gh issue create` slips through in a Project-tracked repo (this rule is a soft enforcer; only branch-protection-style hard gates exist server-side):

1. The orphan issue exists on the repo but not on the Project board
2. `@sync-github` reconciler catches it on next invocation and surfaces the gap
3. The Cascade immediately runs `gh project item-add <num> --owner <owner> --url <issue-url>` to remediate
4. Capture the violation to `queue/pending-review.md` if it represents a NEW failure mode not already covered by this rule

The deleted-branch incident from the HORUS evidence-base audit (Cascade D, 2026-05-23) is the precedent: three issues sat off-board until user-flagged. The remediation pattern there (`gh project item-add` per issue) is the canonical recovery.

This rule supersedes any ad-hoc memories on project-board hygiene and is the canonical statement.

Source: ADR-036 (2026-05-23). Authored alongside `/issue-create` workflow as the release-discipline-style cluster. Promoted from a user-flagged gap during the HORUS evidence-base audit follow-up (#62/#63/#64 filed off-board on the `horus roadmap` Project v2; remediated via `gh project item-add` per issue).
