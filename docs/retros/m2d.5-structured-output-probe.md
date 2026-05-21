---
status: closed
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

**Outcome**: Pre-registered threshold (≥3 of 7 with `json_validity=1, canonical_keys≥12` in either arm) **NOT MET**. Combined max-per-model: 2 of 7 (olmOCR-2-7B + GLM-OCR). Verdict: DEFER #54 (Experiment 2 full-corpus); route follow-up to #41 (Layer 2 MONEY adapter) + #55 (LoRA fine-tuning ADR). Best of probe: GLM-OCR Arm B `micro_F1=0.571` on `EN16931_Einfach` (single-invoice spike, not generalizable). Most methodologically informative finding: GLM-OCR Arm A "schema-shape mimicry" (perfect JSON shape, placeholder values) — surfaces a NEW failure mode + threshold-criterion caveat.

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

## Empirical results — Arm A (uniform JSON prompt)

**Parent run**: `f9273a9d196742cdaa0831d7dcaa8608`
**Experiment**: `structured-output-probe-uniform` (id=7)
**Tuples**: 7 / 7 completed, 0 failed, 0 skipped (no resume)
**Cohort pooled micro_F1**: 0.0367 (EN16931=0.0367, XRECHNUNG=0.0000)
**Wall-clock**: ~12-15 min total (rasterization cached)

| Model | Cat | json_validity | canonical_keys | micro_F1 | Predicted | Observed |
|---|:---:|:---:|:---:|---:|---|---|
| ibm-granite/granite-docling-258M-mlx | 1 | no | 0/16 | 0.000 | NO | NO ✓ |
| opendatalab/MinerU2.5-Pro-2604-1.2B | 1 | no | 0/16 | 0.000 | NO | NO ✓ |
| allenai/olmOCR-2-7B-1025 | 1 | YES | 16/16 | **0.222** | MAYBE | **YES** ✓ |
| PaddlePaddle/PaddleOCR-VL | 2 | no | 0/16 | 0.000 | NO | NO ✓ |
| zai-org/GLM-OCR | 2 | YES | 16/16 | 0.000 | NO | YES (shape) ✗ |
| google/gemma-4-E4B-it | 3 | no | 0/16 | 0.000 | YES | NO ✗ |
| google/paligemma2-3b-mix-448 | 3 | no | 0/16 | 0.000 | NO | NO ✓ |

**Predicted-vs-observed deltas** (methodologically informative per ADR-018 §"Predicted outcomes"):

- **olmOCR-2-7B**: predicted MAYBE, observed YES — emits valid 16/16 JSON with actual extracted values (`micro_F1=0.222`, the only non-zero in Arm A). Ratifies the HF discussion #16 user-reported "JSON via custom prompt" pattern: olmOCR-2's RLVR-fine-tuning evidently includes enough JSON-instruction generalization to override the canonical Markdown-output bias.
- **GLM-OCR**: predicted NO, observed YES on shape but micro_F1=0 — demonstrates a NEW failure mode not anticipated in ADR-018 §"Predicted outcomes": **schema-shape mimicry without value extraction**. The model copied the prompt's `<BT-1>` / `<BT-22 ISO 8601>` / `<BT-72 ISO 8601>` placeholders verbatim into its JSON output instead of populating them with values from the rasterized invoice. Cosmetically perfect JSON; zero information content. The threshold criterion `(json_validity=1, canonical_keys≥12)` does NOT distinguish this from genuine extraction — a finding that surfaces a **methodological caveat** for the verdict.
- **Gemma-4-E4B-it**: predicted YES, observed NO — surprising. Investigation needed at Step 9 (transcript inspection); possible causes: (a) chat-template handling of multi-paragraph prompt, (b) audio-utils warning surfaced during loading suggests partial config drift in the multimodal release.
- **PaddleOCR-VL**: emitted Chinese-key hallucination (`"发票_number"`) followed by infinite-loop repetition of `"order_date": "<BT-21"` (literal degenerate-decoder pattern). Confirms ADR-009 task-prefix-lock prediction; out-of-distribution decoding instability.

