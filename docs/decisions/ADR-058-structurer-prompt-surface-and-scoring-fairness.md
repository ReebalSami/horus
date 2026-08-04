# ADR-058: Structurer prompt-surface + scoring-fairness correction (pre-LoRA)

**Status**: Proposed
**Date**: 2026-08-04
**Supersedes (baselines, not decisions)**: the zero-shot / oracle val baselines recorded in
`data/finetune/eval-*-val.json` prior to this record
**Extends**: ADR-043 (GT optional-zero), ADR-045 + ADR-052 (`tax_rate` exclusions),
ADR-046 (doctype code map), ADR-048 (`predicted_normalize` hook + "prompt-fixable is not a
LoRA target"), ADR-049 (registry-driven glossary), ADR-051 (predicted optional-zero),
ADR-053 (glossary stays flat-only), ADR-056 (answerability ruler), ADR-057 (canonical
reader lineage)

## Context

`eval/per-field-reporting-audit.md` fixed a per-field reporting defect (TN/EXCLUDED
outcomes contaminating per-field F1) and, once the numbers were honest, left **three
fields scoring 0.000 on the ORACLE arm** — the arm fed a ground-truth-rendered perfect
transcript:

| field | BT | oracle F1 (pre-fix) |
|---|---|---|
| `allowance_total_amount` | BT-107 | 0.000 |
| `charge_total_amount` | BT-108 | 0.000 |
| `tax_rate` | BT-119 | 0.000 |

A zero on perfect text cannot be a reading failure. It means the ground truth, the
normalizer, the field definition, or the *prompt* is wrong. This blocked more than the
report: `finetune/dataset.groundtruth_to_target` builds LoRA training labels from the same
registry, so fine-tuning would have taught the structurer to reproduce broken labels, and
ADR-048 already established that **a prompt-fixable gap must never be handed to a LoRA**.

The audit was widened on user challenge ("I'm pretty sure a lot of misleading mistakes are
in the prompts of the fields") — which proved correct, and found contamination worse than
the original three zeros.

## Current-state survey

Measured, not assumed. Two diagnostics were built for this (both retained):

- `scripts/check_oracle_transcript_labels.py` — for each invoice whose GT has a field
  present, renders the oracle transcript and reports whether the label and printed value
  are actually *in* it, next to what the model emitted. This separates "value absent from
  input" (GT/renderer bug) from "value present but prompt never names it" (prompt gap)
  from "value present and named but normalizer rejects it" (scorer bug).
- `scripts/audit_field_prompts.py` — checks every `german_label` and `prompt_alias` against
  the 146 canonical Qwen3-VL-4B transcripts, and every glossary `description` against every
  corpus GT value (in printed variants, not just canonical form).

### Finding 1 — the three zeros have three *different* causes

- **BT-119 `tax_rate`**: the structurer reliably filled `vat_breakdown[].rate_percent` and
  left the flat key `null` — the flat scalar reads as redundant once the table is emitted.
- **BT-113 `prepaid_amount`** (not zero, but weak at 0.000/0.333 on the reader arms): the
  model emitted the value **as printed**, i.e. signed (`-50.0`, `-500.00`) against GTs of
  `50.00` / `500.00`. Verified by grepping the saved generations.
- **BT-107 / BT-108**: the model emitted `0.00` (14×) or `null` (10×) — never a negative.
  So the sign hypothesis recorded in `per-field-reporting-audit.md` was **wrong for these
  two fields**. `check_oracle_transcript_labels.py` showed all 6 allowance cases had
  `Summe Nachlässe: 21,55 €` (etc.) **in the transcript** with `label_in_transcript=True`,
  `value_in_transcript=True`, and `model_emitted: null`. The field was invisible to the
  *prompt*, not to the reader.

### Finding 2 — four ground-truth values were leaked into the prompt

The glossary descriptions embedded literal example values that are verbatim GT for real
corpus invoices, handing the model the answer and inflating those invoices' scores:

| field | leaked value | invoice |
|---|---|---|
| `seller_vat_id` | `DE123456789` | `EN16931_1_Teilrechnung` |
| `seller_tax_id` | `201/113/40209` | `EN16931_1_Teilrechnung` |
| `payment_means_text` | `Überweisung` | `ZUGFeRD_1p0_COMFORT_Einfach` |
| `payment_means_text` | `bank transfer` | `MustangGnuaccountingBeispielRE-20201121_508` |

The fourth was introduced *while fixing the third* and caught only after the leak detector
was strengthened to compare printed variants — evidence that this class of contamination is
easy to reintroduce and needs a gate, not vigilance.

### Finding 3 — 34 of 63 `prompt_alias` entries never occur in the corpus

The aliases asserted "invoices print this label". Measured against 146 transcripts, 34 had
**zero** occurrences, including the label of the very field that scored 0:

| field | ungrounded (0/146) | what the corpus actually prints |
|---|---|---|
| `allowance_total_amount` | `Summe Nachlässe` | `Gesamtbetrag der Abschläge` (88/146) |
| `charge_total_amount` | `Summe Zuschläge` | `Gesamtbetrag der Zuschläge` (88/146) |
| `seller_vat_id` | `UID`, `VAT ID` | `USt.-Id.-Nr` (**91/146**, was missing entirely) |
| `seller_gln` | `ILN`, `GLN (Verkäufer)` | `Globale Nummer` (64/146) |
| `prepaid_amount` | `Bereits gezahlt`, `Vorauszahlung` | `Anzahlung` (80/146) |
| `billing_period_*` | 6 `... Beginn/Ende/von/bis` variants | one range under one heading |
| `rounding_amount` | all 3 | nothing (present on 1/146 invoices) |

`USt-IdNr.` — the alias that *was* listed for a field present on 138/146 invoices — occurs
once. ADR-048 measured over-glossing as net-**negative**, so ungrounded aliases are not
merely inert: they consume prompt budget and assert falsehoods.

### Finding 4 — a bare `FinetuneConfig()` silently selects the superseded reader

`FinetuneConfig.reader_model` defaults to `ibm-granite/granite-docling-258M-mlx`; ADR-057
made `Qwen/Qwen3-VL-4B-Instruct` canonical, and only `configs/finetune-structurer.yaml`
says so. The first audit run was therefore measured against the wrong lineage. Both new
scripts now load the canonical YAML explicitly and document why.

## Options considered

1. **Fix only the three zero fields.** Rejected: leaves the leaks and 34 ungrounded aliases
   in the prompt, so the re-baseline would still be contaminated and non-reproducible.
2. **Fold the sign on the predicted side only** (the initial implementation). Rejected on
   evidence: `zugferd_2p0_BASIC_Rechnungskorrektur` carries GT BT-107 = `-0.23`, so a
   one-sided fold turns a *correct* `-0,23` into `0.23` and scores it FN. Asymmetry in a
   representation rule is a bug by construction.
3. **Fold sign on all MONEY fields.** Rejected: `EN16931_Einfach_negativePaymentDue` is a
   real fixture with a negative payable, and BT-114 rounding is legitimately signed
   (`-0.02` ≠ `+0.02`). Scope the fold to the three spec-non-negative magnitudes only.
4. **Derive `tax_rate` from the GT when absent.** Rejected outright — that is invention and
   violates the tax-domain honesty guardrail (ADR-035). The backfill copies the **model's
   own** emitted rate, and only when exactly one distinct rate exists.
5. **Drop `prompt_aliases` entirely and rely on descriptions.** Rejected: the grounded
   aliases carry the highest-value signal (the printed German label). Prune the ungrounded
   ones, add the measured ones.
6. **Rewrite `german_label` to the printed forms.** Deferred, deliberately — see
   *Known limitation* below.
7. **Full fairness bundle** (chosen): fix all three root causes, make the prompt surface
   100 % corpus-grounded and leak-free, and gate both properties.

## Decision + integration thoughts

### (a) Deterministic single-rate `tax_rate` backfill

`structurer._backfill_single_tax_rate` copies `vat_breakdown[].rate_percent` into the flat
`tax_rate` when the breakdown carries exactly one distinct rate. No-ops when the flat value
is already set, when no breakdown was emitted, or when ≥2 distinct rates appear (there is
then no single document rate, and `null` is correct — matching the GT side, which marks
multi-rate invoices EXCLUDED per ADR-045/052).

Repair, not invention: the value is the model's own. `rate_percent` is already schema-coerced
(`19` / `19.0` / `"19 %"` / `"19,00"` → `"19"`), verified empirically, so no re-coercion.
The three registry key names it depends on are **bound to the registry at import time** and
raise `RuntimeError` if absent — a rename would otherwise silently disable the repair and
re-introduce the BT-119 zero with nothing downstream noticing.

### (b) Two-sided sign fold for BT-107 / BT-108 / BT-113

`ground_truth._normalize_nonneg_money` (GT side) + `normalizers._normalize_predicted_nonneg_money`
(predicted side) both drop a leading minus. EN16931 defines these three as non-negative
magnitudes; the corpus does not honour that consistently, and pages print them as
deductions. Folding both sides makes sign irrelevant in **both** directions. BT-114
`rounding_amount` deliberately keeps the signed normalizer.

### (c) Corpus-grounded, leak-free prompt surface

Every `prompt_alias` is now measured against the canonical transcripts; the 34 ungrounded
entries are replaced with measured ones, with hit counts recorded inline so future edits
stay evidence-based. All four leaked values are replaced by *structural* descriptions
(shape, not sample). `rounding_amount` keeps its description but asserts no label, since
none exists in the corpus and it is present on 1/146 invoices.

### (d) Two gates, one fast and one exhaustive

- `tests/test_structurer.py::test_glossary_descriptions_embed_no_concrete_identifiers` —
  hermetic, corpus-free, blocks value-shaped strings (VAT-id / Steuernummer / IBAN / date /
  decimal-amount shapes) in any description. Runs in `make test`.
- `make audit-prompts` → `scripts/audit_field_prompts.py` — corpus-backed; **fails** on any
  ungrounded alias or any leaked GT value; reports label/advisory findings separately
  because `german_label` is not prompt text.

### (e) Offline re-scoring

`finetune/evaluate.py` gained a shared `_Accumulator` plus `score_saved_outputs`, exposed as
`scripts/finetune_evaluate.py --score-only <dir>`. Scorer/normalizer changes are now
measurable against **frozen generations**, which is what makes (a) and (b) attributable
independently of any model change — and is a prerequisite for the LoRA A/B.

## Measured effect (Tier 1 — frozen generations, no re-inference)

Attributable purely to (a) + (b), since the generations are byte-identical:

| field | granite | qwen3-vl-4b | oracle |
|---|---|---|---|
| `tax_rate` | 0.182 → **0.778** | 0.182 → **0.900** | 0.000 → **0.952** |
| `prepaid_amount` | 0.000 → **0.750** | 0.333 → **0.750** | 0.750 → 0.750 |
| `allowance_total_amount` | 0.000 → 0.000 | 0.000 → 0.000 | 0.000 → 0.000 |
| `charge_total_amount` | 0.571 → 0.571 | 0.889 → 0.889 | 0.000 → 0.000 |
| **overall_micro_f1** | 0.6771 → **0.6856** | 0.8141 → **0.8189** | 0.9608 → **0.9676** |

`allowance_total_amount` / `charge_total_amount` are **unchanged by design**: their cause is
the prompt, and a prompt fix cannot move a frozen generation. They are the measurement that
requires Tier 2 (re-generation). The two-sided GT fold likewise shows no delta here — no
current arm emitted the negative allowance — so it is a *prophylactic* correctness fix whose
absence would have inverted that case once the glossary makes models emit the value.

## Known limitation (deliberately not fixed here)

22 of 34 `german_label` values do not occur in any corpus transcript. They are the canonical
EN16931 German terms, used for reporting and — importantly — by
`dataset.render_oracle_transcript`, which renders `"{german_label}: {value}"`. The oracle
arm therefore presents labels that real pages do not merely vary but **never print**. The
renderer docstring already discloses the oracle as an upper bound; this audit quantifies how
synthetic the label-mapping half of it is.

Not changed in this record, for a measurement reason rather than an effort one: rewriting
`german_label` alters the oracle transcript *and* reporting labels, which would confound the
Tier-2 re-baseline with a second simultaneous change. The LoRA gate compares zero-shot vs
fine-tuned on **real reader transcripts**, so it is unaffected. Tracked as a follow-up with
its own re-baseline.

## Source archival

- EN16931 BT-107 / BT-108 / BT-113 / BT-114 / BT-119 semantics — `docs/sources/standards/`
  (EN16931 core invoice model, already archived for ADR-035/041/043)
- Corpus evidence — `docs/sources/transcripts-multipage/qwen*` (146 canonical transcripts,
  ADR-057 lineage); saved generations under `data/finetune/{oracle,zeroshot,zeroshot-qwen}-outputs/`
- Audit artefacts — `eval/field-prompt-audit.md` (this audit), `eval/per-field-reporting-audit.md`
  (the reporting defect that surfaced the zeros; its sign-mismatch hypothesis is corrected there)
- Reproduce with: `make audit-prompts`, `make glossary`,
  `uv run python scripts/check_oracle_transcript_labels.py <field> --outputs <dir>`

## Consequences

- **Baselines superseded.** Every `data/finetune/eval-*-val.json` predating this record is
  stale in two independent ways (scorer changed; prompt changed). Retained per ADR-011.
- **Re-generation required before the LoRA gate.** ADR-054 conditions the LoRA on a
  re-baseline < 0.90. That comparison must be made against a re-generated zero-shot arm, or
  the fine-tune would be credited with prompt-fixable gains — exactly the ADR-048 error.
- **The prompt is now a measured artefact.** Any future alias must be justified by corpus
  occurrence or `make audit-prompts` fails.
- **`rounding_amount` remains untested** (0 signal-bearing outcomes on val, present on
  1/146). It is reported as untested rather than silently scored 1.000.

## Supersession trigger

Supersede when any of:

- the corpus changes (new invoices / a new reader lineage), invalidating the measured alias
  grounding — re-run `make audit-prompts` and re-record hit counts;
- `german_label` is rewritten to printed forms (the deferred follow-up), which re-baselines
  the oracle arm;
- a Tier-2 re-generation shows the glossary fix does **not** move BT-107/108, which would
  refute the prompt-gap diagnosis and reopen the GT/field-definition hypothesis.
