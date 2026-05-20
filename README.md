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

## Experiment tracking

HORUS uses MLflow (locked in [ADR-011](docs/decisions/ADR-011-experiment-tracker-integration.md)) for all experiment runs, with **SQLite metadata** (`sqlite:///mlflow.db`) and **filesystem artifacts** (`mlruns/<experiment_id>/<run_id>/artifacts/`). Both paths are gitignored — every run stays on the analyst's laptop, matching the privacy frame in [`AGENTS.md`](AGENTS.md) §1.

### Browse runs in the MLflow UI

```sh
make mlflow-ui                            # http://127.0.0.1:8080 (local-only)
make mlflow-ui MLFLOW_UI_PORT=5001        # override port
```

The target binds to `127.0.0.1` by default (no external network exposure) and uses port `8080` to avoid the documented macOS AirPlay Receiver conflict at MLflow's port-5000 default. Wraps `mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 8080`. Per [ADR-015](docs/decisions/ADR-015-mlflow-ui-makefile-wire.md).

### Run organization (per ADR-014)

Pilot-13 runs use a **parent + nested** hierarchy:

- **Parent run** (`pilot-13-full`) — cohort-pooled metrics, hardware fingerprint, deterministic seed, per-(model, field) heatmap (`cohort_heatmap.png`).
- **Nested runs** (one per `(model, invoice)` tuple) — per-tuple `micro_f1`, per-field outcomes, full-text transcript artifact.

`make pilot-13` is resume-safe via `mlflow.search_runs` filtering on `tags.mlflow.parentRunId`.

### Fast adapter dev loop (per ADR-016)

When iterating on adapter heuristics (`src/horus/eval/adapters.py`'s Layer 1 preprocess + Layer 2 to_predicted_dict), the full `make pilot-13` is overkill — it re-runs the VLM for every (model, invoice) tuple. The fast path re-scores cached transcripts against a candidate adapter:

```sh
# Slow path (~3-5 min for the dev cohort): produce canonical transcripts.
make pilot-13 CFG=configs/pilot-13.yaml,configs/pilot-13-dev.yaml

# Fast path (~5-15 s): re-score saved transcripts with candidate adapter.
make adapter-iterate CFG=configs/pilot-13.yaml,configs/pilot-13-dev.yaml
```

The `adapter-iterate` target compares `src/horus/eval/adapters.py` (canonical baseline) against `src/horus/eval/adapters_candidate.py` (gitignored working file). Output: per-(model, field) Δ TP table + cohort pooled Δ headline.

**Stability self-check** (Google "Rules of Machine Learning" §24): when the candidate file is missing OR byte-identical to baseline, the tool runs baseline-vs-baseline and asserts Δ = 0. Catches non-determinism bugs before they cause silent F1 drift.

**Opt-in MLflow audit trail** (`LOG_MLFLOW=1`): when promoting a candidate to canonical, log 2 nested MLflow runs (`adapter=baseline` / `adapter=candidate`) under an `adapter-iterate` experiment for permanent record:

```sh
make adapter-iterate CFG=configs/pilot-13.yaml,configs/pilot-13-dev.yaml LOG_MLFLOW=1
```

**HARKing guard** (per `brainstorm v2 §2` No-HARKing + NeurIPS Paper Checklist): `configs/pilot-13-dev.yaml` sets `cohort.dev_only: true`, which makes the harness refuse to log to the canonical `pilot-13-full` MLflow experiment. The dev cohort (1 model × 3 invoices) is for iterative tuning ONLY; final thesis-reported F1 numbers come from a `dev_only: false` config scored against the held-out test split (issue #46 substrate).

### Filter by experiment / config

Each run carries originating-config metadata as MLflow tags:

- `tags.adr` — `ADR-011` (cohort-smoke validation), `ADR-013` (page-1 scorer), `ADR-014` (multi-page cohort harness)
- `tags.stage` — `smoke` (pre-pilot validation) vs `pilot-13` (full evidence sweep)
- `tags.cohort` — `adr-009-pilot-cohort` (the 7-working-model substrate)
- `tags.profile` — `EN16931` vs `XRECHNUNG` (per ADR-012 Probe 5 split)

See `configs/pilot-13.yaml` for the canonical tag set.

### Headless inspection

For programmatic post-mortem (no browser):

```sh
uv run python scripts/inspect_pilot_13.py
```

Outputs the per-(model, invoice) F1 grid, per-model aggregate, Probe 1 (MONEY-field TPs on `EN16931_Einfach`), and Probe 2 (XRECHNUNG factur-x route DATE outcomes). See `scripts/inspect_pilot_13.py`.

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

> **Superseded for HORUS by ADR-011 (MLflow with extended `Tracker` Protocol). See `## Experiment tracking` above for the active configuration.** This subsection documents the `python-ml-uv` L3 template's substrate; the project-specific override is one section up.

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
