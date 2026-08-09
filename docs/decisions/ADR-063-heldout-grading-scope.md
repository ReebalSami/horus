# ADR-063: Held-out grading — which answer key, and which fields it may claim

**Status**: Accepted. Both questions are settled in code and enforced: `_promoted/` is the
default answer key with no silent fallback, and the held-out headline covers the 34 flat header
fields with repeating groups structurally excluded (`score_groups=False`). The scope this
authorises is the only held-out claim the thesis makes.

**Correction 2026-08-06 (pre-acceptance, in place):** this record was first written saying the
held-out headline covers "the 19 flat fields". **That count was stale by two schema
extensions.** The registry defines **34** flat header fields (`len(horus.eval.ground_truth.FIELDS)
== 34`), and the signed-off key carries all 34 per document. All 34 are graded; 33 carry a
defined F1 because `rounding_amount` is absent on all 39 documents and therefore scores `TN`
39/39 with no F1 defined. The "19" dates from the ADR-041 era, before the full-coverage flat set
landed — ADR-048 already refers to "the flat 16/19/34 set", which is the audit trail of the two
extensions. **No measured number changes**: 0.8767 was always computed over whatever `FIELDS`
contained, never over a hardcoded 19. Only the prose was wrong, and the thesis sentence that
cites this scope has to name the right count.

**Context**

ADR-062 produced a signed-off held-out answer key: 39 documents, 463 cells promoted on a
recorded warrant, 248 decided by the author. Grading against it is now possible. Two questions
have to be answered before a number is reported, and both were answered wrongly last time.

**1. Which tree does a grading run read?** The corpus now holds four per-invoice answer-key
trees: `gt/` (the superseded text-layer draft), `_judge/gt/` (ADR-060), `_azure/gt/`
(ADR-061), and `_promoted/` (the signed-off key). The first three are *input channels to
adjudication*. Grading against `gt/` — which is what the retracted run did — compares the
system to a key that is itself an unreviewed model draft.

**2. What may the number cover?** `overall_micro_f1` pools the 34 flat fields with every
repeating-group cell. The retracted **0.5692** was that pooled number; the flat-only
`micro_f1` on the same run was **0.7907**. The gap is almost entirely repeating groups —
and the group rows in the signed-off key were **never author-reviewed**. The sign-off page
seeds them from the ADR-060 judge and the author was explicitly told to skip them.

The scale is why. Groups were not adjudicated cell-by-cell because rows do not align across
channels (ADR-062): one reader splits a line another merges, so positional comparison
manufactures conflicts out of segmentation. Reviewing them by hand instead means 92 line-item
rows × 7 sub-fields + 35 VAT rows × 4 = **~784 cells with no ranking and no warrant** —
against 248 ranked header decisions. Row counts disagree across channels on 39/39 documents
for `line_items` and 34/39 for `vat_breakdown`, so the seeded rows cannot be trusted unchecked.

**Decision**

**The answer key is `_promoted/`, by default, everywhere.**
`build_heldout_records` defaults `gt_dirname` to `_promoted`; reaching the draft requires
passing `gt_dirname="gt"` explicitly. Two guards make the default load-bearing rather than
cosmetic:

- **No silent fallback.** An invoice with no promoted file comes back `gt=None` with the
  missing path in `gt_error`. `finetune_evaluate.py --heldout` refuses to run at all if any
  invoice lacks a signed-off key, naming the offenders. Scoring whatever happens to exist
  would report a subset while looking like a whole-corpus result.
- **Verification is read from the document, not the index.** `index.json` still carries
  `verified: true` from the old regime. Inheriting that flag would let an invoice with no
  sign-off present as verified. When `gt_dirname` is given, `load_heldout_index` reads
  `verified` out of the GT file itself.

**The held-out headline is the 34 flat fields. Repeating groups are excluded.**
The exclusion is structural, not a reporting convention: `score_groups=False` passes
`predicted_groups=None`, so group cells are never scored *at all*. This is deliberately not
the same as scoring them against an empty ground truth — that would charge every predicted
row as a false positive and *understate* the system for a reason unrelated to the system.
With groups off, `overall_micro_f1` equals `micro_f1` by construction, so there is no second
number that can be quoted by mistake.

