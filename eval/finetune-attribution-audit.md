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
