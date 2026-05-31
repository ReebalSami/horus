# ADR-030 — Reading-ceiling + approach-comparison diagnostic: reframing the HND-3 Layer-1 gate (#76) from winner-pick to diagnose-and-carry-both

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-31 |
| **Milestone** | `experiments-validated` (HND-3 per re-audit plan `~/.windsurf/plans/horus-reaudit-review-d23373.md`; the evidence gate that closes the experiment phase) |
| **Authored by** | Cascade (issue #76 implementation session; plan `~/.windsurf/plans/horus-hnd3-diagnose-first-approach-gate-b4ef56.md`) |
| **Issue** | [`ReebalSami/horus#76`](https://github.com/ReebalSami/horus/issues/76) |

> **Erratum (2026-05-31, per ADR-031):** references to "H2" below were corrected — #76 (free-form-vs-JSON extraction) is **not** §6 H2 (which is single-shot-vs-orchestrated). #76 is an **exploratory** diagnostic per brainstorm §4.2 branches-on-results; the arXiv 2503.08124 exploratory→confirmatory *continuum* is the methodology stance (kept), not a hypothesis label (dropped). See ADR-031.

## Context

Issue #76 (HND-3) is the gate that closes the `experiment` phase: it must compare the two Layer-1 extraction approaches — **free-form + Layer-2 adapter** (`adapter_mode="regex"`, hardened by the ADR-028 Belegsummen MONEY fallback) vs **native JSON** (`adapter_mode="json"`, ADR-018/029) — and decide which HORUS carries forward. The issue's own scope already demanded a **per-model + pooled 4-metric comparison** and **"honest reporting even if neither dominates"** — an **exploratory** diagnostic (brainstorm §4.2 branches-on-results; exploratory→confirmatory continuum, arXiv 2503.08124), **not** a §6 hypothesis test (§6 H2 is single-shot-vs-orchestrated; see ADR-031).

Two problems forced a reframe of the gate during the planning Socratic walk (recorded in the plan file):

1. **The comparison is too narrow to *decide the approach*.** Native JSON works on only 3 of the 7 cohort models (ADR-019/021); free-form works on all 7 (incl. the strongest reader, MinerU). A 3-model contest measures "for JSON-capable models, which output style extracts more *right now*" — a useful diagnostic, **not** a basis for choosing HORUS's Layer-1 approach. The user's analogy: racing two differently-sized riders on one bike size.
2. **Neither approach is at its best.** These are zero-shot numbers, no fine-tuning, the JSON path is bare `json.loads()` (no Pydantic/constrained decoding), the adapter is still maturing. Picking a winner on first-draft numbers would be premature and would violate the exploratory→confirmatory discipline (arXiv 2503.08124).

A third, decisive constraint is the **ADR-028 landmine**: `make inspect-pilot-13` reads the *stale* `pilot-13-full` MLflow run, where the 4 invoice-total MONEY fields are F1=0.000 (pre-ADR-028). Any comparison sourced from the inspector pits JSON against a **crippled** free-form baseline. The post-ADR-028 free-form numbers exist *only* via live re-score from transcripts.

Finally, the user surfaced a long-standing hypothesis worth testing directly: *"the VLMs read the invoices well; the bottleneck was the parser."* The pilot-13 retro + ADR-019 B1 + ADR-028 all support this for the MONEY fields, but it had never been **quantified per model and per field** — which is exactly what would tell us whether the high-ROI lever is the adapter (cheap) or the model (fine-tuning).

This ADR ratifies the reframe (**diagnose both honestly + carry both forward, staged**) and the diagnostic instrument built to do it.

## Current-state survey (2026-05-31)

| Component | Where | Why it could not produce the gate evidence |
|---|---|---|
| `make inspect-pilot-13` | `scripts/inspect_pilot_13.py` (ADR-017/027) | Reads **stale** saved MLflow scores — the ADR-028 landmine. Free-form MONEY = F1 0.000. Unusable for a fair comparison. |
| `make adapter-iterate` | `scripts/rescore.py` (ADR-016/028) | Re-scores live from transcripts (good), but globs **all** transcripts (no model/invoice subset filter — `--cfg` only reads `transcript_archive_dir`+`corpus_root`) and prints the 4 metrics **cohort-pooled only, never per-model**. Cannot produce #76's required per-model + 3×6-subset surface. |
| ADR-027 scorer | `src/horus/eval/scorer.py` | Public 4-metric helpers (`presence_conditional_*`, `spurious_emission_*`, `group_level_*`, `label_outcome_counts`, `f1_from_counts`) — **reusable as-is**. |
| Cached transcripts | `docs/sources/transcripts-multipage/` (182 = 7×26 free-form), `docs/sources/transcripts-json-baseline/` (18 = 3×6 JSON) | The complete offline evidence base. No VLM re-inference needed. |

Dated web survey (`search_web`, trustworthy sources only):

- **Tam et al. 2024, *"Let Me Speak Freely?"* (arXiv 2408.02442, EMNLP industry)** — format restrictions (JSON/constrained decoding) can *degrade* LLM performance; structured generation is not a free win. Corroborating external anchor (with scope caveat: that paper studies reasoning/constrained-decoding, vs HORUS's *prompt-only* extraction).
- **IBM Granite-Docling** (`docs/sources/papers/ibm-2025-granite-docling.md`) — a **single-pass** model, explicitly marketed as *avoiding* the chained OCR→layout→post-process pipeline because cascading stages compound error. Directly informs the "parser-agent" follow-up: IBM's flagship model argues *against* a multi-stage LLM parser; the Docling *library* is the ensemble path.
- **Qwen2.5-VL (3B/7B, open, M1-capable)** — widely rated top-tier for document/OCR extraction; **not** in the ADR-009 cohort. A concrete "are-we-missing-something" candidate for a follow-up evaluation.

## Options considered

**A — How to produce the gate evidence:**

| Option | Why considered | Why not chosen |
|---|---|---|
| Reuse `make inspect-pilot-13` | zero new code | reads the stale pre-ADR-028 MLflow run (the landmine) — scientifically invalid |
| Reuse `make adapter-iterate` (`rescore.py`) | live re-score, no new code | cohort-pooled only + no subset filter — cannot yield #76's per-model 3×6 surface |
| **New `scripts/reading_ceiling.py` (chosen)** | per-model + pooled + subset filter; adds the reading-ceiling + parser-loss split; defuses the landmine by construction (live re-score) | ~small new code + 1 shared-module refactor — justified: #76's own scope requires per-model metrics no existing tool emits |

**B — What the gate should output:**

| Option | Why considered | Why not chosen |
|---|---|---|
| Pick the Layer-1 winner now | closes #76 with a single decision | premature on zero-shot, un-optimized, 3-model-narrow data; violates the exploratory→confirmatory discipline |
| **Diagnose both + carry forward, staged (chosen)** | honest per #76's "neither dominates" clause; sets up the fine-tuning phase with evidence on *where* each approach's headroom is | defers the final pick — acceptable: #76 closes on a *characterization*, the down-select happens post-fine-tuning |

Both arms (free-form+adapter, native JSON) are internal (ADR-028, ADR-029); the external sources above are cited for framing and archived per `horus-source-archival`.

## Decision + integration thoughts

**Reframe ratified.** #76 closes the `experiment` phase with a fair **characterization** of both approaches + a **carry-both-forward (staged)** decision; the final Layer-1 pick is deferred to post-fine-tuning (exploratory→confirmatory; see ADR-031). The down-select happens before the expensive full fine-tuning + held-out (#78) run.

**Instrument shipped** (`scripts/reading_ceiling.py`, `make reading-ceiling`, report at `eval/reading-ceiling-and-approach-comparison.md`):

- **(A) Reading ceiling** — per GT-present field, does a surface form of the GT value appear in the raw transcript text? Upper bound on what *any* parser could extract. Surface forms are field-type-aware (German/US/ISO money + date locales; despaced CODE match). Invariant `readable ⊇ extracted(TP)` holds by construction. Honest caveat: it is an *upper-bound proxy* (substring presence, not verified field association).
- **(B) Parser-loss vs read-miss** — `parser-loss` = readable but not extracted (an *adapter* problem); `read-miss` = absent from raw (a *model* problem).
- **(C) Same-tuple 4-metric** — free-form (post-ADR-028) vs JSON on the identical 3 models × 6 invoices, per-model + pooled, via the ADR-027 scorer.

**Determinism guarantee:** the JSON arm reproduces ADR-029's `docs/sources/json-baseline-metrics.txt` exactly (per-model mean micro-F1 gemma 0.707 / olmOCR 0.660 / GLM 0.475; cohort presence 0.643 / group 0.019 / spurious 0.458). The tool exits non-zero on drift; a unit test pins it. This proves the tool wires the transcript→adapter→scorer path identically to the canonical pipeline.

**Findings (in-sample; diagnostic, NOT a verdict):**

*Reading ceiling & parser-loss (free-form, 7 models, full corpus):*

| model | ceiling | extracted | parser-loss | read-miss | MONEY ceiling | MONEY extracted |
|---|--:|--:|--:|--:|--:|--:|
| MinerU2.5-Pro-1.2B | 0.98 | 0.85 | 0.13 | 0.02 | 1.00 | 0.96 |
| granite-docling-258M | 0.98 | 0.65 | 0.32 | 0.02 | 1.00 | 0.97 |
| gemma-4-E4B | 0.96 | 0.51 | 0.45 | 0.04 | 1.00 | 0.62 |
| PaddleOCR-VL | 0.94 | 0.56 | 0.38 | 0.06 | 0.90 | 0.72 |
| paligemma2-3b | 0.61 | 0.25 | 0.36 | 0.39 | 0.58 | 0.19 |
| GLM-OCR | 0.60 | 0.42 | 0.18 | 0.40 | 0.49 | 0.19 |
| olmOCR-2-7B | 0.57 | 0.31 | 0.26 | 0.43 | 0.51 | 0.08 |
| **COHORT** | **0.81** | **0.51** | **0.30** | **0.19** | **0.78** | **0.53** |

*Same-tuple comparison (3 JSON-capable models × 6 invoices), cohort:*

| arm | mean micro_F1 | presence_F1 | group_F1 | spurious |
|---|--:|--:|--:|--:|
| free-form + adapter | 0.607 | 0.625 | 0.074 | **0.000** |
| native JSON | 0.614 | 0.643 | 0.019 | **0.458** |

Three load-bearing observations for the fine-tuning phase (none is a verdict):

1. **The parser IS the dominant bottleneck for the best readers** — confirming the user's hypothesis. Cohort free-form reads 81% of present values but the adapter extracts only 51% → **30% parser-loss**. For the strongest readers it is starker: gemma reads 0.96, extracts 0.51 (0.45 lost); Granite-Docling reads 0.98, extracts 0.65 (0.32 lost). The high-ROI lever is the **adapter / JSON instructions** (cheap, deterministic) before any fine-tuning.
2. **Free-form and JSON are ~tied on F1 but free-form is far more honest** — cohort 0.607 vs 0.614 mean micro-F1, but spurious-emission 0.000 vs 0.458. "Switch to JSON" does not obviously win; for a tax/audit tool, a 0.458 hallucination rate on absent fields is a serious mark against prompt-only JSON.
3. **JSON mode can *reduce* what a model reads** — gemma's reading ceiling drops 0.96 (free-form) → 0.61 (JSON). In-house corroboration of Tam et al. 2024: the format restriction is not free.

**Best-small-reader signal (vindicates the user's instinct):** Granite-Docling (258M, the *smallest* cohort model) ties MinerU for the **highest reading ceiling (0.98)** and reads MONEY near-perfectly (1.00 ceiling, 0.97 extracted) — its 0.32 overall parser-loss is almost entirely a *parser* gap, not a reading gap. This makes it a prime candidate for the "focus + fine-tune a small reader" follow-up (the diagnostic objectively ranked readers rather than assuming, per the plan's caution).

**Integration with the bigger puzzle:**

- **Shared loader refactor (ADR-016 lineage):** the transcript reader + GT cache were lifted from `scripts/rescore.py` into `src/horus/eval/transcripts.py` (public `parse_transcript` / `split_per_page_texts` / `build_gt_cache`); `rescore.py` now imports them (aliased to its private names — `test_rescore.py` stays green). One canonical transcript parser, no duplication.
- **Forward to `implement` / fine-tuning (#55):** the diagnostic is the substrate for the staged down-select. The `parser-loss` map says *where* adapter work pays off; the `read-miss` map says *which* models need fine-tuning; the honesty axis is a hard selection criterion for the tax domain.
- **No-HARKing:** the metric set (ADR-027) + the two configs (`pilot-13.yaml`, `json-baseline.yaml`) were pre-registered before any number existed; the tool reuses them unchanged.
- **In-sample:** ZUGFeRD synthetic corpus only. NO real-world-accuracy claim — out-of-sample reporting is deferred to the held-out Belege split (#78), per ADR-028 §A.

**Captured follow-ups (filed as issues, NOT built here):** (1) [#88](https://github.com/ReebalSami/horus/issues/88) — Pydantic-typed JSON path + validators; (2) [#89](https://github.com/ReebalSami/horus/issues/89) — focus + fine-tune the best small reader (Granite-Docling per the ceiling ranking); (3) [#90](https://github.com/ReebalSami/horus/issues/90) — evaluate Qwen2.5-VL as a cohort addition; (4) [#91](https://github.com/ReebalSami/horus/issues/91) — parser-agent (small LLM-as-parser) experiment, weighed against IBM's anti-cascade single-model evidence + the deterministic-adapter's no-hallucination property.

## Source archival

- `docs/sources/papers/tam-2024-format-restrictions.md` — **new** stub (Tam et al. 2024, arXiv 2408.02442, "Let Me Speak Freely?").
- `docs/sources/papers/ibm-2025-granite-docling.md` — existing stub (single-pass / anti-cascade framing).
- arXiv 2503.08124 (exploratory→confirmatory methodology) — already archived in `docs/sources/papers/neurips-paper-checklist.md` (supporting-reference list).
- Internal: ADR-027 (4 metrics), ADR-028 (MONEY adapter + landmine), ADR-029 (JSON baseline reproduced), ADR-018/019/021 (JSON-capability evidence), ADR-016/014 (rescore + transcript archive lineage). No external `docs/sources/` stub required for internal ADR cross-references.

## Supersession trigger

This ADR is superseded if **any** of:

1. The held-out **Belege split (#78)** becomes the canonical reporting surface → both arms are re-measured out-of-sample there and these in-sample diagnostic numbers become provenance-only (mirrors ADR-028 §A).
2. **Fine-tuning (#55)** produces post-tuning numbers for either arm → the staged down-select is made in a new ADR that selects the Layer-1 approach, and this diagnostic becomes the exploratory input it cited.
3. A new structured-output **method** (constrained decoding / grammar / JSON-schema-guided generation / a Pydantic-validated JSON path) lands → the "native JSON" arm here becomes the prompt-only floor, not the JSON ceiling, and the comparison re-runs.
4. The reading-ceiling proxy is shown to materially mislead (e.g., a measured false-positive rate that inverts a per-model parser-loss ranking) → the substring proxy is replaced by a normalizer-roundtrip check and the report regenerates.
