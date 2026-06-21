---
trigger: model_decision
description: Before implementing any external library, framework, SDK, or CLI tool, consult its current docs via the `context7` MCP rather than relying on training-data memory.
sources_consulted:
  - portfolio-website/.windsurf/rules/context7-and-docs-first.md (own, primary)
  - obra/superpowers (browsed, no direct rule analog)
  - mattpocock/skills (browsed, no direct rule analog)
  - upstream context7 MCP guidance (https://github.com/upstash/context7)
adapted_for:
  - L1 global rule (was L2 portfolio-only)
  - Windsurf model_decision trigger (description-based; activates on library/API implementation tasks)
  - Removed portfolio-specific bits (`21st.dev`, `UI UX Pro Max skill`, design-decision deferrals); kept the cross-cutting principle
---

# Context7 and docs first

Before implementing anything that touches an external library, framework, SDK, CLI tool, or cloud service:

1. **Consult the current documentation via the `context7` MCP** (`mcp2_resolve-library-id` then `mcp2_query-docs`). Knowledge in training data may be stale; library APIs change.
2. **Base implementation on facts and current syntax.** Never guess APIs, type signatures, configuration keys, or CLI flags.
3. **If documentation is unclear, conflicting, or missing, flag it explicitly** rather than fabricating a plausible-sounding solution. "I don't know; here's what context7 returned" is better than confident wrongness.
4. **Cite the doc source** in commit messages or PR descriptions when the behavior is non-obvious — future-you and reviewers benefit.

This rule is **`model_decision`-triggered** (not always-on) — it activates when the conversation involves implementing/configuring an external dependency. Trivial usage of well-known stable APIs (e.g., `Array.map`, `os.path.join`) doesn't require a docs check; novel or version-sensitive features do.

Source: portfolio-website (own, generalized). Promoted because docs-first is the cheapest way to avoid hallucinated APIs.