**Line-item extraction keeps being measured — on the synthetic ZUGFeRD corpus**, where GT is
extracted from the embedded factur-x XML and is exact by construction, at greater scale, for
free. The held-out set answers *"does header extraction survive real invoices?"*; the
synthetic set answers *"can it read a line-item table?"*. Neither question is dropped; they
are answered on the corpus that can actually support each.

**Measured result** (zero-shot, `google/gemma-4-E4B-it` structurer over Qwen3-VL-4B reader
transcripts, re-scored offline from the frozen generations — no inference, so the delta is
attributable to the answer key alone):

| Answer key | Flat `micro_f1` | Pooled `overall_micro_f1` |
|---|---:|---:|
| `gt/` draft, unverified (**retracted**) | 0.7907 | 0.5692 |
| `_promoted/` signed-off (this ADR) | **0.8767** | 0.8767 (= flat, groups excluded) |

> **Superseded figure, 2026-08-06.** The 0.8767 above remains the correct record of *this*
> measurement and of the answer-key change it attributes. It is no longer the current
> held-out number: **ADR-065** neutralised 8 cells whose value no adjudication channel could
> locate in the page text, giving mean per-invoice **0.8825** and pooled cell F1 **0.8987**
> on the same frozen generations. That is a ruler change, not a system change — TP and FP are
> identical (568 / 28) and only FN moved (108 → 100).

The **+0.086** on identical generations is ground-truth error in the old key, not a change in
the system.

### Two aggregations, both whole-corpus

`micro_f1` in the table above is the **mean of the 39 per-invoice F1 scores**. It is not a
maximum, a best-of, or a single invoice. A second aggregation answers a different question,
and the two are easy to conflate because both get called "micro":

| Aggregation | What it weights | Held-out value |
|---|---|---:|
| **Mean of per-invoice F1** (reported figure, ADR-027) | each invoice once, regardless of how many fields it carries | **0.8767** |
| **Cell-pooled F1** (all TP/FP/FN summed, then one F1) | each *cell* once, so field-dense invoices pull harder | **0.8931** |

The project reports the first because the invoice is the unit a practitioner cares about —
"how well does this go on a document I hand it". The second is the right figure for "what
share of extracted cells is correct". Pooled sits *above* the mean here, which says the
weakest invoices are also the sparsest: their few cells cannot drag a cell-weighted total as
far as they drag an invoice-weighted average.

### By language and acquisition channel

| Group | n | Mean per-invoice F1 | Cell-pooled F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| english / email | 11 | 0.9318 | 0.9379 | 0.9805 | 0.8988 |
| german / email | 18 | 0.8997 | 0.9051 | 0.9533 | 0.8614 |
| german / iphone-pdf-scan | 10 | 0.7748 | 0.8239 | 0.9225 | 0.7443 |
| **all** | 39 | **0.8767** | **0.8931** | 0.9530 | 0.8402 |

The email-vs-scan gap (mean 0.9118 vs 0.7748) is the degraded-input penalty on real documents,
cleanly isolated — which is the measurement the held-out set exists to produce.

#### Addendum 2026-08-09 — the same breakdown under the current (ADR-065) ruler

The table above is retained as the record of the answer-key change it attributes. The figures
below are the current ones, re-derived from the same frozen generations after ADR-065
neutralised the 8 cells no adjudication channel could locate in the page text. **This is the
table the thesis cites**, because the headline and the breakdown must share one ruler and one
aggregation — mixing the 0.8767-era per-invoice means with post-ADR-065 pooled figures produced
an internally inconsistent table in an earlier draft handoff.

| Group | n | Mean per-invoice F1 | Cell-pooled F1 | Precision | Recall | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| english / email | 11 | 0.9345 | 0.9408 | 0.9805 | 0.9042 | 151 | 3 | 16 |
| german / email | 18 | 0.9027 | 0.9079 | 0.9533 | 0.8667 | 286 | 14 | 44 |
| german / iphone-pdf-scan | 10 | **0.7889** | **0.8371** | 0.9225 | 0.7661 | 131 | 11 | 40 |
| **all** | 39 | **0.8825** | **0.8987** | 0.9530 | 0.8503 | 568 | 28 | 100 |

Reproduce with `uv run python scripts/heldout_breakdown.py
data/self-collected/_eval/eval-zeroshot-heldout-adr065.json --outputs
data/self-collected/_eval/outputs-zeroshot` (re-scores from saved generations; no inference).