**Pre-registered threshold check (Arm A alone)**: 2 of 7 with `(json_validity=1, canonical_keys≥12)`. Below the ≥3 threshold. Arm B required before final combined verdict per ADR-018 §"Pre-registered conditional verdict".

## Empirical results — Arm B (per-model native + JSON suffix)

**Parent run**: `fced15055ae244e095cf5347760daf25`
**Experiment**: `structured-output-probe-native-json` (id=8)
**Tuples**: 7 / 7 completed, 0 failed, 0 skipped (no resume)
**Cohort pooled micro_F1**: 0.2034 (EN16931=0.2034, XRECHNUNG=0.0000) — **5.5× Arm A's 0.0367**
**Wall-clock**: ~12-15 min total

| Model | Cat | json_validity | canonical_keys | micro_F1 | Δ vs Arm A | Notes |
|---|:---:|:---:|:---:|---:|---:|---|
| ibm-granite/granite-docling-258M-mlx | 1 | no | 0/16 | 0.000 | 0.000 | DocTags-locked even with `Convert this page to docling.` prefix |
| opendatalab/MinerU2.5-Pro-2604-1.2B | 1 | no | 0/16 | 0.000 | 0.000 | Native `OCR this document.` prefix doesn't unlock JSON; emits markdown |
| **allenai/olmOCR-2-7B-1025** | 1 | YES | 11/16 | **0.546** | **+0.324** | Big lift; emits fewer fields than Arm A but with HIGHER value accuracy |
| PaddlePaddle/PaddleOCR-VL | 2 | no | 0/16 | 0.000 | 0.000 | Native `OCR:` prefix → still degenerate-decoder (Chinese-key loop) |
| **zai-org/GLM-OCR** | 2 | YES | 15/16 | **0.571** | **+0.571** | Best result of probe; native `Recognize all text in the image and output in markdown format` + JSON suffix unlocks **genuine extraction** (NOT shape-mimicry) |
| google/gemma-4-E4B-it | 3 | no | 0/16 | 0.000 | 0.000 | Reused Arm A's uniform prompt by design; same failure mode |
| google/paligemma2-3b-mix-448 | 3 | no | 0/16 | 0.000 | 0.000 | Native `ocr` task prefix doesn't unlock JSON adherence |

**Predicted-vs-observed deltas**:

