# ADR-034 — Held-out evaluation strategy + Layer-1 reader/structurer down-select (Granite reader + Gemma structurer)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-02 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (held-out-evaluation strategy session; plan `~/.windsurf/plans/horus-heldout-eval-strategy-d8c53c.md`) |
| **Issue** | No single closing issue — strategy ADR governing the implement milestone; reconciles the GitHub board (see §"Board reconciliation"). Substrate for #78 (held-out set), #88 (schema), #91 (structurer comparison), #55 (fine-tune), #50 (orchestration), #80 (cloud). |

> **This is the master record of the post-experiment Layer-1 pivot.** ADR-035 (schema) and ADR-036 (Streamlit app) are cross-linked sub-decisions. Read this first to understand why the cohort sweep narrowed to two models and how the board was reconciled.

> **Erratum (2026-06-02, apparatus-build session):** the §"Pre-registration" dev-surface line originally read *"the 26 ZUGFeRD + Aoschu + synthetic corpus."* **Aoschu was never acquired** — `docs/retros/m2d.5-step3-dataset-acquisition.md` records it as `skipped` (n<1K, unclear license) and it is absent from `data/`, configs, and code. The dev surface is corrected below to *"ZUGFeRD (v1+v2) + synthetic"*, with **FATURA2** (English, `data/raw/english/`, examined in `experiments/02-fatura2.py`) available for the non-German robustness probe (#104), and the multilingual probe realized as a synthetic English-content ZUGFeRD invoice (in-schema CII GT). This is a factual correction to a pre-registration line, not a decision reversal — recorded inline per the ADR-011 retention discipline. User-confirmed 2026-06-02.

## Context

The `experiment` phase closed with ADR-030 (reading-ceiling diagnostic) + ADR-032 (H8 efficiency) + ADR-031 (hypothesis-label reconciliation). Those left an explicit, pre-registered hand-off: the final Layer-1 approach pick is *deferred to the held-out Belege split (#78)*, decided with out-of-sample evidence (ADR-030 supersession trigger 1+2).

The implement phase therefore needs a **locked strategy** before any held-out number exists, or the thesis violates its own no-HARKing spine (the same spine ADR-031 had to repair after a *fabricated* hypothesis citation was found). This ADR is that lock. It resolves four coupled questions surfaced during the planning Socratic walk (recorded in the plan file):

1. **Which reader?** The pilot-13 F1 ranking (MinerU 0.710 > Granite 0.463) appeared to make MinerU the best reader. The reading-ceiling diagnostic (ADR-030) shows otherwise.
2. **Which structurer, and how many?** The 7-model cohort sweep is the wrong instrument for the held-out test (JSON works on only 3 of 7 models; the sweep confounds reader quality with parser-fit).
3. **Single-shot vs orchestrated?** The user's long-standing instinct ("the models read well; the parser is the bottleneck; a small LLM could parse better than regex") needs an honest test, not an assumption.
4. **Where does cloud fit?** H1 (local-vs-cloud) is the headline hypothesis but must not contaminate local iteration.

## Current-state survey (2026-06-02)

| Fact | Evidence | Implication |
|---|---|---|
| Granite and MinerU **read equally well** | ADR-030 reading ceiling (7×26 corpus): both 0.98 ceiling, both 0.02 read-miss, both 1.00 MONEY ceiling; Granite MONEY-extracted 0.97 ≥ MinerU 0.96 | MinerU's F1 lead is **not** a reading advantage |
| MinerU's F1 lead is **parser-fit** | ADR-030: MinerU parser-loss 0.13 (extracts 0.85/0.98) vs Granite 0.32 (extracts 0.65/0.98). The German-regex adapter parses MinerU's clean labelled cells better than Granite's DocTags | The bottleneck is the **structurer**, not the reader — confirms the user's hypothesis |
| Granite is ~**134× faster** + fits memory | ADR-032 (n=1 `EN16931_Einfach`): Granite-mlx 9.83 s / 1.54 GB (12 %) / F1 0.800; MinerU 1314 s / 13.40 GB (**105 %**, swaps) / F1 0.929 | MinerU is impractical on M1 Pro 16 GB; Granite is the deployable reader |
| Gemma is the **best + fastest + only-honest** JSON model | ADR-029 (3 JSON-capable models): Gemma 0.707 F1 / ~24 s / spurious **0.000**; olmOCR 0.660 / 0.875; GLM 0.475 / 0.500 | Gemma is the natural structurer; the other JSON-capable models hallucinate on absent fields |
| JSON-mode can *reduce* reading | ADR-030: Gemma ceiling 0.96 (free-form) → 0.61 (JSON); in-house corroboration of Tam et al. 2024 | A reader→structurer split protects reading while gaining structure |
| Held-out set not yet built | #78 (design proceeds; collection pending) | The frozen reporting surface must exist before any out-of-sample claim |
| No per-invoice inspection surface | ADR-015 (MLflow UI = run metrics only); ADR-026 (TUI = live-run progress only) | Error analysis + thesis figures need a dedicated viewer → ADR-036 |

Dated context: Granite-Docling (IBM, single-pass / anti-cascade — `docs/sources/papers/ibm-2025-granite-docling.md`) and Tam et al. 2024 (`docs/sources/papers/tam-2024-format-restrictions.md`) are already archived; both bear directly on the orchestrated-vs-single-shot question below.

## Options considered

**A — Reader:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| Keep the full 7-model cohort on the held-out set | maximal coverage | confounds reader quality with parser-fit; JSON works on only 3/7; 22-min/invoice MinerU is impractical at held-out scale |
| MinerU as the reader | top pilot-13 F1 | F1 lead is parser-fit, not reading (ADR-030); swaps the 16 GB envelope (ADR-032) — wrong for a local-first thesis |
| **Granite-Docling-258M (MLX) (chosen)** | ties MinerU's reading ceiling + MONEY at ~134× the speed, fits in 1.54 GB | the evidence-backed local reader; MinerU retained only as a slow accuracy-reference / upper bound |

**B — Structurer:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| Per-model native parsing (status quo regex adapter) | no new model | the 0.30 cohort parser-loss is exactly the failure being fixed; brittle to label/format/language variance |
| Dedicated text-parser LLM (Qwen2.5-3B-Instruct, MLX) | strong text→JSON, fast on M1 | adds a 3rd model + ADR + breaks the controlled design; kept as a **documented fallback** if Gemma underperforms on dev |
| **Gemma-4 (MLX) as the single structurer for both arms (chosen)** | best+fastest+only-honest JSON model (ADR-029); reused identically across arms | minimal footprint (2 models total) + makes the arm comparison *controlled* (see C) |

**C — Extraction arms (the single-shot-vs-orchestrated question):**

The chosen design uses **Gemma as the single structurer in both arms**, so the only variable is whether a specialist reader precedes it:
- **Arm A (single-shot):** image → Gemma → JSON.
- **Arm B (orchestrated):** image → Granite → text → Gemma → JSON.
- **Baseline:** the old German-regex adapter (ADR-013/028) — a one-shot brittleness baseline *and* an auditable, structurally-no-hallucination reference (important for a tax/audit tool).

This isolates the value of specialist reading (Granite) from the value of the structurer (held constant). Rejected alternative: comparing Gemma-JSON against MinerU+regex — that confounds reader, structurer, and parser simultaneously.

**D — Hypothesis framing (no-HARKing):**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| Label Arm-A-vs-B as a §6 **H2** test | H2 is single-shot-vs-orchestrated | Arm B is VLM+VLM, **not** the "orchestrated *specialist* pipeline" H2 names; ADR-031 explicitly ruled the analogous #76 format-comparison NOT-H2 and just repaired a fabricated H-citation |
| **Exploratory under §4.2 branches-on-results (chosen)** | honest per the §12 cite-an-`H_i`-or-mark-exploratory convention | a *true* H2 test needs a specialist-pipeline arm (Docling-library / MinerU-pipeline-backend) — that is #50's territory, an optional future experiment |

**E — Cloud sequencing:** run cloud H1 (#80) **last**, only after the local config is fine-tuned and locked. Iterating locally with a cloud number visible risks anchoring; and the held-out freeze must be measured once per approach (see §"Pre-registration").

## Decision + integration thoughts

1. **Reader = `ibm-granite/granite-docling-258M-mlx`.** MinerU demoted to an optional slow accuracy-reference (not a deployment reader).
2. **Structurer = `google/gemma-4-E4B-it` (MLX)** for both arms; **Qwen2.5-3B-Instruct (MLX)** is the documented fallback (its adoption would require its own model-choice ADR + source stub per `horus-source-archival`).
3. **Two arms + baseline**, as in option C. The structurer emits the German-canonical Pydantic schema of **ADR-035**; honesty (`spurious_emission`, ADR-027) is measured on every arm — a generative structurer *can* hallucinate, so Pydantic validation + a strict "extract-only-what-is-present, else null" instruction + the honesty metric are the guardrails that keep Arm B safe for the tax domain.
4. **Language-agnostic** by construction: the schema keys are canonical (German/EN16931), values are as-printed in any language; no German-label regex on the critical path. This is also what makes the held-out (real, multilingual) eval valid where the German-only regex adapter was not.
5. **Observability** via the Streamlit app of **ADR-036**.
6. **Arm-A-vs-B is exploratory**; H1 (local-vs-cloud) is the headline; H6 (validator-retry, the "recheck the numbers" idea) remains conditional and is *not* assumed (D11 found no measurable correctable error in-sample).

**Integration:** reuses the ADR-014 harness + ADR-027 scorer + ADR-011 MLflow. The new structurer arms slot in as `adapter_mode` siblings (cf. ADR-018 `adapters_json.py`). No production code is written in this ADR — the build is handed off to coding sessions (plan §"Coding-session handoffs").

## Pre-registration (locked before any frozen-set number exists)

- **Reporting surface:** the frozen Belege held-out set (#78). **Dev surface:** the ZUGFeRD (v1+v2) + synthetic corpus (FATURA2 English available for the non-German robustness probe; see Erratum above).
- **Hard rule:** prompts, schema, and fine-tuning are iterated on **dev only**. The frozen set is measured **once per approach** (Arm A, Arm B, regex baseline, post-fine-tune, cloud). "Best local" is judged on dev; the freeze is touched only for the final measurement. This is the no-HARKing / no-test-contamination spine.
- **Metrics:** the ADR-027 four-metric surface (micro/macro F1, presence-conditional F1, group-level F1, spurious-emission) + per-canonical-label F1. The honesty axis (`spurious_emission`) is a hard selection criterion for the tax domain.
- **Arms measured:** Arm A (Gemma single-shot), Arm B (Granite→Gemma), regex baseline; later fine-tuned Granite/Gemma; later cloud.
- **Reading-ceiling caveat** carried forward (upper-bound proxy; ADR-030 supersession trigger 4).

## Board reconciliation

Executed when this ADR merges; every change carries a comment citing this ADR. Full rationale per row lives here so the pivot is followable.

| Issue | Action | Why |
|---|---|---|
| **#99** Granite-258M MPS 0-tokens | **Close** | Off the critical path — Granite is used via MLX (works: 0.98 ceiling, 9.83 s). The MPS twin was an H8 controlled-pair artifact only (ADR-032, closed). |
| **#85** TUI dashboard crashes on MinerU load | **Close** | MinerU demoted to reference-only; the non-TTY TUI crash is a low-value edge; ADR-036's Streamlit app is the new analysis surface. |
| **#72** Roll out TUI display adapter | **Close** | Superseded by the Streamlit app (ADR-036) as the canonical observability surface; the ADR-026 TUI remains for live cohort-run progress but is not extended. |
| **#89** Focus + fine-tune Granite | **Close → merged into #55** | Duplicate of the fine-tuning work; #55 is the canonical fine-tuning issue (`adr`+`fine-tuning` labels + milestone). |
| **#55** Fine-tuning ADR + LoRA | **Rescope** | Drop MinerU as a fine-tune target (swaps, 22 min/inv); focus Granite (adapter-first → LoRA), absorbing #89. |
| **#88** Pydantic-typed JSON path | **Rescope** | Expand to the German-canonical schema serving *both* arms + the new fields + honesty guardrail + fine-tuning target (ADR-035). |
| **#91** Parser-agent vs adapter | **Rescope** | Becomes the decided structurer comparison: Arm B (Granite→Gemma) vs regex-baseline vs Arm A, on the frozen set, honesty axis. |
| **#81** Layer-1 production hardening | **Rescope** | Productionize the Granite+Gemma+Pydantic winner (post-experiment). |
| **#50** Multi-agent / orchestration ADR slot | **Activate** | Trigger firing; home for the exploratory orchestration decision (Arm-A-vs-B), and for any future *true* H2 specialist-pipeline arm. |
| **#80** Cloud H1 comparison | **Comment** | Sequenced last — fast-follow after local is fine-tuned and locked. |
| **#90** Qwen2.5-VL as reader | **Comment + low-priority** | Deferred (narrowed to Granite+Gemma). Qwen2.5-3B may reappear as the *text-parser fallback* — a distinct role from VLM-reader. |
| **#82** Working prototype (FastAPI+Streamlit+Docker) | **Comment** | The ADR-036 observability app is the unified app; this end-user prototype folds in later as a page. |
| **NEW** Streamlit observability app | **Create** (epic) | ADR-036; first increment Invoice Explorer + Approach Comparison. |
| **NEW** Eval-correctness + multilingual audit | **Create** | Validate scorer correctness + extend the reading-ceiling diagnostic to the new arms + a non-German robustness check. |

**Net:** 4 closed, 8 rescoped/commented, 2 new — a leaner board. Core implement spine after cleanup: #78 · #88 · #91 · #55 · #81 · #50 · the two new issues.

## Source archival

- Internal: ADR-030 (reading ceiling), ADR-032 (efficiency), ADR-031 (hypothesis labels), ADR-029 (JSON baseline), ADR-027 (metrics), ADR-014 (harness), ADR-013/028 (regex adapter), ADR-009 (cohort), ADR-007 (MLX/Transformers). No external `docs/sources/` stub required for internal cross-references.
- External (already archived, cited for the orchestrated-vs-single-shot framing): `docs/sources/papers/ibm-2025-granite-docling.md` (single-pass / anti-cascade), `docs/sources/papers/tam-2024-format-restrictions.md` (format restriction not free), arXiv 2503.08124 (exploratory→confirmatory continuum).
- Granite-Docling and Gemma-4 are already-adopted cohort models (ADR-009); no new model stub. Qwen2.5 adoption (fallback) would add `docs/sources/models/qwen2-5.md` at that time.

## Supersession trigger

Superseded if **any** of:

1. The frozen Belege held-out results land → both arms + baseline are reported out-of-sample; a results ADR records the final Layer-1 down-select and this becomes its pre-registration provenance.
2. Fine-tuning (#55) materially changes the arm ranking → the down-select ADR cites this as the pre-fine-tune baseline.
3. Gemma-as-structurer underperforms on dev → the Qwen2.5-3B fallback is adopted via its own model-choice ADR, amending option B here.
4. A *true* §6 H2 specialist-pipeline arm is built (#50) → the orchestration framing here is extended, not replaced.
5. Cloud H1 (#80) lands → H1 is reported; this ADR's local-only scope is noted as provenance.

## Consequences

- The implement milestone has a locked, evidence-backed, no-HARKing strategy; the held-out set becomes the confirmatory instrument for H1 (and exploratorily for the orchestration question).
- The board reflects the pivot (4 closed / 8 rescoped / 2 new); every change is traceable to this ADR.
- Two further ADRs follow: ADR-035 (schema) and ADR-036 (Streamlit app).
- MinerU is retained in the codebase as a reference reader but leaves the deployment path.
