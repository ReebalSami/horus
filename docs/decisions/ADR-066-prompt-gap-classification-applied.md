# ADR-066: Prompt-gap classification, applied — zero repairs warranted

**Status**: Accepted

**Context**: A handoff proposed closing the fine-tune gate's remaining distance by walking
all 34 flat fields and adding corpus-grounded aliases to each. ADR-064 forbids handing a
prompt-fixable gap to the LoRA — the fine-tune would be credited with gains a free prompt
edit could have produced, since `finetune.dataset.groundtruth_to_target` builds LoRA
labels from the same registry the prompt renders. Discharging that rule needs per-field
evidence of *cause*, not a uniform walk. Two eval reports already on disk — the real-reader
arm and a perfect-text ("oracle") arm, both on the 29 sealed-val invoices — make that
evidence available without a new measurement.

The handoff itself was independently checked before this ADR's work began (`02fe70f`,
recorded in `~/.windsurf/plans/horus-prompt-gap-classification-5a47b9.md` §1) and contained
three defects that made its own diagnostic untrustworthy: a label-folding asymmetry, an
advisory channel dominated by ground-truth values and boilerplate rather than genuine
findings, and a nondeterministic label-extraction order (two runs of the same script
disagreed on corpus counts). Those are fixed in a prior commit (`446616a`) with regression
tests; this ADR covers the classification and repair round that fixing them made possible.

**Decision**: Classify every field by comparing its reader-arm F1 against its own
oracle-arm F1, using `scripts/classify_field_gaps.py`, and repair only what that comparison
*proves* is prompt-caused. Corpus-grounded only — no alias justified by an external
standard, and the held-out real-invoice run stays unspent (read for reporting, not
re-run).

## Classification method

Per field, given signal-bearing (TP/FP/FN) outcome counts on both arms:

1. **No gradable cells on the oracle arm → `untested`.** An F1 of 0.000 over zero outcomes
   is undefined, not a failure (`rounding_amount`: present on 1/146 grounding invoices,
   absent from the 29-invoice val split).
2. **Oracle F1 below the reader F1 → `label-mapping`.** Same model, same instruction; only
   the page wording differs, so the loss is in mapping a label to the right key, not in
   reading. `line_total_amount` is the one instance (oracle 0.863 < reader 0.906) —
   ADR-058/059 changed its oracle label, and the plan flagged this as the priority
   candidate on exactly that signal.
3. **Oracle F1 below 0.98 with ≥ 2 errors on perfect text → `prompt-candidate`.** Escalate.
4. **Oracle F1 below 0.98 with 1 error → `marginal`.** Recorded, not escalated.
5. **Oracle F1 ≥ 0.98 but reader F1 lower → `reading-gap`.** The prompt is proven adequate
   on perfect text; the loss is the reader's. Hands off.
6. **Oracle F1 ≥ 0.98 and reader at the same level → `closed`.**

The plan's own Step 2 rule was a flat "oracle F1 ≥ 0.98 → hands off, else candidate"
threshold. Applied literally it manufactures false candidates on a small denominator:
`billing_period_start` is present on 3 val invoices, so its single miss reads as 0.800 —
indistinguishable, by F1 alone, from a field failing on every occurrence. The plan's own
Step 2 text already special-cased four such fields by hand ("the 1-FN marginals"); rule 3
vs. 4 above formalizes that distinction uniformly instead of by inspection, and is
regression-tested (`tests/test_classify_field_gaps.py::test_a_small_denominator_cannot_manufacture_a_prompt_candidate`).

## Per-field cause table (34 flat fields, `data/finetune/eval-zeroshot-qwen-adr059-val.json`
reader vs `data/finetune/eval-oracle-adr059-val.json` oracle, 29 sealed-val invoices)

