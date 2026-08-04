# Per-field reporting audit — the TN/EXCLUDED contamination defect (#114)

**Status**: defect fixed; three GT/eval-definition findings it exposed remain OPEN.

**Trigger**: after the post-regeneration re-baseline (`overall_micro_f1` 0.6771 → 0.8141)
the plan was to aim the conditional LoRA (ADR-054 §Decision 4) at the weakest fields.
Ranking on `EvalReport.per_field_mean` put `tax_rate` at 0.241 and `rounding_amount` at a
perfect 1.000. Both were artifacts. The ranking was wrong in both directions.

## The defect

Three aggregation sites accumulated `FieldResult.score` for **every** outcome:

| site | surface affected |
|---|---|
| `src/horus/finetune/evaluate.py` | `EvalReport.per_field_mean` → the #55 eval JSONs |
| `src/horus/eval/harness.py` | `per_field_heatmap`, `cohort_heatmap.png`, live `model_mean_f1` |
| `src/horus/eval/arm_b.py` | `per_field_heatmap` (Arm-B) |

Per the ADR-013 truth table a `TN` scores **1.0** and an `EXCLUDED` scores **0.0**. Neither
carries signal — `_aggregate_micro_macro` and `label_outcome_counts` already drop both from
every F1 numerator and denominator. Letting them into a mean makes a field's reported number
a function of **how often that field happens to be absent**, not of how well it was read:

- a field that is usually absent and correctly predicted absent drifts toward **1.0**
- a field with many ADR-045/052 ill-posed exclusions drifts toward **0.0**

**The headline metrics were never affected.** `overall_micro_f1`, `micro_f1`,
`presence_conditional_f1`, `spurious_emission_rate`, and the cohort `micro_f1_*` numbers all
derive from TP/FP/FN counts and are sound. `0.8141` and the ADR-054 LoRA gate verdict stand.
This was a **diagnostic** defect — but the diagnostic is what aims the fine-tune.

## Fix

- `scorer.SIGNAL_OUTCOMES` + `scorer.is_signal_bearing()` — one shared predicate; all three
  sites now gate on it.
- `EvalReport` gained `per_field_f1` (pooled F1 from TP/FP/FN — **the** per-field diagnostic)
  and `per_field_outcomes` (raw `{TP, FP, FN, TN, EXCLUDED}` counts, so any derived number is
  auditable without a re-run). `per_field_mean` survives as a mean *comparator* score
  (ANLS\* for STRING) over signal-bearing outcomes only — useful for "how close", not an F1.
- A field with **zero** signal-bearing outcomes is now **omitted** rather than reported as
  1.0. Reporting 1.0 there says "always right" when it means "never asked".
- Regression tests: `tests/test_scorer.py` (predicate ↔ aggregator agreement, so a future
  outcome kind can't silently leak in) and `tests/test_finetune_evaluate.py` (a field's F1 is
  invariant to added TN/EXCLUDED; untested fields omitted; always-wrong reports 0.0).

## Corrected table — sealed val (29), structurer `gemma-4-E4B-it` zero-shot

Re-scored offline from the saved generations (`data/finetune/{zeroshot,zeroshot-qwen,oracle}-outputs/`)
— no VLM re-run. `n_sig` = signal-bearing outcomes; `tn` = correct rejections; F1 is pooled.

> **Reproduction gap**: `evaluate_structurer`'s docstring promises that `--save-outputs` exists
> so "offline re-scoring never has to re-run the VLM", but no CLI exposes that path —
> `scripts/rescore.py` re-scores saved *reader transcripts* (Arm-A), not saved *structurer
> generations*. This table was derived by driving `structurer.to_predicted_dict` + `score` +
> `_per_field_f1` over the three output dirs directly. A `--score-only <dir>` flag on
> `scripts/finetune_evaluate.py` closes the gap and is a prerequisite for the LoRA A/B
> (scoring adapter-vs-baseline generations without re-inference). Tracked as the next step.

