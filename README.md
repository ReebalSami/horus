# your-pkg

Python ML / research project bootstrapped from the `python-ml-uv` L3 template.

## Post-bootstrap rename (do this first)

1. Rename `src/your_pkg/` to your project's snake_case package slug (e.g., `src/my_project/`).
2. Update `pyproject.toml` `[project] name = "..."` to your project's kebab-case slug (e.g., `my-project`).
3. Update import statements in `tests/test_smoke.py` (or run `make test` and follow failures).
4. Run `make install && make test` to confirm the bootstrap works end-to-end.

A future `/start-project` enhancement will automate this token substitution. See `cascade-system/queue/pending-review.md` for the L1-promotion entry.

## Toolchain

- **Python**: 3.14+ (pinned in `.python-version`)
- **Package manager**: `uv` (Astral) — exclusive; no `pip` / `poetry` / `conda` mixing per the `uv-discipline` rule
- **Build backend**: `uv_build`
- **Linter / formatter**: `ruff`
- **Type checker**: `mypy` (default; `pyrefly` opt-in fast path documented below)
- **Test runner**: `pytest`
- **Notebook discipline**: `jupytext` (write `.py`, convert to `.ipynb` for execution) + `papermill` (parameterized execution); no `.ipynb` checked in by default per the `notebook-discipline` rule

## Quick start

```sh
make install                                  # uv sync (creates .venv, installs deps + dev group)
make test                                     # uv run pytest
make lint                                     # ruff check + format check
make format                                   # ruff format + ruff check --fix
make typecheck                                # mypy src tests
make experiment NB=experiments/baseline.py    # jupytext + papermill flow
```

## Project layout

```
.
├── pyproject.toml          # uv-managed; PEP 735 [dependency-groups]
├── Makefile                # convenience targets
├── .python-version         # 3.14
├── .env.example            # UV_TORCH_BACKEND=auto + future env vars
├── .gitignore              # Python + ML + uv flavored
├── README.md               # this file
├── src/
│   └── your_pkg/            # rename to your package slug post-bootstrap
│       ├── __init__.py
│       ├── seeding.py      # set_global_seed (stdlib + optional torch/numpy)
│       ├── tracking.py     # Tracker Protocol + StdoutTracker (B4=C tracker-agnostic)
│       └── config.py       # @dataclass Config placeholder (B8=C stdlib-only)
├── tests/
│   ├── __init__.py
│   └── test_smoke.py       # validates package imports + seeding determinism + tracker + config
├── experiments/            # jupytext-paired .py files; papermill runs them
│   └── .gitkeep
└── docs/                   # universal layout from _shared/scaffold/ (see docs/structure.md)
```

## Deferred decisions (consumer-customizable)

The python-ml-uv template is deliberately under-opinionated on contested tooling. Choose your project's flavor for each:

### PyTorch installation (B3=A)

Default: `UV_TORCH_BACKEND=auto` in `.env.example` autodetects CPU / MPS / CUDA at install time. Works for solo + macOS contexts.

For Linux GPU clusters (extras-based pinning):

```toml
# pyproject.toml additions
[tool.uv.sources]
torch = [
    { index = "pytorch-cpu", marker = "platform_system != 'Linux'" },
    { index = "pytorch-cu130", marker = "platform_system == 'Linux'" },
]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true
```

See `https://docs.astral.sh/uv/guides/integration/pytorch/` for the full pattern.

### Experiment tracker (B4=C)

Default: `StdoutTracker` in `src/your_pkg/tracking.py` prints metrics to stdout. Swap for MLflow / W&B / TensorBoard / Aim / DVC / Neptune by implementing the `Tracker` Protocol — see `tracking.py` docstring for the swap pattern.

### Config layer (B8=C)

Default: stdlib `@dataclass Config` in `src/your_pkg/config.py`. Extend or replace with Hydra / pydantic / argparse / typer — see `config.py` docstring for swap patterns.

### CI scaffold (B10=C)

Not shipped. To add GitHub Actions:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: make test
      - run: make lint
      - run: make typecheck
```

### Type checker fast path (B1 follow-on)

Default: `mypy`. For Astral's `pyrefly` (Beta as of 2025-11; ~10–60× faster):

```sh
uv add --dev pyrefly
uv run pyrefly src tests
```

Add a `pyrefly` Makefile target if it becomes load-bearing.

## Project lifecycle

This project follows a phase chain defined in `.windsurf/phases.yaml` (copied from the `python-ml-uv` L3 template):

```
literature → brainstorm → spec → issues → experiment → implement → writeup
```

Run a phase via `/run-phase <name>` from a Cascade conversation in this project's directory.

## Provenance

Bootstrapped via `/start-project` from L3 template `python-ml-uv` at `~/.windsurf/templates/python-ml-uv/`. Brainstorm spec at `cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md` (M2B.1 milestone).
