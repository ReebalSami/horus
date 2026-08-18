# ADR-072: Held-out exclusion causes separated, counted, and disclosed

**Status**: Accepted
**Date**: 2026-08-18
**Refs**: ADR-065 (the ratified exclusion this shares an encoding with), ADR-045 + ADR-052
(the flat `tax_rate` neutral-encoding precedent), ADR-062 (the provenance warrants ADR-065
reads), ADR-063 (held-out grading scope — the 34-field header population), ADR-059 (the
renderer defect whose mechanism two manuscript sites misattributed), ADR-013 (the scorer's
truth table), ADR-035 (`validate_and_repair`, the normaliser at fault), ADR-011
(supersede-never-delete, which is why the defect is disclosed rather than quietly repaired),
issue #118 (the open date-normaliser repair)

## Context (current-state survey)

The scorer has a fourth ground-truth state besides absent / empty / content. `_gt_state`
(`src/horus/eval/scorer.py:278-284`) returns `normalizer_rejected` whenever a cell is present
but carries no normalised value, and the truth table maps that state to **EXCLUDED** on all
three predicted-value branches (`scorer.py:14-24`). An excluded cell is removed from the
denominator entirely: it contributes to neither the numerator nor the total of F1, precision
or recall.

Two unrelated situations reach that state through the same `normalized_value is None`
encoding. Both are produced by the same nine lines of
`build_groundtruth_from_mapping` (`src/horus/eval/heldout.py:290-296`):

```python
neutralize = is_present and _is_unlocatable_and_neutralized(spec, provenance)
if not is_present or neutralize:
    normalized_value: str | None = None
else:
    normalized_value = normalized[english_key]
```

1. **Ratified neutralisation.** `neutralize` is true: the field opts in via
   `FieldSpec.neutralize_when_unlocatable` and this invoice's ADR-062 warrant records
   `escalated_as: "null-disputed"`. This is ADR-065's decision, and the manuscript declares it.

2. **The normaliser rejected the answer key's own value.** `neutralize` is false, so the cell
   takes `normalized[english_key]` — and `validate_and_repair` returned `None` for it, because
   the author's signed-off value could not be coerced to the field's declared type. Nobody
   decided this. It is a silent consequence of a locale-parsing gap, and it withdraws cells the
   system should have been graded on.

`heldout.py`'s own docstring already describes route 2 as "audit-preserving; the author catches
it at review". It was not caught at review, and no aggregate could have surfaced it.

### Why no reported number could reveal it

`scripts/audit_heldout_exclusions.py` over the 39 signed-off documents:

| header cell state | cells |
|---|---:|
| `absent` | 628 |
| `present_empty` | 0 |
| `present_content` | 668 |
| `normalizer_rejected` → **EXCLUDED** | **30** |
| total (39 × 34) | 1326 |

`present_content = 668` is exactly `tp + fn` in `eval/heldout-breakdown.json`
(568 + 100 = 668). **The published denominator is already net of all 30 exclusions.** There is
therefore no arithmetic an examiner could perform on the reported figures that would expose
the second class — not a cell count, not a rate, not a residual. Splitting the 30 by cause
requires a per-cell pass against the warrant block, which is what the new audit script does.

| cause | cells | fields |
|---|---:|---|
| ratified neutralisation (ADR-065) | 8 | `payment_means_text` (STRING) |
| **answer-key value the normaliser rejected** | **22** | `issue_date` 8, `billing_period_end` 4, `payment_due_date` 4, `billing_period_start` 3, `delivery_date` 3 — all `DATE` |

The 8 match the manuscript's declared count exactly, so ADR-065's disclosure was accurate for
what it covered. The 22 were undeclared.

### Direction of the bias

Unknown without a re-score, but the available evidence runs *against* the reported figure
rather than for it:

- All 22 are `DATE` fields, which are scored by exact match on the ISO-8601 string — a
  comparator the system does well on where the value is legible.
- 17 of 22 fall in English email invoices, i.e. the language/channel cell the system reads
  **best** (the channel table reports email-native far above phone-scanned).
- The same normaliser is applied to predictions (`_normalize_predicted_date`), so on a repaired
  parser both sides would canonicalise and a correct reading would score TP.

So the likeliest effect of the exclusion is that the headline is *slightly understated*. The
honest statement is that the direction is undetermined, with the concentration noted — which is
what the manuscript now says. This matters: an undisclosed exclusion that plausibly flattered
the result would be a different and far more serious finding.

## Options considered