- **GLM-OCR**: Arm A → schema-shape mimicry (placeholders); Arm B → genuine extraction (`micro_F1=0.571`). The native task prefix `Recognize all text in the image and output in markdown format` (a familiar OCR instruction the model is trained on) followed by the JSON-key-list suffix evidently shifts the model from "echo example shape" mode to "transform invoice content into JSON" mode. **Best result of the entire probe**, on the failure-mode model from Arm A.
- **olmOCR-2-7B**: keys dropped (16 → 11) but F1 nearly tripled (0.222 → 0.546). The terser prompt suppressed the "fill all 16 fields with something" tendency in favor of "fill only fields where confident". Methodologically informative for prompt-design generally — terseness can lift accuracy when the model is RLVR-trained for OCR fidelity (Poznanski+ 2025).
- **PaddleOCR-VL**: native `OCR:` prefix did NOT unlock JSON adherence; still emitted Chinese-key degenerate-decoder loop. Confirms ADR-009 §"Per-model native prompt strategy" task-prefix lock is **structural**, not prompt-fixable (the model's fine-tuning literally cannot emit non-OCR-token output regardless of prompt).

## Pre-registered threshold check — combined (max per model)

| Arm | Models reaching (json_validity=1 AND canonical_keys ≥ 12) | Verdict |
|---|:---:|---|
| A | 2 / 7 (olmOCR-2-7B, GLM-OCR) | below |
| B | 1 / 7 (GLM-OCR; olmOCR fell to 11/16) | below |
| **Combined (max per model)** | **2 / 7** (olmOCR-2-7B, GLM-OCR) | **below ≥3 threshold** |

→ **Verdict: DEFER #54** (Experiment 2 full-corpus run with `adapter_mode="json"`). Route follow-up priority to #41 (Layer 2 MONEY-field adapter) + #55 (LoRA fine-tuning ADR). ADR-018's `adapter_mode="json"` substrate remains landed-and-available for re-activation when (a) a future fine-tuned model lifts adherence, OR (b) the threshold criterion is amended (e.g., to weight value accuracy alongside shape adherence).

**Best of probe (information-only; not the verdict criterion)**: GLM-OCR Arm B at `micro_F1=0.571` on `EN16931_Einfach` — a single-invoice spike. Pilot-13's MinerU best on the FULL 26-invoice cohort was 0.710 (free-form OCR + Layer 1 regex adapters). Single-invoice-spikes are not generalizable evidence; the threshold criterion correctly defers to mass evidence.

## Learnings

Per `bidirectional-learning-pipe` rule:

- **Pattern (worked unexpectedly well)**: **Native task prefix + JSON-key-list suffix** for OCR-trained VLMs (GLM-OCR jumped 0.000 → 0.571). The pattern: anchor the prompt in a task the model is trained on (`Recognize all text in the image and output in markdown format`), then append the schema-extraction instruction. Concatenation matters more than schema-design — the model's distribution-coverage of the prompt's first sentence dominates.
- **Anti-pattern (backfired)**: **Schema example with bracketed placeholders** (`<BT-1>`, `<BT-22 ISO 8601>`) in a uniform JSON prompt. GLM-OCR copied the placeholders verbatim into its JSON output (16/16 canonical keys, 0% value content). The threshold criterion `(json_validity=1, canonical_keys≥12)` cannot distinguish this from genuine extraction — a methodological caveat to capture in future protocols. **Mitigation**: replace `<BT-N>` placeholders with `null` in pre-registered prompts (anchors the value type without offering text-to-copy), OR add a value-non-trivial gate (`micro_F1 ≥ 0.1`) alongside the shape gate.
- **Friction (suggests L1/L3 gap)**: `scripts/inspect_pilot_13.py` hardcodes `experiment_name='pilot-13-full'` and silently returns `0 nested runs` when pointed at any other experiment. Future cohort-style experiments need a generalized inspector that takes `--experiment-name` (or auto-discovers from the parent run's `experiment_id`). Captured: queue/pending-review.md.
- **Trade-off insight**: The pre-registered ≥3-of-7 threshold worked exactly as designed — it prevented post-hoc result-shopping (would have been tempting to declare "GLM-OCR's 0.571 ratifies the substrate" if the threshold weren't locked). The combined-max-per-model rule also worked: olmOCR's per-arm fluctuation (16 keys A, 11 keys B; 0.222 F1 A, 0.546 F1 B) is correctly handled by max-per-model rather than averaging.
- **Tooling discovery**: `mlflow.search_runs(filter_string="tags.adapter_mode='json'")` works over BOTH parent and nested runs uniformly because the harness sets the tag on both (per ADR-018 §"MLflow integration"). Made the inspector trivially findable. Validates the wiring decision.

## Cross-project candidates (L1/L3 promotion candidates)

For `@sprint-review` consideration:

- **Pre-registration discipline**: this is the second probe (after pilot-13) where pre-registered thresholds + combined-max-per-model rules prevented HARKing. Pattern is generalizable to ANY ML evaluation in HORUS (and downstream projects). Candidate for L3 promotion to `python-ml-uv` template as a thin "preregistration.md" prompt-template under `scaffold/docs/decisions/`.
- **Prompt-anchoring pattern** (native-task-prefix + extraction-suffix) is potentially generalizable beyond invoice extraction to any VLM-on-document task. Capture as an L2 HORUS rule first (`horus-prompt-anchoring`); if the pattern repeats in 2+ HORUS projects, promote to L3.
- **Inspector hardcoded experiment name**: file as a HORUS bug; generalizing it is in-scope for issue #56 or similar.
