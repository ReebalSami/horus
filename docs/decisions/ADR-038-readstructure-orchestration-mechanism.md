# ADR-038 — Read-then-structure orchestration mechanism for the exploratory extraction arms (text-only Gemma structurer; named-approach harness dispatch)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-02 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (coding session implementing the extraction arms; plan `~/.windsurf/plans/horus-structurer-arms-review-5a6e57.md`) |
| **Issue** | [`ReebalSami/horus#91`](https://github.com/ReebalSami/horus/issues/91) (the arms); partially activates [`#50`](https://github.com/ReebalSami/horus/issues/50) (orchestration slot) |
| **Relationship** | **Sub-decision of ADR-034** (held-out strategy). Builds on ADR-035 (`InvoiceFields` schema) + ADR-037 (19-field scoring scope). Extends the adapter-dispatch design of ADR-016/ADR-018. |

> **This ADR ratifies the *mechanism* — HOW the two extraction arms are built.** ADR-034 locked *which* models (Granite reader + Gemma structurer) and *that* there are two arms + a regex baseline. It did **not** reconcile a build-level gap: it said the arms "slot in as `adapter_mode` siblings (cf. ADR-018 `adapters_json.py`)", but the orchestrated arm runs a **second model**, not a pure text→dict function. This record resolves that, with a Phase-0 proof behind it.

## Context

ADR-034 chose Granite-Docling-258M (MLX) as the reader and Gemma-4 (MLX) as the structurer for both arms, on the ADR-035 19-field schema, scored at full 19 fields (ADR-037). The coding session that picked up the build surfaced a concrete mismatch between that strategy's "integration" sentence and the actual machinery:

- **Arm A (single-shot):** image → Gemma → JSON. This fits the existing harness path almost exactly — Gemma is the cohort `working_model`, its JSON output text is parsed by a Layer-2 adapter. The only delta vs ADR-029's JSON baseline is the *parser* (typed `validate_and_repair` instead of the bare `json.loads`) and the 19-field+`purpose_summary` prompt.
- **Arm B (orchestrated):** image → Granite → text → Gemma → JSON. This does **not** fit. Two verified blockers:
  1. **Every extractor is image-in only.** `VLMExtractor.extract(image_path, ...)` (`src/horus/vlm_extractor.py`) takes an image; `MLXVLMExtractor` hardcodes `apply_chat_template(..., num_images=1)` + `mlx_generate(..., [str(image_path)], ...)`. There was no path to hand Gemma a block of **text** (Granite's transcript) and get a completion.
  2. **The `adapter_mode` slot is for pure functions.** `cohort.adapter_mode ∈ {regex, json}` dispatches `adapters.py` / `adapters_json.py` — deterministic, fast, GPU-free `to_predicted_dict(_multipage)(text) → dict`. Arm B needs to run a *whole second model* in that role, which the slot is not built for (it is exactly what makes the offline `rescore` / `reading_ceiling` passes possible).

Independently, issue #91's body states *"An ADR is required (new architecture/model choice)"*, and issue #50 is the reserved slot for the single-shot-vs-orchestrated architecture decision. Per `horus-decision-discipline` (every framework/architecture choice is a significant decision), the orchestration mechanism warrants this record before code lands.

## Current-state survey (2026-06-02)

| Fact | Evidence | Implication |
|---|---|---|
| Extractors are image-in only | `vlm_extractor.py` `VLMExtractor.extract(image_path, ...)`; `MLXVLMExtractor` uses `num_images=1` + `[image_path]` | Arm B needs a new text-only generation path |
| `mlx-vlm` **already supports** text-only generation | `mlx_vlm.generate(model, processor, prompt, image=None, ...)` (`image` defaults `None`); `apply_chat_template(..., num_images=0)` omits the image token for the `gemma4` arch (`prompt_utils.py` `_format_list_with_image_type`, guarded by `num_images > 0`) | **No new dependency** is needed; `mlx_lm` (present transitively) is an unused fallback |
| Text-only structuring **works** end-to-end | `experiments/arm-b-structurer-probe.py` on the `EN16931_Einfach` Granite transcript: 15/19 fields non-null, every filled value correct, ISO-date + canonical-money coercion via `validate_and_repair`, **zero hallucination** (honest null on the genuinely-absent `buyer_vat_id` and the ambiguous multi-rate `tax_rate`), 7.75 GB peak, ~6.5 s load + ~34.7 s generate | Arm B is feasible on M1 Pro 16 GB with the existing toolchain; the honesty guardrail holds |
| The schema + validate/repair are merged | ADR-035/037 (`schema.py`, 19-field `FIELDS`, `validate_and_repair`); `main` at `3f0ebe8`, 751 tests green | The structurer's output contract already exists; this work consumes it |
| The transcript I/O for offline passes exists | `transcripts.py` (`parse_transcript` / `split_per_page_texts` / `build_gt_cache`), reused by `rescore.py` + `reading_ceiling.py` | Arm B's two-pass design reuses this, not a new reader loop |
| `adapter_mode` is a binary `{regex, json}` | `config.py` `CohortConfig.adapter_mode` + harness dispatch; ADR-016 supersession trigger #3 fires "past 2 variants" | Adding arm modes is a conscious extension of that binary, recorded here |

## Options considered

**A — Text-only generation backend for the structurer:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| Add `mlx_lm` as a direct dependency and load Gemma as a pure text LM | clean text-LM API | **Rejected.** Adds a dependency + a second load path for the *same* checkpoint; the multimodal checkpoint is not guaranteed to load cleanly under `mlx_lm`. Unnecessary given option below. |
| Render the transcript text back to an image and feed the image | reuses the image-in path verbatim | **Rejected.** Absurd round-trip; reintroduces an OCR step and defeats the point of a text structurer. |
| **`mlx-vlm` text-only via `image=None` + `num_images=0` (chosen)** | already installed; proven in the Phase-0 probe; same library the readers use | **Chosen.** Zero new dependency; one small text-generation helper alongside the existing image path. |

**B — Where Arm B's structuring pass runs:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| In-harness, per (model, invoice) tuple | one code path | **Rejected.** The harness loads one model per tuple; chaining Granite→Gemma per invoice means reloading models repeatedly (thrash on 16 GB) and conflating two models under one "model_id". |
| Behind a new `adapter_mode` value (a model call inside the parser slot) | minimal config surface | **Rejected.** Breaks the pure-function contract of the adapter slot (the property that lets `rescore`/`reading_ceiling` run offline, GPU-free). A model call is not an adapter. |
| **Two-pass offline flow over cached Granite transcripts (chosen)** | mirrors the proven `rescore`/`reading_ceiling` pattern; Granite reading is the existing cohort harness; Gemma structuring is a new text pass | **Chosen.** Pass 1 = Granite reads dev images → transcripts (existing `run_cohort`). Pass 2 = load each transcript via `transcripts.py`, run Gemma text-only → structurer → `score(...)` → MLflow. Reader and structurer load once each, sequentially (fits memory per ADR-032 + the Phase-0 probe). |

**C — Arm A wiring + the shared structurer:**

The shared `structurer.py` turns a model's JSON-ish text into the canonical 19-key dict: the `adapters_json` recovery ladder (reused, not duplicated) → `InvoiceFields.model_validate` → `validate_and_repair`. It exposes the `to_predicted_dict_multipage(per_page_texts, model_id)` surface so Arm A plugs into the harness as a new dispatch target (Gemma image→JSON, parsed by the structurer). The same module is the Pass-2 parser for Arm B. One structurer, two arms — which keeps Gemma the controlled variable per ADR-034 option C.

**D — Adapter-dispatch shape:** the binary `adapter_mode ∈ {regex, json}` grows to a small named-approach set (e.g. `{regex, json, structurer}` or arm-named). This consciously passes ADR-016 supersession trigger #3 ("past 2 variants"). It stays a **closed enum dispatch**, not a pluggable-plugin framework — the trigger is acknowledged and bounded, not a reopening of ADR-016's "no plugin framework" decision.

## Decision + integration thoughts

1. **Text-only structurer path = `mlx-vlm`, no new dependency.** Gemma structures text via `generate(..., image=None)` + `apply_chat_template(..., num_images=0)`. A small text-generation helper sits alongside the existing image-in `MLXVLMExtractor.extract` (shared load/unload lifecycle). `mlx_lm` is **not** adopted.
2. **`src/horus/eval/structurer.py`** is the single structurer: model text → `adapters_json` recovery ladder → `InvoiceFields` + `validate_and_repair` → 19-key scored dict (+ `purpose_summary` in the full dict for the demo). All-null on unparseable output, never raises.
3. **Arm A (single-shot)** is wired as a harness dispatch target: Gemma is the `working_model`, prompted with the reasoning-then-strict-JSON 19-field+`purpose_summary` prompt (a `prompt_template_override`), its output parsed by the structurer.
4. **Arm B (orchestrated)** is a two-pass offline flow: (1) Granite reads dev images → transcripts via the existing cohort harness; (2) a new pass loads each transcript (`transcripts.py`), runs Gemma text-only → structurer → `score(...)` (default 19 fields per ADR-037) → MLflow per approach.
5. **Baseline** = the existing German-regex adapter, run in the same comparison, scored at full 19 (it already returns 19 keys, null on the 3 ADR-035 fields — honest).
6. **Honesty axis** (`spurious_emission`, ADR-027) is measured on every approach — a generative structurer *can* hallucinate; the strict "extract only what is present, else null" prompt + `validate_and_repair` + this metric are the tax-domain guardrails. The Phase-0 probe already shows the guardrail holding (honest nulls, no invented values).
7. **Scope discipline (no-HARKing):** this ratifies the *mechanism* for the **exploratory** (§4.2) arm comparison only. It does **not** declare a single-shot-vs-orchestrated winner, and does **not** close the confirmatory Layer-1-architecture-spine or validator-loop questions — those stay deferred to the frozen held-out set (#50 remains open for them). Everything here is iterated and reported on **dev** until #78 exists.

**Integration:** reuses the ADR-014 harness (Arm A + Arm B Pass 1), the ADR-035 schema (`validate_and_repair`), the ADR-027 scorer + metrics, the ADR-030 `transcripts.py` loader (Arm B Pass 2), and ADR-011 MLflow. New surface is `structurer.py`, the text-only generation helper, the dispatch extension, and per-approach configs. No change to closed-milestone scoring (ADR-037 freeze untouched).

## Source archival

Internal: ADR-034 (strategy + the §Integration gap this resolves), ADR-035 (schema + `validate_and_repair`), ADR-037 (19-field scoring scope), ADR-018 (`adapter_mode` + `adapters_json` recovery ladder), ADR-016 (binary-dispatch decision + supersession trigger #3), ADR-029 (JSON baseline — Arm A's closest precedent + Gemma honesty evidence), ADR-030 (`transcripts.py` + reading-ceiling), ADR-027 (the 4 metrics incl. `spurious_emission`), ADR-014 (harness), ADR-009/007 (Granite + Gemma adoption + MLX backend). No new external source: **no new library is introduced** — `mlx-vlm` (ADR-007) gains no new dependency, only a text-only call mode of the already-adopted package; the text-only API was verified against the installed `mlx-vlm` source + the Phase-0 probe. Evidence artifact: `experiments/arm-b-structurer-probe.py` (re-runnable).

## Supersession trigger

Superseded if **any** of:

1. The frozen held-out results land → the arm comparison becomes confirmatory; a results ADR records the single-shot-vs-orchestrated verdict and this mechanism ADR becomes its provenance.
2. A *true* §6-H2 specialist-pipeline arm is built (Docling-library / MinerU-pipeline backend, #50) → the orchestration framing here is extended, not replaced.
3. Gemma-as-structurer underperforms on dev and the Qwen2.5-3B text-parser fallback is adopted → its own model-choice ADR + source stub amends the structurer-backend decision.
4. Constrained/grammar-guided decoding becomes available on MLX → the post-hoc `validate_and_repair` path becomes the floor and a new ADR ratifies decode-time enforcement (also a supersession trigger on ADR-035).
5. A genuinely new text-generation dependency (e.g. `mlx_lm`) is later required → that adoption gets its own ADR + source stub, amending decision pt 1.

## Consequences

- Arm B is unblocked with the existing toolchain and **no new dependency**; the build can proceed with the two-pass design.
- The adapter dispatch consciously grows past two variants (ADR-016 trigger #3 acknowledged) into a small closed named-approach enum — not a plugin framework.
- The orchestration mechanism is documented before code lands, satisfying `horus-decision-discipline` and #91's "an ADR is required" note; #50 is partially activated (mechanism) while its confirmatory + validator-loop scope stays open.
- The Phase-0 probe is preserved as re-runnable evidence; the build phase refines the structurer prompt on dev (the probe's honest misses — `seller_tax_id`, `line_total_amount`, `tax_rate` — are prompt-tuning targets, not blockers).
- Zero impact on closed-milestone numbers (ADR-037 freeze) or the harness's default `regex`/`json` callers.
