---
name: run-experiment
description: Operationalize a single ML / research experiment in a python-ml-uv project: scaffold a jupytext-paired `.py` from intent, set the global seed, choose a tracker, run via `make experiment`, capture results into `docs/prompts/stages/04-experiments.md`. Consolidates B2 (jupytext + papermill) + B4 (tracker-agnostic adapter) + B8 (stdlib seeding) into one operational pass. Domain-agnostic across thesis, paper repro, Kaggle, RL, vision, NLP, eval-harness consumers.
activation: auto
phase: experiment
produces_artifacts:
  - experiments/<name>.py
  - docs/prompts/stages/04-experiments.md
sources_consulted:
  - ~/.codeium/windsurf/skills/grill-me/SKILL.md (own, L1) — interview discipline (one focused question per turn) for intent capture + iteration triage
  - refs/superpowers/skills/test-driven-development/SKILL.md (browsed, MIT) — red-green-refactor cycle weakly informs the experiment iteration loop (predict → run → observe → adjust); not directly adopted (TDD is universal, not ML-specific, per brainstorm B6 rationale; will surface as L1 `@tdd` when first needed)
  - refs/superpowers/skills/executing-plans/SKILL.md (browsed, MIT) — review-execute-verify-report pattern; loosely informs the run-and-capture flow; not directly adopted (different granularity)
  - cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md (own) — B2=A jupytext+papermill, B4=C tracker-agnostic, B8=C stdlib seeding decisions consolidated here
  - ~/.windsurf/templates/python-ml-uv/scaffold/Makefile (own) — `experiment` target chains jupytext → papermill → jupytext-back; this skill orchestrates that target
  - ~/.windsurf/templates/python-ml-uv/scaffold/src/your_pkg/{seeding,tracking,config}.py (own) — B8 seeding + B4 tracker + B8 config building blocks this skill composes at scaffold-write time
  - cascade-system/docs/decisions/ADR-006-skill-frontmatter-schema.md (own) — frontmatter schema
adapted_for:
  - L3 placement at ~/.windsurf/templates/python-ml-uv/skills/run-experiment/SKILL.md (deployed via /start-project step 6b)
  - python-ml-uv phases.yaml `experiment` phase (artifacts: `experiments/`, `docs/prompts/stages/04-experiments.md`)
  - Domain-agnostic per handoff §9 (passes acceptance test for thesis, Kaggle baseline, LLM-eval, vision classifier, RL agent training alike)
  - Composition over re-implementation: orchestrates the existing scaffold's `Makefile` `experiment` target + `your_pkg/seeding.py` + `your_pkg/tracking.py` + `your_pkg/config.py` rather than re-creating their logic
  - jupytext `.py:percent` format scaffold (B2=A) — no `.ipynb` files authored; consumer can convert to `.ipynb` ad-hoc but discipline is `.py` only for git
---

# @run-experiment — operationalize a single ML / research experiment

Discrete invocable capability that scaffolds a jupytext-paired experiment file with seeding + tracking + config wired in, runs it via `make experiment`, captures the result in the experiment-phase artifact, and surfaces "what next" — another iteration, or transition to `implement` phase.

## When to use

- `/run-phase experiment` in a python-ml-uv consumer project (canonical entry per `phases.yaml`)
- Standalone — user says *"let me run an experiment to test X"* in an active python-ml-uv project
- Iterating on a hypothesis after a prior experiment surfaced a follow-up question

## Hard gate

Refuse to proceed if **any** of:

- `your_pkg/` placeholder is unrenamed (project bootstrap is incomplete; route the user to rename per the M2B.3 queue entry)
- `pyproject.toml` `[project] name = "your-pkg"` is unchanged (same — bootstrap incomplete)
- `make install` has never run (no `.venv/`; deps unresolved)
- User has not stated an experiment intent (refuse vague prompts; ask one focused question instead)

## Procedure

### 1 — Capture experiment intent

Ask one focused question:

```
What's this experiment testing? (1–2 sentences. State the hypothesis,
the metric you'll measure, and the expected outcome shape — "loss
decreases below 0.5 within 3 epochs" beats "see if it works".)
```

Also ask for an experiment slug (kebab-case, used in `experiments/<slug>.py` filename).

### 2 — Scaffold `experiments/<slug>.py` from intent

Author a jupytext `.py:percent` file with these cells (use `# %%` markers):

