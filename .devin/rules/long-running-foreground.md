---
trigger: always_on
description: Long-running commands (model downloads, VLM inference smokes, big test suites, package wheel downloads, dataset clones) stay in the **foreground** with **continuous live output visible**. Pairs with `no-terminal-oneline-scripts` (crash-safety) — this rule covers **observability**. Do NOT background-then-poll, suppress to `/dev/null`, pipe to a buffered consumer (`tail -N`), or hide progress bars. The user needs real-time signal to distinguish working-vs-hung commands. Concise law lives in `~/.codeium/windsurf/memories/global_rules.md`; this file is the full rationale + checklist + patterns.
sources_consulted:
  - `~/Projects/horus/docs/retros/m2d.5-pilot-13-cohort-harness.md` — pilot-13 cross-cutting learning #1 (2026-05-18) on log-streaming
  - `~/Projects/horus/.windsurf/handoffs/horus-adr-009-prb-202605141837-coding.md` — user-stated rule (2026-05-14) on foreground + live output during ADR-009 cohort smokes
  - `~/Projects/cascade-system/queue/pending-review.md` 2026-05-13 entry "token-economy / no-status-polling" — sibling principle on token economics of polling
  - `~/Projects/cascade-system/docs/rules/no-terminal-oneline-scripts.md` — sibling crash-safety rule; this rule's structure mirrors it
  - `~/Projects/cascade-system/docs/rules/make-sure-it-works.md` — evidence-over-claims discipline; foreground streaming IS the evidence channel during long ops
adapted_for:
  - L1 global rule (was project-local observation across 3+ HORUS sessions)
  - Cascade tool model: `Blocking` parameter semantics + `WaitDurationSeconds` semantics made explicit
  - Stack-agnostic: applies to model downloads (HF/git-lfs/wget), inference smokes (Transformers/MLX/Ollama/vLLM), training runs, large test suites, `uv add`/`pip install`/`npm install` wheel downloads, dataset acquisition
  - Promoted from project-local learning to L1 always-on after observed across multiple HORUS milestones (M2D.5 step 3 dataset acquisition, M2D.5 step 5 ADR-009 PR(b) cohort smokes, M2D.5 step 7 pilot-13 cohort sweep)
---

# Long-running foreground (observability discipline)

> **PRINCIPLE**: Long-running commands stay in the **foreground** with **continuous live output**. The user needs real-time signal to distinguish working-vs-hung. Background-then-poll burns tokens, suppresses signal, and produces silent-failure modes.
>
> **Sister rule to `no-terminal-oneline-scripts`**. That rule covers **crash-safety** (don't crash the terminal). This rule covers **observability** (don't blind the user during long ops). Different forcing functions; both always-on.

## Scope — what counts as "long-running"

A command is **long-running** if any of:

1. Wall-clock duration exceeds the user's tolerance for "just wait" (typically ≥ 60 seconds of non-interactive output)
2. Downloads bytes from a remote (HF, GitHub LFS, `uv add`, `pip install`, `npm install`, `wget`, `git clone` of a large repo)
3. Loads / unloads ML model weights (Transformers `from_pretrained`, MLX-VLM `load`, Ollama `pull`, vLLM `serve`)
4. Runs ML inference at non-trivial batch (cohort smokes, eval sweeps, fine-tuning, evaluation loops)
5. Compiles or builds at non-trivial scope (`make build` of a large project, full test suite, type-check + lint + build)
6. Operates on > 100 MB of data (rasterization, image batch processing, dataset preprocessing)

