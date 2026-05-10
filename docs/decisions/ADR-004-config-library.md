# ADR-004 — Config library: Pydantic Settings + PyYAML

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-10 |
| **Milestone** | M2D.5 step 0 (Bundle 2) — config-discipline architectural foundation |
| **Authored by** | Cascade D resume session (`~/.windsurf/plans/kickoff-cascade-d-resume-3a5374.md`) |
| **Supersession trigger** | (1) HORUS adopts a workflow orchestrator (Prefect/Airflow/Dagster) that mandates its own config layer; OR (2) Pydantic v3 ships breaking changes to `BaseSettings` that incentivise a different architecture; OR (3) Hydra v2 lands native Pydantic-schema validation as first-class AND HORUS gains a multirun-sweep use case the current YAML pattern can't model |

## Context

The HORUS L2 rule `horus-config-discipline.md` (ratified 2026-05-10, Bundle 1) mandates that **every experiment knob lives in `configs/<experiment-slug>.yaml`** — `.py` files contain logic + a Pydantic schema only. The contract: experiments accept ONE papermill parameter `cfg_path: str`; cfg loaded via `ExperimentConfig.from_yaml(cfg_path)`; Pydantic raises on missing/malformed/extra-field/type-mismatch BEFORE any model loads, dataset downloads, or compute is spent. The forcing function is **architectural**: Pydantic-validates-at-boot replaces a separate skill/workflow. (See `cascade-system/docs/handoffs/cascade-d-master-thesis.md` §3.2 + `docs/prompts/stages/02-brainstorm.md` §10 here.)

This ADR ratifies the **specific library choice** that implements the rule's contract. The choice gates all subsequent M2D.5 work: Mustang Project / MLX / Docling tooling installs (M2D.5 steps 2–4) all need experiment configs ready; the first pilot data loop (M2D.5 step 6) will produce the first concrete YAML.

The current `src/horus/config.py` is the L3-`python-ml-uv`-template stdlib `@dataclass` placeholder (`seed=42`, `learning_rate=1e-3`, `batch_size=32`, `num_epochs=1`) — exactly the hardcoded-defaults pattern the discipline rule forbids. The `Makefile` `experiment` target accepts only `NB=`. The `configs/` directory does not exist. This ADR + the code changes that follow it close all four gaps in a single PR.

## Current-state survey (2026-05-10)

Web/`context7` MCP findings for the Python ML config-library decision space, dated today.

### Pydantic v2 ecosystem

- **`pydantic` v2.x** (`/pydantic/pydantic`, MIT, ~692 code snippets, score 83.52) — schema validation library powered by type hints; Rust core (`pydantic-core`) for performance; `BaseModel` + `Field` + `ConfigDict(extra="forbid")` is the canonical fail-fast schema pattern.
- **`pydantic-settings` v2.x** (`/pydantic/pydantic-settings`, MIT, ~95 code snippets, score 84.97) — Pydantic-team-maintained extension; `BaseSettings` + `SettingsConfigDict` adds source-aware loading (env vars, dotenv, secrets dirs, YAML / JSON / TOML); `YamlConfigSettingsSource` for YAML loading (requires `pyyaml`); `settings_customise_sources` classmethod for source-precedence control. Native `extra='forbid'` support.
- **Maintenance**: actively developed (Samuel Colvin et al.); used in production by FastAPI, LangChain, the broader Python ML/data ecosystem.

### Hydra ecosystem

- **`hydra-core`** (`/facebookresearch/hydra`, MIT, ~822 code snippets, score 90.7) — Meta-maintained framework for "elegantly configuring complex applications"; uses dataclass-based `ConfigStore` + `@hydra.main(version_base=None, config_path="conf", config_name="config")` decorator + opinionated `conf/` directory + CLI override syntax (`+db=mysql`, `db.timeout=30`) + multirun (`-m`) for parameter sweeps.
- **`hydra-zen`** (`/mit-ll-responsible-ai/hydra-zen`, MIT, score 77.65) — auxiliary library that eliminates hand-written YAML configs from Hydra projects via dynamically generated dataclass configs. Niche; not relevant here.
- **Maintenance**: actively developed (Meta AI Research / Omry Yadan); broadly used in academic ML.

### OmegaConf

- **`omegaconf`** (`/omry/omegaconf`, BSD-3-Clause, ~228 code snippets) — the underlying engine Hydra wraps. `OmegaConf.structured(MyDataclass)` for typed configs, `OmegaConf.load(...)` for YAML, `OmegaConf.merge(schema, conf)` for schema-validated merge, struct-mode for fail-on-extra-field. Runtime-only validation (no static-type-checker integration on par with Pydantic).
- **Maintenance**: actively developed but at lower velocity than Pydantic.

### stdlib + PyYAML

