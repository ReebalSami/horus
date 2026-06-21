---
trigger: model_decision
description: In python-ml-uv projects, `uv` is the exclusive package manager + Python launcher. Three clauses (a) **No `pip install`** — use `uv add`; (b) **No bare `python script.py`** — use `uv run python script.py` (resolves the project venv from the cwd, immune to fresh-terminal venv-state mess); (c) **No mixed package managers** — `poetry` / `pipx` / `conda` / `pyenv` / `pip-tools` are forbidden in derived projects. Apply when seeing any package install / Python invocation / venv keyword.
sources_consulted:
  - cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md (own) — B7=A spec; clause (a) + (b) + (c) wording derives from carry-forward line 162
  - https://docs.astral.sh/uv/ (browsed via `context7 /astral-sh/uv`) — `uv add` / `uv run` / `uv sync` / `uv lock` semantics; loose-pinning pattern for dev deps
  - cascade-system/docs/rules/no-terminal-oneline-scripts.md (own) — single-line shell discipline applies to `uv run` invocations too
  - cascade-system/docs/rules/no-half-knowledge.md (own) — read-the-docs-first applies to uv subcommand semantics
adapted_for:
  - L3 workspace-deployed rule — lives at `~/.windsurf/templates/python-ml-uv/rules/uv-discipline.md`; deployed to consumer projects via `/start-project` step 6b
  - `model_decision` trigger — fires only on package-management / Python-invocation intent (saves context budget)
  - Renamed from `use-uv-not-pip` (original handoff §3 M2B.5 candidate) per brainstorm B7=A carry-forward line 294 — the broader `uv-discipline` framing covers (a) no-pip, (b) uv-run, (c) no-mixed-pkg-mgrs uniformly
---

# uv-discipline (L3, python-ml-uv)

> **CONSTRAINT**: This project is uv-managed end-to-end. Three clauses below cover the most common Python-tooling foot-guns. The `pyproject.toml` `[build-system]` uses `uv_build`; `pyproject.toml` deps + `[dependency-groups]` are uv-managed; `uv.lock` is committed.

## Clause (a) — No `pip install`. Use `uv add`.

When adding a runtime dependency:

```sh
# WRONG
pip install requests

# RIGHT
uv add requests
```

When adding a dev-only tool:

```sh
# WRONG
pip install --dev pytest

# RIGHT
uv add --dev pytest
# or, equivalently for the dev group:
uv add --group dev pytest
```

Why: `pip install` mutates the active venv but does **not** update `pyproject.toml` or `uv.lock`. The dep silently exists locally but vanishes for any consumer who runs `uv sync` from the lockfile. `uv add` updates both pyproject + lockfile + venv atomically.

## Clause (b) — No bare `python script.py`. Use `uv run python script.py`.

When invoking Python:

```sh
# WRONG
python src/my_pkg/train.py
python -m my_pkg.train

# RIGHT
uv run python src/my_pkg/train.py
uv run python -m my_pkg.train
```

When invoking installed tools:

```sh
# WRONG
pytest tests/
mypy src/

# RIGHT
uv run pytest tests/
uv run mypy src/
# or via Makefile (which wraps these):
make test
make typecheck
```

Why: bare `python` resolves to whatever `python` is on PATH at that moment — the active venv (if `source .venv/bin/activate`-d), the system Python (if not), `pyenv shim` (if pyenv is in the chain), etc. Fresh terminals + Cascade subprocess invocations are particularly prone to "I thought I activated the venv" mistakes. `uv run` resolves the project venv from cwd deterministically every time, immune to shell state.

## Clause (c) — No mixed package managers.

In a uv-managed project, do **not** introduce:

- **`poetry`** — its `pyproject.toml` schema overlaps but conflicts with uv's `[tool.uv]`; mixing breaks lockfile coherence
- **`pipx`** — for project-internal tools, use `uv add --group dev <tool>` + `uv run <tool>`. `pipx` is for system-wide CLI tools, not project deps.
- **`conda` / `mamba`** — different env model; mixing confuses both
- **`pyenv`** (for active Python selection) — uv installs + manages Python versions via `uv python install`; pyenv shim layer adds confusion
- **`pip-tools`** (`pip-compile`, `pip-sync`) — uv ships its own resolver + lockfile

Exception: `pyenv` is fine for *user-global* Python installation if uv hasn't been told to manage Python versions yet. Once uv manages Python (`uv python install 3.14`), pyenv shim should not interfere with uv-resolved invocations (it doesn't because `uv run` uses its own discovery).

Why: each of these has its own dep-graph + env model + lockfile (or no lockfile). Mixing produces silent divergence between what `uv.lock` claims and what's actually installed. Reproducibility (B8 brainstorm goal) requires single-source-of-truth.

## Activation triggers (`model_decision` keywords)

The rule activates on:

- "pip install" / "pip uninstall" / "pip-tools" / "pip-compile"
- "python script.py" / "python -m" / "python3" (bare invocation)
- "venv" / ".venv" / "activate" / "source bin/activate"
- "poetry" / "pipx" / "conda" / "mamba" / "pyenv shell"
- "lockfile" / "lock" + dependency context
- "package manager" / "install dependency"

## When the rule does NOT fire

- Pure `src/` editing without invocation
- Documentation / README discussing tooling conceptually
- The user is teaching uv conceptually
- Discussion of upstream library internals (e.g., "torch's setup.py")

## Examples

**Fires** — *"Add torch to the project"*: respond `uv add 'torch>=2.5'`; not `pip install torch`.

**Fires** — *"Run the smoke test"*: respond `uv run pytest tests/test_smoke.py` (or `make test`); not `pytest tests/test_smoke.py`.

**Fires** — *"Set up a clean Python 3.14 venv"*: respond `uv python install 3.14 && uv venv` (uv-managed); not `pyenv install 3.14.0 && python -m venv .venv`.

**Does not fire** — *"What does PEP 735 do?"*: explanation, no installation intent.

## Source

L3 workspace rule for python-ml-uv. Spec: `cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md` §B7=A; renamed from handoff §3 M2B.5 candidate `use-uv-not-pip` per brainstorm carry-forward line 294. Deployed via `/start-project` step 6b. Pairs with `notebook-discipline` (sibling L3 rule).
