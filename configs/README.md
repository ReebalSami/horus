# configs/ — Experiment configuration files

Per-experiment YAML files. Each experiment has exactly one config file in this directory. Loaded + validated by `horus.config.ExperimentConfig.from_yaml()` at experiment boot; Pydantic raises on missing required fields, type mismatches, or extra (unrecognised) keys BEFORE any model loads, dataset downloads, or compute is spent.

This directory is the contract surface of `horus-config-discipline` (`.windsurf/rules/horus-config-discipline.md`) — every knob a future-you might want to tune lives in YAML here, not in `.py` source.

## Naming convention

`configs/<experiment-slug>.yaml`

The `<experiment-slug>` matches the experiment file's slug:

- `configs/granite-pilot.yaml` ↔ `experiments/granite-pilot.py`
- `configs/qwen3-vl-baseline.yaml` ↔ `experiments/qwen3-vl-baseline.py`
- `configs/zugferd-extraction-prompt-v2.yaml` ↔ `experiments/zugferd-extraction-prompt-v2.py`

Slugs are kebab-case. Re-use of slugs across experiments is forbidden — every experiment is a unique git-tracked artifact.

## Schema

The Pydantic schema lives in `src/horus/config.py`. The current minimum (Bundle 2 close):

```yaml
seed: 42                          # int, required
mlflow:
  experiment_name: my-experiment  # str, required
  run_tags:                       # dict[str, str], default empty
    stage: pilot
    cohort: granite
  tracking_uri: null              # str | None, default null
```

The schema **grows per experiment** (`model: ModelConfig`, `dataset: DatasetConfig`, `eval: EvalConfig`, …) — see `docs/decisions/ADR-004-config-library.md` § Decision + integration thoughts. New fields land via PR with the experiment that needs them.

## Env-var overrides

Set `HORUS_*` env vars to override YAML values for secrets-style fields. Use the double-underscore (`__`) convention for nested fields:

```bash
export HORUS_MLFLOW__TRACKING_URI=https://my-mlflow.example.com
# the yaml's mlflow.tracking_uri: null is now overridden
```

YAML wins over env vars for fields PRESENT in YAML (per `pydantic-settings` source ordering — `init_settings` > `env_settings`). Env vars fill in only fields absent from the YAML.

## Running an experiment

```bash
make experiment NB=experiments/<slug>.py CFG=configs/<slug>.yaml
```

The `CFG=` value is injected into the experiment notebook as the papermill parameter `cfg_path`, which the `.py` file passes to `ExperimentConfig.from_yaml(cfg_path)` at boot.

## Cross-references

- **Schema**: `src/horus/config.py`
- **Discipline rule**: `.windsurf/rules/horus-config-discipline.md` (Bundle 1, ratified 2026-05-10)
- **Library decision**: `docs/decisions/ADR-004-config-library.md` (Bundle 2, ratified 2026-05-10)
- **Source archival**: `docs/sources/tools/{pydantic,pydantic-settings,pyyaml,hydra-core,omegaconf}.md`
