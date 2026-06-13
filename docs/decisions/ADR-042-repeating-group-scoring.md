# ADR-042: Unified repeating-group scoring (VAT breakdown · Skonto · line items)

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-13 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (schema-extension session; plan `~/.windsurf/plans/horus-invoice-schema-full-coverage-68a4ac.md`) |
| **Issue** | Step 2 of the full-coverage schema (#111); substrate for #78 (held-out GT drafting), #104 (eval-correctness audit). |

> **Sub-decision of ADR-041 (full-coverage schema). Extends ADR-013/ADR-027 (the flat-field scorer + metric suite).**
> The reserved scope was line-item-only; it is **broadened here** to one *uniform* scorer for **all** repeating structures (the BG-23 VAT breakdown, Skonto tiers, and the BG-25 line-item table), so the same alignment + cell-scoring math serves every list-shaped part of the schema rather than three bespoke paths.

## Context

ADR-041 added the schema *representation* + CII *parsing* + prediction *coercion* for three repeating groups but deliberately deferred their **scoring** to one decision so it would be uniform:

- **VAT breakdown** (BG-23) — one row per VAT rate (category / rate / taxable basis / tax amount).
- **Skonto** — early-payment-discount tiers (percent / days / basis amount).
- **Line items** (BG-25) — the product table (line id / name / seller id / net price / quantity / VAT rate / line amount).

The flat-field scorer (ADR-013) scores a `dict[english_key, str|None]` against a `GroundTruth.header` of the same keys — a fixed 1:1 field set. Repeating groups break that assumption: they are **lists of rows of unknown length and order**, so before any cell can be scored the predicted rows must be **aligned** to the GT rows. This is the line-item-recognition (LIR) problem from the document-IE literature (DocILE; arXiv 2510.15727, 2405.20245).

The user requirement is explicit: *the reported F1 must cover the whole extraction job.* A headline number over only the flat fields silently excludes the table — the densest, hardest part of a real invoice. So repeating-group cells must enter the **same headline metric** as the flat fields.

## Decision

**One uniform repeating-group scorer** (`scorer.score_repeating_group`), reused for all three groups, plus an **opt-in fold** into a new headline `overall_micro_f1` on `InvoiceFieldScores`.

### 1. Row alignment — greedy maximum-similarity bipartite matching

For a group, every (predicted row, GT row) pair gets a **similarity** = fraction of the GT row's *gradable* cells (state `present_content`) that the prediction reproduces (scored with the same comparator dispatch as flat fields — exact for typed, ANLS≥τ for strings). Candidate pairs with similarity > 0 are sorted by `(-similarity, pred_idx, gt_idx)` and greedily matched; each row is used at most once.

- **Matched pair** → score every sub-field cell (TP/FP/FN/TN/EXCLUDED per the flat truth table).
- **Unmatched GT row** (missed) → its gradable cells score **FN** (predicted = None).
- **Unmatched predicted row** (spurious / hallucinated) → its content cells score **FP** (GT = synthetic-absent).

The similarity key generalizes the "natural-key" intuition: for VAT breakdown the rate cell dominates similarity so rows align by rate; for line items the id/name/amount cells jointly drive the match, exactly the content-based LIR matching the reserved ADR described. No separate per-group alignment code is needed.

### 2. Per-cell scoring — reuse the flat truth table

`_score_one_field` was refactored into a spec-explicit core `_score_against_spec(english_key, spec, predicted, gt_field, cfg)`. Flat fields pass `spec = FIELDS[key]`; repeating cells pass the sub-field `FieldSpec` from the group registry (`VAT_BREAKDOWN_FIELDS` / `SKONTO_FIELDS` / `LINE_ITEM_FIELDS`). **Identical** normalization, comparator dispatch, and honesty (an invented cell on an absent GT cell is FP; an honest null is TN). Cell results are labelled `<group>[<pair>].<sub_field>` for the heatmap/diagnostics.

### 3. Metric folding — `overall_micro_f1`, opt-in, backward-compatible

`score(...)` gains `predicted_groups: Mapping[str, Sequence[Mapping]] | None = None`:

- **When `None`** (cohort runs, legacy in-sample baselines, every existing caller) → no repeating scoring; `repeating == {}`; `overall_micro_* == micro_*`. **Published numbers do not move.** This matters because `parse_cii_xml` now *always* populates `gt.vat_breakdown` etc., so auto-scoring them would have silently dropped every cohort F1; the opt-in gate prevents that.
- **When provided** (held-out eval, structurer arms via `to_full_dict`) → each group with GT or predicted rows is scored; its cells join the **headline** `overall_micro_f1` (pooled flat + all cells). The flat `micro_f1` is retained unchanged so flat-vs-overall can be reported side by side.

`InvoiceFieldScores` gains `repeating: dict[str, RepeatingGroupResult]` (per-group P/R/F1 + cell results + matched/missed/spurious row counts) and `overall_micro_{f1,precision,recall}`. The flat `per_field` stays exactly the flat keys, so the existing heatmap (34 columns) is untouched.

## Alternatives considered

- **Optimal (Hungarian) assignment** instead of greedy. Greedy is the pragmatic LIR standard (DocILE) and is exact at the row counts German invoices carry (typically ≤ a few dozen lines); the divergence from optimal requires a pathological similarity tie that does not arise with a discriminative key cell. Revisit if a corpus with large, near-duplicate line tables shows greedy mis-assignment.
- **Folding repeating cells into the existing `micro_f1`** rather than a new `overall_micro_f1`. Rejected: it would retroactively shift every published flat number and conflate two questions (flat-field accuracy vs whole-schema accuracy). Two explicit metrics are more honest and more useful.
- **A bespoke scorer per group.** Rejected as non-DRY and divergent; the uniform similarity matcher already subsumes natural-key alignment.
- **Mandatory (non-opt-in) repeating scoring.** Rejected: would break cohort baselines the moment CII parsing began populating the groups.

## Consequences

- The held-out eval + the two structurer arms can report a single **whole-schema** `overall_micro_f1`, plus per-group F1 (VAT / Skonto / line items) and matched/missed/spurious row counts.
- Cohort runs and frozen in-sample baselines are **provably unaffected** (opt-in gate; verified by `test_score_overall_equals_flat_when_no_groups`).
- Line-item *v1* (ZUGFeRD 1.0) parsing is correct via the new line-level xpath substitutions; the corpus + smoke are v2.
- **Capture + prompt:** the hand-draft GT capture path and the structurer prompt that *requests* these groups are handled alongside (same session); without the prompt the models cannot emit the rows.

## Source archival

Methodology grounded in DocILE LIR (`docs/sources/tools/docile-rossumai.md`) and the line-item-recognition literature (arXiv 2510.15727, 2405.20245). EN16931 business groups BG-23 / BG-25 and BT codes per the standard. No new dependency.

## Supersession trigger

Revisit if (a) a corpus demonstrates greedy mis-assignment on large near-duplicate line tables (→ Hungarian), (b) partial-credit per cell (vs exact/ANLS) becomes desirable for quantity/price tolerance, or (c) the headline metric definition changes (e.g., row-level all-or-nothing F1 à la KIEval for tables).