**A. Repair the date normaliser now, re-score, publish the new figure.** Rejected for this
submission. It moves a published headline, needs its own regression pass over the frozen
generations, and the repair is already scoped as its own piece of work (#118). Landing a
number-moving change to the scoring apparatus on a submission branch is precisely the
sequencing this project's measurement-validity chapter argues against.

**B. Say nothing.** Rejected outright. The chapter's stated discipline is that "an exclusion
requires a criterion declared in advance and applied by a rule"
(`06-measurement-validity.tex:73`). 22 cells are excluded on no criterion at all. A chapter
that argues for that discipline while carrying an undeclared exclusion is the one defect in
this manuscript that would genuinely damage it.

**C. Disclose the count in the exclusion inventory and stop there.** Insufficient. It records
the number without the finding. The transferable result is not "22 cells" — it is that a
single internal marker was carrying a ratified decision and an unintended failure
indistinguishably, and that a corpus-level aggregate cannot separate them.

**D. Disclose as a new entry in the chapter's own defect chronology, plus the inventory count,
plus a re-derivable audit. Chosen.** The chapter already documents its own instrument's defects
in four classes; this is one more of exactly that kind, found by exactly the method the chapter
recommends. Disclosing it there strengthens the chapter's argument instead of undermining it.

Rejected within D: **hand-counting the cells and quoting the number.** The count is
load-bearing — it appears in the manuscript — and `scripts/audit_heldout_evidence.py`'s own
docstring states the standing rule that such numbers "must be re-derivable by command rather
than quoted from a chat log". A figure in the thesis with no command behind it is the same
defect class this record is about.

## Decision + integration thoughts

**Disclose, do not repair, and make the count re-derivable.**

New: `scripts/audit_heldout_exclusions.py` + `make audit-heldout-exclusions`. Read-only.

- Loads each `_promoted/<id>.gt.json` through `build_groundtruth_from_json` — the same loader
  the evaluation uses, so the audited population is by construction the graded population.
- Classifies every registered header cell with the scorer's own `_gt_state`, imported rather
  than reimplemented, so the report **cannot** drift from what the scorer does. A private
  import is deliberate here: a local copy of the two-line rule is exactly the kind of duplicate
  that goes stale silently.
- Separates the causes by calling `_is_unlocatable_and_neutralized` — again the same predicate
  the loader itself uses.
- Header fields only, matching ADR-063's grading scope; repeating groups are structurally out
  of scope and are not part of this population.
- Prints counts, field names and document ids only. No field value reaches stdout (ADR-040), so
  a terminal transcript is safe to paste into a pull request or an appendix.
- Touches no existing code path, so no published figure can move as a consequence of this
  record.

Manuscript changes:

- The exclusion inventory in Class One gains the second class and its count, alongside the 8.
- "What Remains Broken" gains the defect entry, with the encoding collision as the finding and
  the bias direction stated.
- `10-limitations-future-work.tex` — "Two Known Defects Remain Open" becomes three.

**Also corrected in the same pass, same root cause of imprecision, different defect.** Two
sites attributed the ADR-059 renderer defect to omission:

- `06-measurement-validity.tex:192` — "scoring zero because the renderer never rendered them"
- `09-discussion.tex:304` — "made fields score nothing because the renderer never emitted them"

ADR-059's finding is the opposite. Its §1 heading is "The instrument printed labels that no
invoice prints", and its diagnosis reads: "the cause was the rendered label: the model could
not map an invented wording to the key". The values *were* rendered — under the standard's
schema vocabulary, which no page in the 146-invoice corpus prints. `FieldSpec.printed_label`
exists solely to keep those two facts apart. Attributing the defect to omission loses the
finding, which is that schema vocabulary and page vocabulary are different things and
conflating them corrupts a ceiling in an unpredictable direction.

## Source archival

No external source. All internal evidence, re-derivable:

- `make audit-heldout-exclusions` — the 30/8/22 split and its per-field, per-channel,
  per-document breakdowns.
- `src/horus/eval/scorer.py:14-24` (truth table), `:278-284` (`_gt_state`).
- `src/horus/eval/heldout.py:208-233` (`_is_unlocatable_and_neutralized`), `:244-309`
  (the two routes to `None`, and the docstring conceding route 2 is caught "at review").
- `eval/heldout-breakdown.json` — `tp + fn = 668`, the denominator that proves the exclusions
  are already netted out.
- `docs/decisions/ADR-059-...md:32-49` — the renderer defect's actual mechanism.
- `docs/reviews/2026-08-18-fifth-pass-full-audit.md` — the audit that found this.

## Supersession trigger

- **When #118 lands** and the date normaliser parses these 22 values, this record is superseded
  in part: the second exclusion class disappears, the denominator grows from 668 toward 690, and
  the headline must be re-measured and re-reported on frozen generations per the chapter's own
  rule. The manuscript's defect entry then becomes a closed defect rather than an open one.
- **If a field other than `payment_means_text` is ever flagged
  `neutralize_when_unlocatable`**, the ratified count changes and the audit's cause split must
  be re-read before any exclusion figure is quoted again.
- **If the scorer gains a fifth ground-truth state**, or `normalizer_rejected` stops being the
  single encoding for both meanings, the collision this record documents is structurally fixed
  and the audit script's cause logic must be revisited.
