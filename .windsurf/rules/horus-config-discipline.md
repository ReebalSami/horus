---
trigger: model_decision
description: In the HORUS thesis project, ALL experiment knobs (hyperparameters / model IDs / dataset paths / seeds / batch sizes / learning rates / prompt strings / eval thresholds / MLflow tags) live in `configs/<experiment-slug>.yaml` files. `.py` files contain LOGIC + Pydantic schema only. Experiments accept ONE papermill parameter `cfg_path`. Pydantic-validates-at-boot is the architectural forcing function (fails fast on missing/malformed YAML before any model loads). Ratified in `docs/decisions/ADR-NNN-config-library.md` (forthcoming, Bundle 2, M2D.5 step 0).
sources_consulted:
  - ~/.windsurf/plans/cascade-d-resume-rethink-2f7f5a.md §1 Q6/Q7/Q8 (own) — interview content that defines this rule's shape
  - ~/Projects/horus/.windsurf/rules/horus-decision-discipline.md (own) — sibling L2 rule; shape mirror (5-section ADR discipline)
  - ~/Projects/horus/.windsurf/rules/notebook-discipline.md (own) — sibling L3 rule; shape mirror (experiments/ + papermill contract)
  - ~/Projects/cascade-system/docs/decisions/ADR-013-commit-workflow-as-forcing-function.md (own) — forcing-function precedent (rule + workflow pairing)
  - ~/Projects/cascade-system/docs/decisions/ADR-018-release-manager-skill.md (own) — forcing-function precedent (rule + skill pairing)
  - THESIS_BRAINSTORM_STATE_v2.md §4.1 (own) — "scientific-correctness discipline" locked-a-priori commitment that this rule enforces
  - cascade-system/docs/handoffs/cascade-d-master-thesis.md §3.2 (own) — canonical authoring record
adapted_for:
  - L2 workspace rule — HORUS thesis project only; lives at `~/Projects/horus/.windsurf/rules/horus-config-discipline.md`
  - `model_decision` trigger — fires when experiment / config / hyperparameter / model-id / seed / batch-size / learning-rate keywords surface; not always-on to preserve context budget
  - Architectural forcing function = Pydantic-validates-at-boot (no separate skill/workflow needed; the architecture itself is the workflow). Distinguishes from ADR-013/ADR-018 patterns where a workflow/skill pairs with the rule
  - Pre-committed to L3-promotion surfacing at next `@sprint-review` per Q7 of the resume-rethink plan
---

# horus-config-discipline (L2, HORUS thesis)

> **CONSTRAINT**: In the HORUS project, *every* experiment knob lives in a YAML config under `configs/`, NOT in `.py` files. The `.py` files contain logic + the Pydantic schema that validates YAML at boot. This is the contract that makes experiments reproducible + HARKing-resistant + MLflow-loggable + git-bisectable.

## What this rule mandates

The YAML-as-source-of-truth contract for experiment configuration:

1. **Every experiment knob lives in `configs/<experiment-slug>.yaml`** — one YAML file per experiment. Committed to git. Tied 1:1 to an MLflow run (`cfg_path` is logged as a run param + the file is logged as a run artifact).
2. **`src/horus/config.py` defines the Pydantic schema** — the *contract* that validates every YAML at load time. The schema literals INSIDE the Pydantic class definition (defaults / type annotations / `Field(default=..., description=...)`) ARE the canonical documentation of what each knob means.
3. **Experiments accept ONE papermill parameter: `cfg_path: str`** — that's the only knob exposed to the runner. Everything else is in the YAML.
4. **At experiment-`.py` boot**: `cfg = ExperimentConfig.from_yaml(cfg_path)`. If YAML is missing a required field, references an undefined knob, or violates a type / constraint, Pydantic raises *before* any model loads, any dataset downloads, any compute is spent. **Fails fast.**

## What's FORBIDDEN in `.py` files

Outside `src/horus/config.py`'s Pydantic schema, in ANY `.py` file in `src/horus/`, `experiments/`, or `scripts/`, the following are violations:

- **Hyperparameters as default args**: `def train(learning_rate=1e-3, batch_size=32, epochs=10): ...` ❌
- **Hyperparameters as module-level constants**: `LEARNING_RATE = 1e-3` ❌
- **Model IDs hardcoded**: `model = AutoModel.from_pretrained("ibm-granite/granite-docling-258M")` ❌ (the model ID must come from `cfg.model.repo_id`)
- **Checkpoint paths hardcoded**: `checkpoint = "/Users/.../granite-256m.safetensors"` ❌
- **Dataset paths hardcoded**: `dataset = load_dataset("path/to/zugferd-corpus")` ❌ (must be `cfg.dataset.path`)
- **Seeds hardcoded**: `set_global_seed(42)` ❌ in experiment / training code (must be `cfg.seed`)
- **Prompt templates as string literals**: `PROMPT = "Extract the following fields..."` ❌ (must be `cfg.prompt.template` or `cfg.prompt.file` for long prompts)
- **Eval thresholds inline**: `if f1 > 0.85: ...` ❌ (must be `cfg.eval.threshold`)
- **MLflow tags / experiment names**: `mlflow.set_experiment("granite-pilot")` ❌ (must be `cfg.mlflow.experiment_name`)

The principle: anything a future-you might want to tune without changing code is a knob. Knobs live in YAML.

## What's ALLOWED in `.py` files