| field | BT | reader F1 | oracle F1 | verdict |
|---|---|---|---|---|
| `line_total_amount` | BT-106 | 0.906 | 0.863 | label-mapping |
| `seller_iban` | BT-84 | 0.636 | 0.800 | prompt-candidate |
| `seller_name` | BT-27 | 0.945 | 0.945 | prompt-candidate |
| `billing_period_start` | BT-73 | 0.333 | 0.800 | marginal |
| `billing_period_end` | BT-74 | 0.400 | 0.857 | marginal |
| `buyer_vat_id` | BT-48 | 0.667 | 0.923 | marginal |
| `allowance_total_amount` | BT-107 | 0.667 | 0.909 | marginal |
| `buyer_reference` | BT-46 | 0.765 | 0.963 | marginal |
| `delivery_date` | BT-72 | 0.865 | 0.974 | marginal |
| `seller_gln` | BT-29 (scheme 0088) | 0.867 | 0.966 | marginal |
| `tax_rate` | BT-119 | 0.900 | 0.952 | marginal |
| `payment_means_text` | BT-82 | 0.133 | 1.000 | reading-gap |
| `payment_reference` | BT-83 | 0.364 | 1.000 | reading-gap |
| `seller_tax_id` | BT-32 | 0.500 | 1.000 | reading-gap |
| `seller_bic` | BT-86 | 0.615 | 1.000 | reading-gap |
| `buyer_order_reference` | BT-13 | 0.632 | 1.000 | reading-gap |
| `seller_account_name` | BT-85 | 0.667 | 1.000 | reading-gap |
| `payment_means_code` | BT-81 | 0.667 | 1.000 | reading-gap |
| `prepaid_amount` | BT-113 | 0.750 | 1.000 | reading-gap |
| `payment_due_date` | BT-9 | 0.889 | 1.000 | reading-gap |
| `seller_vat_id` | BT-31 | 0.906 | 1.000 | reading-gap |
| `due_payable_amount` | BT-115 | 0.945 | 1.000 | reading-gap |
| `invoice_currency_code` | BT-5 | 0.945 | 1.000 | reading-gap |
| `issue_date` | BT-2 | 0.945 | 1.000 | reading-gap |
| `tax_total_amount` | BT-110 | 0.945 | 1.000 | reading-gap |
| `grand_total_amount` | BT-112 | 0.964 | 1.000 | reading-gap |
| `invoice_number` | BT-1 | 0.964 | 1.000 | reading-gap |
| `tax_basis_total_amount` | BT-109 | 0.964 | 1.000 | reading-gap |
| `document_type` | BT-3 | 0.964 | 0.982 | reading-gap |
| `buyer_address` | BG-8 | 0.982 | 0.982 | closed |
| `buyer_name` | BT-44 | 0.982 | 0.982 | closed |
| `charge_total_amount` | BT-108 | 1.000 | 1.000 | closed |
| `seller_address` | BG-5 | 0.982 | 0.982 | closed |
| `rounding_amount` | BT-114 | — | — | untested |

Counts: 1 label-mapping, 2 prompt-candidate, 8 marginal, 18 reading-gap, 4 closed,
1 untested. **18 of 34 fields are proven hands-off** — at ceiling on perfect text, so
their reader-arm losses (some severe: `payment_means_text` 0.133, `seller_tax_id` 0.500)
are reading losses, not prompt gaps. Full machine-readable artifact:
`data/finetune/field-gap-classification-val.json`.

## Per-invoice escalation of the 3 candidates — all resolve to NOT prompt-fixable

Each was inspected against its actual generations
(`data/finetune/oracle-adr059-fixed-outputs` — the canonical arm; a near-identically named
`oracle-adr059-outputs` directory is the `nocolon` ablation and reproduces a different
report, `eval-oracle-adr059-nocolon-val.json` — confirmed by `finetune_evaluate.py
--score-only`, which loads no model).

- **`line_total_amount` (label-mapping).** On `zugferd_2p1_EN16931_Einfach_DueDate`, BT-106
  and BT-109 (`tax_basis_total_amount`) are both `473.00`; the model correctly emits
  `473.00` for `tax_basis_total_amount` and instead emits the invoice's gross total
  (`529.87`) for `line_total_amount`. Both candidate German terms — `Positionssumme` (88/146)
  and `Nettobetrag` (23/146) — are *already* grounded aliases (`make glossary`); the failure
  is the model picking the wrong already-named total when several coexist with similar
  values, not a missing label. Oracle F1 (0.863) is *below* reader F1 (0.906), so there is
  no headroom to recover even if a prompt change were found — this field cannot pass its
  own gate. **Not repaired.**
