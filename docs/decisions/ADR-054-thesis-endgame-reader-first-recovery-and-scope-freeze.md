# ADR-054: Thesis endgame — reader-first recovery, conditional LoRA, and scope freeze

**Status**: Accepted
**Date**: 2026-07-31
**Refs**: ADR-007/009 (VLM cohort), ADR-031 (hypothesis reconciliation + no-HARKing honesty), ADR-041/042 (field expansions the audit exonerates), #55 (fine-tune epic), #114 (GPU bake-off runbook ticket), `eval/finetune-attribution-audit.md` (the evidence this ADR acts on)

## Context (current-state survey)

### The measurement that forced this decision

The sealed-val zero-shot baseline landed at `overall_micro_f1 = 0.6771` — far below the > 0.90
target. Before any GPU spend, a three-instrument attribution audit (29 sealed val invoices,
structurer = `google/gemma-4-E4B-it` zero-shot, matched precision, **fully local** — the oracle
arm is the same MLX pass fed GT-rendered perfect transcripts, no cloud involved) decomposed the
loss (`eval/finetune-attribution-audit.md`, commit `2494e34`):

| arm | reader text | overall_micro_f1 |
|---|---|---|
| baseline | granite-docling-258M transcripts | 0.6771 |
| oracle | perfect GT-rendered transcripts | **0.9608** |

- **Reader-dominated**: ~0.28 of the 0.32 gap is reading-induced; structurer capability loss ≈ 0.04.
- **Eval definitions exonerated**: on perfect text the ADR-041/042 expansions score 0.971 (line
  items) and 0.986 (VAT breakdown) — the new fields are NOT too hard; their eval-definition loss
  share ≈ 0.
- 51 % of signal errors have the GT value literally *absent* from the granite transcript
  (string-findability lower bound; mangled-context casualties push the true reader share higher).

### The reader landscape (verified 2026-07-31)

- **`opendatalab/MinerU2.5-Pro-2605-1.2B`** — MinerU 3.3-release checkpoint (2026-06-11); fixes
  the 2604 checkpoint's stability issues on complex documents and adds **native multilingual OCR**
  (German relevance). Same 1.2 B qwen2_vl architecture as the 2604 entry already in
  `COHORT_MANIFEST` → identical extractor path. Lineage: MinerU2.5-Pro is absolute SOTA on
  OmniDocBench v1.6 (95.69, arXiv 2604.04771), beating GLM-OCR, PaddleOCR-VL-1.5, Gemini 3 Pro and
  Qwen3-VL-235B — via data engineering alone, architecture unchanged. HF repo existence verified
  via the HF API this session.
- **`Qwen3-VL-4B`** — general-purpose VLM contrast arm; already manifest-wired.
- **`granite-docling-258M`** — current canonical reader; mean answerability 0.658 on the sealed
  val split; Pearson(answerability, micro_f1) = 0.927 — the correlation that motivated the
  bake-off design.
- **Real-world caveat (MDPBench, arXiv 2603.28130)**: open-source parsers drop ~17.8 % on
  *photographed* documents. Our corpus is born-digital PDF renders, so bake-off numbers will not
  transfer 1:1 to camera-scanned Belege — an honesty note for the thesis, not a blocker.
- Local hardware reality: MinerU at bf16 breached the M1 Pro's 12.71 GB Metal working set
  (ADR-032: 13.40 GB → swap, 1314 s/invoice). On the rented A10G 24 GB it is trivial
  (1.2 B params, vLLM-recommended). The privacy-first thesis premise is *on-premises* deployment,
  not necessarily a 16 GB laptop — a workstation GPU keeps documents inside the firm.

### The capacity constraint

The thesis writeup phase has not started. The remaining project capacity must cover: the reader
recovery, the final evaluation lineage, and the entire writeup. Every additional experiment
directly displaces writing. The user has directed: Layers 2–3 (graph RAG etc.) are dropped to
future work, and **after this phase the experiment track stops**.

## Options considered

1. **Keep full scope** (Layers 2–3, cloud arm, degraded-Belege robustness, then write) —
   rejected: displaces the writeup entirely; H3–H6 need infrastructure that does not exist yet
   (Layer-2 KG, Layer-3 retrieval). A thesis with a complete, honest L1 story beats an
   unfinished three-layer sketch.
2. **Fine-tune the structurer on current granite transcripts, skip the reader work** — rejected
   on the audit's evidence: the structurer is not the bottleneck (0.9608 on perfect text);
   fine-tuning against 0.658-answerability transcripts caps the achievable F1 near the current
   0.68 — GPU spend with no path to 0.90.
3. **Cloud-API reader** (Gemini / GPT-4o class) — rejected: violates the privacy-first premise
   that is the thesis's core claim (documents never leave the firm). Usable only as a
   *comparison* arm, and that arm is exactly what's being descoped.
4. **Reader-first recovery + conditional LoRA + scope freeze** — **chosen**, detailed below.

## Decision (+ integration thoughts)

