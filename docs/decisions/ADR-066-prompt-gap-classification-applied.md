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
1 untested. So **18 of 34 fields are proven hands-off for the prompt** — adequate on
perfect text, so their reader-arm losses (some severe: `payment_means_text` 0.133,
`seller_tax_id` 0.500) are not prompt gaps.

Two cautions on that "18", both easy to misread:

1. It is **not** the same 18 as "scores exactly 1.000 on perfect text". That set is also
   18 — coincidentally — but differs by two members: it includes `charge_total_amount`
   (1.000 on both arms, so `closed`) and excludes `document_type` (0.982, which clears the
   0.98 adequacy bar with one error). Quoting either "18" without saying which is meant
   invites conflation.
2. "Not a prompt gap" does **not** imply "the reader failed to transcribe it". For most of
   these fields the value *is* present in the reader transcript and was simply not mapped
   (see the FN-readability section below: 56 of 84 flat FNs are readable). The verdict name
   `reading-gap` marks *where the loss is not* (the prompt), not a positive claim about the
   reader.

Full machine-readable artifact: `data/finetune/field-gap-classification-val.json`.

## Per-invoice escalation of the 3 candidates — all resolve to NOT prompt-fixable

Each was inspected against its actual generations
(`data/finetune/oracle-adr059-fixed-outputs` — the canonical arm; a near-identically named
`oracle-adr059-outputs` directory is the `nocolon` ablation and reproduces a different
report, `eval-oracle-adr059-nocolon-val.json` — confirmed by `finetune_evaluate.py
--score-only`, which loads no model).

- **`line_total_amount` (label-mapping).** The net-vs-gross confusion is real and is
  concentrated on the **oracle** arm, which is what drives oracle (0.863) *below* reader
  (0.906). On three invoices — `EN16931_AbweichenderZahlungsempf`,
  `EN16931_Einfach_DueDate`, `zugferd_2p1_EN16931_Einfach_DueDate` — BT-106 is `473.00`
  (equal to BT-109), the reader arm answers `473.00` correctly, and the **oracle** arm
  answers the gross total `529.87`. The reader arm's own 3 FNs are different invoices and a
  different shape (`410.10`→`403.55`, `202.70`→`193.77`, and one `473.00`→`529.87`), and two
  invoices fail on the reader arm while passing on the oracle arm. So the error is
  **unstable across renderings of the same values**, not a fixed vocabulary miss: both
  candidate German terms — `Positionssumme` (88/146) and `Nettobetrag` (23/146) — are
  *already* grounded aliases, and the field is already glossed with an explicit "NOT a
  single line's amount and NOT one VAT rate's subtotal" description. There is also no
  headroom: oracle < reader means the perfect-text arm cannot certify any improvement.
  **Not repaired.**
- **`seller_iban` (prompt-candidate).** Of the 12 val invoices carrying BT-84, **11** have
  the model emitting a character-identical IBAN; the scorer counts 5 as FN. **4** of those 5
  are the pre-existing, already-documented normalizer asymmetry (GT `DE88 2008 0000 0970
  3757 00` vs prediction `DE88200800000970375700` — space-grouped vs compact):
  `finetune/dataset.py`'s `build_finetune_examples` docstring names "the known `seller_iban`
  CODE-vs-string normalizer asymmetry" as a self-score under-credit, symmetric across arms.
  The 5th (`ZUGFeRD_2_fully_compliant_complete`) is a genuine reader-arm miss — `None`
  emitted where the oracle arm scores TP — i.e. a reading/context failure, not a missing
  label. The reader arm additionally produces **3 FPs** on invoices with *no* GT IBAN, where
  the oracle arm correctly stays silent (TN). None of the four causes — scorer
  normalization, one context miss, three hallucinations — is addressable by adding
  vocabulary; the corpus does print two unlisted forms (`Verkäufer-IBAN`×10, `IBAN-Nr`×3),
  but the model already extracts the value in 11 of 12 cases without them, and ADR-048
  measured that adding prompt text *raises* spurious emission — the exact failure already
  visible in those 3 FPs. **Not repaired.**