- **`seller_iban` (prompt-candidate).** All 12 val invoices carrying BT-84 show the model
  emitting the value **exactly correctly** (`check_oracle_transcript_labels.py seller_iban`).
  The 4 outcomes the report counts as FN are a pre-existing, already-documented scorer
  defect: `finetune/dataset.py`'s `build_finetune_examples` docstring names "the known
  `seller_iban` CODE-vs-string normalizer asymmetry" as a self-score under-credit that is
  symmetric across arms and therefore not corrected there. Fixing a normalizer is a scorer
  change, out of scope for a prompt-classification round. **Not repaired.**
- **`seller_name` (prompt-candidate).** All 3 failing invoices carry a ground-truth defect:
  two (`EN16931_Sachversicherung_berechneter_Steuersatz` twice, once per ZUGFeRD-version
  fixture pair) have GT containing an embedded newline
  (`'MVM Musterhafter\nVersicherungsverein Musterstadt a.G.'`); the model reads the printed
  first line and emits it correctly as far as it goes, but the exact-match comparator wants
  the whole multi-line string. The third
  (`zugferd_2p0_BASIC_Rechnungskorrektur`) has GT polluted with a GLN and a supplier number
  ahead of the actual company name; the model correctly emits the company name and is
  scored FN for not also reproducing the pollution. Ground-truth quality, not prompt
  vocabulary. **Not repaired.**

**Net repair count: zero.** No edit to `src/horus/eval/ground_truth.py`'s `FIELDS`
registry or to `configs/arm-b.yaml`'s prompt preamble was warranted by evidence. This is
itself the finding the ordering rule (ADR-064) exists to produce: proving a candidate is
*not* prompt-caused is as much in scope as proving one is, and sends nothing avoidable to
the LoRA.

## Closing a blind spot in the oracle-ceiling inference

Comparing arms this way has one gap: the oracle page prints the registry's own
`printed_label`, while the reader emits whatever wording it actually read, so "at ceiling
on the oracle page" does not by itself prove the prompt copes with the *reader's* wording
when the two differ. `scripts/finetune_attribution.py` (which already loads the corpus,
transcripts and generations for its cluster tallies) now also reports, per flat field, how
many reader-arm FNs had their value **present** in the transcript (available, not mapped)
vs **absent** (unreadable by construction). This did contradict the simple reading in one
case worth recording: `seller_tax_id` sits at oracle ceiling (1.000) yet has 7 reader FNs,
of which 6 have the value present in the reader transcript. Cross-checked against
`scripts/audit_field_prompts.py --field seller_tax_id`: **zero** unlisted labels — the
grounded aliases (`Steuernummer`, `Steuernr.`) already cover what the corpus prints, so the
loss is not a vocabulary gap either; it is left `reading-gap` as classified. The same
cross-check was run for every field with ≥ 2 readable-but-unmapped reader FNs
(`payment_means_code`, `delivery_date`, `issue_date`, `due_payable_amount`,
`tax_total_amount`, `invoice_number`, `prepaid_amount`, `tax_basis_total_amount`,
`allowance_total_amount`); several surfaced candidate labels, but nearly all are value
collisions where this field's value happens to equal a *different* total on invoices where
no allowance/prepayment applies (e.g. `due_payable_amount`'s `'bruttosumme'×67` candidate is
the gross-total label, not a due-amount label — the two are simply numerically equal on
most invoices). Distinguishing a genuine collision from a real gap on this evidence needs
more than a frequency count and is left for a future round with more val invoices;
recorded here as `marginal`/`reading-gap` per the classifier, not acted on, consistent
with the discipline that produced the zero-repair result above.

## No re-measurement performed

Step 4 of the plan calls for one measured round after repairs, gated on no field
regressing. Since no prompt or registry edit was made, the committed reports already
describe the current, unchanged prompt. This was independently confirmed rather than
assumed: `scripts/finetune_attribution.py`'s built-in reproduction check re-scored the 29
saved reader-arm generations from scratch and got `mean_overall_micro_f1_recomputed
0.8257` against `mean_overall_micro_f1_report 0.8257176151171564` — an exact match
(`data/finetune/attribution-adr059-val.json`). Running a fresh evaluation round would
reproduce the same numbers at additional cost for zero information gain.

## Measured limitation: real-invoice vocabulary narrowness

The prompt's German vocabulary is grounded on one synthetic publisher (146 grounding-corpus
transcripts). `delivery_date` is the clearest measured instance of that narrowness'
consequence:

