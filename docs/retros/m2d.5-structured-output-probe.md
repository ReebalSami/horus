---
status: in-progress
milestone: M2D.5 step 6 (structured-output prompting probe — ADR-018)
sprint: Sprint 2 (Cascade D vertical, post-pilot-13 Seq 5)
parent_issue: "ReebalSami/horus#53"
opened_date: "2026-05-21"
prs:
  - "ReebalSami/horus#TBD (ADR-018: structured-output prompting probe)"
predecessor_prs:
  - "ReebalSami/horus#58 (ADR-016: fast dev + adapter A/B — merged main)"
  - "ReebalSami/horus#59 (ADR-017: perf metrics — merged main)"
  - "ReebalSami/horus#42 (PR(c) cohort harness — pilot-13 ratifying)"
related_adrs:
  - "ADR-018 (structured-output prompting probe — this retro's ratifying ADR)"
  - "ADR-016 (fast dev + adapter A/B substrate — supersedes adapter-iterate path)"
  - "ADR-014 (cohort harness — the reused infrastructure)"
  - "ADR-013 (per-field F1 scorer — reused unchanged)"
  - "ADR-012 (canonical 16-field GroundTruth schema)"
  - "ADR-009 (pilot-VLM cohort + per-model native prompt strategy)"
followups:
  - "ReebalSami/horus#54 (conditional: Experiment 2 full corpus run if probe ratifies)"
  - "ReebalSami/horus#41 (fall-through: Layer 2 MONEY-field adapter if probe defers)"
  - "ReebalSami/horus#55 (fall-through: LoRA fine-tuning ADR if probe defers)"
---

# M2D.5 step 6 — Structured-output prompting probe retrospective

> **Status note**: retro authored as a stub at Step 6 of the plan
> (`~/.windsurf/plans/horus-issue-53-structured-output-probe-4f44ea.md`).
> Empirical sections marked TBD are populated post-Steps 7+8 (probe execution
> Arm A + Arm B) from the MLflow experiments `structured-output-probe-uniform`
> + `structured-output-probe-native-json`. Retro is promoted to `status: closed`
> at Step 9 alongside the conditional verdict per ADR-018 §"Pre-registered
> conditional verdict".

**Outcome (TBD — populated post-probe)**: <1-line summary of empirical
schema-adherence rate + F1 + verdict>.

## What was built (Steps 1-5; landed pre-probe)

| Component | Path | Purpose |
|---|---|---|
| ADR-018 | `docs/decisions/ADR-018-structured-output-probe.md` | 5-section discipline ratification — context + current-state survey + 4-axis options walk + decision + supersession triggers + (TBD-populated) empirical evidence subsections. |
| Schema additions | `src/horus/config.py::CohortConfig` | `prompt_template_override: dict[str, str] \| None` + `adapter_mode: Literal["regex", "json"]` + cross-field `@model_validator` (catches typos + misuse at boot). |
| JSON adapter | `src/horus/eval/adapters_json.py` | Sibling to `adapters.py`; same `(preprocess, to_predicted_dict)` public surface; 5-step permissive JSON-recovery ladder; top-level-shape gate rejects array-wrapped JSON. |
| Harness dispatch | `src/horus/eval/harness.py` | 1-import + 1-conditional binary dispatch (`adapters_regex` vs `adapters_json`) per `cohort.adapter_mode`; per-model prompt override via dict `.get(model_id, manifest_default)`; `adapter_mode` MLflow tag on parent + nested runs; transcript header `# Adapter:` + `# Prompt:` lines for audit. |
| Two YAML overlays | `configs/pilot-13-structured-probe-uniform.yaml` + `configs/pilot-13-structured-probe-native-json.yaml` | Compose on `pilot-13.yaml`; declare per-arm `mlflow.experiment_name`, distinct `parent_run_name` + `transcript_archive_dir`, `dev_only: true` HARKing guard, full 7-model `prompt_template_override` map. Pre-registered Arm A + Arm B prompts locked PRE-PROBE per NeurIPS Paper Checklist + brainstorm v2 §2 No-HARKing. |
| Test coverage | `tests/test_config_pilot_13.py` (+9), `tests/test_adapters_json.py` (NEW, 22), `tests/test_harness.py` (+4) | +35 tests; full suite 427 passing post-Step 5. |

## Pre-registered conditional verdict (locked PRE-PROBE)

Per ADR-018 §"Pre-registered conditional verdict":

| Condition | Verdict |
|---|---|
| ≥3 of 7 models reach `(json_validity=1, canonical_key_count ≥ 12)` in either arm | File issue #54 (Experiment 2 — full 26-invoice corpus run with `adapter_mode="json"`); ADR-018 ratifies the substrate. |
| <3 of 7 models reach `(json_validity=1, canonical_key_count ≥ 12)` in both arms | Defer #54 indefinitely; route follow-up priority to #41 (MONEY-field adapter) + #55 (LoRA fine-tuning ADR). ADR-018's `adapter_mode="json"` path remains available for re-activation when a future fine-tuned model lifts adherence. |

## Empirical results — Arm A (TBD)

**Parent run**: `<MLflow parent_run_id; populated post-Step 7>`
**Experiment**: `structured-output-probe-uniform`
**Tuples**: 7 / 7 attempted, <n_completed> / <n_failed> / <n_skipped>

| Model | Cat | json_validity | canonical_keys | micro_F1 | Predicted | Observed verdict |
|---|---|:---:|:---:|---:|---|---|
| ibm-granite/granite-docling-258M-mlx | 1 | TBD | TBD | TBD | NO | TBD |
| opendatalab/MinerU2.5-Pro-2604-1.2B | 1 | TBD | TBD | TBD | NO | TBD |
| allenai/olmOCR-2-7B-1025 | 1 | TBD | TBD | TBD | MAYBE | TBD |
| PaddlePaddle/PaddleOCR-VL | 2 | TBD | TBD | TBD | NO | TBD |
| zai-org/GLM-OCR | 2 | TBD | TBD | TBD | NO | TBD |
| google/gemma-4-E4B-it | 3 | TBD | TBD | TBD | YES | TBD |
| google/paligemma2-3b-mix-448 | 3 | TBD | TBD | TBD | NO | TBD |

## Empirical results — Arm B (TBD)

**Parent run**: `<MLflow parent_run_id; populated post-Step 8>`
**Experiment**: `structured-output-probe-native-json`
**Tuples**: 7 / 7 attempted, <n_completed> / <n_failed> / <n_skipped>

(Same 7-row × 4-column table; populated post-Step 8.)

## Pre-registered threshold check (TBD)

| Arm | Models reaching (json_validity=1, canonical_keys ≥ 12) | Verdict |
|---|---|---|
| A | TBD | TBD |
| B | TBD | TBD |
| Combined (max per model) | TBD | TBD |

## Learnings (TBD post-probe)

Pre-registered learning categories per `bidirectional-learning-pipe` rule:

- **Pattern** (what worked unexpectedly well across the probe):
- **Anti-pattern** (what backfired):
- **Friction** (recurring annoyance suggesting L1/L3 gap):
- **Trade-off insight** (decision made, reasoning worth preserving):
- **Tooling discovery** (non-obvious MCP / library / platform capability):

## Cross-project candidates (TBD post-probe)

Entries that may warrant L1/L3 promotion per `bidirectional-learning-pipe`:

- (TBD)
