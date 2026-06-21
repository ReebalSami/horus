---
trigger: model_decision
description: In python-ml-uv projects, experiments live in `experiments/` as jupytext-paired `.py:percent` files (NOT in `notebooks/` and NOT as raw `.ipynb`). Papermill consumes the `.py` for parameterized execution. `.ipynb` is a transient build artifact; the `Makefile` `experiment` target generates / consumes / cleans it. **Cascade-authored content is `.py` only** — `.ipynb` editing is allowed only by explicit user request because `.ipynb` is JSON-encoded and brittle to text-edit tools. `*.executed.ipynb` and `*.executed.py` are gitignored.
sources_consulted:
  - cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md (own) — B2=A is this rule's spec
  - https://jupytext.readthedocs.io/ (browsed) — `.py:percent` format + paired-notebook semantics
  - https://papermill.readthedocs.io/ (browsed) — parameterized execution model
  - cascade-system/docs/rules/no-half-knowledge.md (own) — agent-side `.ipynb` brittleness clause derives from "read fully, edit precisely" — JSON-encoded notebooks defeat this
adapted_for:
  - L3 workspace-deployed rule — lives at `~/.windsurf/templates/python-ml-uv/rules/notebook-discipline.md`; deployed to consumer projects via `/start-project` step 6b (L3 type's rules → `<project>/.windsurf/rules/`)
  - `model_decision` trigger — fires only when notebook / Jupyter / `.ipynb` / experiment-running intent surfaces (saves context budget)
  - python-ml-uv scaffold concrete realization (B2=A): `experiments/` directory; `Makefile` `experiment` target chains jupytext → papermill → jupytext-back; `.gitignore` excludes `*.ipynb` + `*.executed.*`
---

# notebook-discipline (L3, python-ml-uv)

> **CONSTRAINT**: This project follows jupytext + papermill discipline. Experiments are `.py:percent` files in `experiments/`. `.ipynb` is build-artifact-only; agents author `.py`, never `.ipynb`.

## The three clauses

### 1. `experiments/` is the experiment home (NOT `notebooks/`)

The experiment-phase artifacts of this project live in `experiments/<slug>.py` — jupytext-paired `.py:percent` files (cells delimited by `# %%` markers). `notebooks/` does not exist as a convention here; if the consumer wants a `notebooks/` directory for ad-hoc exploration, they create it manually and document the exception.

Why: `.py` files are diffable, scriptable, and survive `git log` / code review. `.ipynb` files are JSON-encoded and produce noisy diffs.

### 2. `.ipynb` is a transient build artifact

The `Makefile` `experiment NB=experiments/<slug>.py` target chains:

```
jupytext --to ipynb experiments/<slug>.py -o experiments/<slug>.ipynb
papermill experiments/<slug>.ipynb experiments/<slug>.executed.ipynb
jupytext --to py:percent experiments/<slug>.executed.ipynb -o experiments/<slug>.executed.py
```

The intermediate `.ipynb` is removed; the persisted artifacts are `<slug>.py` (committed) and `<slug>.executed.py` (gitignored — output, not source).

Why: jupytext gives committable text-based source; papermill gives parameterized execution; the round-trip preserves cell outputs without forcing JSON into git.

### 3. Cascade-authored content is `.py` only

When this rule fires, Cascade authors / edits experiment files as `.py:percent` only. `.ipynb` editing is forbidden unless the user explicitly requests it.

Why: `.ipynb` is JSON; text-edit tools (`edit`, `multi_edit`, `replace_content`) malform the JSON structure on non-trivial edits, breaking the file. The `no-half-knowledge` rule's "read fully, edit precisely" discipline cannot hold against JSON-in-text edits.

If user explicitly asks Cascade to edit a `.ipynb`: surface the brittleness warning, recommend converting via `jupytext --to py:percent` first, edit the `.py`, then convert back. If user insists, comply with explicit risk acknowledgement.

## Activation triggers (`model_decision` keywords)

The rule activates when intent signals notebook / experiment work:

- "notebook" / "jupyter" / "lab" / "ipynb"
- "experiment" / "run experiment" / "training run" / "epoch"
- "papermill" / "jupytext"
- "cell" + execution context (e.g., "run this cell", "the parameters cell")

## When the rule does NOT fire

- Pure `src/` / `tests/` work — no notebook involvement
- README / docs editing
- `pyproject.toml` / dependency management — that's `uv-discipline`'s territory
- The user is teaching / explaining notebooks conceptually (no edit intent)

## Examples

**Fires** — *"Run the baseline experiment"*: dispatch via `make experiment NB=experiments/baseline.py` (per the rule). If `experiments/baseline.py` doesn't exist, scaffold via `@run-experiment` first.

**Fires** — *"Edit the parameters cell of training.ipynb"*: refuse direct `.ipynb` edit; surface the brittleness; offer the convert-edit-convert path. Or invoke `@run-experiment` to author a `.py:percent` replacement.

**Does not fire** — *"What does this `import torch` line do?"*: explanation, no edit intent.

## Source

L3 workspace rule for python-ml-uv. Spec: `cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md` §B2=A. Deployed via `/start-project` step 6b. Pairs with `uv-discipline` (sibling L3 rule) and `@run-experiment` skill (the executor).
