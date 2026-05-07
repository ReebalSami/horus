# HORUS

**H**ybrid **O**CR-free **R**eading & **U**nderstanding **S**ystem.

Master's thesis project (FH Wedel, SS 2026): privacy-first document intelligence for German tax/accounting professionals via local vision-language models. Documents stay inside the firm; the analyst keeps full audit-trail visibility.

## Why HORUS?

**Backronym**: **H**ybrid **O**CR-free **R**eading & **U**nderstanding **S**ystem.

**Symbolic anchor**: Horus is the Egyptian falcon-headed god of vision and kingship. The **Eye of Horus** — the *wedjat* — is one of antiquity's most enduring symbols of perception, protection, and restoration. Vision-language models *see* documents holistically without an OCR transcription step; the mythology maps directly to the central methodological commitment of this thesis (OCR-free, VLM-first; see brainstorm v2 §1 + §3.1, ratified at `docs/decisions/ADR-003-brand-naming-horus.md`).

**Why not the alternatives?** `vellum` / `hearth` / `aegis` / `codex` were all evaluated and rejected — see `docs/decisions/ADR-003-brand-naming-horus.md` for the elimination tree.

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
│   └── horus/              # main package (kebab `horus` = snake `horus`; no split needed)
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

Default: `StdoutTracker` in `src/horus/tracking.py` prints metrics to stdout. Swap for MLflow / W&B / TensorBoard / Aim / DVC / Neptune by implementing the `Tracker` Protocol — see `tracking.py` docstring for the swap pattern.

### Config layer (B8=C)

Default: stdlib `@dataclass Config` in `src/horus/config.py`. Extend or replace with Hydra / pydantic / argparse / typer — see `config.py` docstring for swap patterns.

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

Bootstrapped via `/start-project` from L3 template `python-ml-uv` at `~/.windsurf/templates/python-ml-uv/` (Vertical B output of the cascade-system meta-repo, milestones M2B.1–M2B.8). HORUS identity ratified at `docs/decisions/ADR-003-brand-naming-horus.md` (M2D.1). Tool-decision discipline + source archival ratified at `docs/decisions/ADR-001-tool-decision-discipline.md` and `ADR-002-source-archival.md` (M2D.2). Project handoff context: `cascade-system/docs/handoffs/cascade-d-master-thesis.md` + kickoff plan `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md`.

## License

Proprietary — all rights reserved (thesis project). Source code, models, datasets, and derived artifacts are not licensed for external use, redistribution, or commercial adaptation. The thesis text itself is governed by FH Wedel's Prüfungsordnung.
