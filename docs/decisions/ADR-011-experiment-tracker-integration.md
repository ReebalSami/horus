# ADR-011 — Experiment-tracker integration: MLflow + `Tracker` Protocol extension + Bundle 4 L3 promotion

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-16 |
| **Milestone** | `experiments-validated` (pilot #13's tracker-substrate sub-issue) |
| **Authored by** | Cascade D (issue #16 implementation session; plan `~/.windsurf/plans/horus-adr-011-mlflow-tracker-integration-d01298.md`) |
| **Issue** | `ReebalSami/horus#16` (sub of `#13`) |
| **Supersession trigger** | (1) MLflow's full package becomes incompatible with a future Python pin (HORUS is on 3.14 today; MLflow 3.12.0 supports it) — fallback to `mlflow-skinny` (tracking client only) or another tracker that meets the privacy + Apache 2.0 + local-self-hosted constraints; OR (2) the SQLite-backed file-system layout becomes unworkable at corpus-scale (when pilot #13's harness logs ≥ 10⁵ runs across the German/English/Korean corpora) — migrate to a Postgres backend without changing the tracker abstraction; OR (3) the `Tracker` Protocol's 7-method shape proves to leak MLflow-specific semantics into other backends (W&B run-grouping diverges from MLflow's `nested=True`, etc.) — refactor the Protocol with concrete evidence from the second-tracker integration attempt; OR (4) Apache 2.0 license terms change in a way incompatible with thesis publication (extremely unlikely; the precedent ratifies via ADR-005 / ADR-007) — re-evaluate among similarly-licensed alternatives |

## Context

The HORUS thesis (`docs/prompts/stages/02-brainstorm.md` v2 §5.5 + §10) evaluates **local vision-language models** for German B2B invoice extraction. Pilot #13 ([ReebalSami/horus#13](https://github.com/ReebalSami/horus/issues/13)) builds the first data loop: 10–50 synthetic invoices + the on-disk ZUGFeRD corpus → VLM extraction → XML-grounded F1 (per ADR-010) → per-field error heatmap (per brainstorm v2 §5.5).

To make pilot #13 reproducible + comparable across cohort members (ADR-009's 10 models) + auditable by the thesis examiner, every run needs a tracker that records:

- **Run identity**: unique run-id; parent/nested grouping for cohort sweeps
- **Hyperparameters**: model_id, max_tokens, prompt template, ordering, seed
- **Metrics**: load time, extract time, output length, per-field F1, per-field precision/recall
- **Structured data**: per-field error heatmap (a dict, not a scalar metric)
- **Categorical metadata**: hardware fingerprint, git commit SHA, experiment stage, cohort label
- **Artifacts**: full extracted text, per-fixture transcript, the dummy heatmap → eventually the real heatmap
- **Reproducibility**: deterministic seed visible alongside every run

### What is already half-built

Two prior decisions partially landed this work; this ADR finishes the job:

- **ADR-004 (Bundle 2, 2026-05-10)** ratified Pydantic Settings + PyYAML as the config-library. The schema in `src/horus/config.py` already includes an `MLflowConfig` sub-model (`experiment_name`, `run_tags`, `tracking_uri`) — but no concrete tracker class consumes it.
- **`src/horus/tracking.py`** (`python-ml-uv` template scaffold, M2D.5 step 1) already ships a 3-method `Tracker` Protocol + `StdoutTracker` default. Its module docstring explicitly anticipates an MLflow swap, but the swap was deferred to "per-project decision" — i.e., this ADR.
- **`docs/prompts/stages/02-brainstorm.md` v2 §10**: *"Experiment tracking | MLflow | Already wired in POC."* The brainstorm names MLflow as the indicated choice based on the pre-thesis prototype work that ships at the thesis substrate.

### What is novel in this ADR

Three additions that no prior decision covered:

1. **The concrete `MLflowTracker` class** delegating 1:1 to MLflow's native API.
2. **The `Tracker` Protocol extension** (3 → 7 methods: `start_run`, `end_run`, `log_dict`, `set_tag` added). The two new lifecycle methods (`start_run` + `end_run`) support **nested runs** for cohort sweeps; `log_dict` + `set_tag` are load-bearing for pilot #13's **per-field heatmap** (structured non-scalar data) and **hardware fingerprint** (categorical metadata), respectively. The original 3-method shape cannot express these without convention-based flattening that would couple consumers to MLflow-specific encoding tricks.
3. **`horus-config-discipline` Bundle 4 closure** by promoting the project-local L2 rule's generic content to the `python-ml-uv` L3 template (`~/.windsurf/templates/python-ml-uv/rules/config-discipline.md`). Future python-ml-uv projects bootstrapped via `/start-project` auto-receive the generic version; the HORUS L2 rule stays as-is (additive promotion, not supersession — see ADR-009 retention principle).

