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

## Multi-file composition (ADR-016)

`ExperimentConfig.from_yaml()` accepts a single path (the original API) OR a list of paths. When a list is given, files are deep-merged in order with later-wins semantics — the canonical pydantic-settings 2.x composition pattern. Use this to compose a small dev / ablation overlay on top of a stable base config without duplication:

```bash
make pilot-13 CFG=configs/pilot-13.yaml,configs/pilot-13-dev.yaml
make adapter-iterate CFG=configs/pilot-13.yaml,configs/pilot-13-dev.yaml
```

`pilot-13-dev.yaml` is a ~15-line overlay declaring only what differs from the base (1 model instead of 7, 3 invoices instead of 26, distinct MLflow experiment name + transcript archive dir, `dev_only: true` HARKing-prevention guard). The shared knobs (seed, eval thresholds, rasterizer DPI, corpus root, resume policy, most MLflow tags) inherit unchanged from `pilot-13.yaml`.

### Structured-output probe overlays (ADR-018, issue #53)

Two overlays drive the structured-output prompting probe (1 invoice × 7 models × 2 prompt arms):

```bash
# Arm A — cohort-uniform JSON prompt for all 7 models
make pilot-13 CFG=configs/pilot-13.yaml,configs/pilot-13-structured-probe-uniform.yaml

# Arm B — per-model native task prefix + JSON suffix (respects ADR-009 §"Per-model native
# prompt strategy" task-prefix-lock findings for Cat 2/3 models)
make pilot-13 CFG=configs/pilot-13.yaml,configs/pilot-13-structured-probe-native-json.yaml
```

Both overlays compose on `pilot-13.yaml` (NOT on `pilot-13-dev.yaml` — the probe needs the FULL 7-model cohort, not the 1-model dev subset). Both set `cohort.adapter_mode: json` (dispatches harness to `src/horus/eval/adapters_json.py`), `cohort.invoice_subset: [EN16931_Einfach]` (1-invoice probe scope), `cohort.dev_only: true` (HARKing-prevention forcing function inherited from ADR-016), and distinct `mlflow.experiment_name` + `cohort.parent_run_name` + `cohort.transcript_archive_dir`. The per-model prompts in `cohort.prompt_template_override` are pre-registered in ADR-018 §"Pre-registered prompts" — locked PRE-PROBE per NeurIPS Paper Checklist + brainstorm v2 §2 No-HARKing.

**Merge semantics**:

- **Scalars** (str, int, bool, None) — later file wins.
- **Nested dicts** (e.g., `mlflow.run_tags`) — merged recursively; per-key later-wins.
- **Lists** (e.g., `cohort.working_models`) — REPLACED, not concatenated. The dev overlay's 1-model list fully replaces the base's 7-model list.

**Drift prevention**: when `pilot-13.yaml` changes (e.g., DPI bumped 300 → 400), the dev overlay picks it up automatically. No silent staleness.

**Fail-fast**: missing files raise `FileNotFoundError`; non-mapping top-level YAML raises `ValueError`; the merged result is Pydantic-validated (`extra='forbid'` still enforced post-merge). All failures happen before any model loads or compute is spent.

## Cross-references

- **Schema**: `src/horus/config.py`
- **Discipline rule**: `.windsurf/rules/horus-config-discipline.md` (Bundle 1, ratified 2026-05-10)
- **Library decision**: `docs/decisions/ADR-004-config-library.md` (Bundle 2, ratified 2026-05-10)
- **Source archival**: `docs/sources/tools/{pydantic,pydantic-settings,pyyaml,hydra-core,omegaconf}.md`