- **Header docstring** — intent verbatim from step 1; expected metric + outcome shape; date authored; pairs to `docs/prompts/stages/04-experiments.md` entry
- **Imports cell** — `from your_pkg import seeding, tracking, config` (uses the renamed package); standard ML imports as relevant
- **Parameters cell** — papermill-injectable; tag as `# %% [parameters]`. Defaults from `config.Config`; consumer overrides via papermill `-p` flags at run time.
- **Setup cell** — `seeding.set_global_seed(seed)`; `tracker = tracking.DEFAULT_TRACKER` (consumer can rebind to their chosen tracker before run)
- **Main cell** — placeholder body with `# TODO: implement experiment` + a comment listing what the cell should do given the intent
- **Results cell** — log final metrics via `tracker.log_metric(...)`; collect any artifact paths via `tracker.log_artifact(...)`; return a `dict` of summary outputs

The scaffold leaves the main cell intentionally minimal — the consumer's actual experiment body is theirs to author. This skill's job is to wire the discipline (seeding, tracker, config) reliably; the science is the consumer's.

### 3 — Pre-flight checks (B8 + B4 sanity)

Before suggesting `make experiment`, verify the scaffolded file:

- `seeding.set_global_seed(...)` is called before any randomness-using code (no exceptions per B8)
- `tracker.log_metric` / `tracker.log_param` is called at least once (otherwise the experiment leaves no record)
- The current tracker is surfaced — if `StdoutTracker` (default) and the user's project README mentions thesis-grade work, warn: *"Still using StdoutTracker; choose MLflow / W&B / TB before promoting to thesis-grade. See `tracking.py` swap pattern."* — non-blocking warning.
- No `.ipynb` files are about to be checked in (B2=A; the `experiment` Makefile target produces `*.executed.ipynb` which is gitignored)

### 4 — Run via `make experiment`

```sh
make experiment NB=experiments/<slug>.py
```

This runs the Makefile's `experiment` target:

1. `uv run jupytext --to ipynb experiments/<slug>.py -o experiments/<slug>.ipynb`
2. `uv run papermill experiments/<slug>.ipynb experiments/<slug>.executed.ipynb` (with the parameters injected if user passed any)
3. `uv run jupytext --to py:percent experiments/<slug>.executed.ipynb -o experiments/<slug>.executed.py`
4. cleanup of the intermediate `.ipynb`

Surface stdout / stderr verbatim. Report exit code. If non-zero: propose next action (read the traceback in `<slug>.executed.py` cells, fix, re-run).

### 5 — Capture results into the phase artifact

Append to `docs/prompts/stages/04-experiments.md` (create with header on first invocation). Each experiment gets a numbered entry:

- **Header** — `## NN — <slug>` + date + status (`successful` / `failed` / `inconclusive`)
- **Hypothesis** — verbatim from step 1
- **Setup** — seed + key params + tracker choice + brief commit SHA reference
- **Result** — final metric values; 2–3 sentence narrative; reference to the `<slug>.executed.py` artifact for full trace
- **Next** — does this answer the hypothesis? Open follow-up questions? (informs whether to iterate or transition)

### 6 — Surface "what next"

Ask one focused question:

```
Result captured. Next:
1. Iterate (new experiment slug, refined hypothesis)
2. Same hypothesis, different params (re-run via papermill -p ...)
3. Transition to `implement` phase (results converged enough to build for real)
4. Pause (capture state; resume later)
```

User picks. The skill does NOT auto-transition phases — `/run-phase implement` is a separate user invocation.

## Anti-patterns

- **Writing to `notebooks/`** — directory is `experiments/` per B2=A; using `notebooks/` undermines the jupytext discipline.
- **Auto-committing `*.executed.py` outputs** — those are gitignored; the experiment's lasting record is the `04-experiments.md` artifact, not the executed file.
- **Skipping the seeding pre-flight** — B8 is non-negotiable; an unseeded experiment is theatrical.
- **Editing `.ipynb` files directly** — B2=A: jupytext `.py:percent` only; `.ipynb` is a transient build artifact during `make experiment`.
- **Domain-specific scaffold body** — the placeholder main cell must NOT contain RL-specific / vision-specific / NLP-specific framing; consumer fills it per their domain.
- **Auto-transitioning phases** — `experiment → implement` is the consumer's call, not this skill's.

## Termination

`@run-experiment` ends when:

- Experiment ran successfully + result captured in `04-experiments.md` + user picked next action. **Or**
- Experiment failed + traceback surfaced + user decided to fix-and-retry or pause. **Or**
- User cancels at any focused-question gate → no experiment file written.

## Provenance

See frontmatter `sources_consulted`. Spec: `cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md` §B2=A + §B4=C + §B8=C consolidated. Issue: M2B.4 (`ReebalSami/cascade-system#78`). Pairs with `@literature-review` (sibling L3 skill). Composes scaffold modules `your_pkg/seeding.py`, `your_pkg/tracking.py`, `your_pkg/config.py` + `Makefile` `experiment` target.