### Acceptance-criteria reconciliation (issue #16)

The issue body's criterion 4 (*"Test run logs successfully to local MLflow with all expected fields (run-id, hyperparams, **F1**, **error heatmap**, hardware fingerprint, deterministic seed)"*) is over-prescribed for this PR's scope. **F1 and a real error heatmap** require pilot #13's eval-harness sub-issue, which is downstream of this ADR (per ADR-010 §"What this ADR does NOT decide": *"F1 / error-heatmap metric computation: lives in pilot #13 step 5 + step 6 (downstream)"*).

What this PR *can* honestly demonstrate: the extended Protocol + MLflowTracker class are **schema-capable** of logging all listed fields — including a dummy heatmap via `log_dict(...)` proving the structured-data path works end-to-end. Pilot #13's harness replaces the dummy values with real per-field F1 computed against the CII XML ground-truth (per ADR-010); no further tracker changes will be needed.

## Current-state survey (2026-05-16)

| Component | Where | Ratified by | Role for this issue |
|---|---|---|---|
| `mlflow>=3.7` (Python, PyPI) | `pyproject.toml` (added this PR; uv-resolved to `mlflow==3.12.0`) | This ADR | **Primary tracker package.** Full `mlflow` (not `mlflow-skinny`) — the brainstorm §10 "Already wired in POC" anchor implies UI usage; skinny drops the `mlflow ui` server. License: Apache 2.0. |
| `MLflowConfig` sub-model | `src/horus/config.py:39-59` | ADR-004 (Bundle 2) | **Schema substrate.** Fields: `experiment_name: str` (required), `run_tags: dict[str, str]` (default empty), `tracking_uri: str \| None` (default None = MLflow's auto-default). Pydantic-validated at boot. |
| `Tracker` Protocol + `StdoutTracker` | `src/horus/tracking.py` (extended this PR) | python-ml-uv template scaffold (M2D.5 step 1) | **API surface.** Was 3 methods (`log_metric` / `log_param` / `log_artifact`); extended to 7 (`+ start_run` / `end_run` / `log_dict` / `set_tag`). `StdoutTracker` extended with nesting depth + new methods. `DEFAULT_TRACKER` preserved for backward compatibility. |
| `MLflowTracker(cfg: MLflowConfig)` class | `src/horus/tracking.py` (new this PR) | This ADR | **Concrete impl.** Delegates every Protocol method 1:1 to MLflow's native API (`mlflow.start_run`, `mlflow.log_metric`, …). Lazy mlflow imports inside each method body keep `StdoutTracker` users zero-dep. |
| `get_tracker(cfg: ExperimentConfig \| None) -> Tracker` | `src/horus/tracking.py` (new this PR) | This ADR | **Factory.** `cfg is None → StdoutTracker()`; `cfg given → MLflowTracker(cfg.mlflow)`. Removes the `if/else` boilerplate that would otherwise repeat at every consumer call site. |
| `Run` dataclass | `src/horus/tracking.py` (new this PR) | This ADR | **Typed run handle.** Frozen dataclass: `run_id: str \| None` + `run_name: str \| None`. Yielded from `start_run`'s context manager so callers can reference the run identity (e.g., echo it into the transcript for cross-tool traceability). |
| `configs/cohort-smoke.yaml` | `configs/cohort-smoke.yaml` (new this PR) | This ADR | **Smoke lock file.** Committed YAML config consumed by `make cohort-smoke ... CFG=configs/cohort-smoke.yaml`. Anyone re-running the smoke gets identical run shape. Per `horus-config-discipline`. |
| `scripts/cohort_smoke.py` `--cfg PATH` flag | `scripts/cohort_smoke.py` (extended this PR) | This ADR | **Cohort wire-up.** New optional flag; when set, the cohort sweep is wrapped in a parent MLflow run with one nested run per model. When omitted: current behavior preserved exactly (no MLflow import, no behavioral diff). |
| Hardware-fingerprint helper | `scripts/cohort_smoke.py::_get_hardware_fingerprint` (new this PR; inline) | This ADR | **Tag-value source.** Captures CPU brand (macOS via `sysctl machdep.cpu.brand_string`), RAM (via `sysctl hw.memsize`), OS + release, Python version, PyTorch + MPS availability. Slash-joined single-line tag. Per `know-your-hardware` rule. |
| `mlflow.db` (SQLite tracking backend) | repo root, gitignored | MLflow 3.7+ default | **Backend store.** MLflow 3.7+ changed its default backend from filesystem (`./mlruns/`) to SQLite (`sqlite:///mlflow.db`). HORUS adopts the new default verbatim. `.gitignore` covers `mlflow.db` + `mlflow.db-journal` (WAL). |
| `mlruns/<experiment_id>/<run_id>/artifacts/` | repo root, gitignored | MLflow 3.7+ default (sqlite backend) | **Artifact store.** MLflow 3.7+ keeps using `mlruns/` as the artifact root when the tracking backend is SQLite (only the metadata moved into SQLite; artifacts stay on the filesystem). `.gitignore` already covered `mlruns/` from the python-ml-uv template scaffold; this PR adds `mlartifacts/` defensively (used only when MLflow server is invoked with `--artifacts-destination`). |

The decision is **substantially overdetermined** by what is already installed and indicated by the brainstorm. The §"Options considered" walk below is preserved for the 5-section discipline mandate per `horus-decision-discipline`, but is honest about the post-hoc-ratification shape — same precedent as ADR-010.

## Options considered

| Option | Stack | License | Outcome |
|---|---|---|---|
| **`mlflow` (Databricks, full package)** | Python (Apache 2.0) | Apache 2.0 | **Chosen as primary tracker — see Decision.** Brainstorm §10 indicates "Already wired in POC". MLflow 3.12.0 (latest stable) installs cleanly on Python 3.14.3 (`mlflow/mlflow#bbf9dec` added 3.14 to CI). 3.7+ default backend is SQLite (`sqlite:///mlflow.db`) — clean local-only deployment, no separate server. Native context-manager + nested-run support maps 1:1 onto the extended Protocol. UI via `uv run mlflow ui` for run comparison. Apache 2.0 license aligns with HORUS's thesis publication path (precedent: ADR-005 factur-x, ADR-007 transformers, ADR-008 docling — all Apache or BSD). |
| `mlflow-skinny` (Databricks, tracking-client-only) | Python (Apache 2.0) | Apache 2.0 | **Considered, rejected as primary.** Skinny ships the tracking client only — no Flask, no SQL backend, no UI server, no scikit-learn / pandas / scipy. Significantly lighter dependency footprint (~20 transitive deps vs ~44 for full). But it lacks `mlflow ui` — the brainstorm §10 anchor implies the user expects to view runs in the MLflow UI (consistent with the prior POC experience), and a thesis-grade run-comparison workflow benefits from the UI's filterable columns. Future supersession trigger (1) reserves the path back to skinny if Python compatibility or footprint becomes the binding constraint. |
| Aim (aimhubio) | Python (Apache 2.0) | Apache 2.0 | **Eliminated by indication — secondary candidate.** Aim is a strong alternative (better-designed UI per `aimstack.io/blog`, ~10× faster than MLflow per `mltraq.com/benchmarks` on synthetic write benchmarks, supports `aimlflow` MLflow-log import for cross-tool migration). But the brainstorm §10 anchor is MLflow + `MLflowConfig` already exists in `src/horus/config.py` + the prior POC's tooling habits → switching to Aim would impose a learning + migration cost that the thesis schedule cannot absorb for marginal benefit. If MLflow becomes untenable per supersession trigger (1) or (3), Aim is the first-line replacement. |
| Weights & Biases (W&B / Wandb Inc.) | SaaS + Python client (MIT client, proprietary server) | MIT (client), proprietary (server) | **Rejected — privacy frame.** HORUS's stakeholder (`AGENTS.md` §1: "documents stay inside the firm; the analyst keeps full audit-trail visibility") forbids uploading experiment metadata + artifacts to a third-party SaaS. Self-hosted W&B Server exists but is proprietary + license-restricted. Local-only is non-negotiable for the German tax/accounting use case. |
| TensorBoard | Python (Apache 2.0) | Apache 2.0 | **Rejected — category mismatch.** TensorBoard is a scalar-metric visualizer (loss curves, histograms, images), not a structured-experiment tracker. Logging hyperparameters works via `add_hparams` but the API is contorted; logging dicts works only through awkward `add_text(tag, json.dumps(d))` patterns. No native nested-run concept. Eliminated by category. |
| ClearML (Allegro AI) | Python (Apache 2.0) + server (Apache 2.0) | Apache 2.0 | **Eliminated by reference.** Supports self-hosted server (good — passes privacy gate), Apache 2.0 (good — passes license gate). But the brainstorm §10 anchor + the existing `MLflowConfig` in `src/horus/config.py` make MLflow the path of least friction; ClearML's heavier server-side dependency footprint (Redis + MongoDB + Elasticsearch) adds infrastructure complexity that thesis-scope work doesn't need. |
| Sacred + Omniboard | Python (MIT) | MIT | **Eliminated by reference — abandoned.** Sacred upstream has been in maintenance mode since ~2022 (last meaningful release 0.8.x, sporadic minor patches; community-managed). Mounting risk for a thesis-substrate dependency. |
| Comet ML | SaaS + Python client | MIT (client), proprietary (server) | **Rejected — same privacy frame as W&B.** |
| Neptune.ai | SaaS + Python client | Apache 2.0 (client), proprietary (server) | **Rejected — same privacy frame as W&B.** |
| DVC Studio (Iterative) | SaaS + DVC CLI | Apache 2.0 (DVC), proprietary (Studio UI) | **Eliminated by reference — different abstraction.** DVC is a data + pipeline versioning tool that also offers experiment tracking via Studio (its hosted UI) or self-hosted; but its tracker is best-fit for git-versioned pipeline executions, not the ad-hoc cohort sweeps + per-model-nested-runs shape HORUS uses. Existing `src/horus/tracking.py` module docstring references DVC as one possible swap target; that statement holds, but the brainstorm indication + MLflowConfig precedent make MLflow the more direct path. |
| Plain JSON in `runs/` (no library) | n/a | n/a | **Below the rigor bar.** Doable but anti-DRY — every consumer reimplements a partial tracker, run-comparison requires custom tooling. The brainstorm v2 §4.1 "scientific-correctness discipline" commitment + the per-field heatmap requirement push toward a real tracker library, not a hand-rolled solution. |

## Decision + integration thoughts

> **Honest light-ADR clause** (per `be-honest-direct-critical`, mirrors ADR-010 §"Decision"): this ADR retroactively ratifies what is already half-built rather than walking an open design space. `MLflowConfig` exists in `src/horus/config.py` since ADR-004 (Bundle 2, 2026-05-10), the `Tracker` Protocol's docstring at `src/horus/tracking.py` explicitly anticipates an MLflow swap, and the brainstorm v2 §10 indicates MLflow as "Already wired in POC". The novel work in this ADR — the concrete `MLflowTracker` class, the Protocol extension to 7 methods, the `--cfg` wire-up on `cohort_smoke.py`, the Bundle 4 L3 promotion — is the *concretization* of decisions previously taken, not a contested choice. The §"Options considered" walk above is documented for the 5-section discipline mandate, not because the decision was genuinely contested.

### Chosen

- **Tracker library**: `mlflow>=3.7` (PyPI). Resolved to `mlflow==3.12.0` at install time (`uv add mlflow>=3.7`, 2026-05-16); 44 transitive packages added (acknowledged in §Consequences Negative).
- **Tracking backend**: SQLite (MLflow 3.7+ default) at `sqlite:///mlflow.db` when `cfg.mlflow.tracking_uri` is `None`. Override via the YAML field or the `HORUS_MLFLOW__TRACKING_URI` env var per pydantic-settings.
- **Artifact store**: `mlruns/<experiment_id>/<run_id>/artifacts/` (MLflow's filesystem-backed artifact root when the tracking URI is SQLite). Gitignored.
- **Protocol shape**: extended `Tracker` Protocol (7 methods total, was 3 — see code module docstring for the canonical usage pattern).
- **Construction**: `MLflowTracker(cfg: MLflowConfig)` directly takes the Pydantic sub-model; `get_tracker(cfg: ExperimentConfig | None) -> Tracker` factory wraps the dispatch.
- **`DEFAULT_TRACKER`**: preserved as `StdoutTracker()` module-level constant — zero-dep imports + tests still work.
- **cohort_smoke wire-up**: optional `--cfg PATH` argparse flag; current behavior preserved exactly when omitted.

### Extended `Tracker` Protocol shape

```python
class Tracker(Protocol):
    def start_run(
        self,
        run_name: str | None = None,
        nested: bool = False,
        tags: dict[str, str] | None = None,
    ) -> AbstractContextManager[Run]: ...
    def end_run(self, status: str = "FINISHED") -> None: ...
    def log_metric(self, key: str, value: float, step: int | None = None) -> None: ...
    def log_param(self, key: str, value: object) -> None: ...
    def log_dict(self, key: str, data: dict[str, Any]) -> None: ...
    def set_tag(self, key: str, value: str) -> None: ...
    def log_artifact(self, path: str) -> None: ...
```

The two new lifecycle methods (`start_run` + `end_run`) mirror `mlflow.start_run` / `mlflow.end_run` exactly — context-manager-returning, `nested=True` for child runs under an active parent, optional `tags` applied atomically at run-creation time. `log_dict` + `set_tag` round out the structured-data + categorical-metadata surface; `log_dict` writes to an auto-named `.json` artifact (filename `key.json` if `key` lacks an extension), `set_tag` overwrites any existing tag with the same key on the active run.

Both Pythonic forms work:

```python
# Context-manager (recommended; auto-ends, exception-safe).
with tracker.start_run(run_name="cohort-sweep", tags={"stage": "smoke"}) as parent:
    for model_id in cohort:
        with tracker.start_run(run_name=model_id, nested=True) as child:
            tracker.log_param("model_id", model_id)
            tracker.log_metric("extract_seconds", t)

# Procedural (long-lived scripts that span function boundaries).
tracker.start_run(run_name="single-run")
tracker.log_param("seed", 42)
tracker.end_run()
```

`StdoutTracker` implements the same Protocol with nesting-indented `BEGIN RUN` / `END RUN` brackets; tests pass against both implementations interchangeably.

### Empirical evidence captured at decision time

Probed during this PR's authoring session (2026-05-16) against the on-disk corpus. Documented here so the design choices (parent-run-wraps-cohort, dummy heatmap on parent, hardware-fingerprint as tag) are traceable to evidence, not preference.

**Probe 1 — End-to-end smoke invocation + transcript shape**:

```text
$ make cohort-smoke MODEL=ibm-granite/granite-docling-258M-mlx \
                    CFG=configs/cohort-smoke.yaml \
                    OUT=/tmp/adr-011-smoke-transcript.txt

Reusing existing data/raw/smoke/EN16931_Einfach.page1.png.
2026/05/16 17:14:12 INFO mlflow.store.db.utils: Creating initial MLflow database tables...
2026/05/16 17:14:12 INFO mlflow.store.db.utils: Updating database tables
2026/05/16 17:14:12 INFO mlflow.tracking.fluent: Experiment with name 'cohort-smoke'
                     does not exist. Creating a new experiment.
[cohort_smoke] MLflow tracker enabled: experiment='cohort-smoke',
               tracking_uri=<MLflow default: sqlite:///mlflow.db>
[1/1] Running ibm-granite/granite-docling-258M-mlx ...
Fetching 13 files: 100%|██████████| 13/13 [00:00<00:00, 271273.39it/s]
```

Transcript file (preserved bit-for-bit from the no-cfg path; the tracker calls are ADDITIVE, not replacement output):

```text
========================================================================
HORUS cohort smoke — ADR-009 §Decision evidence
========================================================================
Image:          /Users/reebal/Projects/horus/data/raw/smoke/EN16931_Einfach.page1.png
Image size:     713,699 bytes
Cohort size:    1 model(s)
Ordering:       transformers-first
MLflow:         enabled (cfg=configs/cohort-smoke.yaml)
Hardware:       Apple M1 Pro / 16 GB RAM / Darwin 25.5.0 / Python 3.14.3 /
                torch 2.11.0 / MPS-available
Commit SHA:     a2106b2

------------------------------------------------------------------------
Model:          ibm-granite/granite-docling-258M-mlx
Category:       Cat 1
Backend:        mlx-vlm
Status:         ok
Load wall-time:        0.87 s
Extract wall-time:     9.78 s
Output length:         3743 chars
... (transcript snippet omitted; full text in mlruns artifact) ...
------------------------------------------------------------------------

========================================================================
SUMMARY: 1/1 cohort models ran to completion
========================================================================
```

**Probe 2 — MLflow run-tree inspection (parent + nested children)**:

```text
$ uv run python /tmp/inspect_mlflow.py

========================================================================
MLflow run inspection — ADR-011 smoke evidence
========================================================================
Experiment: cohort-smoke (ID=1)
Artifact location: /Users/reebal/Projects/horus/mlruns/1
Tracking URI: sqlite:///mlflow.db

------------------------------------------------------------------------
[PARENT] run_name=cohort-sweep
  run_id:    fb96c2c6e7b14c1187f70f6270dc676b
  status:    FINISHED

  Params:
    cohort_size = 1
    image_path = /Users/reebal/Projects/horus/data/raw/smoke/EN16931_Einfach.page1.png
    ordering = transformers-first
    seed = 42

  Metrics:
    n_models = 1.0
    n_ok = 1.0
    total_extract_seconds = 9.780631208996056
    total_load_seconds = 0.871920500008855

  Tags (non-mlflow-internal):
    adr = ADR-011
    cohort = adr-009-pilot-cohort
    commit_sha = a2106b2
    hardware_fingerprint = Apple M1 Pro / 16 GB RAM / Darwin 25.5.0 / Python 3.14.3
                           / torch 2.11.0 / MPS-available
    image_path = /Users/reebal/Projects/horus/data/raw/smoke/EN16931_Einfach.page1.png
    issue = 16
    stage = smoke

------------------------------------------------------------------------
[NESTED CHILD] run_name=ibm-granite__granite-docling-258M-mlx
  run_id:    9b604ef4496442cd86e776c055d521ac
  status:    FINISHED
  parent_id: fb96c2c6e7b14c1187f70f6270dc676b

  Params:
    backend_name = mlx-vlm
    category = 1
    max_tokens = 1536
    model_id = ibm-granite/granite-docling-258M-mlx
    prompt_template = Convert this page to docling.

  Metrics:
    extract_seconds = 9.780631208996056
    load_seconds = 0.871920500008855
    output_len_chars = 3743.0

  Tags (non-mlflow-internal):
    adr = ADR-011
    cohort = adr-009-pilot-cohort
    issue = 16
    stage = smoke
    status = ok
```

**Probe 3 — Artifact filesystem layout (`mlruns/` after the smoke run)**:

```text
mlruns/
└── 1/                                              # experiment ID
    ├── fb96c2c6e7b14c1187f70f6270dc676b/           # PARENT run (cohort-sweep)
    │   └── artifacts/
    │       └── field_f1_dummy.json                 # log_dict output (dummy heatmap)
    └── 9b604ef4496442cd86e776c055d521ac/           # NESTED CHILD (granite-docling)
        └── artifacts/
            └── ibm-granite__granite-docling-258M-mlx_output__4l565pd.txt
                                                    # full model output (3,743 chars)

# Total disk: 696 KB (mlflow.db SQLite) + ~8 KB (artifacts)
```

**Probe 4 — `log_dict` content (the parent-run dummy heatmap)**:

```json
{
  "seller_name": 0.85,
  "invoice_number": 0.95,
  "invoice_date": 0.9,
  "total_amount": 0.88,
  "_note": "Dummy per-field F1 heatmap; demonstrates ADR-011 Tracker.log_dict capability. Pilot #13's eval harness replaces these stub values with real F1 against CII XML ground truth (ADR-010)."
}
```

**Findings**:

1. The full pipeline works end-to-end on Python 3.14.3 + MLflow 3.12.0 + Apple Silicon (M1 Pro / 16 GB / Metal 4).
2. SQLite-backed metadata (`mlflow.db`, ~700 KB after one cohort run) + filesystem-backed artifacts (`mlruns/<exp>/<run>/artifacts/`) is the MLflow 3.7+ default; no `mlflow server` process needed for local-only use.
3. The parent / nested run shape (`mlflow.parentRunId` tag links child to parent) is verified by `mlflow.search_runs` — exactly the UI-collapsible-tree structure the cohort sweep needs.
4. **Hardware fingerprint** (`hardware_fingerprint` tag on the parent run) survives intact across the SQLite encode/decode roundtrip; pilot #13's per-field-F1 heatmap will appear alongside it as a filterable column in the MLflow UI.
5. **Deterministic seed** is logged as a param on the parent run (`seed = 42`); pilot #13's harness reads it from the same YAML lock via `cfg.seed` before any model loads — closes the issue #16 acceptance-criterion "deterministic seed" bullet.
6. The **dummy heatmap** (Probe 4) demonstrates the Protocol-extended `log_dict` round-trip — Python dict → MLflow `artifact_file=...json` → on-disk artifact. Pilot #13 replaces `seller_name`, `invoice_number`, etc. with real per-field F1 values from the CII XML parser (per ADR-010 §"What this ADR does NOT decide").
7. **Model output quality is irrelevant to this ADR**. Granite-Docling-258M-mlx is the smallest/fastest cohort member and is **known-weak** on `EN16931_Einfach.pdf` (per ADR-009 Amendment 1 — the model's German recognition is poor, producing hallucinated tokens like repeated "Bemerkungen" entries). ADR-011's smoke proves the **logging pipeline** works; the **extraction quality** is an ADR-009 / pilot-#13 concern. Picking a stronger model would have made the smoke slower (more wall-time + more disk) without changing what this PR demonstrates.

### Bundle 4 — L3 promotion of `config-discipline` rule

The HORUS L2 rule `~/Projects/horus/.windsurf/rules/horus-config-discipline.md` was pre-committed at authoring time (2026-05-10, Bundle 1) to surface for L3 promotion *"at the next `@sprint-review`"*. This ADR executes the promotion atomically alongside the tracker integration because the two concerns are tightly coupled: the YAML-as-source-of-truth contract is precisely what makes `cohort_smoke.py --cfg configs/cohort-smoke.yaml` work — pilot #13's harness will use the same pattern.

**Mechanics (additive, not superseding)**:

1. **Add** `~/.windsurf/templates/python-ml-uv/rules/config-discipline.md` (new file; generic content with HORUS-specific examples stripped). Future python-ml-uv projects bootstrapped via `/start-project` auto-receive this file copied into `<project>/.windsurf/rules/`.
2. **Keep** `~/Projects/horus/.windsurf/rules/horus-config-discipline.md` as-is. The L2 file remains HORUS's active rule (Windsurf workspace scope); L3 template files are not runtime-loaded.
3. **Documentary status update** on the L2 file's `## L3 promotion plan` section: status flipped from "pre-committed" to "COMPLETE 2026-05-16, see L3 at `~/.windsurf/templates/python-ml-uv/rules/config-discipline.md`".

This resolves the contradiction in the L2's original "supersede the L2 rule" language — supersession-as-deletion would leave HORUS without an active rule (Windsurf does NOT read rules from `~/.windsurf/templates/` at runtime; only `/start-project` reads them at bootstrap-time). The additive shape preserves cross-file references (ADR-004, brainstorm §10, AGENTS.md, cascade-system handoffs all unchanged) and the L2's HORUS-specific examples (Granite-Docling model ID, §14 UStG references) stay where they belong.

### What this ADR does NOT decide

- **Real per-field F1 computation**: lives in pilot #13's eval-harness sub-issue (downstream of ADR-010 + this ADR). The dummy heatmap in Probe 4 is a Schema-capability demonstration only.
- **Real per-field error heatmap**: same — pilot #13 step 5/6.
- **`mlflow ui` deployment posture**: invoking `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db` is documented in `docs/sources/tools/mlflow.md`; not wired into the Makefile (single-user local-dev affordance, not a thesis-substrate deliverable).
- **MLflow autologging hooks** (e.g., `mlflow.pytorch.autolog`): not used. Manual `log_param` / `log_metric` calls are explicit + reviewable; autologging captures things the thesis doesn't need (model topology, optimizer state) and misses things it does need (per-field metrics).
- **Multi-user / remote MLflow server deployment**: future supersession trigger (2) reserves the migration path to a Postgres-backed remote tracking server if pilot #13's corpus-scale work outgrows SQLite.
- **`@run-experiment` skill awareness of `get_tracker(cfg)`**: deferred to a separate `@update-horizontal` follow-up (the skill's L3 template asset lives at `~/.codeium/windsurf/skills/run-experiment/SKILL.md`). Surfaced to `cascade-system/queue/pending-review.md` for the next `@sprint-review`.
- **MLflow on non-macOS hosts** (e.g., CI Linux runners): the `_get_hardware_fingerprint()` helper degrades gracefully on non-macOS (falls back to `platform.machine()` for CPU + drops RAM tag) but the smoke evidence in this ADR is macOS-only.

## Source archival

Per `horus-source-archival` rule + ADR-002, every option in `## Options considered` is archived under `docs/sources/`:

- **`docs/sources/tools/mlflow.md`** — added in this PR. Stub matches Obsidian-clipper format (so a later clip overwrites atomically). Cites the PyPI page (3.12.0), the MLflow docs (`https://mlflow.org/docs/latest/`), the SQLite-default-backend issue (`https://github.com/mlflow/mlflow/issues/18534`), and the Python 3.14 support PR (`https://github.com/mlflow/mlflow/actions/runs/18339096943`).
- **Aim** (browsed, not adopted), **W&B** / **Comet** / **Neptune** (rejected on privacy grounds), **TensorBoard** (rejected on category mismatch), **ClearML** / **Sacred** / **DVC Studio** (eliminated by reference) — not archived per `horus-source-archival` §"When the rule does NOT fire" ("alternatives explicitly considered-and-rejected in the same ADR but not cited as positive evidence").

## Consequences

- **Positive**:
  - Pilot #13 has its tracker substrate: every cohort sweep produces a parent MLflow run + N nested per-model runs with parameters / metrics / artifacts / tags fully captured. The eval-harness sub-issue starts from working infrastructure.
  - **Privacy-frame-aligned**: SQLite + filesystem artifacts mean run metadata + outputs stay on the analyst's laptop. No third-party SaaS upload, no remote server, no network egress. Matches the HORUS stakeholder contract (`AGENTS.md` §1).
  - **Reproducibility-first**: every smoke / pilot run is locked by a YAML config that's committed to git (per `horus-config-discipline`). Anyone with the repo + the corpus can re-run identical run shapes via `make cohort-smoke MODEL=... CFG=configs/<slug>.yaml`.
  - **MLflow 3.7+ SQLite default verified empirically**: the new backend works out-of-the-box on Python 3.14 + Apple Silicon; no migration tooling needed. The pre-3.7 file backend (`./mlruns/*` for metadata) is deprecated upstream (MLflow Issue #18534), so HORUS adopts the new default rather than the deprecated one.
  - **Protocol extension is non-leaky**: every new method maps 1:1 onto an MLflow native call; swapping to Aim / W&B / TensorBoard would require ≤7 new method bodies in a new tracker class (no other code changes).
  - **`StdoutTracker` zero-dep preserved**: tests + bare scripts that don't have an MLflow config continue working with no changes (verified by the existing `tests/test_smoke.py::test_default_tracker_protocol` smoke).
  - **Bundle 4 closed**: the `horus-config-discipline` L3 template version is now available; future python-ml-uv consumer projects auto-receive it.

- **Negative**:
  - **Significant dependency footprint**: `uv add mlflow>=3.7` adds 44 transitive packages (alembic, blinker, cachetools, cloudpickle, databricks-sdk, docker, flask, flask-cors, gitdb, gitpython, google-auth, graphene, graphql-core, graphql-relay, gunicorn, huey, importlib-metadata, itsdangerous, joblib, mako, mlflow-tracing, opentelemetry-api/proto/sdk/semantic-conventions, prettytable, pyasn1, pyasn1-modules, scikit-learn, skops, smmap, sqlalchemy, sqlparse, threadpoolctl, wcwidth, werkzeug, zipp + 3 mlflow* packages). Five existing packages were also downgraded for compatibility (`cryptography 48 → 46`, `protobuf 7.34 → 6.33`, `pyarrow 24 → 23`, `starlette 1.0 → 0.52`). `uv.lock` grows by several hundred lines. `mlflow-skinny` would reduce this to ~20 transitive deps but at the cost of `mlflow ui`. Supersession trigger (1) reserves the path back.
  - **Cohort_smoke.py grew from 340 → 575 lines** (+235 LOC) — adds the `_get_hardware_fingerprint`, `_get_commit_sha`, `_model_slug` helpers + the parent/nested-run wrap + the dummy heatmap log. Still single-file, single-purpose; future Cascade readers will follow the additive shape (`if tracker is not None:` gates) without trouble.
  - **MLflow 3.7+'s SQLite-default backend is non-overrideable from inside the schema**: if a future HORUS deployment wants to stay on the deprecated `./mlruns/` filesystem backend, the YAML's `tracking_uri: file://./mlruns` field is the only knob. Documented in `configs/README.md` (existing) + `docs/sources/tools/mlflow.md` (new).
  - **`mlflow` does not ship `py.typed`**: a new `[[tool.mypy.overrides]]` entry was added (`ignore_missing_imports = true`), matching the existing precedent for factur-x / fpdf / mineru / mlx_vlm. Loose type-check at the MLflow API boundary; tight type-check everywhere else.

- **Neutral**:
  - The `Tracker` Protocol grew from 3 methods to 7. Consumers that only used `log_metric` / `log_param` / `log_artifact` (the original 3) continue working unchanged — the new methods are additive.
  - `mlflow ui` (the run-comparison UI) is invokable on demand via `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db` but is not Makefile-wired (single-user dev affordance, not a thesis deliverable).
  - The dummy heatmap (`field_f1_dummy.json`) is intentionally non-realistic — the field names + scores are placeholders for the real per-field F1 that pilot #13's harness computes. Future readers should not be misled into thinking this PR computes F1.

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate; "Context" / "Current-state survey" / "Options considered" / "Decision + integration thoughts" / "Source archival" / "Supersession trigger" all present).
- **ADR-002** — source-archival convention (this ADR's `## Source archival` cites; `docs/sources/tools/mlflow.md` added).
- **ADR-004** — config library (Pydantic Settings + PyYAML). `MLflowConfig` sub-model defined there is the substrate this ADR's `MLflowTracker(cfg: MLflowConfig)` consumes. Tight coupling; this ADR is the natural Bundle-2 ⇒ Bundle-4 closure.
- **ADR-009 Amendment 1** — the load-bearing forward-pointer that designates the embedded factur-x XML as pilot #13's authoritative ground truth. This ADR's tracker substrate consumes (eventually) the F1 numbers Amendment 1 implies.
- **ADR-010** — ZUGFeRD XML extraction. The CII XML this ADR consumes (via pilot #13's harness) for per-field F1 grounding. The `log_dict` artifact-schema this ADR establishes is the channel by which that F1 lands in MLflow.
- **Cascade-system ADR-013** — `/commit` workflow (multi-line commit bodies routed through tempfile per `no-terminal-oneline-scripts`; used for this PR's commit).
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager` per `branch-and-pr-required`).
- **Future pilot-#13 eval-harness ADR** — consumes this ADR's `MLflowTracker` + `Tracker.log_dict` to record real per-field F1 + real per-field error heatmap against CII XML ground truth.