**The endgame is a fixed, short pipeline; each step gates the next; no new experiments after it.**

> **Execution-substrate amendment (2026-07-31, same day — superseded by amendment 2 below)**:
> AWS denied the G-instance vCPU quota increase twice (fresh-account ramp policy, support
> case 178548148400462, both us-east-1 and eu-central-1). The rented box is now a **RunPod
> A40 48 GB pod, EU region** (≈ $0.35–0.44/hr, per-second billing, no quota gate; runbook
> §1B). The decision's substance — one rented CUDA session, same candidates, same decision
> rule, same budget envelope — is unchanged; only the provider swapped. Cost improves
> (< $5 projected vs ~$6 on A10G).

> **Execution-substrate amendment 2 (2026-08-01)**: the quota appeal on the same case
> (178548148400462) was **APPROVED** — "Running On-Demand G and VT instances" raised to
> 4 vCPUs in eu-central-1 Frankfurt. This supersedes the RunPod amendment above before it
> was ever executed: the rented box is the originally planned **AWS `g5.xlarge` (A10G
> 24 GB), eu-central-1, on-demand ≈ $1.01/hr** — runbook §1A reinstated as plan of record,
> §1B retained as fallback. Decision substance again unchanged — same candidates, same
> decision rule, same ≲ $15 budget envelope (projected ≈ $6 on A10G).

1. **GPU reader bake-off** (#114, runbook `scripts/gpu/README.md`, one rented CUDA-box
   session — AWS g5.xlarge per amendment 2 above): candidates are **MinerU2.5-Pro-2605-1.2B
   (lead)**, **Qwen3-VL-4B (contrast)**,
   **granite-docling-258M (control)**, all via `--force-transformers` at bf16. Decision rule:
   highest mean answerability on the 29 sealed val invoices; ties break toward the smaller model.
   The 2605 checkpoint is manifest-wired by this ADR; the 2604 entry stays untouched for
   pilot-13 lineage comparability.
2. **Transcript regeneration** with the winner over the full corpus (same GPU session), synced
   back and committed as the new canonical reader lineage (supersedes, does not delete, the
   granite transcripts per ADR-011 retention).
3. **Re-baseline**: re-run the zero-shot structurer eval on the new transcripts (local M1, no GPU
   needed — the structurer pass is the same MLX rig as the audit).
4. **Conditional LoRA**: fine-tune the structurer (per #55) **only if** the re-baseline stays
   < 0.90 overall. If the reader fix alone clears 0.90, LoRA is *skipped* and recorded as
   not-needed — the cheapest possible thesis result. (Oracle ceiling 0.9608 bounds what LoRA can
   add on top of a good reader: a few points on skonto/new-flat.)
5. **Scope freeze**: H3–H6 (Layers 2–3, graph RAG, router), the cloud comparison arm (H1's full
   form), degraded/photographed-Belege robustness (MDPBench axis), and template-shift (H7) move
   to the thesis **future-work chapter**. They are pre-registered, honestly reported as "not
   evaluated within thesis scope" per the ADR-031 no-HARKing convention.
6. **Writeup phase begins** when the reader-recovery milestone closes (event-based gate, not a
   date). The final numbers lineage for the thesis: sealed split (train/val fingerprints) →
   attribution audit → bake-off table → final transcripts → final baseline (+ LoRA delta if
   step 4 fired). Each artifact is already committed or has a committed runbook.

Integration notes: the 2605 manifest entry reuses the 2604 wiring (`TransformersMPSExtractor`,
`repetition_penalty=1.05`, `"OCR this document."`) — zero new code paths; the bake-off script,
answerability scorer, split seal, and eval harness are all already merged on
`feat/structurer-finetune`.

## Source archival

Per `horus-source-archival`:

- `docs/sources/papers/wang-2026-mineru25-pro.md` — MinerU2.5-Pro paper (arXiv 2604.04771), added
  with this ADR.
- `docs/sources/papers/mdpbench-2026-multilingual-document-parsing.md` — MDPBench (arXiv
  2603.28130), added with this ADR (real-world photographed-doc caveat).
- `docs/sources/tools/mineru-2-5.md` — pre-existing MinerU tool stub (dual-backend distinction).
- `eval/finetune-attribution-audit.md` + `data/finetune/attribution-*.json` — in-repo evidence.

## Supersession trigger

- If the bake-off winner's regenerated transcripts do NOT lift the re-baseline materially
  (< +0.10 over 0.6771), the reader-dominance diagnosis needs re-examination (mangled-context
  hypothesis vs answerability metric validity) — supersede with a revised recovery plan.
- If the thesis scope changes (e.g., an extension makes Layer-2 feasible), the scope-freeze
  clause is superseded by a new ADR; the frozen hypotheses remain pre-registered and untouched.
- If a strictly better ≤ 2 B open-weights German-capable reader ships before the GPU session
  runs, swap the lead candidate via a one-line manifest addition + ADR amendment note — the
  bake-off design already accommodates any manifest-wired candidate.