- **`seller_name` (prompt-candidate).** **2 of the 3** reader-arm FNs are ground-truth
  defects, not the 3 originally recorded here: `zugferd_2p1_EN16931_Sachversicherung_...`
  has GT with an embedded newline (`'MVM Musterhafter\nVersicherungsverein Musterstadt
  a.G.'`) and the model emits the first line only; `zugferd_2p0_BASIC_Rechnungskorrektur`
  has GT polluted with a GLN and a supplier number ahead of the company name, and the model
  is scored FN for emitting just the company name. (Its 2p0 sibling
  `EN16931_Sachversicherung_berechneter_Steuersatz` is a reader **TP** — the model happened
  to join the two lines with a space — so this is one invoice, not a fixture pair.) The
  **third** FN is a genuine model error: on the French credit note `Avoir_FR_type380_EN16931`
  the reader arm emits the contact person `Tony Dubois` where GT is the company `Au bon
  moulin`, and the oracle arm gets it right. That is one invoice — below this round's
  two-error escalation floor, and therefore `marginal` by the same rule applied everywhere
  else. `seller_name` is unglossed (no `description`, no `printed_label`, no aliases) and
  still scores 26/29, so the 24/146 `Name` label the advisory channel surfaces is not what
  is failing — and `Name` is ambiguous across buyer/contact/account name, exactly the
  collision ADR-049's per-field descriptions exist to prevent. **Not repaired.**

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
vs **absent** (unreadable by construction). Across the 34 flat fields the reader arm has
**84 FNs, 56 of them readable (67 %)** and 28 unreadable, plus 58 FPs — so most of the
reader arm's residual loss is *not* the reader failing to transcribe.

Two fields were escalated through this lens, per invoice:

- **`seller_tax_id`** sits at oracle ceiling (1.000) yet has **10** reader FNs, **7** of
  them readable. The vocabulary question is closed from both directions:
  `scripts/audit_field_prompts.py --field seller_tax_id` reports **zero** unlisted labels
  (the corpus prints nothing the alias list lacks), and per-invoice inspection shows **6 of
  those 7 readable FNs print a label that is already listed** (`Steuernummer`, both the
  field's `german_label` and one of its two aliases) while the field is already glossed with
  an explicit "NEVER the USt-IdNr./VAT id" warning — and the model still emits `None`. So
  the loss is neither an absent value nor a missing word; it is a mapping failure in real
  transcript context, and no vocabulary edit addresses it. Classified `reading-gap`, hands
  off for the prompt, and *available* to the fine-tune.
- **`payment_reference`** has 7 reader FNs, 6 readable, and its advisory channel does
  surface one genuine unlisted label (`Referenz (bitte bei Zahlung angeben)`×3). Checked
  per invoice anyway: **none** of the 6 readable FNs prints that label, and none prints an
  already-listed one either. Their GT values (`AV-2017-0005`, `FA-2017-0008`,
  `RE-20170509/505`, `80003371`) are the **invoice number repeated** — which is what makes
  them "readable" at all. The pages simply do not label a remittance reference. Nothing to
  add. **Not repaired.**

That second case exposes a limit of the diagnostic itself, worth stating so it is not
over-read: `fn_readable` is a **value-containment** test, so any field whose value
legitimately coincides with another field's value inherits that other field's readability.
"Available, not mapped" therefore over-counts wherever values collide (BT-83 ≡ BT-1 here;
BT-106 ≡ BT-109 on several invoices above). It is a *suspect-raising* signal, not proof of
a prompt gap — which is exactly how it was used.

The same advisory cross-check was run for the remaining fields with ≥ 2 readable FNs
(`payment_means_code`, `delivery_date`, `issue_date`, `due_payable_amount`,
`tax_total_amount`, `invoice_number`, `prepaid_amount`, `tax_basis_total_amount`,
`allowance_total_amount`; the other high-readable fields are the three escalated candidates
above). Several surfaced candidate labels, but they are dominated by the same collision
mode — e.g. `due_payable_amount`'s `bruttosumme` candidate is the *gross-total* label, not a
due-amount label; the two are numerically equal whenever no prepayment or rounding applies
(`bruttosumme` occurs on 89/146 corpus transcripts). Separating a genuine gap from a
collision needs more val invoices than are currently sealed; recorded as
`marginal`/`reading-gap` per the classifier and not acted on, consistent with the discipline
that produced the zero-repair result above.

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
unspent. Note that `data/self-collected/` is **gitignored** (real client invoices; the
privacy premise of the project), so that row is not reproducible from a fresh clone — it is
verifiable only on the author's machine, where it was re-read for this ADR. The 39-invoice
totals it aggregates to are published in ADR-063. The grounding corpus is correct for what
it contains and narrow for real invoices; corpus-measured vocabulary cannot close a gap the
corpus itself never exhibits.
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
  ADR's scope — candidates for a future scorer-fix or ground-truth-repair round. Two more
  join them from the corrected evidence: the reader arm's **3 hallucinated `seller_iban`
  FPs** on invoices with no IBAN (the oracle arm stays silent on all three), and the
  `Avoir_FR_type380_EN16931` **company-vs-contact-person** confusion on `seller_name`. Both
  are single-field, sub-threshold observations here; neither is prompt-shaped.
- **Where the fine-tune's headroom actually is** (the useful hand-back to #55): of the
  reader arm's 84 flat-field FNs, **56 (67 %) have the value present in the transcript** and
  were simply not mapped, and there are 58 FPs on top. `seller_tax_id` is the sharpest
  single case — value present, an already-listed label present, an explicit disambiguating
  description present, and the model still answers `None` on 6 invoices. That mass is
  exactly what a LoRA can learn and what no prompt edit reached, which is the positive form
  of ADR-064's ordering rule being satisfied.
- The LoRA gate (ADR-054) is re-read against these unchanged numbers in the issue tracking
  this work (#122) and is unaffected: `mean_overall_micro_f1` remains 0.8257 against the
  0.90 threshold, since no prompt or registry edit occurred to move it.

## Self-audit correction (pre-merge, same branch)

This ADR's first draft stated the right conclusions from partly wrong evidence. A
pre-merge audit re-derived every claim from the committed artifacts and corrected four
things; all are fixed in the text above, and none changed the zero-repair outcome:

1. **`line_total_amount`'s worked example was attributed to the wrong arm.** The
   `473.00`→`529.87` gross-total confusion happens on the **oracle** arm (3 invoices); the
   reader arm answers that invoice correctly. This actually *explains* the label-mapping
   verdict better than the original text did — oracle < reader is the whole signal.
2. **`seller_iban` "all 12 exactly correct" was false.** It is 11 of 12; the 12th emits
   `None` on reader text (TP on oracle). The FN count is 5, not 4, and the arm also produces
   3 hallucinated FPs where no IBAN exists — which the original text omitted entirely.
3. **`seller_name` "all 3 are GT defects" was false.** 2 of 3 are; the third is a genuine
   company-vs-contact-person error on a French credit note. The "fixture pair" claim was
   also wrong — the sibling invoice is a reader TP.
4. **`seller_tax_id`'s FN counts were wrong** — 7 FNs / 6 readable stated; **10 / 7**
   actual, straight from `attribution-adr059-val.json`. Its supporting claim ("zero unlisted
   labels") was re-verified as **true** and kept, and strengthened with a per-invoice
   finding it had missed: 6 of the 7 readable FNs print an **already-listed** label and the
   model still emits `None`.

The audit also found the diagnostic's own limit (`fn_readable` is value-containment, so
colliding values inflate it) and one field the original scope sentence claimed to have
checked but had not (`payment_reference`, now checked — result recorded above).

Method note, since it is the transferable part: the table of 34 rows was verified by
*parsing this file* and diffing every cell against
`data/finetune/field-gap-classification-val.json` rather than by reading it — that part was
clean on the first pass. Every error above was in the **prose**, which no artifact
constrains. Narrative claims about specific invoices need the same mechanical
re-derivation as tables; eyeballing them is what let four wrong statements through.

**Source**: `~/.windsurf/plans/horus-prompt-gap-classification-5a47b9.md` (the operative
plan); commits `446616a` (Step 1, diagnostic fixes) and `521ddfc` (Step 2, classifier +
attribution split) on branch `fix/prompt-gap-classification`; issue #122.
