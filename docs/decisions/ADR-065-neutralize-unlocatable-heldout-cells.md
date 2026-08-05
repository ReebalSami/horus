# ADR-065: Ground-truth validity — neutralize held-out answers no channel could locate

**Status**: Accepted
**Date**: 2026-08-06
**Refs**: ADR-043 (GT-side optional-zero totals), ADR-045 + ADR-052 (flat `tax_rate`
EXCLUDED where ill-posed — the closest precedent), ADR-046 (as-printed vs as-stored),
ADR-062 (the provenance schema + `escalated_as` warrants this reads), ADR-063 (held-out
grading scope), ADR-064 (why this is a *ruler* fix and not a prompt or fine-tune one),
ADR-040 (the held-out set)

## Context (current-state survey)

The signed-off held-out key records, per cell, *how* the answer was established (ADR-062).
One escalation reason is `null-disputed`: **no adjudication channel could locate the value in
the page text; it was decided anyway.**

Scoring a reading system against such a cell asks it to produce something the page does not
show. The project has already ruled four analogous cases ill-posed and neutralised them
rather than counting them wrong — the flat `tax_rate` on multi-rate invoices (ADR-045) and on
single-zero-rate invoices (ADR-052), and the optional-zero totals (ADR-043/051). Those
exclusions are *semantic*: the field is undefined on that document. This record extends the
same lineage to a *provenance* criterion: the field is defined, but this document does not
state it.

### The measurement that identified the field

`payment_means_text` (BT-82) is singular across the whole 34-field key:

| property | value |
|---|---|
| present cells in the signed-off key | 18 |
| with printed-text proof | **0** |
| with two independent channels agreeing | **0** |
| author-adjudicated | **18** (all of them) |
| measured F1 on real invoices | **0.462** |
| measured F1 on a perfect transcript | **1.000** |
| recovery on its `null-disputed` cells | **0 of 8** |

No other scoring field is in that position while also scoring badly. The 1.000 on perfect
text is the decisive part: the extractor is fully capable, so the loss is **page ambiguity**,
not comprehension — which is exactly what ADR-064's cause-classification step is for. And
EN16931 derives a payment method from no other field, so when the page is silent there is
nothing to compute, only something to guess.

### Why the criterion cannot simply be generalised

Two tempting generalisations were tested against the data and both fail.

**(1) "Neutralize every `null-disputed` cell."** Corpus-wide those cells score TP 21 / FN 24 —
so a blanket rule would discard 21 correct answers. The recoveries are concentrated:

| field | recovered / present, among `null-disputed` cells |
|---|---:|
| `due_payable_amount` | **11 / 12** |
| `payment_means_text` | **0 / 8** |
| `tax_rate` | 1 / 5 |
| `delivery_date` | 0 / 2 |
| `invoice_number` | 0 / 2 |

One field supplies 11 of the 21. The amount due is fixed by an arithmetic rule in the
standard — gross total, less prepayments, plus rounding — so on an invoice without
prepayments it simply equals the gross total. No channel matched it as a *separate printed
string* because the page prints one total, not two. Those cells are not ill-posed; they are
**determined**. `null-disputed` therefore pools two populations: arithmetically determined
(recovered) and genuinely absent (not recovered).

**(2) "Key on the provenance `class` instead."** Worse. `author-adjudicated` conflates four
different situations, only one of which is a quality problem:

| why it needed judgement | example | score |
|---|---|---|
| the value is a **classification**, never printed literally | `document_type` | **36/39** |
| the value is a **composite block** (letterhead, address) | `seller_name` 26/27 | strong |
| the value is **normalised** (page shows `€`, key stores `EUR`) | `invoice_currency_code` | 35/39 |
| the value is **genuinely absent from the page** | `payment_means_text` 6/18 | weak |

`document_type` and `payment_means_text` sit in the *same* class and score 0.92 and 0.46. A
pooled `author-adjudicated` split is driven by **field type, not answer-key quality**, and
reporting it as an evidence-strength finding would be a false claim. (It nearly was: the
pooled three-way split — 0.912 printed-proof / 0.865 two-channel / 0.723 author-adjudicated —
looks like a clean result and is confounded. Recorded here so the same trap is not re-entered.)

## Decision

**A held-out cell is scored EXCLUDED (neutral) when BOTH hold:**

1. the field opts in via **`FieldSpec.neutralize_when_unlocatable = True`**, and
2. this invoice's ADR-062 warrant for that field is **`escalated_as: "null-disputed"`**.

Encoded exactly as ADR-045/052 encode the ill-posed `tax_rate`: `is_present=True` with
`normalized_value=None`, which the scorer already reads as EXCLUDED. No scorer change. The
`raw_value` stays on the record, so the answer remains auditable.

**Applied to exactly one field: `payment_means_text`.** The registry flag documents the
two conditions required to set it — no EN16931 derivation rule, **and** measured
non-recovery — with `due_payable_amount` named inline as the counter-example.

