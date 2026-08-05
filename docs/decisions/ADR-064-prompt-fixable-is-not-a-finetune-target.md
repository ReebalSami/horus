# ADR-064: A prompt-fixable gap is never a fine-tune target

**Status**: Accepted
**Date**: 2026-08-06
**Refs**: ADR-048 (the record this principle was *wrongly* attributed to — see §"Why this
record exists"), ADR-054 (the conditional-LoRA gate this ordering protects), ADR-058
(BT-107/108 glossary gap — the worked example), ADR-049/053 (the registry-driven glossary
that is the repair surface), ADR-059 (oracle-transcript fidelity — the instrument that
distinguishes the causes), ADR-063 (held-out grading scope)

## Context (current-state survey)

Five call sites assert, in prose, that *a prompt-fixable gap must never be handed to a
fine-tune*, and every one of them sources the claim to ADR-048:

| Call site | Wording |
|---|---|
| `docs/decisions/ADR-058-…md` §Refs | `ADR-048 (predicted_normalize hook + "prompt-fixable is not a LoRA target")` |
| `docs/decisions/ADR-058-…md` §Context | "ADR-048 already established that **a prompt-fixable gap must never be handed to a LoRA**" |
| `docs/decisions/ADR-058-…md` §Consequences | "the fine-tune would be credited with prompt-fixable gains — exactly the ADR-048 error" |
| `scripts/check_oracle_transcript_labels.py` | "Cause 2 is fixable by prompt work alone and must NOT be handed to a LoRA (ADR-048's lesson)" |
| `scripts/heldout_attribution.py` | "the generalized form of the ADR-048 / ADR-058 rule that a prompt-fixable gap must never be handed to a fine-tune" |

**ADR-048 does not contain that rule.** It is a scoring-fairness record for BT-118
(`vat_breakdown[].category_code`): it adds the `FieldSpec.predicted_normalize` hook so a
controlled-vocabulary code that is never printed on the page can be recovered from the
model's rendering. It never mentions LoRA, fine-tuning, or training at all.

Worse, the one place it *does* discuss prompt guidance says close to the opposite of the
attributed claim (ADR-048 §Alternatives considered):

> **Prompt guidance (tell the model the category vocabulary + "output only the code").**
> Measured live on Arm B: it *did* fix `category_code` … **but** it perturbed the model's
> whole generation, raising flat spurious-emission from 0.071 to 0.357 … Rejected as the
> *ruler* fix; **it remains a legitimate, separately-measured model-improvement
> experiment.**

So ADR-048 rejected prompt guidance as a **scoring-fairness** mechanism while explicitly
*endorsing* it as a separately-measured model-improvement path. The citation chain
inverted that into "prompt-fixable is not a LoRA target", then propagated the inversion
into two source docstrings and one more ADR.

A thesis examiner following the citation finds nothing. That is the defect this record
closes.

## Decision

**The principle stands on its own — restated here with its actual evidence.**

> A gap that the prompt can close is not a fine-tune target. Repair the prompt first,
> re-measure, and only then evaluate the fine-tune gate.

Two independent reasons, both measured in this project rather than asserted:

1. **Attribution.** `finetune/dataset.groundtruth_to_target` builds LoRA training labels
   from the same `FIELDS` registry that `structurer.render_field_glossary` renders into the
   prompt. If a field is invisible to the prompt, the zero-shot arm scores it near 0 for a
   reason that has nothing to do with model capability. Fine-tuning across that gap and
   comparing to the un-repaired baseline credits the adapter with a gain a one-line
   registry edit would have produced for free. ADR-058's BT-107/108 case is the worked
   example: `check_oracle_transcript_labels` proved all 6 allowance invoices carried
   `Summe Nachlässe: <value>` in the input while the model emitted `null` — a glossary gap,
   not a capability gap. Post-repair those fields moved 0.000 → 0.667 and 0.889 → 1.000 on
   real reader text (0.000 → 0.909 / 0.000 → 1.000 on perfect text) with **no model
   change**.

2. **Cost.** A prompt edit is free, reversible, and re-scorable against frozen generations.
   A fine-tune costs a training run, is not reversible without re-training, and cannot be
   attributed after the fact. Spending the expensive instrument on a defect the cheap one
   fixes is the wrong order of operations regardless of the attribution argument.

**The counter-constraint, from ADR-048, is equally load-bearing**: a prompt edit is *not*
free of risk. ADR-048 measured a prompt change that fixed its target field while raising
flat spurious-emission 0.071 → 0.357 — the model invented VAT rows. So the ordering rule is
not "prompt edits are safe, do them freely"; it is:

**Ordering rule.**

1. Classify the zero/low score by cause. Three causes, distinguishable with existing tools:
   the value is **absent from the input** (a reading or data defect), the value is
   **present but the prompt never names it** (a prompt defect), or the value is
   **present and named but the normalizer rejects the model's rendering** (a scorer
   defect). `scripts/check_oracle_transcript_labels.py` separates the first two;
   `--score-only` re-scoring against frozen generations isolates the third.