A command is **NOT** long-running (and this rule doesn't apply) if:

- Single-file edit / read / grep
- `git status`, `git log -n 5`, `git diff <single-file>`
- Short package-manager status checks
- Single-file test execution

## Pre-flight checklist (run before EVERY long-running `run_command`)

1. **Is this long-running by the criteria above?** → if yes, treat per the rest of this checklist.
2. **Will the command print streaming progress (`flush=True` Python prints, `tqdm`, `huggingface-cli` progress bars, `wget` progress, `pip install` per-wheel lines, `pytest -v`, etc.)?** → if yes, run **`Blocking=true`** so the user sees real-time output.
3. **Is the command genuinely fire-and-forget (e.g., start a dev server that runs indefinitely)?** → if yes, `Blocking=false` is appropriate but **DO NOT poll-every-N-sec** to check status; use `WaitDurationSeconds=0` for instant snapshots only when downstream orchestration needs to know.
4. **Am I about to pipe through a buffering consumer (`tail -N`, `head`, `awk`, `grep` without `--line-buffered`)?** → if yes, **STOP**. Buffering defeats streaming. Either drop the pipe or add `stdbuf -oL` / `--unbuffered` / `--line-buffered` flags.
5. **Am I about to suppress output (`> /dev/null`, `2>/dev/null`, `&> /dev/null`)?** → if yes, **STOP**. Suppression silences the only diagnostic channel during long ops.
6. **Otherwise**: foreground + streaming → proceed.

## Banned patterns (silence the user)

- **Background-then-poll-every-N-sec**: `run_command Blocking=false` followed by repeated `command_status WaitDurationSeconds=60`. Burns tokens for no signal — if the user wants to see progress, they look at the terminal directly. The `command_status` returns "Status: RUNNING" which conveys nothing.
- **Suppression to `/dev/null`**: `wget ... > /dev/null`, `python -m huggingface_hub download ... 2>/dev/null`. Silences download progress bars, model-loading messages, training step logs. If the command fails silently, the user has no signal.
- **`tail -N` / `head -N` on streaming output**: `pytest -v | tail -50`, `make build | head -100`. These tools buffer all input before emitting. The user sees nothing for the entire duration, then a wall of output at the end.
- **Hiding progress bars**: `HF_HUB_DISABLE_PROGRESS_BARS=1`, `--quiet`, `--silent`, `-q` flags on long downloads. The progress bar is THE signal; silencing it defeats the purpose.
- **`tee` without line-buffering**: `command | tee log.txt` — `tee` by default flushes per-block, not per-line; for long ops use `stdbuf -oL tee log.txt` or `command | tee --output-error=warn log.txt` to retain line-level flushing.

## Allowed patterns (preserve signal)

- **`Blocking=true` for observable long ops**: `make cohort-smoke MODEL=qwen3-vl-4b CFG=configs/pilot-13.yaml` — runs in foreground, user sees per-page rasterization + per-model load + per-invoice extraction in real time.
- **`Blocking=false` + `WaitDurationSeconds=0` for genuine fire-and-forget**: starting a dev server (`make serve`, `ollama serve`, `uvicorn ...`) — user wants control returned immediately, not progress.
- **Parallel-background for independent network ops**: per the 2026-05-13 token-economy observation — kick off N independent downloads with `Blocking=false`, do non-network work in parallel, snapshot with `WaitDurationSeconds=0` only when orchestration needs the result. Different from polling — this is async dispatch, not synchronous wait-and-recheck.
- **`stdbuf -oL` / `--unbuffered` / `--line-buffered`**: when piping is unavoidable, line-buffer to preserve streaming. Examples: `python -u script.py`, `stdbuf -oL python script.py | tee log.txt`, `grep --line-buffered ERROR | tee errors.txt`.
- **Explicit logging to file PLUS terminal**: `command 2>&1 | tee /tmp/log.txt` — captures evidence in a file (for post-hoc inspection / commit attachment) AND retains terminal streaming.

## Why

### User-stated need (verbatim from system memory)

> *"User wants to SEE real-time progress and tell working-vs-hung. The smokes in ADR-009 PR(b) (olmOCR-2-7B, Qwen3-VL-4B, PaliGemma-2-3B, Molmo-7B-D, PaddleOCR-VL, GLM-OCR) and the GLM-OCR escalation chain (vLLM / Ollama / SGLang attempts) are all in-scope."*

### Empirical evidence from HORUS sessions

- **M2D.5 step 5 (ADR-009 PR(b))**: 6 VLM cohort smokes, each 5–60 minute wall time. Background-then-poll would have produced 30+ `command_status` calls × 60-second waits = ~30 minutes of "Status: RUNNING" with zero signal. Foreground-streaming surfaced model-load failures (PyDataType incompat in MLX, chat-template missing in transformers, ROCm/CUDA-only deps in vLLM) within seconds of occurrence; user redirected the runner immediately.
- **M2D.5 step 7 (pilot-13 cohort sweep)**: 26 invoices × 7 models = 182 inference calls. Streaming per-tuple output let the user observe per-model F1 trend in real-time and catch the MONEY-field FN pattern before the sweep completed.
- **M2D.5 step 3 (dataset acquisition)**: parallel-background works for independent `huggingface-cli download` invocations (5 datasets in parallel) — but EACH process individually must stream its progress. Suppressing per-process progress to `/dev/null` defeats the parallel-background pattern (no signal of which dataset is hung).

### Token economics

Polling `command_status WaitDurationSeconds=60` while a command runs for 30 minutes wastes ~30 tool calls × token cost per call. Foreground execution costs 1 tool call. The token saving is non-trivial for hours-scale work. The `bidirectional-learning-pipe` queue entry "2026-05-13 — token-economy / no-status-polling" is the canonical capture.

### Silent-failure prevention

A command that fails after 15 minutes of `2>/dev/null` produces only an exit code. Streaming output surfaces the failure cause (HTTP 403, OOM, disk full, network timeout, model-load error) inline. The user can intervene without re-running. This is operationally critical for hours-scale autonomous Cascade work.

## Interaction with other rules

- **`no-terminal-oneline-scripts`** — sibling. That rule prevents terminal crashes (embedded newlines in quoted args); this rule prevents silent operation. Both always-on. Both have pre-flight checklists. Both have banned + allowed patterns.
- **`make-sure-it-works`** — foreground streaming IS the evidence channel for "did it work". When asked to verify, the streamed output (model loaded, batch progressed, test passed) is the proof. Without streaming, "make-sure-it-works" reduces to checking exit codes — necessary but insufficient.
- **`know-your-hardware`** — long-running ops on M1 Pro 16 GB hit memory/thermal limits in patterns that only show in streaming output (page faults, swap thrashing, fan ramp). Suppression hides hardware-saturation signals.
- **`bidirectional-learning-pipe`** — the queue entry that motivated this rule's promotion (M2D.5 step 3 token-economy + pilot-13 retro learning #1) is the canonical example of a project-local observation crossing the L2-to-L1 threshold.
- **`anti-laziness-core-principles`** — "no shortcuts" applies: background-then-poll-every-60s is the shortcut that looks like activity but produces no value.

## Migration / propagation

- **Existing projects**: this rule is `always_on` in `global_rules.md` from the moment of L1 promotion. No per-project workspace copy required for enforcement.
- **New projects via `/start-project`**: step 6a copies all long-form rules into `<project>/.windsurf/rules/`; this rule will be included automatically.
- **Existing per-project workspace `.windsurf/rules/` directories** (e.g., HORUS): manually copying the long-form file there is optional and provides workspace-level long-form for project-specific Cascade sessions. The always-on enforcement does not require it.

## Provenance

- **Promotion trigger**: post-pilot-13 rethink session 2026-05-19 (Cascade D), per `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §3 + §4 + §8 Phase 3 + Q9=A user-confirmed shape (sibling rule, not extension of `no-terminal-oneline-scripts`).
- **Authoring session**: the same session as `chore/redact-supervisor-and-reframe-meeting` Phase 1+2 (ReebalSami/horus PR #43 + ReebalSami/cascade-system PR #105).
- **Pre-promotion observations**: HORUS sessions 2026-05-13 (M2D.5 step 3 dataset acquisition), 2026-05-14 (ADR-009 PR(b) cohort smokes), 2026-05-18 (pilot-13 retro).
- **Acceptance bar**: rule lands in `~/Projects/cascade-system/docs/rules/` + `~/Projects/cascade-system/docs/rules/INDEX.md` updated + concise law section added to `~/.codeium/windsurf/memories/global_rules.md` (≤ 6000 chars total budget preserved by compressing `l1-canonical-paths` section).

## Revisit triggers

- If empirical evidence emerges that foreground-streaming is operationally infeasible for a category of commands not yet considered (e.g., a future runner that genuinely requires fire-and-forget across hours) — revisit at `@sprint-review` to add an exception class.
- If the `command_status` tool gains a "stream-since-last-call" mode that materially changes the token-economics calculation — revisit.
- If Windsurf's `run_command` semantics change (e.g., `Blocking=true` no longer surfaces real-time output in the IDE terminal) — supersession candidate.
