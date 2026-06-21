---
trigger: always_on
description: CRITICAL — `run_command` invocations with embedded newlines in any quoted argument WILL CRASH the Windsurf integrated terminal on macOS. No heredocs, no `-c`/`-e` with multi-line bodies, no `git commit -m` with embedded newlines. Multi-line content goes to a file via `write_to_file` first, then is consumed via `-F` / `-f` / `script.py` / etc. Use `/commit` for any git commit with body content.
sources_consulted:
  - portfolio-website/.windsurf/rules/no-terminal-oneline-scripts.md (own, primary)
  - Sprint 0 retro friction note (`~/Projects/cascade-system/retros/sprint-0.md`) — heredocs ban observed in practice
  - User operating constraints (Sprint 1 handoff prompt) — explicit re-statement of the ban
  - Sprint 1 hardening session — direct observation of the authoring Cascade violating ADR-012 within minutes of writing it (rules-as-text are insufficient; forcing function required)
adapted_for:
  - L1 global rule (was L2 portfolio-only)
  - Cascade tool model: `run_command` vs `write_to_file` / `edit` separation made explicit
  - Stack-agnostic: dropped `pnpm`-specific exception phrasing; replaced with "short well-defined commands" criterion
  - Promoted to crash-level language (was "fragile") after observed in-session violation; pairs with `/commit` workflow as a forcing function
---

# No terminal one-line scripts

> **HARD CONSTRAINT (Windsurf macOS)**: `run_command` invocations with **embedded newlines inside any quoted argument string** WILL CRASH the integrated terminal. Not "may". Not "sometimes". **Will.**
>
> This is not a style guideline. It is a runtime hazard. The crash is silent for the agent and visible to the user.

## Pre-flight checklist (run before EVERY `run_command` call)

Before issuing any `run_command`, self-check:

1. **Does the `CommandLine` contain a literal newline character inside a quoted string?**  → if yes, **STOP**. Refactor: write the multi-line content to a file via `write_to_file`, then pass the file path to the command.
2. **Is the command a heredoc (`<< 'EOF' … EOF`, `<<-EOF`, etc.)?** → if yes, **STOP**. Use `write_to_file`.
3. **Is the command an inline interpreter with a non-trivial body (`python -c "…"`, `node -e "…"`, `bash -c "…"`)?** → if yes, **STOP**. Write a script file and run it.
4. **Is the command a `git commit` with body paragraphs?** → if yes, invoke `/commit` workflow (the forcing function) — do NOT call `git commit` directly.
5. **Otherwise**: short single-line command, no embedded newlines → proceed.

Treat this checklist as a runtime invariant. Skipping it caused a terminal crash during Sprint 1 hardening (the authoring Cascade authored ADR-012 forbidding embedded-newline `-m`, then issued one within minutes — the user caught it; the agent did not).

## Banned patterns (will crash or corrupt)

- **Heredocs** as content delivery: `cat > file.md << 'EOF' … EOF` — use `write_to_file`.
- **Inline interpreters with multi-line bodies**: `node -e "…"`, `python -c "…"`, `bash -c "…"` containing newlines or non-trivial logic.
- **Any quoted argument with embedded newlines** — including `-m "subject\n\nbody"`, `--message "…\n…"`, `--body "…\n…"`, etc. The shell may parse it; the Windsurf integrated terminal on macOS will not.
- **Long inline strings** as `run_command` `CommandLine` — multi-line strings, JSON blobs, templated code.
- **Pipes/chains exceeding ~3 stages** that aren't well-known idioms — refactor into a script.
- **One-off shell scripts** written to `/tmp/` — write to a tracked path, run, clean up.

## Allowed patterns (safe in Windsurf macOS terminal)

- Simple package-manager calls: `pip install <pkg>`, `npm i <pkg>`, `uv add <pkg>`, `gh issue list`, etc.
- Project-defined targets: `make <target>`, `npm run <script>`, `pytest <flags>`.
- Filesystem commands with clear single intent: `ls`, `mv`, `cp`, `mkdir`, `cat <file>` (read), `rm <specific-path>`.
- Short pipelines for inspection: `gh issue list --json … | jq …` (well-known idiom, ≤3 stages).
- **Single-line `git commit -m "subject"`** — no body, no newlines. Safe.
- **`git commit -F /tmp/<file>.txt`** — body content lives in a file. Always safe. Canonical for any commit with a body.

## Git commit messages

Per ADR-012 (revised). The **canonical** path for any commit with body content is the **`/commit` workflow** (`~/.codeium/windsurf/workflows/commit.md`). It writes the message to a tracked-then-cleaned tempfile and invokes `git commit -F` — bypassing the crash hazard entirely.

**Decision tree**:

| Commit shape | Pattern |
|---|---|
| Subject only (≤72 chars, no body) | `git commit -m "subject"` |
| Subject + body | **Invoke `/commit` workflow** (writes to file, commits with `-F`) |
| Many short paragraphs, all single-line | `git commit -m "subject" -m "para 1" -m "para 2"` (each `-m` value MUST be single-line — no embedded newlines) |
| Long structured body (lists, code blocks) | `/commit` workflow only |

**FORBIDDEN** (will crash Windsurf integrated terminal on macOS):

```sh
# ✗ Embedded newline inside a single -m
git commit -m "subject

body paragraph"

# ✗ Embedded newline inside one of multiple -m flags
git commit -m "subject" -m "para 1
- bullet
- bullet"

# ✗ Heredoc as commit message body
git commit -F - << 'EOF'
subject

body
EOF
```

The crash is silent for the agent and disrupts the user's terminal session. Do not gamble on "this shell handled it last time" — Windsurf's integrated terminal on macOS will not.

## Rationale

- **Auditability** — tracked files diff cleanly; terminal scrollback doesn't.
- **Reusability** — a command in a file can be re-run; an inline blob is single-use.
- **Crash-safety** — the Windsurf integrated terminal on macOS crashes on embedded-newline quoted arguments. This is the dominant constraint; everything else is secondary.
- **Tool reliability** — Cascade's `write_to_file` / `edit` tools handle multi-line content correctly; `run_command` quoting does not.
- **Forcing function** — `/commit` workflow + this rule together make the safe path the only path for non-trivial commits. Rules-as-text alone proved insufficient (Sprint 1 hardening: authoring Cascade violated ADR-012 minutes after writing it).
- **Sprint 0 evidence** — the meta-repo's bootstrapping required this discipline. See `~/Projects/cascade-system/retros/sprint-0.md`.

This rule supersedes any ad-hoc memories on heredoc usage and is the canonical statement.

Source: portfolio-website (own). Promoted to L1 + strengthened to crash-level language during Sprint 1 hardening, paired with `/commit` workflow as forcing function. See ADR-012.
