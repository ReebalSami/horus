---
trigger: always_on
description: Evidence over claims. Verify changes by running the project's lint/build/test/demo before declaring success. "Should work" without evidence is a violation.
sources_consulted:
  - portfolio-website/.windsurf/rules/make-sure-it-works.md (own, primary — heavily adapted)
  - portfolio-website/.windsurf/rules/local-demo-before-push.md (own, secondary — spirit absorbed)
  - obra/superpowers/skills/verification-before-completion (MIT, refs/superpowers/skills/verification-before-completion) — closest upstream analog; adapted naming and scope
  - mattpocock/skills (browsed, no direct rule analog)
adapted_for:
  - L1 global rule (was L2 portfolio-only with stack-specific commands)
  - Windsurf rule frontmatter
  - Stack-agnostic: project-defined verification commands, not hardcoded `make lint/build`
  - Absorbed `local-demo-before-push.md` so we have one rule for "verify before declaring done", not two
---

# Make sure it works

**Evidence over claims.** Before declaring any change complete:

- **Run the project's verification commands.** What "verification" means is project-defined: tests, linter, type-checker, build, manual demo, or a combination. Each L3 template documents its own (e.g., python-ml-uv → `pytest` + `ruff` + `mypy`; future nextjs-app → `pnpm lint` + `pnpm build` + browser demo).
- **Document outcomes.** Commit messages or chat summaries name what was verified and the result. "Tests pass" without specifying which is insufficient.
- **No "should work" without evidence.** If you cannot run verification (sandbox limitation, missing tooling, etc.), say so and provide the exact command for the user to run.
- **No hardcoding** of paths, IDs, credentials, constants, or user-facing strings. Use config files, environment variables, or i18n keys per the L3 template's conventions.
- **For UI work**: validate at expected breakpoints; check theme variants if the project supports them. Specific breakpoints/themes are L3-defined.
- **Iterate until acceptance criteria are met.** "It compiles" is a checkpoint, not a finish line.

This rule reinforces the legacy `~/.windsurf/rules.md` entry "Always verify before assuming". No conflict.

Source: portfolio-website (own — distilled from `make-sure-it-works.md` + `local-demo-before-push.md`; portfolio-specific verification commands removed). Upstream cross-check: superpowers `verification-before-completion` confirms the principle is well-established.