The degraded-input penalty survives the ruler change and is the finding of record: **11.6
points of mean per-invoice F1 between email-native PDFs and phone photographs** (0.9148 vs
0.7889), or 8.7 points cell-pooled. Precision holds on scans (0.9225) while recall falls to
0.7661 — poor input makes the system abstain rather than invent.

**The error profile is asymmetric and favourable**: 568 TP, **28 FP, 108 FN**. Precision
0.9530 against recall 0.8402 — roughly four in five errors are a field left empty, not a field
invented. For an accounting tool this is the safer direction to fail in: a missing value is
visible to the reviewer, a fabricated one is not. Recall is where the remaining headroom is,
and it degrades on scans (0.7443) while precision largely holds (0.9225) — i.e. poor input
makes the system *abstain*, not hallucinate.

**Circularity** (ADR-040 §F): the promoted key is drafted by a cloud vision judge, an Azure
specialist model, and a Cascade text-layer draft, then adjudicated and author-decided. None of
the three is the system under test (a local Qwen3-VL reader feeding a local Gemma structurer),
and no contestant output ever entered the key. Auto-acceptance additionally required either
printed-text proof or two independent channels agreeing, so no single channel determined a
cell on its own.

**Alternatives considered**

- **Hand-review the ~784 group cells.** Rejected: it is 3× the header workload, unranked and
  unwarranted, to hand-annotate on 39 real invoices what the synthetic corpus already provides
  exactly and at scale. The information gained does not justify the most expensive annotation
  in the project.
- **Report the pooled number anyway, with a footnote.** Rejected: the pooled number would rest
  on unreviewed GT, which is precisely the property that forced the retraction. A footnote
  does not make an unverified number verified.
- **Score groups against an empty GT** (leave groups on, accept the FPs). Rejected: it
  understates the system by charging correct line-item extractions as errors, and it reports a
  number that looks like a measurement of group extraction while measuring nothing of the kind.
- **Build row alignment and adjudicate groups properly.** Not rejected — deferred. It is the
  honest path to a real-invoice line-item number, and the design (align rows on a stable cell
  such as `line_amount`, then adjudicate within aligned rows) is known. It is out of scope for
  unblocking the header claim, and ADR-054 froze thesis scope to Layer 1.
- **Delete `gt/` now that it is superseded.** Rejected per ADR-011: it is still an adjudication
  input, and it is the record of what produced the retracted figure.

**Consequences**

- The held-out claim the thesis may make is **header-field extraction on real invoices**,
  stated with its scope rather than implied to cover the full schema.
- Repeating-group performance on real invoices is an explicit, documented **limitation**, with
  a known route to closing it if it ever becomes load-bearing.
- Any future held-out run inherits the correct key and scope by default; reproducing the
  superseded measurement is possible but requires saying so on the command line.
- `overall_micro_f1` and `micro_f1` are equal on held-out reports by construction, so the two
  cannot be confused the way they were when 0.5692 and 0.7907 came out of the same run.

**Source archival**

No external sources. Internal: ADR-034 (held-out eval strategy), ADR-040 (held-out set +
circularity guard), ADR-042 (repeating-group scoring), ADR-054 (scope freeze to Layer 1),
ADR-060/061 (the two cloud channels), ADR-062 (adjudication + promotion).

**Supersession trigger**

Superseded or amended if **any** of:

1. Repeating-group rows in the held-out key become author-reviewed (via row-aligned
   adjudication or direct annotation) → the exclusion is lifted and the pooled number becomes
   reportable.
2. A held-out grading run is wired for a contestant that *did* contribute to the answer key →
   the circularity analysis above must be redone before any number is published.
3. The field registry changes such that the "34 flat fields" scope no longer describes what is
   graded. The count is already pinned in code —
   `tests/test_ground_truth.py::test_fields_registry_consistency` asserts `len(FIELDS) == 34`
   and documents the 16 + 3 + 15 derivation — so a registry change fails the suite loudly. The
   drift corrected above was **prose-only**: no test and no measured number ever said 19. When
   that test's expected count changes, this scope sentence must change with it.
4. A second annotator is added and inter-annotator agreement becomes reportable → the warrant
   classes in ADR-062 and the scope here both need revisiting.
