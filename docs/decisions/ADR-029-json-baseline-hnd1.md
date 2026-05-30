# ADR-029 — Structured-output JSON baseline (HND-1): clean JSON extraction arm over a 6-invoice ZUGFeRD subset

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-30 |
| **Milestone** | `experiments-validated` (HND-1 per re-audit plan `~/.windsurf/plans/horus-reaudit-review-d23373.md`; the clean JSON baseline feeding the HND-3 approach-gate #76) |
| **Authored by** | Cascade (issue #54 implementation session; plan `~/.windsurf/plans/hnd1-json-baseline-4899b9.md`) |
| **Issue** | [`ReebalSami/horus#54`](https://github.com/ReebalSami/horus/issues/54) |
| **Supersession trigger** | (1) HND-3 (#76) selects a structured-output *approach* beyond prompt-only JSON (grammar/constrained decoding, JSON-schema-guided generation, or fine-tuning) → a new ADR surveys that library/method and this prompt-only JSON arm becomes the comparison floor, not the chosen method. OR (2) the held-out Belege split (#78) becomes the canonical thesis-reporting surface → the JSON baseline is re-measured there and these in-corpus numbers become diagnostic-only (mirrors ADR-028 §A). OR (3) a future cohort model release proves JSON-capable (the ADR-019/021 verdict is release-specific) → the 3-model scope extends and the sweep re-runs. OR (4) the canonical 16-field schema (ADR-012) changes → the per-model JSON prompts + per-label pooling are revisited. |

## Context

HORUS extracts 16 EN16931-anchored fields from local-VLM invoice transcripts and scores them against factur-x XML ground truth (ADR-013 scorer + ADR-014 cohort harness). Two extraction *approaches* exist in the codebase:

1. **Free-form + Layer-2 adapter** (`adapter_mode="regex"`) — the model transcribes the document in its native style; a German-label-anchored extractor (ADR-013) plus the section-scoped Belegsummen MONEY fallback (ADR-028) pulls the 16 fields out. This is the `pilot-13-full` baseline.
2. **Structured-output JSON** (`adapter_mode="json"`, ADR-018) — the model is prompted to emit a single JSON object with the 16 keys directly; a thin JSON adapter (`adapters_json.py`) parses it.

HND-0 (#74, ADR-027) shipped 4 additive metrics. HND-2 (#41, ADR-028) hardened approach (1)'s MONEY recovery. **HND-1 (#54) measures approach (2)** on a multi-invoice subset, so the HND-3 approach-gate (#76) can weigh "prompt-only JSON" against "free-form + Belegsummen adapter" on equal footing rather than on the single-invoice probe.

The ADR-018 structured-output probe (corrected verdict, ADR-019 bug catalog + ADR-021 verdict matrix) established that **only 3 of the 7 cohort models can emit usable JSON at all**:

| Model | JSON-capable? | Evidence (ADR-019/021) |
|---|---|---|
| `google/gemma-4-E4B-it` | ✅ yes — F1 0.696, honest nulls | general-instruction-tuned; emits clean JSON |
| `allenai/olmOCR-2-7B-1025` | ✅ yes — F1 0.667 (Arm B ≡ Arm A) | RLVR OCR model; JSON hacked via prompt per HF discussion #16 |
| `zai-org/GLM-OCR` | ✅ yes — F1 0.571 (Arm B only) | needs per-model native prefix; Arm A → 0.0 (schema-mimicry) |
| `ibm-granite/granite-docling-258M-mlx` | ❌ no | DocTags model; ignores JSON instruction (ADR-019 §B3 decoder-loop) |
| `opendatalab/MinerU2.5-Pro-2604-1.2B` | ❌ no | DocTags model; decoder-loop on JSON OOD prompt (ADR-019 §B7) |
| `PaddlePaddle/PaddleOCR-VL` | ❌ no | decoder-collapse (ADR-019 §B6) |
| `google/paligemma2-3b-mix-448` | ❌ no | base VLM; refuses (ADR-019 §B8; knowable at design time) |

This ADR runs the 3 JSON-capable models on a 6-invoice subset and **cites** ADR-019/021 for the 4 incapable ones rather than re-running them (their JSON-mode failure is structural, already-evidenced, and re-running MinerU alone costs ~22 min/page on the M1 Pro 16 GB host per ADR-028 §B — hardware-prohibitive and scientifically redundant per `know-your-hardware` + the ADR-020 model-behavior-vs-extractor-bug rule).

### Re-inference was required (not offline rescore)

The ADR-020 offline-rescore path re-*parses* cached transcripts; it cannot produce JSON-mode numbers because JSON-mode transcripts existed for **exactly one** invoice (`EN16931_Einfach`, the probe). The 26-invoice `pilot-13-full` transcripts are free-form; re-parsing them with the JSON adapter yields F1≈0 (ADR-018 rejected this as "Option C1"). A ≥5-invoice JSON baseline therefore *required* re-running the 3 models in JSON mode. This is a model-behavior measurement (a new prompt arm), not an extractor-bug rescore — so re-inference is the correct, ADR-020-compliant choice.

## Current-state survey (2026-05-30)

| Component | Where | Role |
|---|---|---|
| `adapter_mode: Literal["regex","json"]` + `prompt_template_override` | `src/horus/eval/harness.py` + `CohortConfig` (ADR-018) | The two declarative fields that switch the harness to JSON mode + per-model prompts. **Reused unchanged.** |
| `adapters_json.py` (`to_predicted_dict_multipage`) | `src/horus/eval/adapters_json.py` (ADR-018) | Parses model JSON → 16-field predicted dict. **Reused unchanged.** |
| `configs/pilot-13-structured-probe-native-json.yaml` | `configs/` (ADR-018) | The pre-registered **Arm B** prompt set (per-model native prefix + JSON suffix). The 3 JSON-capable models' prompts are copied verbatim into the HND-1 overlay. |
| `scripts/run_pilot_13.py` + `make pilot-13` | `scripts/`, `Makefile` (ADR-014) | The harness runner. `--cfg` accepts multi-file composition (ADR-016). **Reused unchanged.** |
| `scripts/inspect_pilot_13.py` + `make inspect-pilot-13` | `scripts/`, `Makefile` (ADR-017/027) | Reads the experiment name from `--cfg` (the ADR-019 §B9 hardcoded-experiment limitation is fixed) and prints all 4 ADR-027 metrics from the per-run `per_field_scores.json`. **Reused unchanged — no report code written for HND-1.** |
| `eval/probe-verdict-matrix.md` | `eval/` (ADR-021) | The probe's 2×2 verdict surface, carried forward as the per-model JSON-capability provenance. |

**No production code changed.** HND-1 is one new YAML overlay (`configs/json-baseline.yaml`) + the re-inference run + the existing inspector + this ADR.

## Options considered

### Axis 1 — re-parse cached transcripts vs re-inference

| Option | Outcome |
|---|---|
| Offline rescore of the 26-invoice `pilot-13-full` transcripts with the JSON adapter | **Rejected.** Those transcripts are free-form; the JSON adapter finds no JSON object → F1≈0 (ADR-018 "Option C1"). Re-parsing cannot fabricate JSON the model never emitted. |
| **Re-inference: re-run the 3 models in JSON mode on the subset** | **Accepted.** A new prompt arm is a model-behavior measurement, which ADR-020 explicitly says *requires* re-running. ~50 min foreground on the M1 Pro; resume-safe. |

### Axis 2 — model scope (3 JSON-capable vs all 7)

| Option | Outcome |
|---|---|
| All 7 cohort models (maximal parity with `pilot-13-full`) | **Rejected.** The 4 incapable models' JSON failure is structural and already-evidenced (ADR-019/021). MinerU alone is ~22 min/page (ADR-028 §B); PaddleOCR collapses; PaliGemma refuses. Multi-hour run re-confirming known zeros, prohibitive on 16 GB unified memory. |
| **3 JSON-capable models; cite ADR-019/021 for the other 4** | **Accepted.** Scopes on pre-established evidence, transparently disclosed (this is a documented scoping decision, not silent cherry-picking — the 4 excluded models' verdicts are linked). Hardware-safe. |

### Axis 3 — prompt arm (A uniform vs B per-model native + JSON suffix)

| Option | Outcome |
|---|---|
| Arm A (uniform JSON prompt for all) | **Rejected.** GLM-OCR scores 0.0 under Arm A (schema-mimicry, ADR-019 §B4); it requires its native prefix. |
| **Arm B (per-model native prefix + JSON suffix)** | **Accepted.** Arm B dominates for all 3: Gemma A≡B (general-instruction-tuned, no prefix needed), olmOCR A≡B, GLM-OCR B 0.571 ≫ A 0.0. Reused verbatim from the pre-registered probe overlay → preserves apples-to-apples + pre-registration. |

### Axis 4 — `dev_only` flag (true exploratory vs false reported)

| Option | Outcome |
|---|---|
| `dev_only: true` (frame as exploratory, like the probe) | **Rejected.** The probe was a feasibility check ("can they emit JSON?"); HND-1 is a baseline measurement feeding a gate. Labelling it a throwaway dev fixture misrepresents its role. |
| **`dev_only: false` (reported, in-sample/diagnostic baseline)** | **Accepted.** Matches `pilot-13-full`'s status as the free-form in-corpus reported baseline, so HND-3's comparison is like-for-like. A new experiment name (`json-baseline`) keeps it off the canonical `pilot-13-full` experiment (the `dev_only` guard's only hard target). No-HARKing is satisfied by pre-registration (below), independent of the flag. |

## Decision + integration thoughts

Ship `configs/json-baseline.yaml` — a thin overlay composed on `configs/pilot-13.yaml` (ADR-016 multi-file deep-merge; list fields replace, so `working_models: [3]` replaces the base 7). It sets the new experiment/parent/transcript-dir, `adapter_mode: json`, `dev_only: false`, the 3 `working_models`, the 6-invoice `invoice_subset`, and the 3 verbatim Arm B prompts.

- **Run:** `HORUS_DASHBOARD=plain make pilot-13 CFG=configs/pilot-13.yaml,configs/json-baseline.yaml` (`plain` adapter gives line-by-line streaming for foreground observability; resume-safe via `mlflow.search_runs`).
- **Report:** `make inspect-pilot-13 CFG=configs/pilot-13.yaml,configs/json-baseline.yaml` → the 4 ADR-027 metrics, captured to `docs/sources/json-baseline-metrics.txt`. No report code written.

**Invoice subset (6, pre-registered):** `EN16931_Einfach` (simple + probe cross-check), `EN16931_Gutschrift` (credit note), `EN16931_Miete` (rent), `EN16931_Rabatte` (discounts → MONEY complexity), `EN16931_Innergemeinschaftliche_Lieferungen` (0 % VAT → tax edge), `XRECHNUNG_Einfach` (XRECHNUNG profile + factur-x date route per ADR-012 Probe 5). Chosen to span distinct field/tax/profile scenarios while avoiding the multi-page `Reisekostenabrechnung` (olmOCR runtime).

## Empirical results — 3 models × 6 invoices (18 tuples, 0 failed, 50 m 32 s)

Source: experiment `json-baseline` (id=11), parent run `0f934104a6b14dfcb87908bd7e5103fc`. Full report archived at `docs/sources/json-baseline-metrics.txt`; transcripts at `docs/sources/transcripts-json-baseline/`.

**Sanity cross-check vs the ADR-018 probe** (shared invoice `EN16931_Einfach`): Gemma `0.696` (probe `0.6957`), GLM-OCR `0.571` (probe Arm B `0.5714`), olmOCR `0.667` (probe `0.6667`). The re-inference reproduces the probe exactly → the harness + adapter are deterministic and the baseline is trustworthy.

**Per-model aggregate (mean micro-F1, τ=0.50):**

| Model | n | mean micro-F1 | wall s/inv | decode tps | peak GB (%MPS) | spurious-emission |
|---|---|---|---|---|---|---|
| `google/gemma-4-E4B-it` | 6 | **0.707** | 24.4 | 30.9 | 7.75 (61 %) | **0.000** |
| `allenai/olmOCR-2-7B-1025` | 6 | 0.660 | 383.8 | 21.0 | 8.59 (68 %) | 0.875 |
| `zai-org/GLM-OCR` | 6 | 0.475 | 90.2 | 127.1 | 3.01 (24 %) | 0.500 |

**ADR-027 4-metric report:**

| Model | n_inv | presence-conditional F1 | group-level F1 (KIEval) | spurious-emission rate |
|---|---|---|---|---|
| `allenai/olmOCR-2-7B-1025` | 6 | 0.706 | 0.000 | 0.875 |
| `google/gemma-4-E4B-it` | 6 | 0.706 | 0.056 | 0.000 |
| `zai-org/GLM-OCR` | 6 | 0.496 | 0.000 | 0.500 |
| **COHORT** | 18 | **0.643** | **0.019** | **0.458** |

**Per-canonical-label F1 (cohort-pooled, hardest first):** `buyer_reference` 0.000 (0/0/18) · `line_total_amount` 0.105 (1/0/17) · `buyer_vat_id` 0.167 (1/5/5) · `seller_tax_id` 0.235 (2/3/10) · `seller_vat_id` 0.286 (3/0/15) · `tax_basis_total_amount` 0.286 (3/0/15) · `tax_total_amount` 0.364 (4/0/14) · `seller_gln` 0.381 (4/2/11) · `grand_total_amount` 0.560 (7/0/11) · `due_payable_amount` 0.714 (10/0/8) · `buyer_name` 0.759 (11/0/7) · `delivery_date` 0.897 (13/1/2) · `issue_date` 0.909 (15/0/3) · `seller_name` 0.941 (16/0/2) · `invoice_number` 0.971 (17/0/1) · `invoice_currency_code` 1.000 (18/0/0).

### Findings (the HND-3 inputs)

1. **Honest-null vs hallucinate-on-absent is the headline JSON axis.** olmOCR and Gemma have **identical** presence-conditional F1 (0.706) — equal recall on GT-present fields — yet olmOCR's spurious-emission rate is 0.875 vs Gemma's **0.000**. Forced into JSON, olmOCR (and GLM-OCR, 0.500) invent plausible values for genuinely-absent fields; Gemma emits `null`. This is exactly the ADR-021 "canonical_keys penalises honest nulls" finding, now generalised across 6 invoices, and exactly what ADR-027's recall/precision decomposition was built to expose. **Gemma-4 is the standout JSON-capable model** (best F1, fastest, zero hallucination).
2. **Prompt-only JSON under-recovers the Belegsummen MONEY totals.** `line_total_amount` 0.105, `tax_basis_total_amount` 0.286, `tax_total_amount` 0.364, `grand_total_amount` 0.560 — far below the ~0.68–0.74 the ADR-028 regex+Belegsummen fallback achieves on the same fields (different cohort/corpus, so field-level qualitative, not a head-to-head). The models do not reliably place the totals into a JSON object. **This is the critical HND-3 input: "switch to JSON" does not obviously beat "free-form + Belegsummen adapter" — on MONEY it is markedly worse.** The rigorous same-tuple head-to-head is HND-3's job (#76).
3. **Group-level correctness is near zero.** KIEval all-or-nothing group F1 is 0.019 cohort-wide — almost no invoice yields a fully-correct seller/buyer/totals business group. Prompt-only JSON is far from structured-complete.
4. **Header/identity fields are easy; references and totals are hard.** `invoice_currency_code` 1.000, `invoice_number` 0.971, `seller_name` 0.941, dates ~0.90; while `buyer_reference` (BT-46) is 0.000 across all 18 (consistent with its ADR-028 FN behaviour) and the MONEY totals trail.

## Threats to validity / scope of these numbers

Mirrors ADR-028 §A — the same scope-bounding applies.

1. **In-sample / diagnostic.** All numbers are on the FeRD ZUGFeRD 2.2 *reference* corpus (clean, digitally-generated PDFs), in-sample. They are diagnostic, not a generalisation claim. No held-out split.
2. **External validity.** Real firm documents (scans, skew, stamps, heterogeneous layouts) will score materially lower. These numbers do **not** predict real-scan accuracy.
3. **Construct validity.** Reported F1 is micro-F1 with exact-match on normalised values (ANLS\* only for seller/buyer name). `0.707` is the harmonic mean of precision/recall over exact-match field outcomes on clean reference invoices, not "71 % of fields colloquially right".
4. **Canonical reporting surface.** The out-of-sample claim is deferred to the held-out Belege split (#78 / HND-5) + cloud comparison (#80 / HND-6). **Until #78 lands, no number here may be cited as HORUS's real-world accuracy.**
5. **Cohort-asymmetric comparison.** The MONEY comparison to ADR-028 is field-level qualitative (3 models × 6 invoices here vs 7 × 26 there). The like-for-like same-tuple JSON-vs-free-form comparison is HND-3 (#76).

## No-HARKing

The metric set (ADR-027) and the HND-1 scope (3 models, 6 invoices, Arm B, `dev_only` stance) were **pre-registered before any post-run numbers existed** — locked in the confirmed plan `~/.windsurf/plans/hnd1-json-baseline-4899b9.md` and encoded in `configs/json-baseline.yaml` (authored before the run). The Arm B prompts are the verbatim ADR-018 pre-registered set. No metric or scope was chosen after seeing results. The in-corpus numbers remain diagnostic; the held-out Belege split (#78) stays the canonical thesis-reporting surface.

## Source archival

No new external sources. Builds on the already-archived literature/tooling of ADR-018 (structured-output prompting), ADR-021 (KIEval `arXiv 2503.05488` for group-level F1; HELM + lm-eval-harness `--log_samples` precedent for transcript-as-evidence), and ADR-027 (the 4 metrics). The empirical evidence base is the newly-archived `docs/sources/transcripts-json-baseline/` (18 JSON-mode transcripts + per-field scores) and `docs/sources/json-baseline-metrics.txt` (the report), re-aggregatable offline per ADR-020.

## Cross-references

- Predecessors: `ADR-018` (structured-output probe — `adapter_mode`/`prompt_template_override` + Arm B prompts), `ADR-019` (per-model JSON-(in)capability bug catalog), `ADR-020` (re-inference-vs-rescore rule), `ADR-021` (2×2 verdict matrix — JSON-capability provenance), `ADR-027` (the 4 metrics reported here), `ADR-028` (the free-form+Belegsummen MONEY path this baseline contrasts with), `ADR-014` (the harness), `ADR-016` (multi-file YAML composition).
- Verdict provenance: `eval/probe-verdict-matrix.md` (ADR-021).
- Evidence: `docs/sources/transcripts-json-baseline/`, `docs/sources/json-baseline-metrics.txt`.
- Plan: `~/.windsurf/plans/hnd1-json-baseline-4899b9.md`.
- Successor gate: HND-3 approach decision (#76) — weighs this JSON baseline against the free-form `pilot-13-full` baseline.
- Issue: [`ReebalSami/horus#54`](https://github.com/ReebalSami/horus/issues/54) — closed by this PR.
