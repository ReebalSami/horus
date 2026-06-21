---
trigger: always_on
description: Never `git push` while on `main` in any repo. All changes flow through `@release-manager` (branch → commits → push → PR → CI → squash-merge → cleanup). Cold-start exception: `git push -u origin main` immediately after `gh repo create` when no upstream exists, working tree has 1 commit, and remote has no `main` branch yet.
sources_consulted:
  - cascade-system/docs/decisions/ADR-018-release-discipline-cluster.md (own) — codifies this rule + paired skill + workflows
  - cascade-system/docs/decisions/ADR-013-commit-workflow-forcing-function.md (own) — pattern precedent (rule + skill/workflow as forcing function)
  - cascade-system/docs/architecture/parked-items-brainstorm.md (own) — §1 + §2 design walking
  - refs/superpowers/skills/finishing-a-development-branch/SKILL.md (MIT) — 4-option model adopted in `/branch-merge-and-cleanup`
  - refs/superpowers/skills/using-git-worktrees/SKILL.md (MIT) — worktree directory priority adopted in `/branch-start --worktree`
  - Sprint 1 hardening session — direct observation of push-to-main happening despite git-flow being "obvious"; rules-as-text proven insufficient
adapted_for:
  - L1 always_on rule (was deprecated `~/.windsurf/rules/` shape; now ADR-014 layer-1 archive + concise `global_rules.md`)
  - Cascade tool model: `git push` is the choke point; rule fires on the intent, skill orchestrates the resolution
  - Solo-dev workflow: branch-protection skip-with-warning when unenforceable (free-tier private repos)
  - Pairs with `@release-manager` skill as forcing function (mirrors `no-terminal-oneline-scripts` ↔ `/commit` pairing)
---

# branch-and-pr-required

> **HARD CONSTRAINT**: `git push` while checked out on `main` (in any repo) is forbidden. All changes to `main` arrive via squash-merged PR through `@release-manager`. Cold-start is the only exception.
>
> This is not a style guideline. It is a discipline backstop. Direct push to `main` already happened during Sprint 1 hardening despite git-flow being "obvious"; rules-as-text alone are insufficient (Lesson 1 from `parked-items-brainstorm.md` §1.1).

## Pre-flight checklist (run before EVERY `git push` command)

Before issuing any `git push`, self-check:

1. **Am I checked out on `main`?** → if yes, **STOP**. Invoke `@release-manager` to start a branch.
2. **Am I pushing a feature/fix branch to its own remote ref?** → safe; proceed.
3. **Am I pushing `main` after a local merge?** → forbidden. Merging-on-`main`-then-pushing bypasses the PR gate. Use `gh pr merge` instead.
4. **Is this a cold-start push?** → see "Cold-start exception" below.

Treat this checklist as a runtime invariant. Skipping it caused the push-to-main incident referenced in ADR-018.

## Cold-start exception

`git push -u origin main` is allowed **only** when **all three** conditions hold:

1. Local branch `main` has no upstream tracking branch (`git rev-parse --abbrev-ref --symbolic-full-name @{u}` exits non-zero)
2. Working tree contains exactly 1 commit ahead of an empty repository (`git rev-list HEAD --count` returns 1)
3. Remote has no `main` branch yet (`gh api repos/:owner/:repo/branches/main` returns HTTP 404)

This covers the `gh repo create` → first commit → first push flow. After the first push, `main` has an upstream and a remote ref; the cold-start window closes; the rule applies in full.

State-based detection (not time-based) per `no-time-estimates`. `@release-manager` step 1 detects cold-start automatically.

## Banned patterns

- `git push` while `git branch --show-current` returns `main` (outside cold-start)
- `git push origin main` from any branch (forces `main` ref update without PR review)
- `git push --force` to `main` (any context)
- Local merge to `main` followed by push (`git checkout main && git merge feature && git push`) — bypasses PR gate
- Auto-staging with `git add -A` followed by direct push (compounds with the rule violation)

## Allowed patterns

- `git push -u origin <feature-branch>` — feature branches push freely
- `git push` while on a feature branch with upstream set — safe
- `gh pr merge --squash --delete-branch <pr>` — the canonical way to update `main`
- The cold-start exception above

## Forcing function

`@release-manager` is the active forcing function:

- Skill body inlines the pre-flight checklist and refuses to proceed when on `main`
- 4 helper workflows (`/branch-start`, `/branch-push-and-pr`, `/ci-watch`, `/branch-merge-and-cleanup`) implement the deterministic procedures
- `/start-project` step 11 sets `main` branch protection on the GitHub side (when enforceable); this rule is the agent-side mirror and remains load-bearing on free-tier private repos where server-side protection cannot enforce.

The rule + skill pairing mirrors the proven `no-terminal-oneline-scripts` + `/commit` pattern (ADR-013).

## Rationale

- **Auditability**: every change to `main` has a PR with description + diff + (when CI exists) check status
- **Reversibility**: a bad PR is reverted via `git revert` of one squash commit; a bad direct-push is harder to clean
- **Discipline backstop**: even if the agent forgets to invoke `@release-manager`, the rule fires
- **Cold-start pragmatism**: the first commit of a brand-new repo cannot have a PR (no main exists yet); explicit exception keeps `gh repo create` flow simple
- **Solo-dev compatibility**: the user is the only reviewer; the PR exists for diff visibility + history granularity, not for human gating
- **Forcing function precedent**: ADR-013's `/commit` proved that pairing a rule with an active skill/workflow beats rules-alone for high-blast-radius invariants

## Interactions with other rules

- **`no-terminal-oneline-scripts`**: `git push` invocations are single-line; safe. Branch-protection setup uses single-line `gh api` per the same rule.
- **`make-sure-it-works`**: `@release-manager` waits for CI green before merge (when CI exists); a passing test suite on a branch with no PR is still discipline drift.
- **`clean-project-structure`**: a clean working tree is required before merge (per ADR-008); `@release-manager` enforces this in `/branch-merge-and-cleanup`.
- **`document-as-you-go`**: PRs that introduce conventions get an ADR before merge.

## Consequences when violated

If a direct push to `main` slips through (this rule is a soft enforcer; only branch protection on the GitHub side is hard):

1. The push-to-main commit stays in history (don't rewrite published `main`)
2. Capture the violation to `queue/pending-review.md` as a Sprint review item
3. The next sprint retro evaluates whether the rule needs strengthening (e.g., add a pre-commit hook)

This rule supersedes any ad-hoc memories on git-flow discipline and is the canonical statement.

Source: ADR-018 (Sprint 2 mid-sprint amendment). Authored alongside `@release-manager` skill + 4 helper workflows + `know-your-hardware` rule as the release-discipline cluster.
