---
source_url: "https://mlflow.org/"
source_title: "MLflow — Open-source platform for the complete ML lifecycle"
source_author: "Databricks / Linux Foundation contributors"
source_date: ""
retrieved_date: "2026-05-16"
extracted_concepts: []
tags: ["mlflow", "experiment-tracking", "python-library", "self-hosted", "sqlite-backend", "primary-tooling", "adr-011"]
archived_pdf: ""
status: stub
---

Open-source platform (Apache 2.0) for the complete ML lifecycle — experiment tracking, model registry, packaging, deployment, GenAI tracing + evaluation. PyPI: `mlflow` 3.12.0 (resolved 2026-05-16; `requires_python>=3.10`, Python 3.14 support added via `mlflow/mlflow#bbf9dec`, in CI since the 3.10–3.12 line).

**Role in HORUS (per ADR-011)** — primary experiment tracker. Consumed by `horus.tracking.MLflowTracker(cfg: MLflowConfig)` via the extended `Tracker` Protocol (7 methods: `start_run` / `end_run` / `log_metric` / `log_param` / `log_dict` / `set_tag` / `log_artifact`). Pilot #13's eval harness reads per-field F1 + per-field error heatmap via the same Protocol surface; cohort sweeps log a parent MLflow run with one nested run per model.

**Package choice — full `mlflow` (not `mlflow-skinny`)**:

- `mlflow` (full): tracking client + Flask-based UI server + SQLAlchemy backend + model registry + Docker integration + LLM tracing. ~44 transitive deps.
- `mlflow-skinny`: tracking client only. ~20 transitive deps. NO `mlflow ui` server.

HORUS picks the full package because the brainstorm v2 §10 "Already wired in POC" anchor implies UI usage (run comparison via `uv run mlflow ui` — single-user dev affordance). Supersession trigger (1) in ADR-011 reserves the path back to `mlflow-skinny` if footprint becomes the binding constraint.

**Backend default change (MLflow 3.7+)** — the platform's default tracking backend changed from filesystem (`./mlruns/*` for metadata) to SQLite (`sqlite:///mlflow.db`). HORUS adopts the new default verbatim: when `cfg.mlflow.tracking_uri` is `None`, MLflow auto-creates `./mlflow.db` (SQLite) at the cwd + keeps using `./mlruns/<exp_id>/<run_id>/artifacts/` as the filesystem-backed artifact root. The pre-3.7 file backend is deprecated upstream (see `mlflow/mlflow#18534`). HORUS `.gitignore` covers `mlflow.db`, `mlflow.db-journal`, `mlruns/`, and (defensively) `mlartifacts/`.

**Key API surface used by HORUS** (all stable since MLflow 2.x, verified on 3.12.0):

- `mlflow.set_tracking_uri(uri)` / `mlflow.get_tracking_uri()` — backend selection
- `mlflow.set_experiment(name)` — experiment scoping
- `mlflow.start_run(run_name=, nested=, tags=)` — opens a run, returns a `ActiveRun` context manager
- `mlflow.end_run(status=)` — ends the active run (`FINISHED` / `FAILED` / `KILLED`)
- `mlflow.log_metric(key, value, step=)` — scalar metric
- `mlflow.log_param(key, value)` — immutable hyperparameter
- `mlflow.log_dict(dictionary, artifact_file)` — JSON/YAML-serialized dict as an artifact (HORUS uses this for the per-field heatmap)
- `mlflow.set_tag(key, value)` — overwriteable categorical metadata (HORUS uses this for hardware fingerprint, commit SHA, status)
- `mlflow.log_artifact(local_path)` — file/directory artifact
- `mlflow.search_runs(experiment_names=[...], output_format='list')` — read-back API used by `tests/test_tracking.py` to verify the full round-trip

**Privacy frame**: SQLite + filesystem artifacts mean all run metadata + outputs stay on the analyst's laptop. No third-party SaaS upload, no remote server, no network egress. Matches the HORUS stakeholder contract (`AGENTS.md` §1: "documents stay inside the firm").

**Documentation entry points**:

- Self-hosting overview: `https://mlflow.org/docs/latest/self-hosting/`
- Backend stores (SQLite vs file vs Postgres vs MySQL): `https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/`
- Python tracking API: `https://mlflow.org/docs/latest/python_api/mlflow.html`
- Releases changelog: `https://mlflow.org/releases/`
- Filesystem backend deprecation notice: `https://github.com/mlflow/mlflow/issues/18534`
- SQLite-as-default PR: `https://github.com/mlflow/mlflow/pull/18497`
- Python 3.14 support: `https://github.com/mlflow/mlflow/actions/runs/18339096943`

**What HORUS does NOT use from MLflow**:

- **Autologging** (`mlflow.pytorch.autolog`, `mlflow.transformers.autolog`, etc.) — manual `log_param` / `log_metric` calls are explicit + reviewable; autologging captures things the thesis doesn't need (model topology, optimizer state) and misses what it does need (per-field metrics).
- **Model registry** — HORUS doesn't promote models to a registry; the substrate is research, not production deployment.
- **Model serving / scoring** — no `mlflow models serve` / `mlflow.pyfunc.spark_udf` paths.
- **Databricks-specific integration** — `databricks-sdk` is a transitive dep but never invoked by HORUS code.
- **MLflow Recipes / pipelines** — HORUS uses jupytext + papermill for experiment orchestration per `notebook-discipline`.
- **LLM tracing + evaluation** (MLflow 3.x additions) — HORUS may revisit at pilot-13+ scale; not used in current substrate.

**Alternative tracker libraries considered + rejected in ADR-011**:

- **Aim** (Apache 2.0; strong secondary candidate; rejected by indication — brainstorm §10 names MLflow + `MLflowConfig` already exists)
- **W&B / Comet / Neptune** (rejected — privacy frame; require SaaS or proprietary server)
- **TensorBoard** (rejected — category mismatch; scalar-only, no nested-run concept)
- **ClearML** (eliminated by reference; heavier server-side dependency footprint)
- **Sacred + Omniboard** (eliminated by reference; upstream in maintenance mode)
- **DVC Studio** (eliminated by reference; pipeline-versioning abstraction differs from per-experiment-run tracking)
- **Plain JSON in `runs/`** (below the rigor bar; anti-DRY)