- **Pydantic schema literal defaults INSIDE `src/horus/config.py`** — this is the schema's job. Example: `class TrainingConfig(BaseModel): learning_rate: float = Field(default=1e-3, description="AdamW learning rate")` ✅. The literal `1e-3` documents the default. The YAML can override.
- **Package metadata**: `__version__ = "0.1.0"` in `src/horus/__init__.py` ✅
- **Structural constants**: column names (`COL_INVOICE_NUMBER = "rechnungsnummer"`), schema field names (used as dict keys / DataFrame columns), enum values for typing (`class ModelFamily(str, Enum): GRANITE = "granite"`) ✅. These are NOT tunable knobs; they're part of the type system.
- **Test fixtures inside `tests/`**: hardcoded test inputs / expected outputs ✅ (tests verify behavior at specific inputs; that's the point)
- **Constants from the EN 16931 / §14 UStG schema**: legal-fixed field names + types ✅ (these aren't knobs; they're legal definitions)
- **Pydantic validators that reference other config fields**: cross-field validation logic ✅ (logic about constraints, not constraint values)

## The contract (experiment `.py` shape)

Every experiment `.py:percent` file in `experiments/` follows this shape:

```python
# %% [markdown]
# # Experiment: <slug>
# Config: `configs/<slug>.yaml`

# %% tags=["parameters"]
cfg_path: str = "configs/<slug>.yaml"  # papermill injects this

# %%
from horus.config import ExperimentConfig
cfg = ExperimentConfig.from_yaml(cfg_path)  # Pydantic validates here; raises if invalid

# %%
# ... rest of experiment uses `cfg.foo.bar` for every knob ...
```

Run: `make experiment NB=experiments/<slug>.py CFG=configs/<slug>.yaml` (Makefile update is Bundle 2 work, M2D.5 step 0).

## Forcing function

**Pydantic-validates-at-boot is the architectural backstop.** No separate skill or workflow is needed.

This distinguishes `horus-config-discipline` from the ADR-013 (`no-terminal-oneline-scripts` rule + `/commit` workflow) and ADR-018 (`branch-and-pr-required` rule + `@release-manager` skill) patterns. In those patterns, a workflow/skill is the active forcing function that the agent invokes; the rule is the discipline-statement.

Here, **the architecture itself is the workflow**:

- A `.py` file that hardcodes a knob bypasses the Pydantic schema → loses validation → loses MLflow logging → loses reproducibility. The cost is paid immediately and locally.
- A `.py` file that loads from `cfg.foo.bar` where `foo.bar` isn't in the schema → Pydantic raises at boot → the violation is caught before any model loads.
- An experiment YAML missing a required field → Pydantic raises at boot → caught before any compute is spent.

The agent (Cascade) must still actively follow the discipline when authoring `.py` files. This rule is the agent-side mirror of the architecture-side forcing function. The two together = full-stack coverage.

## Activation triggers (`model_decision` keywords)

The rule activates when intent signals experiment / config / training / inference work:

- "config" / "configuration" / "configs" / "yaml" / "settings"
- "experiment" / "run experiment" / "training run" / "inference run"
- "hyperparameter" / "hyperparam" / "knob" / "tuning"
- "model id" / "checkpoint" / "weights" / "huggingface repo"
- "seed" / "random seed" / "deterministic"
- "batch size" / "learning rate" / "epoch" / "warmup"
- "prompt" / "prompt template" / "system prompt"
- "eval threshold" / "metric threshold" / "F1 cutoff"
- "mlflow" / "experiment name" / "run tag"

## When the rule does NOT fire

- **Pure logic / algorithm work** — no knob involvement (e.g., implementing a string-similarity function)
- **README / docs editing** — explanatory text, not executable knobs
- **`pyproject.toml` / dependency management** — that's `uv-discipline`'s territory
- **Test fixtures inside `tests/`** — test data, not experiment knobs
- **The user is teaching / explaining concepts** — no edit intent
- **`pyproject.toml` package metadata** — `version`, `name`, `description` are not knobs

## Examples

**Fires** — *"Add a training experiment with learning_rate=2e-4 and batch_size=16"*: refuse to write the hardcoded values inline; create `configs/<slug>.yaml` with those values; ensure the `.py` references `cfg.training.learning_rate` and `cfg.training.batch_size` (and that the Pydantic schema accommodates them, extending `src/horus/config.py` with an ADR if non-trivial).

**Fires** — *"Run the Granite-Docling pilot on 10 invoices with seed 42"*: dispatch as `make experiment NB=experiments/granite-docling-pilot.py CFG=configs/granite-docling-pilot.yaml`. If `configs/granite-docling-pilot.yaml` doesn't exist, scaffold it FIRST with the model ID, dataset path, n=10, seed=42, and any other knobs. Verify the schema accepts all fields. THEN run.

**Fires** — *"Change the prompt template to use German legal terminology"*: refuse to edit a `PROMPT_TEMPLATE` constant in `.py`; create/edit the prompt file at `configs/prompts/<slug>.txt` (or extend the YAML's `cfg.prompt.template` field if short).

**Does NOT fire** — *"What does `set_global_seed` do?"*: explanation, no edit intent.

**Does NOT fire** — *"Add a column-name constant `COL_BRUTTOBETRAG = 'bruttobetrag'` for use across the parser module"*: structural constant, not a tunable knob. Allowed.

**Does NOT fire** — *"Bump `__version__` to 0.2.0 in `src/horus/__init__.py`"*: package metadata, not an experiment knob.

## L3 promotion plan

Pre-committed to surface for L3 promotion at the next `@sprint-review` per Q7 of the resume-rethink plan (`~/.windsurf/plans/cascade-d-resume-rethink-2f7f5a.md` §1). The shape is generic enough to apply to any python-ml-uv project (the YAML + Pydantic + papermill pattern is industry-standard for ML research repos). If `@sprint-review` confirms the pattern proves valuable across other consumers, route via `@update-horizontal` to `~/.windsurf/templates/python-ml-uv/rules/config-discipline.md`.

The L3 promotion would supersede the L2 rule (per `document-as-you-go` retention policy — supersession, not deletion). Until promotion, the L2 rule is authoritative for HORUS.

## Source

L2 workspace rule for the HORUS thesis project. Authored during Cascade D's 2026-05-10 resume-rethink session (Bundle 1 of the config-discipline split-landing).

- **Resume-rethink plan**: `~/.windsurf/plans/cascade-d-resume-rethink-2f7f5a.md` (§1 Q6/Q7/Q8 interview resolutions; §4.3 edit spec; §7 ADR slots; §8 acceptance gates)
- **Canonical record**: `cascade-system/docs/handoffs/cascade-d-master-thesis.md` §3.2 (the handoff sub-section that records this rule's arrival)
- **Brainstorm cross-reference**: `~/Projects/horus/docs/prompts/stages/02-brainstorm.md` §10 (in same PR as this rule)
- **Forthcoming ADRs** (Bundle 2, deferred to new cascade M2D.5 step 0):
  - `ADR-NNN-config-library` — Pydantic Settings (indicated) vs Hydra vs OmegaConf vs stdlib + PyYAML; walked Socratically per `horus-decision-discipline`
  - `ADR-NNN-config-schema` — the initial `ExperimentConfig` field set; grows per-experiment as the cohort expands

Pairs with `horus-decision-discipline` (sibling L2 rule, every tool/dep choice gets an ADR), `notebook-discipline` (sibling L3 rule, experiments live as `.py:percent` in `experiments/`), and `uv-discipline` (sibling L3 rule, package management via `uv add` only).