2. Repair the prompt defects on the **synthetic** corpus, where ground truth comes from the
   embedded factur-x XML and is exact by construction.
3. Re-measure the synthetic arms and require **no field regresses** — this is the guard
   against the ADR-048 perturbation failure mode. A prompt change that lifts its target
   while degrading anything else is not accepted.
4. Only then evaluate the fine-tune gate (ADR-054: fine-tune only if the re-baseline stays
   below 0.90 pooled).

**Every citing site is re-pointed to this record.** Where a site is genuinely about
ADR-048's *own* content — the `predicted_normalize` hook, the as-printed-vs-as-stored
class, or the measured cost of over-glossing — the ADR-048 citation stays, because it is
correct there.

## Alternatives considered

- **Amend ADR-048 to add the principle.** Rejected. ADR-048 is `Accepted` and records a
  decision that was actually made on 2026-06-14; retrofitting a rule it never contained
  would falsify the record's own history and defeat the purpose of dated decision records.
  Supersession-over-deletion (ADR-011) cuts both ways: records are not editable to match a
  later belief about what they said.
- **Amend ADR-058, which states the principle most fully.** Rejected. ADR-058 is a
  prompt-surface *correction* for three specific fields; the principle is cross-cutting and
  is cited from modules that have nothing to do with those fields
  (`heldout_attribution.py` applies it to the reader/structurer split on real invoices).
  Burying a cross-cutting rule inside a field-specific record is what made it hard to cite
  correctly in the first place.
- **Drop the attribution and state the rule inline at each call site.** Rejected: five
  copies of a rule drift (this repo has now had three generations of drift on a *field
  count* for exactly that reason — see ADR-063's correction note). One record, five
  citations.
- **Promote it to a workspace rule in `.windsurf/rules/`.** Not now, deliberately. The
  existing `horus-decision-discipline` rule already requires an ADR per tool/model choice;
  this is a *methodology* constraint on one workflow, not a standing authoring
  obligation. Revisit if it starts being violated rather than merely mis-cited.

## Source archival

No external sources. Internal only, and all of it verifiable in-repo:
`docs/decisions/ADR-048-predicted-vat-category-normalizer.md` §Alternatives (the inverted
quote, and the measured 0.071 → 0.357 spurious-emission cost),
`docs/decisions/ADR-058-structurer-prompt-surface-and-scoring-fairness.md` §Measured effect
(the BT-107/108 before/after), `docs/decisions/ADR-054-*.md` (the < 0.90 conditional-LoRA
gate), `src/horus/finetune/dataset.py` (`groundtruth_to_target` reading the same registry),
`src/horus/eval/structurer.py` (`render_field_glossary` rendering it into the prompt).

## Supersession trigger

Superseded or amended if **any** of:

1. The LoRA training labels stop deriving from the same registry the prompt renders — the
   attribution argument in reason 1 is registry-coupling-specific and would need restating.
2. A prompt repair is measured to lift a field on the synthetic corpus **and** the fine-tune
   is later shown to have produced an independent gain on the same field — that would mean
   the two are not substitutes and the ordering rule needs a carve-out.
3. Constrained decoding becomes available locally (ADR-018 records that MLX has none), which
   would change what counts as a "prompt-fixable" gap: schema enforcement at decode time
   removes a class of defects the prompt currently has to carry.
4. A future record supersedes ADR-054's conditional-LoRA gate, since step 4 of the ordering
   rule names it directly.
