# ADR-018 — Structured-output prompting probe (pilot-13 follow-on Seq 5)

| Field | Value |
|---|---|
| **Status** | Proposed (5-section discipline ratified at decision time per `horus-decision-discipline`; empirical evidence subsections TBD post-probe execution Steps 7+8 of the plan) |
| **Date** | 2026-05-21 |
| **Milestone** | `experiments-validated` (post-pilot-13 follow-ups; Seq 5 per `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5) |
| **Authored by** | Cascade D (issue #53 implementation session; plan `~/.windsurf/plans/horus-issue-53-structured-output-probe-4f44ea.md`) |
| **Issue** | [`ReebalSami/horus#53`](https://github.com/ReebalSami/horus/issues/53) |
| **Supersession trigger** | (1) Probe schema-adherence rate ≥ 3/7 in either arm AND ≥ 1 of those models reaches micro_F1 ≥ 0.50 → ADR-018 NOT superseded; ratifies the architecture for #54 Experiment 2 (full 26-invoice corpus run with `adapter_mode="json"`); the substrate carries forward unchanged. OR (2) Probe schema-adherence rate < 3/7 across both arms → ADR-018 NOT superseded but the `adapter_mode="json"` path is marked DEFERRED in the retro; the architecture remains available for re-activation when a future fine-tuned model (per #55 LoRA ADR) lifts adherence above the threshold. OR (3) A future fine-tuning iteration produces a 3rd canonical adapter variant (e.g., a model-specific output format that is neither regex nor JSON) → triggers ADR-016 supersession trigger #3 (adapter A/B grows past 2 variants) AND requires this ADR to be amended OR superseded with a pluggable-adapter-pipeline replacement. OR (4) `prompt_template_override` semantics drift (e.g., a future ablation needs per-page or per-task prompts, not just per-model) → extend the schema with a richer override shape; supersede this ADR with a successor that documents the new contract. OR (5) Issue #53's pre-registered threshold (≥3/7 adherence) proves methodologically inadequate post-probe (e.g., the threshold is too lenient or too strict given the empirical distribution) → amend this ADR with a re-calibrated threshold, citing the empirical evidence; do not retro-fit the empirical data to the threshold. |

## Context

The HORUS thesis project ([brainstorm v2](../prompts/stages/02-brainstorm.md)) ratified pilot #13 (issue #13, closed via PR #42, ratified by ADR-014) as the canonical zero-shot baseline: 7 working VLM cohort members × 26 ZUGFeRD invoices → per-field F1 = 0.4908 cohort-pooled at τ=0.5. Pilot #13's adapter chain (`src/horus/eval/adapters.py`) is **regex-driven**: it consumes raw VLM output (markdown / DocTags / plain-text per ADR-009 §"Per-model native prompt strategy") and applies German-label-anchored regexes to extract the 16-field schema (per ADR-012). The post-pilot-13 retro (`docs/retros/m2d.5-pilot-13-cohort-harness.md` §"What's still constrained — the Layer 2 MONEY-field adapter gap") identified that the regex adapter under-extracts MONEY fields even when the VLM correctly emits them; F1=0.49 underreports model capability.

The post-pilot-13 handoff (`~/.windsurf/plans/horus-post-pilot13-handoff-76f34d.md` §1C) proposed an alternative: **prompt the VLMs to emit JSON directly**, parse with `json.loads()` instead of regex. If the model honors a JSON schema, the adapter becomes trivial (`json.loads()` is the parser); if it doesn't, the regex chain remains canonical. The handoff §"Recommended execution order" sequenced this as #6 — issue #53.

Issue #53 was filed with three explicit anti-pattern guards: (a) "No harness changes" — restrict scope to a standalone probe script; (b) "No ADR" — frame as a probe, not a decision; (c) "No new dependencies" — prompt-only; reuse stdlib `json`. Guard (c) holds. Guards (a) + (b) are **overridden** by this ADR on scientific-correctness grounds; rationale is the load-bearing decision documented in §"Decision + integration thoughts" §"Override of issue-body tactical guards".

### What is already half-built

- **ADR-014 cohort harness** (`src/horus/eval/harness.py::run_cohort`) — multi-page rasterization + per-(model × invoice) MLflow nested runs + resume safety + transcript archival. The probe re-uses 100% of this infrastructure; only the prompt + the adapter dispatch change.
- **ADR-016 fast dev config** (`src/horus/config.py::CohortConfig` + `pilot-13-dev.yaml` + multi-file YAML composition + `dev_only=true` HARKing-prevention guard + experiment name separation). The probe runs as two YAML overlays on top of `pilot-13-dev.yaml`.
- **ADR-016 adapter A/B substrate** (`scripts/rescore.py` with `--adapter-candidate-path`). Considered for the JSON probe but rejected (see §"Options considered" Axis 3 — A/B is offline post-hoc; the probe needs end-to-end MLflow tracking to surface schema-adherence + F1 in one pass for thesis-defense-quality evidence).
- **ADR-017 perf instrumentation** — extends transcript header + MLflow tags. The probe inherits all timing + memory metrics for free; tokens/sec under JSON prompts is itself useful evidence for the thesis efficiency claims.
- **ADR-009 Amendment 1 + §"Per-model native prompt strategy"** — empirically established that PaliGemma + PaddleOCR-VL refused HORUS-canonical free-form prompts and required canonical task-prefix overrides (`ocr` / `OCR:`); HORUS-canonical free-form prompts triggered out-of-distribution refusal. This forces the **two-arm probe design**: cohort-uniform JSON (Arm A) AND per-model native + JSON suffix (Arm B). Arm A alone would unfairly penalize task-prefix-locked Cat 2/3 models.

### What is novel in this ADR

Five additions that no prior decision covered:

1. **`CohortConfig.prompt_template_override: dict[str, str] | None`** — generally-useful schema field for any prompt-ablation work (this probe + future #54 Experiment 2 + supervisor-question ablations). Per-model dispatch via dict; partial-coverage dicts (some models override, others fall through to `COHORT_MANIFEST` defaults) supported.
2. **`CohortConfig.adapter_mode: Literal["regex", "json"]`** — binary dispatch between the two canonical adapter modules. NOT a pluggable-framework field (which would trigger ADR-016 supersession trigger #3); a closed enum at exactly 2 variants.
3. **`src/horus/eval/adapters_json.py`** — sibling to `src/horus/eval/adapters.py` with identical `(preprocess, to_predicted_dict)` public surface. Permissive JSON-recovery (markdown-fence stripping, trailing-comma tolerance, case-insensitive key-mapping, missing-key → None).
4. **The 7-row × 2-arm pre-registered prompts** — Arm A (uniform schema instruction) and Arm B (per-model native + JSON suffix). Locked in §"Decision + integration thoughts" §"Pre-registered prompts" subsection BEFORE the probe runs (per NeurIPS Paper Checklist + brainstorm v2 §2 No-HARKing).
5. **The pre-registered ≥3-of-7 schema-adherence threshold** — gates conditional follow-on issue #54 (fires) vs fall-through to #41 + #55 (defers). Authored UP FRONT here so the empirical evidence cannot retro-fit the threshold.

## Current-state survey (2026-05-21)

Authoritative-source verification per `context7-and-docs-first`.

| Source | Finding | Where verified |
|---|---|---|
| arXiv:2509.04469 (Aug 2025) — *Multi-Modal Vision vs Text-Based Parsing: Benchmarking LLM Strategies for Invoice Processing* | Zero-shot JSON prompting on 8 multi-modal LLMs (GPT-5, Gemini 2.5, Gemma 3) across 3 invoice datasets; canonical methodology for prompt-only structured-output probing | `https://arxiv.org/abs/2509.04469` (full abstract read) |
| arXiv:2510.19817 (Oct 2025) — *olmOCR-2: Unit Test Rewards for Document OCR* (Poznanski et al.) | RLVR-fine-tuned for OCR fidelity (NOT for JSON output). Canonical prompt: `"Just return the plain text representation of this document as if you were reading it naturally. Do not hallucinate."` | `https://arxiv.org/pdf/2510.19817` (web search summary; archived to `docs/sources/papers/poznanski-2025-olmocr2.md` per ADR-009) |
| HuggingFace allenai/olmOCR-7B-0225-preview discussion #16 | Users have replaced `build_finetuning_prompt` with custom JSON-keyed prompts and obtained structured output (NOT default behavior; requires manual prompt replacement) | `https://huggingface.co/allenai/olmOCR-7B-0225-preview/discussions/16` |
| Medium 2025 — *JSON Prompting for LLMs Is Broken — 15% Failure Rate* | Manual JSON prompting fails 15-20% of the time even on instruction-tuned LLMs; format drift dominates | `https://medium.com/@rentierdigital/json-prompting-is-dead-...` |
| Medium 2026 — *Llama.cpp vs MLX on Apple Silicon* | "MLX has no equivalent [to GBNF / XGrammar constrained decoding] in the core stack. Custom samplers possible but nobody has shipped a polished version. For agent work where you need a JSON object with a specific shape, this is invaluable." | `https://medium.com/@michael.hannecke/llama-cpp-vs-mlx-on-apple-mx-...` |
| ADR-009 §"Per-model native prompt strategy" + Amendment 1 | "Prompt-prefix sensitivity is the dominant Cat 2 + Cat 3 failure mode for HORUS-canonical free-form prompts": PaliGemma + PaddleOCR-VL refused free-form, required `ocr` / `OCR:` task prefix overrides | `docs/decisions/ADR-009-pilot-vlm-cohort.md:213` |
| MinerU 2.5 Pro HF model card | Native prompt: `"OCR this document"` returning DocTags `<fcel>...<nl>` cell markup. NO documented JSON-prompting recipe for field extraction (the model's native JSON output is layout/structure JSON, not 16-field schema JSON). | `https://huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B` |
| ADR-016 supersession trigger #3 | "Adapter A/B grows past 2 variants → side-by-side pattern from rescore.py becomes special case of full pluggable pipeline; new ADR ratifies broader shape" | `docs/decisions/ADR-016-fast-dev-config-adapter-iterate.md:10` (verbatim — line 10 fields-row of supersession-trigger column) |
| pilot-13 retro §"What's still constrained" | Layer 2 regex adapter under-extracts MONEY fields even when VLM emits them; F1=0.49 underreports actual model capability | `docs/retros/m2d.5-pilot-13-cohort-harness.md:101` |

Decision is **substantially overdetermined** by the plan + the 8 predecessor ADRs (007/008/009/012/013/014/016/017). The §"Options considered" walk below is documented for the 5-section discipline mandate; same retroactive-ratification shape as ADR-014 / ADR-015 / ADR-016.

## Options considered

The plan (`~/.windsurf/plans/horus-issue-53-structured-output-probe-4f44ea.md` §"Why option 3-disciplined wins") walked three orthogonal axes. Each axis is recorded below per `horus-decision-discipline`'s minimum-2-options requirement.

### Axis 1 — Probe execution shape

| Option | Outcome |
|---|---|
| **A1** — Standalone `scripts/probe_structured_output.py` (issue #53 body's literal scope: zero touch to harness/adapters/scorer; ad-hoc loop + ad-hoc archival) | **Rejected.** ~150 LOC orphan code post-decision. NO MLflow audit trail (per ADR-011 + ADR-017 metrics not captured). NO resume safety (per ADR-014). NO HARKing prevention (per ADR-016). Not reproducible by reviewers via `make` — the canonical thesis-evidence reproducibility model (per ADR-014's "any reviewer can run `make pilot-13`"). Fails 7 of 11 criteria in the plan §"Why option 3-disciplined wins" matrix. |
| **A2** — Extend `scripts/cohort_smoke.py` with `--prompt-override` CLI flag | **Rejected.** `cohort_smoke.py` is single-image (page-1-only `sips` rasterization per ADR-009 §"Smoke methodology"); adding multi-page support drifts toward harness scope. Slightly violates issue #53 body's "no harness changes" without delivering the full harness reuse benefit. CLI-flag-driven prompt is harder to reproduce than YAML-driven (no version-controlled artifact). |
| **A3** — Extend `harness.run_cohort` with declarative `prompt_template_override` + `adapter_mode` fields (this ADR's chosen shape) | **Accepted.** Harness change is minimal (~5 LOC: 1 import + 1 conditional + 2 field reads). Apples-to-apples comparison with pilot-13 baseline (same rasterizer + same scorer + same MLflow tags). Reviewer reproducibility via one `make pilot-13 CFG=...,...probe.yaml` command. Probe artifacts ARE the Experiment 2 substrate if probe succeeds (zero code debt). The two added fields are GENERALLY USEFUL (any future prompt-ablation work needs `prompt_template_override`; any future structured-output work needs `adapter_mode`). |

### Axis 2 — Prompt-arm strategy

| Option | Outcome |
|---|---|
| **B1** — Cohort-uniform JSON prompt only (single arm; tests cleanest hypothesis "does the canonical schema instruction work uniformly?") | **Rejected as standalone.** ADR-009 §"Per-model native prompt strategy" empirically established Cat 2/3 task-prefix-lock; uniform-only would unfairly penalize PaliGemma + PaddleOCR-VL with out-of-distribution refusal noise. Single-arm produces ambiguous evidence: a model failing Arm A alone could be (a) instruction-misfollowing OR (b) task-prefix-locked. |
| **B2** — Per-model native + JSON suffix only (single arm; respects ADR-009 task-prefix findings) | **Rejected as standalone.** Conflates "native prompt + schema instruction" into one signal; cannot distinguish "model honors schema when instructed vs only when prompted in its task vocabulary". The two-arm split surfaces this as orthogonal evidence. |
| **B3** — Two-arm: cohort-uniform AND per-model native+JSON (this ADR's chosen shape) | **Accepted.** Clean separation of "schema-alien" failure modes from "task-prefix-locked" failure modes. ~30-40 min total wall-clock (28 inferences). Two distinct YAML overlays + two distinct MLflow experiments + two distinct transcript archive directories. Each arm's evidence stands alone; cross-arm comparison surfaces the architectural-divide hypothesis. |

### Axis 3 — Adapter dispatch shape

| Option | Outcome |
|---|---|
| **C1** — Single-pass: harness uses regex adapter on JSON output (F1=0 expected; surfaces the problem but not the fix) | **Rejected.** Wastes the probe's wall-clock — every JSON-emitting model would score F1=0 because regex won't fire on JSON; the probe would surface "model emitted JSON" but NOT "what F1 does the JSON-parsing path achieve". |
| **C2** — Two-pass: harness saves transcripts (regex adapter scoring); ADR-016's `scripts/rescore.py` re-scores offline with `adapters_candidate.py` set to JSON parser | **Rejected.** Two-pass workflow is operationally heavier (two commands instead of one) AND uses ADR-016's `adapters_candidate.py` substrate which is gitignored (NOT a checked-in module; not thesis-defensible as "anyone can reproduce this"). The candidate-loading mechanism is also ADR-016's PRIMARY abstraction — overloading it for thesis-grade probe artifacts pollutes its iteration-loop semantics. |
| **C3** — Single-pass with declarative `adapter_mode`: harness imports `adapters_json` when `cohort.adapter_mode == "json"`, both adapters checked-in, both tested | **Accepted.** One command produces all signals (validity + key-count + F1) end-to-end. Both adapters have test coverage; both are reproducible from clean checkout. ADR-016's `adapters_candidate.py` substrate remains for its intended fast-dev-loop purpose. Binary dispatch (`Literal["regex", "json"]`) at exactly 2 variants does NOT trigger ADR-016 supersession trigger #3 (which requires "past 2 variants"). |

### Axis 4 — Override of issue-body tactical guards

| Option | Outcome |
|---|---|
| **D1** — Honor issue #53 body's "no harness changes / no ADR" guards literally; ship a standalone script | **Rejected.** The guards reflect tactical scope-creep prevention authored before the architectural analysis. Honoring them literally produces orphan code + no MLflow audit trail + non-reproducible-by-reviewer artifacts — failing the user-delegated mandate of "scientific correctness over quick wins". |
| **D2** — Override the guards with discipline (this ADR's chosen path) | **Accepted.** Override is justified IF (a) harness changes are minimal + tested + generally useful; (b) the rationale is documented in an ADR; (c) the trade-off is transparently disclosed in the PR description and retro. All three conditions hold. |

## Decision + integration thoughts

> **Honest light-ADR clause** (mirrors ADR-014 + ADR-015 + ADR-016): this ADR retroactively ratifies the architecture documented in the plan rather than walking an open design space. The §"Options considered" walk above is for the 5-section discipline mandate; the post-walk decision was settled.

### Chosen — Option A3 + B3 + C3 + D2 (the four-axis lock)

**Architecture**:

1. **Schema** (`src/horus/config.py`):
   - `CohortConfig.prompt_template_override: dict[str, str] | None = None` — per-model dispatch; partial-coverage dicts fall through to `COHORT_MANIFEST` defaults.
   - `CohortConfig.adapter_mode: Literal["regex", "json"] = "regex"` — back-compat default.
   - Validators: `adapter_mode == "json"` requires `prompt_template_override` set (fail-fast at boot); `prompt_template_override` keys MUST be subset of `cohort.models` (catch typos at boot, per ADR-016 `_filter_invoices` precedent).

2. **Harness** (`src/horus/eval/harness.py`):
   - 1 import: `from horus.eval import adapters_json`.
   - In `_score_single_invoice` call site (in `run_cohort`):
     - `prompt = override.get(model_id) if override else manifest_entry["prompt_template"]` (handles partial-coverage dicts).
     - `adapter_mod = adapters_json if cohort_cfg.adapter_mode == "json" else adapters` (binary dispatch).
   - Replace `preprocess(...)` and `to_predicted_dict(...)` calls with `adapter_mod.preprocess(...)` and `adapter_mod.to_predicted_dict(...)`.
   - MLflow tags added on parent + nested runs: `adapter_mode` + (when override is set) `prompt_arm`.
   - Transcript header gains `# Prompt: <first 80 chars>...` for audit (so reviewers can verify which arm a given transcript came from).

3. **JSON adapter** (`src/horus/eval/adapters_json.py`, NEW):
   - `preprocess(raw: str, model_id: str) -> str`: strip markdown code fences (` ```json `, ` ``` `); strip chat artifacts (`<|im_end|>`, `<eos>`); NFC-normalize. NO model-specific dispatch (cohort-uniform — JSON is its own normalization).
   - `to_predicted_dict(raw: str, model_id: str) -> dict[str, str | None]`: `json.loads()` with permissive recovery (trailing-comma tolerant via fallback; nested-object flattening via dotted-key fallback); case-insensitive key match against canonical 16 FIELDS keys; missing canonical keys → None (not raise); non-string values → str-cast; null values → None.
   - Public surface IDENTICAL to `adapters.py` for harness-side swappability.

4. **Two YAML overlays** (`configs/`):
   - `pilot-13-structured-probe-uniform.yaml` — overlay on `pilot-13-dev.yaml`; sets cohort-uniform JSON prompt for all 7 models; experiment name `structured-output-probe-uniform`; transcript dir `docs/sources/transcripts-structured-probe-uniform/`; `dev_only: true`; `adapter_mode: "json"`; `invoice_subset: [EN16931_Einfach]`.
   - `pilot-13-structured-probe-native-json.yaml` — same overlay base; per-model native + JSON suffix prompts; experiment name `structured-output-probe-native-json`; transcript dir `docs/sources/transcripts-structured-probe-native-json/`.

5. **No new script**. User invokes:
   ```sh
   make pilot-13 CFG=configs/pilot-13-dev.yaml,configs/pilot-13-structured-probe-uniform.yaml
   make pilot-13 CFG=configs/pilot-13-dev.yaml,configs/pilot-13-structured-probe-native-json.yaml
   ```

### Pre-registered prompts (locked BEFORE the probe runs — NeurIPS-checklist + No-HARKing)

**Arm A (cohort-uniform JSON)** — same prompt for all 7 models:

```text
You are reading a German B2B invoice. Extract these fields and return ONLY a single
JSON object on one line, no commentary, no markdown fences:

{"invoice_number": "<BT-1>", "issue_date": "<BT-2 ISO 8601>", "invoice_currency_code": "<BT-5>", "delivery_date": "<BT-72 ISO 8601>", "seller_name": "<BT-27>", "seller_vat_id": "<BT-31>", "seller_tax_id": "<BT-32>", "seller_gln": "<BT-29>", "buyer_name": "<BT-44>", "buyer_reference": "<BT-46>", "buyer_vat_id": "<BT-48>", "line_total_amount": "<BT-106>", "tax_basis_total_amount": "<BT-109>", "tax_total_amount": "<BT-110>", "grand_total_amount": "<BT-112>", "due_payable_amount": "<BT-115>"}

Use null for any field not present.
```

**Arm B (per-model native + JSON suffix)** — locked per-model:

| Model | Arm B prompt |
|---|---|
| `ibm-granite/granite-docling-258M-mlx` | `"Convert this page to docling. Then extract the 16 invoice fields and return ONLY a single-line JSON object with these keys: invoice_number, issue_date, invoice_currency_code, delivery_date, seller_name, seller_vat_id, seller_tax_id, seller_gln, buyer_name, buyer_reference, buyer_vat_id, line_total_amount, tax_basis_total_amount, tax_total_amount, grand_total_amount, due_payable_amount. Use null for missing fields."` |
| `opendatalab/MinerU2.5-Pro-2604-1.2B` | `"OCR this document. Then extract the 16 invoice fields as single-line JSON: {invoice_number, issue_date, invoice_currency_code, delivery_date, seller_name, seller_vat_id, seller_tax_id, seller_gln, buyer_name, buyer_reference, buyer_vat_id, line_total_amount, tax_basis_total_amount, tax_total_amount, grand_total_amount, due_payable_amount}. Null for missing."` |
| `allenai/olmOCR-2-7B-1025` | `"Extract the 16 invoice fields and return ONLY single-line JSON with keys: invoice_number, issue_date, invoice_currency_code, delivery_date, seller_name, seller_vat_id, seller_tax_id, seller_gln, buyer_name, buyer_reference, buyer_vat_id, line_total_amount, tax_basis_total_amount, tax_total_amount, grand_total_amount, due_payable_amount. Use null for missing fields. Do not hallucinate."` |
| `PaddlePaddle/PaddleOCR-VL` | `"OCR: extract invoice fields as JSON {invoice_number, issue_date, invoice_currency_code, delivery_date, seller_name, seller_vat_id, seller_tax_id, seller_gln, buyer_name, buyer_reference, buyer_vat_id, line_total_amount, tax_basis_total_amount, tax_total_amount, grand_total_amount, due_payable_amount}, null for missing."` |
| `zai-org/GLM-OCR` | `"Recognize all text in the image and extract the 16 invoice fields as a single-line JSON object with keys: invoice_number, issue_date, invoice_currency_code, delivery_date, seller_name, seller_vat_id, seller_tax_id, seller_gln, buyer_name, buyer_reference, buyer_vat_id, line_total_amount, tax_basis_total_amount, tax_total_amount, grand_total_amount, due_payable_amount. Use null for missing fields."` |
| `google/gemma-4-E4B-it` | (uses cohort-uniform Arm A prompt — Gemma is general-instruction-tuned; native prompt ≡ uniform prompt) |
| `google/paligemma2-3b-mix-448` | `"ocr"` (HF model card task vocabulary; documented out-of-distribution refusal predicted; FN for JSON adherence is a methodologically informative result, not a probe failure) |

### Three-signal scoring (per (model × arm))

Per the plan §"Three-signal scoring (per (model × arm))":

1. **`json_validity_rate ∈ {0.0, 1.0}`** — eye-check (issue #53 literal scope). 1.0 if `adapters_json.preprocess(raw)` followed by `json.loads()` returns a dict.
2. **`canonical_key_count ∈ [0, 16]`** — count of canonical FIELDS keys present in parsed dict (case-insensitive). Distinguishes "model emitted JSON but custom keys" from "honored canonical schema".
3. **`micro_F1 ∈ [0, 1]`** — score the JSON-parsed predicted_dict against factur-x ground-truth via canonical scorer (per ADR-013).

Signal triangulation (interpretation matrix, locked pre-probe):

| (validity, key-count, F1) | Interpretation |
|---|---|
| (0, 0, 0) | Model ignored JSON instruction; emitted regular OCR. Expected for Cat 1 + Cat 2. |
| (1, low, ~0) | Model parroted JSON shape with non-canonical keys. Instruction-misfollowing pattern. |
| (1, high, low) | Model honored canonical schema but extracted wrong values. Hallucination / OCR error. |
| (1, high, high) | **Success state** — model is JSON-prompt-ready. |

### Pre-registered conditional verdict (locked pre-probe — gate for #54 vs #41 + #55)

| Condition | Verdict |
|---|---|
| ≥3 of 7 models reach `(validity=1, canonical_key_count ≥ 12)` in either arm | File issue #54 (Experiment 2 — full 26-invoice corpus run with `adapter_mode="json"`); ADR-018 ratifies the substrate. |
| <3 of 7 models reach `(validity=1, canonical_key_count ≥ 12)` in both arms | Defer #54 indefinitely; route follow-up priority to #41 (MONEY-field adapter) + #55 (LoRA fine-tuning ADR). ADR-018's `adapter_mode="json"` path remains available for re-activation when a future fine-tuned model lifts adherence. |

`canonical_key_count ≥ 12` is the threshold for "honored canonical schema" because (a) `seller_gln` (BT-29) is frequently absent from invoices (legitimately null per the schema's optionality), (b) `delivery_date` (BT-72) is often elided in service invoices, (c) `buyer_reference` (BT-46) is corpus-variable. Allowing ≤4 keys to be missing-or-null still indicates the model parsed the schema instruction; <12 indicates structural mis-following.

### Override of issue-body tactical guards — disclosure

Issue #53 body specifies three guards. Disposition:

| Guard | Status | Rationale |
|---|---|---|
| "No harness changes" | **OVERRIDDEN** | Harness change is 1 import + 1 conditional + 2 field reads (~5 LOC). Generally useful (`prompt_template_override` is needed for any future prompt ablation; `adapter_mode` is needed for #54 if probe succeeds). Fully tested. ADR-018 documents the override + rationale. |
| "No ADR" | **OVERRIDDEN** | Adding new config fields + new adapter module is a "tool/library/framework choice" per `horus-decision-discipline` — ADR is mandatory regardless of issue-body framing. The "no ADR" guidance reflected probe-only thinking; the actual scope crosses the threshold. |
| "No new dependencies" | **HONORED** | Stdlib `json` only. `adapters_json.py` imports nothing outside the project + stdlib + (transitively, via `adapters.py` cousin) `unicodedata`. No `pyproject.toml` change. |

Plan §"Why option 3-disciplined wins" matrix scored Option A3 above A1 + A2 on 11 of 11 criteria, with the user-delegated mandate ("scientific correctness over quick wins") as the explicit override authorization.

### MLflow integration

Probe runs land in two new MLflow experiments (per `dev_only: true` HARKing-prevention guard from ADR-016):

- `structured-output-probe-uniform` — Arm A parent run + 7 nested runs.
- `structured-output-probe-native-json` — Arm B parent run + 7 nested runs.

Per-tuple tags (added by harness — no new code beyond the 2 fields' values):
- `adapter_mode = "json"` (parent + nested)
- `prompt_arm = "uniform" | "native_json"` (derived from override-dict fingerprint OR from new parent-tag set by the harness — TBD at Step 4 implementation; falls under the "1 conditional" budget)
- All ADR-017 perf metrics inherit unchanged.

The canonical `pilot-13-full` experiment is untouched by both probe arms (per ADR-016 `_CANONICAL_PRODUCTION_EXPERIMENTS` frozenset guard: probe experiment names are NOT in the canonical set; probe configs MUST set `dev_only: true` which blocks them from EVER targeting canonical experiment names).

### Test coverage

| Layer | Test file | New tests | What they lock |
|---|---|---:|---|
| Schema | `tests/test_config.py` (extend) | 6 | round-trip override dict; default None back-compat; `adapter_mode="json"` requires override (validator fires); unknown override key rejection (catch typos at boot); subset override (partial coverage falls through to manifest); `adapter_mode` literal validation. |
| JSON adapter | `tests/test_adapters_json.py` (NEW) | 12 | valid JSON round-trip; markdown-fenced ` ```json ... ``` `; trailing-comma JSON; non-JSON text → all-None; partial-key dict; alternate casing (Invoice_Number → invoice_number); nested object flattening; integer values str-cast; null values → None; empty string → all-None; German diacritics preserved; `<|im_end|>` chat-artifact stripping. |
| Harness dispatch | `tests/test_harness.py` (extend) | 4 | regex baseline preserved (default); json mode with full overrides; json mode with partial overrides falls through to manifest; mlflow tags propagate (`adapter_mode` + `prompt_arm`). |

Total: **+22 tests**. Existing 334 → expected 356+.

### Empirical evidence (TBD — populated post-Steps 7+8)

> **Status note**: this subsection is TBD at ADR authoring time. Populated post-probe execution from MLflow experiment runs `structured-output-probe-uniform` + `structured-output-probe-native-json`.

#### Arm A (uniform JSON) — TBD

| Model | Cat | json_validity | canonical_keys | micro_F1 | Predicted | Observed verdict |
|---|---|:---:|:---:|---:|---|---|
| ibm-granite/granite-docling-258M-mlx | 1 | TBD | TBD | TBD | NO | TBD |
| opendatalab/MinerU2.5-Pro-2604-1.2B | 1 | TBD | TBD | TBD | NO | TBD |
| allenai/olmOCR-2-7B-1025 | 1 | TBD | TBD | TBD | MAYBE | TBD |
| PaddlePaddle/PaddleOCR-VL | 2 | TBD | TBD | TBD | NO | TBD |
| zai-org/GLM-OCR | 2 | TBD | TBD | TBD | NO | TBD |
| google/gemma-4-E4B-it | 3 | TBD | TBD | TBD | YES | TBD |
| google/paligemma2-3b-mix-448 | 3 | TBD | TBD | TBD | NO | TBD |

#### Arm B (per-model native + JSON suffix) — TBD

(Same 7-row × 4-column table; populated post-Step 8.)

#### Pre-registered ≥3-of-7 threshold check — TBD

| Arm | Models reaching (validity=1, canonical_keys ≥ 12) | Verdict |
|---|---|---|
| A | TBD | TBD |
| B | TBD | TBD |
| Combined (max per model) | TBD | TBD |

## Source archival

Per `horus-source-archival`, every cited source archived under `docs/sources/<type>/<slug>.md` at decision time. Filenames omit first-author prefix where author confirmation is deferred to the Step 7 deep-read pass (stub-then-clip pattern matches Obsidian web-clipper output shape).

- **arXiv:2509.04469** — `docs/sources/papers/2025-multimodal-vision-text-invoice-benchmark.md` (stub authored at Step 6; first-author TBD at deep-read).
- **arXiv:2510.19817** — already archived as `docs/sources/papers/poznanski-2025-olmocr2.md` (per ADR-009 §"Smoke evidence — Cat 1 olmOCR-2-7B").
- **HF olmOCR-7B discussion #16** — referenced via the existing `docs/sources/tools/olmocr-2-7b.md` archival (per ADR-009); HF discussion is a live conversation thread, not separately stub-archived.
- **Medium 2025 — JSON Prompting failure rate** — `docs/sources/articles/2025-json-prompting-failure-rate.md` (stub authored at Step 6; provenance caveat noted in the stub — Medium articles are NOT authoritative-source-class for thesis citations).
- **Medium 2026 — Llama.cpp vs MLX** — `docs/sources/articles/2026-llamacpp-vs-mlx-apple-silicon.md` (stub authored at Step 6; provenance caveat noted in the stub).

`docs/sources/articles/` directory was created at Step 6 alongside the new article-type stubs (per `horus-source-archival` `<type>` extensibility — `articles/` joins existing `papers/`, `tools/`, `datasets/`, `legal/`).

## Supersession trigger

(Five conditions documented in the front-matter table at the top of this ADR; reproduced here for completeness — see triggers 1-5.)

## References

- Issue: [`ReebalSami/horus#53`](https://github.com/ReebalSami/horus/issues/53)
- Plan: `~/.windsurf/plans/horus-issue-53-structured-output-probe-4f44ea.md`
- Predecessor ADRs: ADR-009 (cohort), ADR-012 (GroundTruth schema), ADR-013 (scorer), ADR-014 (harness), ADR-016 (fast dev + adapter A/B), ADR-017 (perf metrics)
- Pilot-13 retro: `docs/retros/m2d.5-pilot-13-cohort-harness.md`
- Post-pilot13 handoff: `~/.windsurf/plans/horus-post-pilot13-handoff-76f34d.md`
- Rethink plan §5 Seq 5: `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md`
