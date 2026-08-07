# ADR-057: Reader selection — Qwen3-VL family (4B winner, one 8B sibling test)

**Status**: Accepted — **fully resolved 2026-08-07**; the 8B sibling test is adjudicated in
§"8B sibling test — result" and the 4B stands confirmed. No sub-decision remains open.
**Date**: 2026-08-02 (8B adjudication appended 2026-08-07)
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

## 8B sibling test — result (appended 2026-08-07)

**Outcome: the 4B stands confirmed.** The pre-registered rule in §Decision 2 is conjunctive
(replace **iff** a **and** b **and** c). Clauses (a) and (c) pass; **clause (b) fails**.

No new GPU spend was required. The 8B bake-off had **already been run** in the 2026-08-04
batch and all 29 transcripts were committed under
`data/finetune/bakeoff/qwen__qwen3-vl-8b-instruct/` — same A10G session, same manifest
prompt/decode, so the same-hardware premise clause (c) depends on holds. The run was never
adjudicated, which is why this ADR sat at "pending" while its evidence was already on disk.

| clause | requirement | measured | verdict |
|---|---|---|---|
| (a) | strictly reduces the 16 audited true misses | **13** (corrected findability **0.976** vs 4B 0.970) | **PASS** |
| (b) | no new failure class under the same audit protocol | **decode-collapse on 1/29**; 4B does this on **0/29** | **FAIL** |
| (c) | ≤ 2.5× the 4B per-invoice wall-clock | **1.247×** (mean 59.63 s → 74.38 s over 29) | **PASS** |

Clauses (a) and (c) are reproducible with
`uv run python scripts/findability_corrected.py` (same ruler, same 23 audited exclusions)
and from the `# Extract: <n>s total` header each transcript carries.

### Why clause (b) fails

On `zugferd_2p0_EXTENDED_Fremdwaehrung` the 8B **collapses into a repetition loop**. Both
readers report `Pages: 3`, `Errors: 0/3`. The 4B emits a complete `Belegsummen` block:

```
**Bruttosumme** | 1021,91
**Erhaltene Anzahlungen** | -500,00
**Zahlbetrag** | 521,91
```

The 8B reaches `| Steuerbetrag in | |` and then emits **911 `&nbsp;` entities** in a single
5,466-character repeated run, never producing the three summation values. It loses **BT-112
grand total, BT-115 due payable, and BT-113 prepaid** — three of its 13 misses, all on this
one invoice, all domain-critical money fields. Its wall-clock on this invoice is 179.95 s vs
the 4B's 78.50 s (2.3×, against a 1.247× corpus mean), consistent with spending the token
budget on the loop.

A scan for degenerate generation (≥ 50 `&nbsp;`, or any ≥ 10× repeated substring run over 400
chars) finds **8B: 1/29, 4B: 0/29**.

This is a **new class for the Qwen family**. The 4B's characterised mechanism is "reads every
margin block; rare character-level slips INSIDE values" — corrupted-but-present values, which
are detectable downstream by checksums and validation. An unbounded decode collapse that
truncates the monetary summation is not a character slip; it is the **MinerU-2605 loop-collapse
class** this project already rejected on evidence (ADR-056, 0.753). Clause (b) exists precisely
to stop a better headline number from buying a worse mechanism, which is the same reasoning
that rejected olmOCR at +0.022 F1 in §Options 1.

### Honest limits of this adjudication

- The 23 page-impossible exclusions in `data/finetune/findability-exclusions.json` were
  derived from the **4B/olmOCR** manual audit. The 8B's 13 misses have **not** had an
  independent manual judge pass, so some may be (V) ruler-variant or (P) not-findable rather
  than true reader errors. That would move (a) further in the 8B's favour, not against it —
  so the conclusion is unaffected, because the rule fails on (b), not (a).
- Only 3 of the 13 are the collapse. The other 10 are composite-address and multi-line-name
  normalisation gaps plus the same FR-VAT digit-run the 4B also misses; spot checks confirm
  the content **is** present in the 8B transcript for those, so they are ruler-shaped, not
  reader-shaped.
- One invoice is a small denominator. The rule as written asks whether a new failure *class*
  appears, not how often — deliberately, because a silent unbounded failure is a
  qualitative risk in the Steuerberater domain, not a rate to be averaged.

### Consequences

- Reader stays `Qwen/Qwen3-VL-4B-Instruct`. The canonical transcript lineage in
  `docs/sources/transcripts-multipage/` is **unchanged**, so no regeneration and no
  re-baseline: the fine-tune gate remains **0.8257** on sealed validation (< 0.90).
- The model-jumping freeze in §Decision 2 now binds fully: any future reader swap is a new ADR.
- §Decision 4's target state (reader findability ≈ ceiling before structurer work) is met as
  far as the pre-registered budget allows — 0.970 against a 0.995 text-layer ceiling, with the
  one candidate authorised to close that gap having been tested and rejected on mechanism.

## Source archival

Per `horus-source-archival`: HF model cards verified via the HF API this session
(Qwen3-VL-4B/8B-Instruct, olmOCR-2-7B-1025, MinerU2.5-Pro-2604/2605); in-repo evidence:
`eval/reader-findability-audit.md`, `data/finetune/findability-exclusions.json`,
`data/finetune/bakeoff/**`, `data/finetune/eval-zeroshot-{qwen,olmocr}-val.json`,
`scripts/findability_corrected.py`. Existing stubs: `docs/sources/tools/mineru-2-5.md`,
`docs/sources/papers/wang-2026-mineru25-pro.md`, `docs/sources/papers/mdpbench-2026-*`.

## Supersession trigger

- ~~The 8B sub-decision self-resolves by the pre-registered rule in §Decision 2.~~
  **Resolved 2026-08-07** — see §"8B sibling test — result": clause (b) failed, 4B confirmed.
  Re-opening this would require a new ADR under the §Decision 2 model-jumping freeze.
- If the regenerated-lineage re-baseline does not lift materially over 0.6771
  (< +0.10), ADR-054's supersession trigger governs (revised recovery plan).
- If a future reader candidate is proposed, it must beat the corrected-findability +
  audited-mechanism protocol of this ADR (not a public leaderboard number) — see the
  MinerU-2605 lesson (OmniDocBench 95.69 vs 0.753 here).
