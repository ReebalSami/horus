# ADR-039 — Live single-method extraction demo page (bounded exception to the read-only app)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-03 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (app live-extraction coding session; plan `~/.windsurf/plans/horus-app-live-extraction-review-06f082.md`) |
| **Issue** | [#109](https://github.com/ReebalSami/horus/issues/109) (relates [#82](https://github.com/ReebalSami/horus/issues/82) end-user prototype, [#103](https://github.com/ReebalSami/horus/issues/103) app epic) |
| **Relationship** | Sub-decision of **ADR-036**; a **bounded exception** to ADR-036 §D (read-only); early Layer-1 slice of **#82** (folds in as a page per ADR-036 §C). |

## Context

The supervisor meeting needs a working LOCAL demo: take ~5 **brand-new** invoices the system has never seen, run extraction **live**, and show what came out — for human-eye review. The existing Streamlit app (ADR-036, PR #107/#108) is **read-only by ratified design**: it shows only already-computed runs from the local MLflow store + saved transcripts + ground truth, and ADR-036 §D explicitly rejected "recompute-in-UI" (slow, non-reproducible, couples the UI to model loading).

There is **no ground truth** for arbitrary uploaded invoices, so this page **cannot and must not score** — it shows the extraction for visual review only. And it **must run a model live**, which is precisely what §D scoped out for the *research* surfaces. ADR-036 §C anticipated this: the #82 end-user demo "folds in LATER as a page within the same app." This ADR ratifies that fold-in for the Layer-1 extraction slice.

The predecessor's hard lesson (ADR-036 § Amendment, the `app/pages/`→`app/views/` rename) is the procedural anchor: **amend/author the ADR before landing the code**, never silently contradict a ratified decision. This ADR is written before any app code.

## Current-state survey (2026-06-03)

| Surface | Where | Mode |
|---|---|---|
| Overview / Invoice Explorer / Approach Comparison | `app/views/` (PR #107) | **read-only** — reads MLflow runs + saved transcripts + CII GT; no inference |
| Inference primitives | `src/horus/vlm_extractor.py`, `src/horus/eval/{rasterize,structurer,arm_b}.py` | live VLM inference, used by the offline harness + `run_arm_b` |
| Offline Arm B runner | `src/horus/eval/arm_b.py::run_arm_b` | reads **cached** transcripts, scores vs GT, logs MLflow — **not** an uploaded-file path |
| Method/model registry | `app/data/approaches.py` | resolves each arm's model IDs **from `configs/*.yaml`** (no hard-coding) |
| `#82` prototype | issue (planned) | full end-user product: L1 extract + L2 KG + L3 GraphRAG + FastAPI + Ollama + Docker |

Gap: no surface runs a model on a **user-uploaded** file. Building it on the read-only app is a direct departure from §D — hence this ADR.

## Options considered

**A — Add live inference to the existing pages vs. a dedicated page:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Dedicated end-user page, research pages stay read-only (chosen)** | Bounds the exception; keeps the research/analysis surfaces fast, deterministic, side-effect-free | the only honest way to keep §D intact where it matters while serving the demo need |
| Make the existing Invoice Explorer also accept uploads | one fewer page | would couple the read-only analysis surface to model loading (the exact thing §D rejected); blurs "scored vs. unscored" |

**B — How many methods at launch:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Two AI methods — Arm A + Arm B (chosen)** | the actual AI approaches; Arm B is the strongest (dev micro-F1 0.935, spurious 0.000) and Arm A the simplest | smallest reliable surface for an end-user audience; user-confirmed |
| All three (incl. regex baseline) | full comparison story | the regex baseline is German-only + brittle by design — a research *reference*, not an end-user method; deferred (additive later) |
| One method only | least to build | loses the "single-shot vs. read-then-structure" contrast that is genuinely interesting to show |

**C — Reuse vs. rebuild the orchestration:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **New pure module `src/horus/eval/live.py` over the existing primitives (chosen)** | importable + unit-testable; no MLflow/scoring/GT coupling | `run_arm_b` is the wrong shape (cached-transcript + scoring + MLflow); the primitives (`rasterize_pdf`, `get_extractor`, `MLXVLMExtractor.extract`/`.extract_text`, `structurer.to_full_dict`) compose cleanly into a no-scoring live flow |
| Reuse `run_arm_b` | already exists | reads cached transcripts, scores vs GT, writes MLflow runs — none of which applies to a live upload |

**D — Scoring on the page:** **None.** No GT for uploaded files → the page shows extracted values for **human-eye review only**, with an explicit "visual review only, not a scored result" banner. Showing any fabricated metric would violate the tax-domain honesty guardrail (ADR-027/034). Rejected: a confidence proxy (would be mistaken for accuracy).

**E — Image resolution fed to the model:** **300 DPI** (the evaluation DPI in `pilot-13.yaml`), not the 150-DPI on-screen preview used by the read-only pages. Feeding the model a lower-resolution image than it was evaluated on would make the demo under-represent measured performance. Rejected: 150 DPI (faster render, but unfaithful).

## Decision + integration thoughts

1. **Live single-method inference is allowed on the END-USER demo page only.** The three research/analysis surfaces (Overview / Invoice Explorer / Approach Comparison) stay read-only — ADR-036 §D still governs them. This page is a **bounded exception, not a reversal**.
2. **Two AI methods:** Arm A (single-shot Gemma) and Arm B (Granite reader → Gemma structurer). The regex baseline is deferred.
3. **New pure-orchestration module** `src/horus/eval/live.py`: one function per method, taking **already-loaded** extractor(s) + prompts + page-image paths and returning a small result object (the 19 fields + `purpose_summary`, the Granite transcript for Arm B, page-image paths, timings). No MLflow, no scoring, no GT, **not** `run_arm_b`. Unit-tested with the extractor **mocked** (no model loads in `make test`).
4. **New page** `app/views/live_extraction.py`: `st.file_uploader` (pdf/png/jpg) → save the in-memory upload to a temp file → `st.radio` method picker (the human-friendly names from `app/data/approaches.py`) → **Read** → `st.spinner` → render the page image, a **non-scoring** field→value table (the existing `field_table` is scoring-coupled and needs GT, so a new display is added), the `purpose_summary` prominently, and (Arm B) the Granite transcript. Explicit "no ground truth — visual review only" banner. Failures render a plain message (the extractor never raises past `.extract()`).
5. **Model loaded once per session** via `st.cache_resource` keyed by `model_id`; the cached extractor is **not** `.unload()`-ed per click (that would defeat the cache). Arm B holds two models (~9 GB resident) — fits the 16 GB envelope but tight with the browser/OS (`know-your-hardware`); pre-warm before the meeting.
6. **Rasterize at 300 DPI** (`pilot-13.yaml`) for the model input; display can downscale.
7. **All prompts + model-IDs read from `configs/arm-{a,b}.yaml` (`cohort.prompt_template_override`) + `COHORT_MANIFEST`** (Granite reader prompt + `max_tokens=1536`); nothing hard-coded in the page (`horus-config-discipline`).
8. **Registered** in `app/Home.py` under a new "Try it" navigation section, distinct from "Evaluation".

**Integration:** reuses `src/horus/eval` primitives + `app/components/theme` (palette) + `app/data/fields` (labels/order) + `app/data/approaches` (config-driven method/model resolution). The read-only data readers (`results`/`metrics`/`mlflow_store`) are **not** used. No new dependency (`streamlit` + `mlx-vlm` + `pypdfium2` already installed).

## Source archival

- Internal: ADR-036 (parent app + §D read-only constraint), ADR-038 (the two arms + Arm B two-pass mechanism), ADR-034/035/037 (strategy + 19-field schema + `purpose_summary`), ADR-009/032/034 (model IDs), ADR-014 (300-DPI rasterizer), ADR-027 (honesty axis rationale).
- External: Streamlit `st.file_uploader` / `st.cache_resource` / `st.spinner` / `st.radio` re-verified via context7 `/streamlit/docs` (2026-06-03); snapshot in `docs/sources/tools/streamlit.md`. Key facts: `file_uploader` returns an in-memory `UploadedFile` (BytesIO, not a path → temp-file write required); `cache_resource` is the correct load-once decorator for an ML model.

## Supersession trigger

Superseded / amended if **any** of:

1. The **#82 end-user prototype is built as a separate deployable** (FastAPI + Ollama + Docker) rather than folded in as a page → a new ADR records the split and the shared-component boundary (this is also ADR-036 supersession trigger 2).
2. The demo needs **scoring** (e.g., a held-out set with GT is wired into the page) → a new ADR ratifies the scoring path (it would no longer be "visual review only").
3. A **third method** (the regex baseline, or a future arm) is added → amend §Decision pt 2 (additive; not a re-decision).
4. The model-load latency or memory footprint forces a different serving model (e.g., a background worker / a separate inference service) → a new ADR ratifies it.

## Consequences

- HORUS gains an end-user "upload → pick a method → Read" surface for live, unscored extraction — the meeting deliverable.
- The read-only guarantee for the research/analysis surfaces is preserved and explicitly bounded.
- The live orchestration is reusable + tested; the page is thin.
- `#109` closes when the page works locally + lands; `#82` remains open (this is only its Layer-1 slice).
- A new caching pattern (`st.cache_resource` for a model) enters the app alongside the existing `st.cache_data` (data) — documented here.
