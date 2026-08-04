# ADR-057: Reader selection — Qwen3-VL family (4B winner, one 8B sibling test)

**Status**: Accepted (8B-vs-4B sub-decision pending the single pre-registered test below)
**Date**: 2026-08-02
**Refs**: ADR-054 (endgame step 1 this concludes), ADR-056 (ruler fix + blank-page guard), #114 (bake-off ticket), #55 (fine-tune epic), `eval/reader-findability-audit.md` (the manual-audit evidence base), ADR-009 (cohort; §3.2 traded the 8B away for local deployability — partially superseded here for the reader role)

## Context (current-state survey)

ADR-054 step 1 ran the GPU bake-off (A10G bf16, 29 sealed val invoices, 4 candidates +
granite baseline). The raw tables were then subjected to the findability-first audit
protocol agreed with the user (2026-08-02 walk): deterministic ruler → manual
invoice-by-invoice judgment of EVERY miss against the page rasters → ruler/GT fixes →
corrected comparison. Chronology of instruments (each documented):

1. Raw ruler (pre-ADR-056): olmOCR 0.774 / Qwen-4B 0.777 / MinerU-2604 0.741 /
   MinerU-2605 0.630 / granite 0.658. Ruler ceiling on PERFECT text: 0.794 → tables
   dominated by measurement artifacts (ADR-056).
2. Fixed ruler (ADR-056): olmOCR 0.913 / Qwen-4B 0.906 — order inverted within noise
   → endpoint F1 added as second instrument: olmOCR 0.8335 / Qwen-4B 0.7829 (raw).
3. Manual audit (52 residual misses judged by hand; `eval/reader-findability-audit.md`)
   → ruler wave 2 + GT fixes + 23 page-impossible exclusions → **corrected findability**:
   **Qwen-4B 0.970 / olmOCR 0.965 / MinerU-2604 0.925 / granite 0.830 / MinerU-2605
   0.753**; text-layer ceiling 0.995. Blank-page guard applied to both finalists →
   **corrected F1: olmOCR 0.8335 / Qwen-4B 0.8118**.

### The decisive mechanism evidence (not scores — behavior)

- **olmOCR-2-7B silently drops margin furniture** (letterheads/footers/header blocks):
  ALL 19 of its true misses, including seller IBAN/BIC/USt-ID on all three Mustang
  fixtures, seller identity on all three FNFE fixtures, and Beleg-Nr/-Datum on the
  Kostenrechnung. For the Steuerberater domain this is the worst failure class —
  silent, systematic per layout, unrecoverable downstream.
- **Qwen3-VL-4B reads every margin block**; its 16 true misses are rare
  character-level slips INSIDE values (`Lieferant`→`Lieberant` f/b on 7
  stylesheet-rendered fixtures; FR-VAT digit-run +1; one dropped reference). Corrupted
  values are detectable downstream (checksummed IDs, validation); dropped blocks are not.
- Sibling context: MDPBench (arXiv 2603.28130) documents photographed-document
  degradation for open parsers — orthogonal caveat, unchanged from ADR-054.

## Options considered

1. **olmOCR-2-7B** (higher corrected F1 by +0.022) — rejected: the F1 edge rides on
   cleaner body text flattering the zero-shot structurer (a Phase-E prompt-work
   target), while its findability loss is concentrated on the domain-critical banking
   /identity fields and cannot be fixed downstream. Also 2× the size and officially
   EN-only.
2. **Qwen3-VL-4B** — **chosen**: wins the pre-registered decision rule on both clauses
   (highest corrected findability 0.970 AND smaller); reads margins; officially
   multilingual (German); half the inference cost; its failure class is rare,
   character-local, and validation-detectable.
3. **MinerU family** — eliminated on evidence (2605 loop-collapses, ADR-056 table;
   2604 third at 0.925).
4. **Keep granite** — eliminated (0.830 corrected; the ADR-054 recovery premise).

## Decision (+ integration thoughts)

1. **Reader = Qwen3-VL family.** Presumptive winner **Qwen/Qwen3-VL-4B-Instruct**.
2. **One pre-registered sibling test** (user-approved, 2026-08-02 walk): during the
   regeneration relaunch, run `Qwen/Qwen3-VL-8B-Instruct` (manifest-wired by this ADR;
   same arch/prompt/decode) over the same 29 sealed val invoices at bf16. Decision
   rule, fixed in advance: the 8B replaces the 4B **iff** it (a) strictly reduces the
   16 audited true misses, (b) shows no new failure class under the same audit
   protocol, and (c) costs ≤ 2.5× the 4B's per-invoice wall-clock (frontier
   trade-off). Otherwise the 4B stands confirmed. Either way NO further candidates —
   the model-jumping freeze from the walk applies (any future swap = new ADR).
3. **Transcript regeneration** (ADR-054 step 2) with the confirmed winner over all
   146 GT-bearing invoices, blank-page guard active, committed into
   `docs/sources/transcripts-multipage/` (same-dir lineage, slug-discriminated;
   user-confirmed) — supersedes granite as the Arm-B canonical reader lineage
   (granite transcripts retained per ADR-011).
4. **Findability protocol becomes standing methodology** (user direction): the
   deterministic ruler (ADR-056 + wave 2) is the primary metric; an LLM-as-judge
   second instrument + agreement matrix + cost-quality frontier land with the
   Phase-A2 apparatus; the manual audit is the gold arbiter. Target state: reader
   findability ≈ ceiling (0.995 here) before structurer work begins.

## Source archival

Per `horus-source-archival`: HF model cards verified via the HF API this session
(Qwen3-VL-4B/8B-Instruct, olmOCR-2-7B-1025, MinerU2.5-Pro-2604/2605); in-repo evidence:
`eval/reader-findability-audit.md`, `data/finetune/findability-exclusions.json`,
`data/finetune/bakeoff/**`, `data/finetune/eval-zeroshot-{qwen,olmocr}-val.json`,
`scripts/findability_corrected.py`. Existing stubs: `docs/sources/tools/mineru-2-5.md`,
`docs/sources/papers/wang-2026-mineru25-pro.md`, `docs/sources/papers/mdpbench-2026-*`.

## Supersession trigger

- The 8B sub-decision self-resolves by the pre-registered rule in §Decision 2.
- If the regenerated-lineage re-baseline does not lift materially over 0.6771
  (< +0.10), ADR-054's supersession trigger governs (revised recovery plan).
- If a future reader candidate is proposed, it must beat the corrected-findability +
  audited-mechanism protocol of this ADR (not a public leaderboard number) — see the
  MinerU-2605 lesson (OmniDocBench 95.69 vs 0.753 here).