**Scope discipline.** The wider `null-disputed` population is deliberately left scored, to be
revisited on post-vocabulary-repair numbers. Two reasons: the confound above needs a per-field
derivability argument that the standard's normative term list is not yet archived to support
(see ADR-058 §Source archival), and neutralising more cells in the same measurement as the
vocabulary work would make neither delta attributable.

**Fail-safe.** A missing `provenance` block, a missing field key, a non-mapping warrant, or an
unrecognised escalation all resolve to *scored*. A malformed warrant can never silently
convert a miss into a neutral cell — the direction that would flatter the result.

**ZUGFeRD is untouched.** `provenance` is a new optional argument; when absent the builder is
byte-identical to before. The synthetic corpus carries no provenance and reaches
`GroundTruth` via `parse_cii_xml`, not this path, so published ZUGFeRD figures cannot move —
ADR-062's invariant is preserved and now has a regression test.

## Alternatives considered

- **Drop the field from held-out grading entirely** (report on 33). Rejected: it changes the
  instrument immediately after ADR-063 corrected a field-count confusion, and removing the
  weakest field wholesale is the move most likely to read as flattering the result. The
  per-cell version achieves the same correctness — 10 of its 18 cells stay graded.
- **Grade everything, name it a limitation in prose.** Rejected: it knowingly counts as errors
  8 answers no channel could find on the page, which is the same unfairness ADR-045/052 were
  introduced to remove. Being inconsistent with the project's own precedent is its own defect.
- **Blanket-neutralize all `null-disputed` cells.** Rejected on the measured confound above:
  it would discard 21 correct answers, 11 of them on one arithmetically-derived field.
- **Neutralize by provenance `class` instead of `escalated_as`.** Rejected: `class` is
  confounded by field type (table above).
- **Fix it in the prompt instead.** Rejected per ADR-064's classification step: the value is
  absent from the input, so this is cause (1) — a ground-truth/instrument matter — not cause
  (2), a prompt gap. A prompt alias here would additionally *leak an answer*, since this
  field's ground truth **is** the payment-method phrase; the registry comment above the
  `description` records that an earlier attempt did exactly that.
- **Wait until after the fine-tune.** Rejected: the fix is free, needs no inference, and
  leaving it in place means the fine-tune's target list contains cells that are not
  legitimately winnable.

## Measured effect (Round 1 — frozen generations, no re-inference)

Attributable to the ruler alone; the generations are byte-identical.

| metric | before | after |
|---|---:|---:|
| `payment_means_text` F1 | 0.462 | **0.667** |
| — of which cells neutralised | 0 | **8** |
| mean per-invoice F1 | 0.8767 | **0.8825** |
| pooled cell F1 | 0.8931 | **0.8987** |
| recall | 0.8402 | **0.8503** |
| precision | 0.9530 | 0.9530 |
| TP | 568 | **568** |
| FP | 28 | **28** |
| FN | 108 | **100** |

**TP and FP are unchanged.** Only the 8 unwinnable cells moved out of FN. Not one correct
answer was discarded — the direct consequence of the 0/8 recovery measurement, and the
property a blanket rule would have lost.

Per language / channel, pooled: english/email 0.9408, german/email 0.9079,
german/iphone-pdf-scan 0.8371.

Reproduce:

```sh
uv run python scripts/finetune_evaluate.py --heldout \
    --score-only data/self-collected/_eval/outputs-zeroshot \
    --label zeroshot-heldout-adr065 \
    --out data/self-collected/_eval/eval-zeroshot-heldout-adr065.json
uv run python scripts/heldout_breakdown.py \
    data/self-collected/_eval/eval-zeroshot-heldout-adr065.json \
    --outputs data/self-collected/_eval/outputs-zeroshot
```

## Source archival

No external sources. Internal: `src/horus/eval/ground_truth.py`
(`FieldSpec.neutralize_when_unlocatable`, the `payment_means_text` row),
`src/horus/eval/heldout.py` (`_is_unlocatable_and_neutralized`,
`_UNLOCATABLE_ESCALATION`, `build_groundtruth_from_mapping`/`_from_json`),
`tests/test_heldout.py` §"Unlocatable-cell neutralization" (12 hermetic tests, no corpus
needed), `docs/decisions/ADR-062-heldout-gt-adjudication.md` (the warrant vocabulary).

## Supersession trigger

Superseded or amended if **any** of:

1. A second annotator is added and inter-annotator agreement becomes reportable — the
   `null-disputed` warrant is single-annotator by construction, so its meaning changes.
2. The vocabulary re-grounding lands and the post-repair numbers show a different recovery
   profile on `null-disputed` cells — that is the pre-registered moment to revisit whether
   more fields qualify.
3. The standard's normative German term list is archived, enabling a per-field derivability
   argument that this record currently declines to make for the wider population.
4. Any flagged field's measured recovery on its `null-disputed` cells rises above zero — the
   flag's second condition would no longer hold and it must come off.
5. `escalated_as` gains a new value that also means "absent from the page", which would need
   adding alongside `null-disputed` rather than replacing it.