| field | granite | qwen4b | oracle | gap→oracle | n_sig | tn | excl |
|---|---|---|---|---|---|---|---|
| payment_means_text | 0.222 | **0.286** | 1.000 | 0.714 | 12 | 17 | 0 |
| billing_period_end | 0.571 | **0.364** | 1.000 | 0.636 | 9 | 20 | 0 |
| payment_reference | 0.200 | **0.333** | 0.941 | 0.608 | 10 | 19 | 0 |
| payment_means_code | 0.267 | **0.556** | 1.000 | 0.444 | 13 | 16 | 0 |
| prepaid_amount | 0.000 | **0.333** | 0.750 | 0.417 | 5 | 24 | 0 |
| buyer_order_reference | 0.533 | **0.600** | 1.000 | 0.400 | 14 | 15 | 0 |
| seller_account_name | 0.800 | **0.615** | 1.000 | 0.385 | 9 | 20 | 0 |
| seller_bic | 0.444 | **0.615** | 1.000 | 0.385 | 9 | 20 | 0 |
| seller_tax_id | 0.421 | **0.571** | 0.929 | 0.357 | 15 | 14 | 0 |
| billing_period_start | 0.571 | **0.444** | 0.800 | 0.356 | 7 | 22 | 0 |
| buyer_vat_id | 0.545 | **0.600** | 0.923 | 0.323 | 7 | 22 | 0 |
| buyer_reference | 0.643 | 0.788 | 0.963 | 0.175 | 20 | 9 | 0 |
| seller_iban | 0.526 | 0.636 | 0.800 | 0.164 | 15 | 14 | 0 |
| seller_gln | 0.692 | 0.828 | 0.966 | 0.138 | 17 | 12 | 0 |
| delivery_date | 0.889 | 0.865 | 1.000 | 0.135 | 21 | 8 | 0 |
| payment_due_date | 0.667 | 0.914 | 1.000 | 0.086 | 19 | 10 | 0 |
| issue_date | 0.945 | 0.926 | 1.000 | 0.074 | 29 | 0 | 0 |
| seller_vat_id | 0.857 | 0.902 | 0.964 | 0.062 | 28 | 1 | 0 |
| tax_total_amount | 0.792 | 0.926 | 0.964 | 0.038 | 29 | 0 | 0 |
| due_payable_amount | 0.840 | 0.945 | 0.982 | 0.037 | 29 | 0 | 0 |
| grand_total_amount | 0.840 | 0.964 | 1.000 | 0.036 | 29 | 0 | 0 |
| invoice_currency_code | 0.840 | 0.964 | 1.000 | 0.036 | 29 | 0 | 0 |
| tax_basis_total_amount | 0.840 | 0.964 | 1.000 | 0.036 | 29 | 0 | 0 |
| line_total_amount | 0.698 | 0.885 | 0.906 | 0.021 | 29 | 0 | 0 |
| document_type | 0.964 | 0.964 | 0.982 | 0.018 | 29 | 0 | 0 |
| buyer_address | 0.945 | 0.982 | 1.000 | 0.018 | 29 | 0 | 0 |
| invoice_number | 0.964 | 0.982 | 1.000 | 0.018 | 29 | 0 | 0 |
| seller_address | 0.945 | 0.982 | 1.000 | 0.018 | 29 | 0 | 0 |
| buyer_name | 0.945 | 0.982 | 0.982 | 0.000 | 29 | 0 | 0 |
| seller_name | 0.945 | 0.964 | 0.945 | −0.019 | 29 | 0 | 0 |
| **allowance_total_amount** | 0.000 | **0.000** | **0.000** | 0.000 | 6 | 23 | 0 |
| **tax_rate** | 0.182 | **0.182** | **0.000** | −0.182 | 10 | 6 | **13** |
| **charge_total_amount** | 0.571 | **0.889** | **0.000** | −0.889 | 5 | 24 | 0 |
| `rounding_amount` | — | — | — | — | **0** | 29 | 0 |

### How badly the old numbers misled

| field | old `per_field_mean` | true pooled F1 |
|---|---|---|
| `rounding_amount` | 1.000 | **never tested** (29/29 TN) |
| `payment_means_text` | 0.640 | 0.286 |
| `payment_reference` | 0.727 | 0.333 |
| `billing_period_end` | 0.759 | 0.364 |
| `allowance_total_amount` | 0.793 | 0.000 |
| `tax_rate` | 0.241 | 0.182 (13/29 EXCLUDED) |

## Findings that remain OPEN

### 1. Three fields are broken on *perfect* text (oracle-confirmed) — **RESOLVED, see ADR-058**

> **Correction (2026-08-04).** This section originally asserted the defect must be "in the GT,
> the normalizer, or the field definition" and attributed all three zeros to a **sign
> mismatch**. Both claims were wrong. The list of candidate causes omitted the **prompt**, and
> that turned out to be the cause for two of the three fields. Full evidence:
> `eval/field-prompt-audit.md`; decision: ADR-058. Kept in place per ADR-011 rather than
> rewritten, so the reasoning trail stays visible.

The oracle arm feeds the structurer a GT-rendered perfect transcript, so an oracle F1 of 0
means the field is unwinnable **as posed** — the defect is in the GT, the normalizer, the field
definition, **or the prompt** (the omission that misdirected this triage):

