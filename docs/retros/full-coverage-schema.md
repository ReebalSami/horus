# Retro — full-coverage extraction schema (ADR-041 + ADR-042)

**Status**: closed
**Date**: 2026-06-13
**Branch**: `feat/schema-step1` (stacked on the held-out branch `feat/heldout-belege-gt`)
**Scope**: extend the scored schema from 19 fields to the whole invoice so the reported
F1 describes the entire extraction job, not a subset.

## What shipped

| Wave | Content | Commit |
|---|---|---|
| 1a | 15 flat fields (document type, payment block, bank details, extra totals, order ref, billing period); frozen-16 positive-list rework | `ec4a861` |
| 1b | VAT breakdown (BG-23) + Skonto repeating groups — representation + CII parse + prediction coercion | `9647a5a` |
| 2 — model | line-item table (BG-25): registry + v1 xpaths + parse + submodel + coercion | `63c965e` |
| 2 — scoring | unified repeating-group scorer (greedy alignment + per-cell F1) → `overall_micro_f1`; ADR-042 | `63c965e` |
| 2 — capture | `gt_document`/`build_*` round-trip + 3 review-grid editors | `a442436` |
| 2 — prompt+wiring | arm-a/arm-b prompts request all fields+groups; harness/arm_b thread `predicted_groups` → MLflow | `c159047` |
| 2 — app | Invoice Explorer shows whole-schema + per-group accuracy | `4cf0c11` |

Scored schema: **19 → 34 flat fields** + 3 repeating groups (VAT breakdown / Skonto /
line items). 835 tests pass; ruff + mypy clean throughout.

## Live validation (the proof)

3-invoice Gemma single-shot smoke on the ZUGFeRD corpus, MLflow-tracked (`arm-a-dev`,
parent `b76a1657`):

| Invoice | flat μF1 | whole-schema μF1 | VAT breakdown F1 | line-items F1 |
|---|---|---|---|---|
| EN16931_Einfach | 0.581 | 0.667 | 0.222 | 0.923 |
| EN16931_Gutschrift | 0.516 | 0.636 | 0.222 | 0.923 |
| EN16931_Rabatte | 0.588 | 0.395 | 0.769 | 0.000 |

Transcripts confirm the model emits the new fields + nested arrays
(`vat_breakdown`, `line_items` with `net_price`/`line_amount`). The dashboard renders it.

## Learnings

- **Opt-in scoring saved the baselines.** `parse_cii_xml` now always populates the GT
  repeating groups; auto-scoring them would have silently dropped every cohort/baseline
  F1. Gating repeating-group scoring behind `score(predicted_groups=...)` kept all frozen
  numbers provably unmoved (`test_score_overall_equals_flat_when_no_groups`). Pattern worth
  reusing: **additive metrics must be opt-in when the GT side grows underneath them.**
- **Spec-explicit refactor unlocked reuse.** Splitting `_score_one_field` into a
  spec-explicit `_score_against_spec` let flat fields and repeating-group cells share one
  truth-table + comparator path — no second scorer, no drift.
- **A live smoke is worth more than the unit suite for "does it actually work".** The unit
  tests were green long before the prompt was updated; only the smoke proved the models
  emit the new fields. The user's instinct ("test it live first") was correct and is the
  reason the prompt update was pulled forward rather than deferred.
- **Greedy similarity matching subsumes natural-key alignment.** One matcher handles VAT
  (rate-keyed), Skonto, and line items (id/amount-keyed) — no per-group code.

## Follow-ups (not blocking; candidates for issues)

- **App per-row group table.** The Invoice Explorer shows per-group F1; a row-by-row
  predicted-vs-GT table for the groups (like the flat field table) is the next UI step.
- **Cross-page line-item merge.** `to_predicted_groups_multipage` is first-non-empty-page-
  wins; a true cross-page concatenation would help multi-page line tables.
- **Skonto structured-text parsing.** Only the structured `ApplicableTradePaymentDiscountTerms`
  is parsed; the FeRD `#SKONTO#…#` free-text convention is a parser follow-up.
- **v1 line-item fixture test.** v1 line-level xpath substitutions are implemented; a v1
  ZUGFeRD-1.0 line-item fixture test would lock them (corpus + smoke are v2).

## PR status

Not yet opened — the branch stacks on the unpushed held-out branch, and the user sequences
the merge. `@release-manager` lands it when ready.