| measurement | value | source |
|---|---|---|
| `delivery_date`, grounding corpus (29 sealed-val invoices, reader text) | F1 0.865 (ceiling 0.974) | `eval-zeroshot-qwen-adr059-val.json` / `eval-oracle-adr059-val.json` |
| `delivery_date`, 39 held-out real invoices | F1 0.435 (TP 5 / FP 0 / FN 13 / TN 18 / EXCLUDED 3) | `data/self-collected/_eval/eval-zeroshot-heldout-signed.json` (read only — not re-run) |
| `Lieferdatum` (EN16931 spec term) in the 146-transcript grounding corpus | 0/146 | independently re-verified this session against `configs/finetune-structurer.yaml`'s reader lineage |
| `Leistungsdatum` (current grounded `printed_label`, the shortest common stem) | 85/146 | same |
| `Liefer- und Leistungsdatum` / `Liefers- und Leistungsdatum` (compound forms; the second is a 19/146 reader OCR variant, not a distinct printed label) | 41/146 / 19/146 | same |

The held-out figures were already on disk from a prior held-out evaluation round and are
cited, not regenerated — per this round's decision to keep the single held-out run
unspent. The grounding corpus is correct for what it contains and narrow for real
invoices; corpus-measured vocabulary cannot close a gap the corpus itself never exhibits.
This is a result about the grounding corpus's coverage, not a defect in the classification
method above, and is the honest basis for treating a larger or more diverse
real-invoice grounding set as future work rather than in-scope here.

## Source correction

`docs/sources/legal/zugferd-technischer-anhang-de.md` is corrected to record that
standards-warranted aliases (e.g. from the KoSIT `xrechnung-visualization` German term
table) are explicitly out of scope for this round, and that the table's labels are
context-scoped (`Gesamtsumme` denotes BT-109, BT-112 **and** BT-116 depending on which
section of a rendered invoice it appears in) — recorded so a future session does not
import it mechanically and reintroduce the ambiguity ADR-049's per-field descriptions
exist to remove.

**Alternatives considered**:

- *Apply the plan's literal 0.98-threshold rule with no error-count floor.* Rejected —
  demonstrated above to manufacture a prompt-candidate verdict from a single miss on a
  3-invoice denominator.
- *Treat `line_total_amount`/`seller_iban`/`seller_name` as prompt gaps and add aliases
  anyway, since the plan expected repairs here.* Rejected — the per-invoice evidence
  contradicts a prompt cause in all three cases, and ADR-048 measured over-glossing as
  net-negative; adding text the evidence does not support is exactly the failure mode this
  round exists to avoid.
- *Fix the `seller_iban` scorer asymmetry now, since it was found during this work.*
  Rejected for this ADR's scope — it is a scorer change, already documented at its own
  definition site, and mixing it into a prompt-classification round would make the "zero
  registry edits" result harder to audit. Left as a known, pre-existing issue.
- *Act on every check-C candidate surfaced by the readability cross-check
  (`invoice_number`, `issue_date`, `tax_total_amount`, …).* Rejected — most are value
  collisions between fields that happen to share a value on invoices where no
  allowance/prepayment/discount applies, not genuine missing labels; separating the two
  needs more val invoices than are currently sealed.

**Consequences**:

- `scripts/classify_field_gaps.py` and its 2-error escalation floor are the durable
  instrument for future rounds — re-run whenever the reader or oracle val report changes.
- `scripts/finetune_attribution.py`'s per-field FN-readability table is now a standing
  diagnostic, not a one-off; it should be consulted alongside `classify_field_gaps.py`
  before trusting any oracle-ceiling reading-gap verdict.
- The `seller_iban` normalizer asymmetry and the `seller_name` embedded-newline /
  GLN-pollution ground-truth defects are now explicitly named, open issues outside this
  ADR's scope — candidates for a future scorer-fix or ground-truth-repair round.
- The LoRA gate (ADR-054) is re-read against these unchanged numbers in the issue tracking
  this work (#122) and is unaffected: `mean_overall_micro_f1` remains 0.8257 against the
  0.90 threshold, since no prompt or registry edit occurred to move it.

**Source**: `~/.windsurf/plans/horus-prompt-gap-classification-5a47b9.md` (the operative
plan); commits `446616a` (Step 1, diagnostic fixes) and `521ddfc` (Step 2, classifier +
attribution split) on branch `fix/prompt-gap-classification`; issue #122.