- **`pyyaml`** (https://pyyaml.org/, MIT) — canonical Python YAML 1.1 parser; `safe_load` is mandatory (never `yaml.load` — arbitrary Python execution risk).
- **`dataclasses`** (Python stdlib) — type-annotated record classes; no validation at instantiation; no fail-fast on extra fields.

## Options considered

| Library | Link | Why considered | Why not chosen / chosen |
|---|---|---|---|
| Pydantic v2 (`BaseModel`) + PyYAML | https://docs.pydantic.dev/latest/ + https://pyyaml.org/ | Minimal-deps Pydantic option; matches `horus-config-discipline` rule body's `BaseModel`/`Field` references literally; 3-line `from_yaml` implementation | Lacks env-var / dotenv / secrets-loading machinery HORUS will need for cloud-baseline API keys (Mistral OCR / Gemini / GPT-5 per brainstorm §8.2) + MLflow tracking URI; layering pydantic-settings on later means a schema migration |
| **Pydantic Settings + PyYAML** | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | Indicated direction in handoff §3.1 + brainstorm §10; Pydantic-team-maintained; `BaseSettings` + `SettingsConfigDict(extra="forbid")` matches the rule's fail-fast contract; native env-var override layer addresses secrets future-proofing; explicit `from_yaml` via `cls(**yaml.safe_load(path))` is idiomatic | **Chosen — see Decision** |
| Hydra (`hydra-core`) | https://hydra.cc/ | Strongest "ML config framework" community brand; CLI-override + multirun ergonomics powerful for sweep-style work; broad academic adoption | `@hydra.main` decorator wants to OWN the entry point — wrapping inside papermill's `cfg_path` parameter contract requires manual `hydra.compose()` and forfeits CLI/multirun (the only differentiating features); `conf/` directory + structured-config opinion adds layout overhead the one-YAML-per-experiment pattern doesn't need; heavier dep tree (`hydra-core` → `omegaconf` → `antlr4-python3-runtime`) for capabilities unused |
| OmegaConf alone | https://omegaconf.readthedocs.io/ | Lighter than Hydra; struct-mode + typed validation; YAML loading native | Runtime-only validation (no Pydantic-mypy-plugin equivalent for static type checking); uses dataclasses, not Pydantic models — would force a rewrite of `horus-config-discipline`'s rule body which explicitly cites `BaseModel`/`Field`; no env-var / dotenv / secrets layer |
| stdlib `dataclasses` + PyYAML manually | https://docs.python.org/3/library/dataclasses.html + https://pyyaml.org/ | Zero new deps beyond `pyyaml` | No validation at instantiation; no fail-fast on extra/missing fields; no type-coercion; defeats the discipline's "Pydantic-validates-at-boot" forcing function — just a YAML dict with `dataclass` syntactic sugar |

## Decision + integration thoughts

**Chosen**: `pydantic-settings` (with `pydantic` + `pyyaml` as transitive runtime deps; `types-PyYAML` as dev dep for mypy).

### Schema shape (initial — extends per experiment per `horus-config-discipline`)

```python
# src/horus/config.py
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLflowConfig(BaseModel):
    """MLflow tracking metadata (sub-model of ExperimentConfig)."""

    model_config = ConfigDict(extra="forbid")

    experiment_name: str = Field(description="MLflow experiment name (e.g., 'granite-pilot').")
    run_tags: dict[str, str] = Field(
        default_factory=dict, description="Tags applied to the MLflow run."
    )
    tracking_uri: str | None = Field(
        default=None,
        description="MLflow tracking URI; None = local file:./mlruns. Override via HORUS_MLFLOW__TRACKING_URI.",
    )


class ExperimentConfig(BaseSettings):
    """Single source of truth for an experiment's knobs.

    Loaded via `ExperimentConfig.from_yaml(cfg_path)` from `configs/<slug>.yaml`.
    `HORUS_*` env vars layer on top (per `pydantic-settings` source ordering)
    for secrets-style overrides (e.g., `HORUS_MLFLOW__TRACKING_URI`).
    """

    model_config = SettingsConfigDict(
        env_prefix="HORUS_",
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=False,
    )

    seed: int = Field(description="Global RNG seed (Python, NumPy, PyTorch via `horus.seeding`).")
    mlflow: MLflowConfig

    @classmethod
    def from_yaml(cls, cfg_path: str | Path) -> "ExperimentConfig":
        """Load + validate config from YAML file. Raises before any compute."""
        path = Path(cfg_path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
```

This is intentionally minimal. **The schema grows per experiment**, not pre-emptively: the first Granite-Docling pilot ADR (M2D.5 step 6) extends the schema with `model: ModelConfig`, `dataset: DatasetConfig`, etc. fields as those concepts solidify. Per `horus-config-discipline` § Examples, "the schema is the spec".

### Integration with HORUS components

- **`.windsurf/rules/horus-config-discipline.md`** (Bundle 1, ratified upstream) — this ADR provides the concrete library that implements the rule's "Pydantic-validates-at-boot" forcing function. The rule body's `BaseModel` / `Field` examples are literal Pydantic API calls now executable.
- **`src/horus/seeding.py`** — `set_global_seed(cfg.seed)` is the canonical pattern at experiment boot; `seed` is the first required field.
- **`src/horus/tracking.py`** — `cfg.mlflow.experiment_name` + `cfg.mlflow.run_tags` flow into the eventual `MLflowTracker` (M2D.6+ scope; current `StdoutTracker` default is unchanged this PR).
- **`Makefile` `experiment` target** — gains `CFG=configs/<slug>.yaml` parameter; passes to papermill via `-p cfg_path "$(CFG)"`. Updated in same PR.
- **`configs/`** — new directory at repo root with a `README.md` documenting the per-experiment YAML naming convention (`<experiment-slug>.yaml`) and pointer to this ADR + `horus-config-discipline` rule.
- **Future `MLflowConfig.tracking_uri`** — when MLflow is added in a later ADR (M2D.5 tooling-install cluster), env-var override `HORUS_MLFLOW__TRACKING_URI` is already wired; no schema change needed.
- **Cloud-baseline API keys (Mistral OCR / Gemini / GPT-5 per brainstorm §8.2)** — when those ADRs land, secrets are added as separate `BaseSettings` submodels with no defaults, populated exclusively from `HORUS_*` env vars (never YAML-tracked); the `pydantic-settings` substrate makes this clean.

### Forward-compatibility constraints this introduces

- All future experiment scaffold authoring (`@run-experiment` skill consumption) MUST use `cfg_path: str` as the sole papermill parameter and dereference everything else from `ExperimentConfig`. The L2 `.windsurf/skills/run-experiment/SKILL.md` was authored before `horus-config-discipline` and references the older `config.Config` + papermill `-p` overrides pattern. Captured to `cascade-system/queue/pending-review.md` for next `@sprint-review` triage; not modified in this PR (separate L3-skill modification scope).
- Schema additions (new fields) trigger a `git commit` inside `src/horus/config.py` referenced by the experiment that needs them; no "config drift" without a code change. Reviewable.
- Env-var precedence over YAML: pydantic-settings defaults to `init_settings` > `env_settings`. Our `from_yaml` passes YAML data as init kwargs — so YAML wins by default. If an experiment ever needs env-var to override YAML (e.g., per-host secret rotation), `settings_customise_sources` is the lever. Documented in the schema docstring; not enabled by default.

### Known limitations

- **Multi-YAML composition** — Hydra's `defaults:` / config-group composition isn't replicated. If HORUS later needs experiment-A-base + ablation-overlay style sweeps, the pattern is: separate YAMLs (no inheritance) or a meta-runner script that emits per-run YAMLs from a template. Acceptable for the M2D.5–M2D.6 pilot scope; revisit at first sweep ADR.
- **CLI overrides** — Hydra's `db.timeout=30` shell-arg override isn't replicated. papermill's `-p cfg_path <new-path>` is the substitute (point to a different YAML). Acceptable.
- **Type stubs for PyYAML** — PyYAML ships without inline type hints; `types-PyYAML` is added as a dev dep so mypy passes without per-import overrides.

## Source archival

Per ADR-002, every option in `## Options considered` is archived under `docs/sources/`:

- `docs/sources/tools/pydantic.md` — Pydantic v2 (chosen, transitive)
- `docs/sources/tools/pydantic-settings.md` — Pydantic Settings (chosen)
- `docs/sources/tools/pyyaml.md` — PyYAML (chosen, transitive)
- `docs/sources/tools/hydra-core.md` — Hydra (alternative considered)
- `docs/sources/tools/omegaconf.md` — OmegaConf (alternative considered)

Stdlib `dataclasses` is not archived (Python language reference, not external citation).

## Workspace rule

Implements `~/Projects/horus/.windsurf/rules/horus-config-discipline.md` (Bundle 1). No new rule authored here; this ADR ratifies the library that satisfies the existing rule's contract.

## Consequences

- **Positive**: every experiment is reproducible from `git commit + configs/<slug>.yaml` alone (the YAML is committed; the schema is committed; the env-var layer is documented). Pydantic-validates-at-boot fails fast on every category of config error. Future env-var / secrets needs (cloud APIs, MLflow URI) require zero schema migration.
- **Negative**: `pydantic-settings` adds two transitive deps (`pydantic`, `pyyaml`) that will be on every CI and dev install. For a Python-3.14-pinned thesis project, this is acceptable. mypy gains one dev dep (`types-PyYAML`) instead of a per-import override row.
- **Neutral**: the `horus-config-discipline` rule body remains accurate without edit (it already speaks "Pydantic schema" and `BaseModel`).

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate)
- **ADR-002** — source-archival convention (this ADR's `## Source archival` cites)
- **ADR-003** — brand naming (no direct dependency)
- **Cascade-system ADR-013** — `/commit` workflow forcing function (precedent for "rule + active mechanism" pattern; here the active mechanism is the architecture itself, per `horus-config-discipline` § Forcing function)
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager`)
