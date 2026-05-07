---
trigger: always_on
description: Read and analyze files fully, never partially. No assumptions from `head`/`tail`/snippets — full file or full reasoning chain.
sources_consulted:
  - portfolio-website/.windsurf/rules/no-half-knowledge.md (own, primary)
  - obra/superpowers/skills/systematic-debugging (MIT, refs/superpowers/skills/systematic-debugging) — full-trace debugging mindset overlaps
  - mattpocock/skills (browsed, no direct rule analog)
adapted_for:
  - L1 global rule (was L2 portfolio-only)
  - Windsurf tool calls (`read_file` with no offset/limit by default)
  - Cross-project, not just code: also applies to docs, configs, ADRs, retros
---

# No half-knowledge

When reading or analyzing any file:

- **Never use `head`, `tail`, or partial reads as a substitute for understanding.** Use `read_file` without offset/limit when the file is small enough; with a generous offset/limit when paginating a large file.
- **Read the entire file before making changes** — at minimum, the section being edited plus its dependencies (imports, types referenced, config consumed).
- **When debugging, trace the full data flow.** Don't assume based on a snippet. Walk: input → handler → side effect → output.
- **When reviewing a component, config, or ADR, read it end-to-end.** Truncated reads produce truncated thinking.

For multi-file investigations, prefer `grep_search` + `code_search` to map first, then targeted full reads of the located files. **Map then read; never partial-read in lieu of mapping.**

This rule reinforces the legacy `~/.windsurf/rules.md` entry "When reading/analyzing files, do it fully and completely". No conflict.

Source: portfolio-website (own). Promoted because partial-read shortcuts have produced wrong code more than once.
