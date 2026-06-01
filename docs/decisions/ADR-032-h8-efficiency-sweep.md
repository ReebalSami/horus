# ADR-032 — H8 efficiency sweep: per-model tps + peak memory, memory-fit verdict, throughput-claim reframe

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-01 |
| **Milestone** | `experiments-validated` (HND-4 per re-audit plan `~/.windsurf/plans/horus-reaudit-review-d23373.md`; H8 efficiency substrate) |
| **Authored by** | Cascade (issue #77 implementation session; plan `~/.windsurf/plans/horus-issues-77-75-79-522413.md`) |
| **Issue** | [`ReebalSami/horus#77`](https://github.com/ReebalSami/horus/issues/77) |

## Context

H8 (pre-registered 2026-05-31 via ADR-031) states: *"MLX-routed VLMs achieve ≥3× decode tokens/sec compared to Transformers-MPS-routed VLMs at comparable F1 on the ZUGFeRD corpus, and the cohort's local document VLMs run within the M1 Pro / 16 GB unified-memory envelope."* The `pilot-13-full` run predates the ADR-017 (#52) perf instrumentation, so it logged **no** efficiency metrics; issue #77 (HND-4) is the dedicated re-run to obtain `decode_tps` / `inference_tps` / `peak_memory_gb` / `%_max` per model.

> **NOTE — issue #77's body still labels this "H4 substrate".** That label predates the 2026-05-31 ADR-031 hypothesis-label reconciliation: the efficiency hypothesis is **H8** (§6 H4 is the Layer-3 graph-vs-vector hypothesis). This ADR uses the corrected **H8** label throughout.

The planning Socratic walk (plan file) established that the H8 statement is a **conjunction** of two claims with very different testability on this hardware, which this ADR addresses head-on rather than overclaiming.

## Current-state survey (2026-06-01)

| Fact | Evidence | Implication for H8 |
|---|---|---|
| MPS `decode_tps` is **unmeasurable** | ADR-017 + `ExtractionResult` docstring: `TransformersMPSExtractor` sets `generation_tps = 0.0` because public `transformers.generate()` cannot separate decode from prefill timing | The decode-throughput half of H8 has **no MPS number** to compare against — the only 2 MPS-backed cohort models (`MinerU`, `paligemma2`) report `decode_tps = 0.0` (sentinel, not zero) |
| Backend is **confounded with model identity** | Each cohort model is bound to exactly one backend (MinerU/paligemma2 = transformers-only; the 5 MLX models = MLX-only). Verified in `COHORT_MANIFEST` | "MLX vs MPS" across the cohort is really "these 5 models vs those 2 models" — not a clean backend benchmark |
| `MinerU` **swaps** the 16 GB envelope | ADR-028 real-timing measurement (~1323 s/page, ~15.75 GB mean / 16.63 GB max); **independently reproduced by this #77 run** (13.40 GB post-extract snapshot = 105.4 % of the 12.71 GB recommended MPS working set; 1314.60 s wall; 0.73 e2e_tps) | Its measured throughput is memory-starved (swap), not compute-bound → would artificially inflate any MLX/MPS ratio |
| The cohort has **no same-model both-backend pair** natively | `COHORT_MANIFEST` | To get a confound-free backend comparison, a controlled pair must be constructed deliberately (this ADR adds the granite-docling-258M MPS twin, bf16, matching the MLX entry's precision) |
| The ADR-017 instrumentation **exists** (shipped #52) | `make inspect-pilot-13` two-column `decode_tps`/`e2e_tps` table; `mx.get_peak_memory()` (MLX) + `torch.mps.driver_allocated_memory()` snapshots (MPS) | The re-run needs only a fresh config + (for the controlled pair) one manifest entry — no instrumentation code |

ADR-031 supersession-trigger (b) explicitly anticipated splitting H8 into decode-throughput vs memory-fit; line 80 sanctions reporting an untested/untestable clause honestly ("not evaluated within scope"). This ADR exercises that provision.

## Options considered

| Option | Why considered | Why not chosen |
|---|---|---|
| **Synthesis: measure substrate + render the memory-fit verdict cleanly + reframe the throughput claim to `inference_tps`, documenting decode-≥3× as a hardware/API limitation** (chosen) | Honest + complete; matches what is actually measurable; ADR-031-sanctioned | — |
| Build MPS decode-tps instrumentation (`TextIteratorStreamer` first-token timing) | Would let the decode-≥3× claim be tested directly | Fragile + model-specific (custom-arch VLMs may not cooperate); MinerU still swap-confounded; risks re-opening the issue; rejected on cost/uncertainty |
| Test H8 verbatim on `decode_tps` only | Literal reading of the pre-registration | Impossible — the MPS side has no `decode_tps` (sentinel 0.0); would yield a vacuous or misleading verdict |
| Skip the controlled pair (cohort-only sweep) | Smallest scope | Loses the only path to a confound-free backend datapoint; user chose to include it |

## Decision + integration thoughts

Run a dedicated efficiency sweep (`configs/h8-efficiency.yaml`, MLflow experiment `h8-efficiency`, `dev_only: true`, `resume_on_existing_run: false`) over the 7 ADR-009 working models **+ a controlled-pair MPS twin** of granite-docling (`ibm-granite/granite-docling-258M`, bf16, added to `COHORT_MANIFEST`; the same model + precision as the existing MLX entry), on 1 invoice (`EN16931_Einfach`). One invoice because the efficiency metrics are ~invoice-stable and the H8 verdict is **qualitative** (fits-vs-swaps; measurable-vs-not) — n=1 is sufficient for the verdict and caps MinerU (the ~22 min/page swapper) to one run; multi-invoice variance is a documented follow-up.

**The H8 verdict is rendered as two clauses** (per ADR-031 trigger (b)):
- **Memory-fit clause** — cleanly testable on the M1 Pro / 16 GB envelope. Reported per model via `peak_memory_gb` + `%_max`.
- **Decode-throughput (≥3×) clause** — documented as **NOT cleanly testable** on this hardware/instrumentation, for three reasons (MPS `decode_tps` unmeasurable; backend⊥model confound; MinerU swap). The measurable proxy (`inference_tps`, end-to-end) is reported for all models, and the granite-docling MLX-vs-MPS controlled pair is the one confound-free backend datapoint attempted.

**Integration:** reuses the ADR-014 harness + ADR-017 instrumentation + ADR-011 MLflow with zero new infra. The `factur-x` GT route + the (post-#75) v1-aware parser are unaffected (this sweep uses the v2 `EN16931_Einfach` fixture). The granite-MPS manifest entry is excluded from `pilot-13.yaml` working_models (not an ADR-009 cohort member) and from the ADR-009 category-distribution invariant (test updated to filter it).

## Results

> Per-model perf from `make inspect-pilot-13 CFG=configs/h8-efficiency.yaml` on the `h8-efficiency` parent run `316ca04c00dd4e19a2eaab58737b019e` (MLflow experiment `h8-efficiency`, 1 invoice `EN16931_Einfach` @ 2 pages, n=1). Sorted by `wall_s` ascending (fastest first).

| model | backend (precision) | F1 | wall_s | decode_tps | e2e_tps | peak_GB | %_max |
|---|---|---:|---:|---:|---:|---:|---:|
| `ibm-granite/granite-docling-258M` | Transformers-MPS (bf16) | 0.000 | 1.00 | — | 0.00 | 1.31 | 10.3 % |
| `ibm-granite/granite-docling-258M-mlx` | MLX (bf16) | 0.800 | 9.83 | 189.17 | 120.94 | 1.54 | 12.1 % |
| `google/gemma-4-E4B-it` | MLX (4-bit) | 0.696 | 48.19 | 26.74 | 22.51 | 7.58 | 59.6 % |
| `PaddlePaddle/PaddleOCR-VL` | MLX (4-bit) | 0.800 | 60.93 | 141.86 | 13.36 | 8.09 | 63.7 % |
| `zai-org/GLM-OCR` | MLX (4-bit) | 0.571 | 71.73 | 108.33 | 5.79 | 3.02 | 23.7 % |
| `google/paligemma2-3b-mix-448` | Transformers-MPS (bf16) | 0.421 | 305.30 | — | 7.78 | 7.05 | 55.4 % |
| `allenai/olmOCR-2-7B-1025` | MLX (4-bit) | 0.500 | 338.33 | 23.19 | 6.58 | 8.40 | 66.1 % |
| `opendatalab/MinerU2.5-Pro-2604-1.2B` | Transformers-MPS (bf16) | 0.929 | 1314.60 | — | 0.73 | 13.40 | 105.4 % |

**Reading the table (measurement caveats, per ADR-017):**
- **`%_max` is relative to the 12.71 GB recommended MPS working set** (`torch.mps.recommended_max_memory()`, logged once at parent as `perf.mps_recommended_max_gb`), **not** the 16 GB physical RAM. The recommended working set is the threshold above which Metal begins spilling; exceeding it is the swap trigger. MinerU's 13.40 GB = 105.4 % of that set (and 83.8 % of physical 16 GB; ADR-028's transient 16.63 GB max reached physical RAM).
- **`decode_tps`** = decode-only tokens/s, native `GenerationResult.generation_tps`, **MLX-routed models only**. The 3 Transformers-MPS rows render `—`: decode-only timing is unmeasurable via the public `transformers.generate()` API (sentinel 0.0).
- **`e2e_tps`** = end-to-end tokens/s (prompt-encode + decode + post-proc); always computable; use for user-perceived latency.
- **`peak_GB`** measurement differs by backend: MLX = true peak via `mx.get_peak_memory()`; MPS = post-extract snapshot via `torch.mps.driver_allocated_memory()` (a documented **under**-estimate of transient peak — so MinerU's true transient peak is ≥ 13.40 GB, consistent with ADR-028's higher number).
- **`decode_tps`/`e2e_tps` use each model's native tokenizer** → NOT cross-model comparable in absolute terms (ADR-017). The only intended comparison is within-model MLX-vs-MPS (the controlled pair).
- F1 is the single-invoice micro-F1 (n=1); the efficiency metrics — not F1 — are this sweep's deliverable (`dev_only: true` keeps F1 out of the thesis lineage).

### Controlled-pair finding (granite-docling-258M, MLX vs MPS, bf16)

Final perf confirms the early observation. The MLX twin generated **1187 tokens** → F1 **0.800**, e2e_tps **120.94**, decode_tps **189.17**, in **9.83 s**. The MPS twin generated **0 tokens** → F1 **0.000**, e2e_tps **0.00**, decode_tps unmeasurable, in **1.00 s** — near-instant, empty generation. The same model + precision (bf16) + prompt produces valid DocTags on MLX but degenerate (empty) output on Transformers-MPS (idefics3 path), most plausibly a chat-template / prompt-format mismatch in the transformers idefics3 generation path (out of #77 scope to fix; filed as #99). **Consequence:** the controlled pair did NOT yield a clean MLX-vs-MPS throughput datapoint — the MPS side does no equivalent work (0 tokens), and the H8 "at comparable F1" precondition fails outright (0.000 vs 0.800). This *reinforces* the decision to reframe rather than force a ≥3× decode verdict: even a deliberately model-matched, quant-matched pair hit a backend-specific integration failure.

## Verdict

**Memory-fit clause — HOLDS for the cohort, with one documented exception (MinerU).**
7 of 8 models run within the M1 Pro recommended MPS working set (12.71 GB): peak ranges **1.31–8.40 GB** (10.3 %–66.1 %), the largest being `olmOCR-2-7B` at 8.40 GB / 66.1 % — comfortable headroom. `MinerU` alone breaches it: **13.40 GB post-extract snapshot = 105.4 %** of the recommended set (and ADR-028's transient measurement reached 16.63 GB, the 16 GB physical ceiling). Its 1314.60 s wall and 0.73 e2e_tps are memory-starved (swap), not compute-bound. → The H8 sub-claim *"the cohort's local document VLMs run within the 16 GB envelope"* **holds for 7/8 models**; MinerU is the documented swapper, reproduced independently here from ADR-028. (The controlled-pair MPS twin fit at 1.31 GB but is excluded from the accuracy comparison — 0 tokens.)

**Decode-throughput ≥3× clause — NOT cleanly evaluable on this hardware/instrumentation (final position, per ADR-031 trigger (b) / line 80).**
Three independent reasons, all confirmed by the data:
1. **No MPS `decode_tps` exists** — all 3 Transformers-MPS models (`granite-258M`, `paligemma2`, `MinerU`) report the 0.0 sentinel (rendered `—`). A direct MLX-vs-MPS *decode* ratio is impossible by construction.
2. **The one deliberate controlled pair is broken on the MPS side** — `granite-docling-258M` MPS produced 0 tokens (e2e_tps 0.00, F1 0.000) vs MLX 1187 tokens (e2e_tps 120.94, F1 0.800). No valid ratio; "comparable F1" fails.
3. **The `e2e_tps` proxy is confounded** — each cohort model is backend-locked (model ⊥ backend), and native tokenizers are not cross-comparable. MLX models reach high decode_tps (granite-mlx 189.17, PaddleOCR-VL 141.86) but this cannot be attributed cleanly to the *backend* over the *model*.
→ The ≥3× decode claim is **honestly bounded as not cleanly testable** — a documented final position, not an open TODO. Even a model-matched, quant-matched pair hit a backend-specific failure, which itself is the strongest evidence for the reframe.

**Efficiency–accuracy note (surfaced, not part of the H8 verdict):** the most accurate model on this invoice (`MinerU`, F1 0.929) is also the slowest and the only swapper, while `granite-docling-258M-mlx` reaches F1 0.800 in 9.83 s — **~134× faster wall-clock at near-equal accuracy**. For the thesis's local-deployment story, the MLX document-VLMs (granite-mlx, PaddleOCR-VL) dominate the efficiency frontier; MinerU buys its top F1 with a swap-bound 22-minute runtime that is impractical at scale on 16 GB.

## Source archival

No new `docs/sources/` stubs required: no new library/dataset/paper is adopted. The granite-docling-258M (transformers/idefics3) model is IBM-published, apache-2.0, already in the same family as the archived granite-docling MLX entry; the instrumentation + harness are ADR-017/014; MLflow is ADR-011.

## Supersession trigger

This ADR is superseded if **either**: (a) MPS decode-only timing becomes measurable (e.g., a future `transformers` API exposing first-token latency, or an adopted `TextIteratorStreamer` instrumentation) AND a swap-free host is used — enabling a direct, confound-controlled decode-≥3× test; **or** (b) the H8 throughput claim is promoted to a thesis result requiring multi-invoice variance bars + a fixed-hardware re-run (≥32 GB / no-swap, or CUDA) — a new ADR ratifies that protocol.

## Consequences

- H8 gains its efficiency substrate (per-model `decode_tps`/`inference_tps`/`peak_memory_gb`/`%_max`) in MLflow experiment `h8-efficiency`; closes #77.
- The decode-≥3× clause is **honestly bounded** as not-cleanly-evaluable on local hardware — a final, documented position (not an open TODO), per ADR-031 line 80.
- `COHORT_MANIFEST` gains the granite-docling-258M MPS twin (11th entry; documented as the H8 controlled-pair variant, excluded from the ADR-009 cohort invariants).
- Follow-ups (out of #77 scope): the transformers-MPS idefics3 degenerate-output issue (#99); multi-invoice throughput variance; MPS decode-tps instrumentation.
