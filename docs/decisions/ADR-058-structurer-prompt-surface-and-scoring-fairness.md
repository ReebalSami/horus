# ADR-058: Structurer prompt-surface + scoring-fairness correction (pre-LoRA)

**Status**: Accepted
**Date**: 2026-08-04 / **accepted 2026-08-06** once the Tier-2 re-generation this record
conditioned itself on was measured — see §"Measured effect (Tier 2)"
**Supersedes (baselines, not decisions)**: the zero-shot / oracle val baselines recorded in
`data/finetune/eval-*-val.json` prior to this record
**Extends**: ADR-043 (GT optional-zero), ADR-045 + ADR-052 (`tax_rate` exclusions),
ADR-046 (doctype code map), ADR-048 (`predicted_normalize` hook + the measured cost of
over-glossing), ADR-064 ("a prompt-fixable gap is never a fine-tune target" — the principle
this record leans on, mis-cited to ADR-048 until ADR-064 was written),
ADR-049 (registry-driven glossary), ADR-051 (predicted optional-zero),
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
**a prompt-fixable gap must never be handed to a LoRA** (ADR-064).

> **Citation correction 2026-08-06.** This paragraph originally attributed that principle to
> ADR-048. It is not in ADR-048 — that record is a BT-118 scoring-fairness fix and its
> §Alternatives explicitly calls prompt guidance "a legitimate, separately-measured
> model-improvement experiment". The principle is sound and is now stated in its own record,
> ADR-064, with its actual evidence. Nothing measured in this record changes.

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

## Measured effect (Tier 2 — re-generated arms) — added 2026-08-06

This is the evidence the Tier-1 section above deferred, and the basis for accepting this
record. Re-generated arms, `qwen-tier1` → `zero-shot-qwen-adr059` (real reader text) and
`oracle-tier1` → `oracle-adr059` (perfect text). Reproduce with
`uv run python scripts/compare_eval_reports.py`.

| field | reader text | perfect text |
|---|---|---|
| `allowance_total_amount` (BT-107) | 0.000 → **0.667** | 0.000 → **0.909** |
| `charge_total_amount` (BT-108) | 0.889 → **1.000** | 0.000 → **1.000** |
| `prepaid_amount` (BT-113) | 0.750 → 0.750 | 0.750 → **1.000** |
| `line_total_amount` (BT-106) | 0.885 → **0.906** | 0.906 → *0.863* |
| `delivery_date` (BT-72) | 0.865 → 0.865 | 1.000 → *0.974* |
| `payment_means_text` (BT-82) | 0.286 → *0.133* | 1.000 → 1.000 |
| **flat `micro_f1`** | 0.8616 → **0.8649** | 0.9641 → **0.9743** |
| **pooled `overall_micro_f1`** | 0.8189 → **0.8257** | 0.9676 → **0.9719** |

**The success criterion is met**: BT-107/108 — the two fields this record diagnosed as
*invisible to the prompt* — moved off zero on both arms, with the glossary repair as the only
cause.

**Three fields moved down, and none of them is a regression in the system.** Recording them
explicitly because a "no field regresses" claim that quietly omits the fields that moved is
worthless:

- **`payment_means_text` 0.286 → 0.133 on reader text** is the **leak removal working as
  intended**. This audit found a payment-method phrase among the 4 ground-truth values that
  had leaked verbatim into glossary descriptions. The pre-fix 0.286 was **inflated by
  contamination** — the prompt was handing the model the answer for the invoices carrying
  that phrase. 0.133 is the first honest measurement of this field. The perfect-text score is
  **1.000 both before and after**, which proves the extractor is fully capable and the loss is
  page ambiguity, not comprehension. A number going *down* here is the evidence the leak was
  real.
- **`line_total_amount` 0.906 → 0.863 and `delivery_date` 1.000 → 0.974, both on perfect
  text only** (reader text held or improved). These are **honest-ceiling corrections caused by
  ADR-059**, which shipped alongside this record and changed what the oracle page *prints*
  from the EN16931 schema term to the corpus-measured wording (`Summe Nettobeträge` →
  `Positionssumme`; `Liefer-/Leistungsdatum` → `Leistungsdatum`). The model scored marginally
  better against schema jargon than against the wording real invoices use — so the old
  ceiling was optimistic for these two fields, and the new number is the truthful one. This is
  exactly the failure mode ADR-059 exists to remove; see ADR-059 §"Measured effect".

## Known limitation (deliberately not fixed here) — **RESOLVED by ADR-059**

> **Resolved 2026-08-04 by ADR-059**, which shipped alongside this record and is the
> "follow-up with its own re-baseline" promised in the last line of this section. It adds
> `FieldSpec.printed_label` + the `rendered_label` property, gates rendered-label grounding in
> `make audit-prompts` check B (flat registry **and** every repeating-group cell), and
> maintains a bidirectionally-gated `_NO_PRINTED_LABEL_REASONS` exception list. The
> re-baseline cost is recorded in §"Measured effect (Tier 2)" above: two fields' perfect-text
> ceilings came *down* to their honest values. The text below is retained as the original
> statement of the problem.

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

- EN16931 BT-107 / BT-108 / BT-113 / BT-114 / BT-119 semantics —
  `docs/sources/legal/zugferd-en16931.md` (the path recorded per ADR-041).
  **Citation corrected 2026-08-06**: this line previously read `docs/sources/standards/`
  "already archived for ADR-035/041/043". That directory **has never existed**, and neither
  ADR-035 nor ADR-043 archives an external EN16931 stub at all (ADR-035 states "no new
  external stub"). Flagged further: the file that *does* exist is `status: stub` — a
  Mustang-Project landing page with `archived_pdf: ""` and no normative business-term list —
  so it does **not** yet support a claim about the standard's German term names. Obtaining the
  normative term list is tracked as outstanding work, not asserted here.
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
  the fine-tune would be credited with prompt-fixable gains — the error ADR-064 forbids.
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
