# Fine-tune attribution audit — zero-shot val F1 decomposition

**Question**: the sealed-val zero-shot baseline landed at `overall_micro_f1 = 0.6771` — far below the
target (> 0.90). Before renting a GPU (#55 follow-up), decompose the loss: is it the **reader**
(granite-docling transcripts missing values), the **structurer** (gemma failing to map readable
values), or the **eval definition** (the ADR-041/042 field expansions being intrinsically too hard)?

**Method** (three instruments, all on the 29 sealed val invoices, structurer = `google/gemma-4-E4B-it`
zero-shot, matched-precision decode):

1. **Field-cluster re-score** — persist the structurer's raw generations
   (`scripts/finetune_evaluate.py --save-outputs`), re-score the *same* predictions per cluster:
   legacy-16 vs ADR-041 flat additions vs ADR-042 repeating groups
   (`scripts/finetune_attribution.py`).
2. **Readable/unreadable FN split** — every FN classified by whether the GT value (with German/ISO
   date, decimal-comma, grouped-IBAN variants) is literally findable in the granite transcript
   (reader's fault if absent).
3. **Oracle-transcript probe** — run the identical structurer pass on *perfect* GT-rendered
   transcripts (`--oracle`): the score is the structurer's ceiling independent of reading.

## Results

| arm | reader text | overall_micro_f1 |
|---|---|---|
| baseline | granite-docling-258M transcripts | **0.6771** |
| oracle | perfect GT-rendered transcripts | **0.9608** |

Per-cluster (pooled over 29 invoices; FN split by transcript answerability):

| cluster | granite F1 | oracle F1 | FN (granite) | FN unreadable (reader) | FN readable (structurer) |
|---|---|---|---|---|---|
| legacy-16 | 0.837 | 0.975 | 98 | 77 | 21 |
| new-flat (ADR-041) | 0.687 | 0.900 | 82 | 39 | 43 |
| group:line_items | 0.555 | 0.971 | 239 | 157 | 82 |
| group:vat_breakdown | 0.590 | 0.986 | 78 | 31 | 47 |
| group:skonto | 0.333 | 0.750 | 8 | 0 | 8 |

Loss-mass shares (granite arm, 597 signal errors = 505 FN + 92 FP):

- **reader-attributed** (GT value absent from transcript): 304 = **51 %**
- **structurer/readable-missed + spurious FP**: 293 = **49 %**

## Verdict — reader-dominated

- The **oracle probe is the decisive instrument**: on perfect text the *unmodified, zero-shot*
  structurer already scores **0.9608** — including 0.971 on line items and 0.986 on VAT breakdown.
  The ADR-041/042 definitions are **not** intrinsically too hard; the eval-definition share of the
  loss is ≈ 0.
- The string-findability split (51 % reader) **understates** the reader's share: "readable" only
  means the value string occurs somewhere in the transcript — mangled table structure and garbled
  context still sink extraction. The oracle delta is the honest bound: of the 0.32 total gap,
  **~0.28 is reading-induced, ~0.04 is structurer capability**.
- `legacy-16` at 0.837 on granite text confirms the earlier > 0.90 era is not comparable: those runs
  scored 16 easy header fields on in-sample invoices; the sealed-val baseline scores 30+ fields
  incl. repeating groups on a harder mix.
- Residual structurer headroom (skonto 0.750, new-flat 0.900 on oracle) is precisely the LoRA
  fine-tuning target — but fine-tuning on 0.68-quality transcripts caps the achievable result;
  **the reader must improve first**.

**Decision consequence**: proceed with the GPU reader bake-off per `scripts/gpu/README.md`
(pre-flight condition "audit verdict = reader-dominated" is satisfied).

## Reproduction

```sh
uv run python scripts/finetune_evaluate.py --split val --label zero-shot \
  --save-outputs data/finetune/zeroshot-outputs --out data/finetune/eval-zeroshot-val.json
uv run python scripts/finetune_evaluate.py --split val --label oracle --oracle \
  --save-outputs data/finetune/oracle-outputs --out data/finetune/eval-oracle-val.json
uv run python scripts/finetune_attribution.py --split val \
  --outputs data/finetune/zeroshot-outputs \
  --baseline-report data/finetune/eval-zeroshot-val.json \
  --oracle-report data/finetune/eval-oracle-val.json \
  --out data/finetune/attribution-val.json
```

JSON artifacts: `data/finetune/attribution-val.json` (granite arm) ·
`data/finetune/attribution-oracle-val.json` (oracle arm) · both force-added over `data/*` gitignore
alongside the sealed split, per the sealed-evidence precedent.

## Amendment (ADR-059) — the oracle arm was measuring its own renderer

The verdict above rests on the oracle probe, so the probe's own correctness is load-bearing. Auditing
it turned up **five defects in `render_oracle_transcript`**, every one of which depressed the ceiling
it was supposed to establish. All are in the measurement apparatus, not the model:

| # | Defect | Effect on the "perfect" page |
|---|---|---|
| 1 | Labels were spec jargon, not what pages print | printed wordings occurring in **0/146** real transcripts |
| 2 | Group cells rendered `<label> <value>`, no separator | `Pos 1`, `Umsatzsteuer S` — **103 cells** lost to punctuation alone |
| 3 | `category_code` borrowed `Umsatzsteuer`, which labels the VAT *section* | `Umsatzsteuer: S` → 11 FNs (1.000 → 0.831) |
| 4 | Row prefix was `enumerate`, an unlabelled number | returned as `rate_percent` on rows with no rate; **contradicted the GT** on 0-based invoices |
| 5 | Multi-line CII values printed verbatim into a one-line row | line-item table structurally broken on 1/29 invoices |

Defect 2 is the instructive one: `<label> <value>` only *looks* fine while labels are long German
compounds. Fixing defect 1 shortened them, and the latent ambiguity became a 103-cell loss on
PERFECT input. Grounding a label is not enough — it must also be *separable* from its value.

Defect 3 is the counterexample to naive grounding: `Umsatzsteuer` is well attested (97/146) but names
a different concept than the value beside it. **Grounded-but-wrong is worse than synthetic-and-clear**;
it is now a documented exception gated by `make audit-prompts`.

### Corrected ceiling (29 sealed val invoices, same structurer, same decode)

| metric | before | after |
|---|---|---|
| `overall_micro_f1` | 0.9676 | **0.9719** |
| `micro_f1` (flat) | 0.9641 | **0.9743** |
| `presence_conditional_f1` | 0.9717 | **0.9812** |
| `spurious_emission_rate` | 0.0176 | **0.0145** (lower better) |

`before` is the archived tier-1 oracle generations **re-scored under current code**, not the 0.9608
printed earlier in this document — that figure predates later scorer/normalizer changes. Both columns
share one scorer, so only they are comparable to each other.

The two fields the amendment was raised for both leave zero, confirming they were apparatus artefacts
rather than structurer blind spots:

- `allowance_total_amount` **0.000 → 0.909** (FN=6 → TP=5, FN=1)
- `charge_total_amount` **0.000 → 1.000** (FN=5 → TP=5)

`vat_breakdown` (0.986) and `skonto` (0.750) end unchanged; `line_items` is flat at 0.971 with better
precision (FP 21 → 11); `line_items.line_id` reaches **1.000**.

### Open findings (NOT fixed here — apparatus limits, recorded not hidden)

- **`line_items.seller_assigned_id` 0.929 → 0.776** (FN 1 → 8). On the `*_Rabatte` invoices the
  structurer merges the following cell into the name (`name="Kunstrasen grün 3m breit | Art-Nr: KR3M"`,
  `seller_assigned_id=null`), i.e. `" | "` is a weak boundary once the label is the short, real-world
  `Art-Nr`. Reverting to the unattested `Artikelnummer` would flatter the model by reintroducing
  defect 1, so it stands. The real fix is a **true table render** (column headers stated once,
  positional cells), already flagged as a known layout caveat in the renderer docstring.
- **GT `name` sometimes holds a whole product block**, not a name — e.g.
  `"GTIN 4123456000014\nArt-Nr-Lieferant ZS9997\nZitronensäure 100ml\nVerpackung: Flasche\nVKE/Geb: 1"`,
  with `seller_assigned_id` simultaneously `None` even though the article number sits inside that
  blob. No reader can win this; it is a GT-definition question, not an extraction one.
- **`skonto` 0.750** is unchanged by all of the above and remains genuine structurer headroom.

Regression guards: `tests/test_finetune_dataset.py` pins the label/value separator, the GT-sourced
row ordinal, and the one-row-one-line contract (the last hermetically, since the corpus is gitignored
and corpus-gated tests never run in CI).