- `allowance_total_amount` — **0.000 on all three arms** (6 signal-bearing cases).
  *Actual cause*: prompt invisibility. `scripts/check_oracle_transcript_labels.py` proved all
  6 cases had `Summe Nachlässe: <value>` in the transcript while the model emitted `null`. Its
  only German alias was the EN16931-style name the corpus never prints (0/146; the corpus
  prints `Gesamtbetrag der Abschläge`, 88/146). **Not** a sign mismatch — no arm ever emitted
  a negative here. Prompt-fixable ⇒ explicitly NOT a LoRA target (ADR-048).
- `charge_total_amount` — qwen4b 0.889 but **oracle 0.000**. Same prompt-invisibility cause
  (`Summe Zuschläge` 0/146 vs `Gesamtbetrag der Zuschläge` 88/146).
- `tax_rate` — **oracle 0.000** on the 10 cases ADR-045/052 leaves well-posed.
  *Actual cause*: the model filled `vat_breakdown[].rate_percent` and left the flat key null.
  Fixed by a deterministic single-rate backfill → **0.952** on frozen generations.

The sign-mismatch hypothesis was not baseless — it was simply about a **different field**:
`prepaid_amount` (BT-113) really was emitted signed (`-50.0` / `-500.00` vs GT `50.00` /
`500.00`) and is fixed by a two-sided fold → **0.750** on all three arms.

This blocked the LoRA, not just the report: `finetune/dataset.groundtruth_to_target` builds the
training labels from the **same** registry, so fine-tuning would have taught the structurer to
reproduce broken labels.

### 2. `rounding_amount` is untestable on this split

29/29 TN. It cannot be scored, so it must not appear in any thesis per-field table as a
number. Either widen the split to include a rounding case or report it as "not exercised".

> **Update (ADR-058)**: BT-114 is present on exactly **1/146** corpus invoices, so widening
> the val split can add at most one case. All three of its `prompt_aliases` also scored 0/146
> and were removed. Reported as untested.

### 3. The new reader regressed three fields

Real, and not visible in the old reporting: `billing_period_end` 0.571 → 0.364,
`billing_period_start` 0.571 → 0.444, `seller_account_name` 0.800 → 0.615. Cheap to
investigate (likely rendering/normalization of period + account blocks) and cheaper than
spending a fine-tune on them.

## LoRA target list (replaces the list the old table implied)

Concentrated in the ADR-041 Step-1a **`payment`** group, plus billing period and party tax
IDs — all fields where the oracle is at 0.93–1.00, i.e. the structurer *can* do it given the
text: `payment_means_text`, `payment_reference`, `payment_means_code`, `seller_account_name`,
`seller_bic`, `seller_iban`, `billing_period_start`/`_end`, `buyer_order_reference`,
`seller_tax_id`, `buyer_vat_id`, `prepaid_amount`.

> **Update (ADR-058) — this list is PROVISIONAL and must be re-derived.** Every field on it
> had ungrounded or missing `prompt_aliases` at the time it was written, so its gap was
> partly prompt-fixable rather than capability-limited: `seller_tax_id` (`St.-Nr.` /
> `Steuer-Nr.` both 0/146), `buyer_vat_id` (all 3 aliases 0/146, missing the `USt.-Id.-Nr`
> printed 91/146), `billing_period_start`/`_end` (all 6 aliases 0/146), `seller_account_name`
> (`Konto lautend auf` 0/146), `payment_reference` (`Verwendungszweck` 0/146),
> `payment_means_text` / `payment_means_code` (4 aliases 0/146), `buyer_order_reference`
> (2 of 3 aliases 0/146), `prepaid_amount` (2 of 3 aliases 0/146, now fixed by the fold).
> Re-derive **after** the Tier-2 re-generation with the corrected glossary; spending a
> fine-tune on a prompt gap is the ADR-048 error.

## Provenance

Same failure mode as ADR-056 (the answerability ruler measuring artifacts rather than reading
quality), two milestones apart: **validate the ruler before ranking on it.** Recurrence is why
the fix is a shared predicate with an agreement test rather than three local patches.

Refs: ADR-013 (truth table), ADR-027 (metric surface), ADR-041/042 (field expansions),
ADR-045 + ADR-052 (`tax_rate` exclusion paths), ADR-054 (LoRA gate), ADR-056 (ruler fix),
ADR-057 (reader selection), `eval/reader-findability-audit.md`,
`eval/finetune-attribution-audit.md`.
