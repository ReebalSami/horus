# ADR-045: Ground-truth validity — flat tax_rate EXCLUDED for multi-distinct-rate invoices

**Status**: Accepted
**Date**: 2026-06-14
**Refs**: ADR-035 (tax_rate added to schema), ADR-041/042 (VAT-breakdown repeating group), ADR-013/027 (scorer truth table + EXCLUDED outcome), ADR-043 (sibling ground-truth ruler fix)

## Context

ADR-035 added the flat document-level `tax_rate` (BT-119) to the scored schema "as the standard rate for single-rate invoices; the multi-rate full breakdown is deferred." Its GT xpath is `ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent`.

The complication: in CII the header-level `ApplicableTradeTax` elements **are** the per-rate VAT breakdown — the exact same elements ADR-041 parses into the `vat_breakdown` repeating group. So on any multi-rate invoice the flat `tax_rate` xpath matches 2+ elements, and `parse_cii_xml` previously took the **first in document order** (logging a warning). For a visual-extraction model this is ill-posed: when an invoice prints 7% on some lines and 19% on others, there is no single "the rate" on the page. Whatever single value the model emits is simultaneously correct (it is *a* rate on the document) and wrong (it is not "the first one in the XML's document order", which is an artifact of XML serialization, not of the page). The per-rate truth is fully captured and scored by the `vat_breakdown` group's `rate_percent` cells.

Measured impact: in the Arm-A-vs-Arm-B dev comparison at full coverage, `tax_rate` scored **0 TP across every invoice** for both arms (Arm A 0/3, Arm B 0/6) — it was a guaranteed FN/FP regardless of model quality, depressing recall on a field that is not actually a single-valued extraction target. The synthetic ZUGFeRD corpus's simple invoices (`EN16931_Einfach`, `EN16931_Rabatte`) all carry 7%+19%, so the flat field penalized every one.

## Decision

In `parse_cii_xml`, when the `tax_rate` xpath matches multiple elements with **more than one distinct normalized rate**, record the field as **EXCLUDED**: `is_present=True, normalized_value=None` (the scorer's existing `_gt_state` → `normalizer_rejected` → `EXCLUDED` path), with `raw_value` set to the sorted distinct rates (e.g. `"19|7"`) for audit. The `EXCLUDED` outcome contributes to neither numerator nor denominator of any metric (ADR-013), so a model emitting any rate, or `null`, neither helps nor hurts. Single-rate invoices — including multiple `ApplicableTradeTax` elements that all carry the **same** rate — are scored unchanged. This aligns the GT with ADR-035's documented intent ("standard rate for single-rate invoices").

## Alternatives considered

- **Keep "take first in document order".** Rejected: penalizes correct behaviour and makes `tax_rate` an un-winnable field; the "first" choice is an XML-serialization artifact with no visual correlate.
- **Treat multi-rate `tax_rate` as absent (`is_present=False`).** Rejected: "absent" implies the honest answer is `null` and would score a model that emits a real rate as FP. There *are* rates on the page; the field is simply not single-valued. EXCLUDED (neutral) is the honest treatment — distinct from ADR-043's optional-zero-totals case, where `null` genuinely *is* the correct answer.
- **Score `tax_rate` as TP if the prediction matches any of the distinct rates.** Rejected: invents a bespoke many-valued comparator for one field, double-counts signal already measured in `vat_breakdown.rate_percent`, and muddies the flat-field contract.
- **Drop the flat `tax_rate` field entirely.** Rejected: it is a valid, useful single-valued target on single-rate invoices (the common case for many real documents); excision would lose that signal.

## Consequences

- `tax_rate` recall stops being structurally zero on multi-rate invoices; the per-rate truth remains measured in `vat_breakdown`. The flat field now reports honestly on the single-rate invoices where it is well-defined.
- Frozen closed-milestone baselines (ADR-037 `LEGACY_EXPERIMENT_FIELDS`, 16-field) are **unaffected** — `tax_rate` is not in that set.
- A reader inspecting GT sees `tax_rate` with `normalized_value=None` + `raw_value="19|7"`; the `EXCLUDED` outcome surfaces in the scorer/dashboard. The internal `_gt_state` label "normalizer_rejected" is reused as the EXCLUDED carrier (no new state added); the ADR documents the deliberate semantic.
- Applies to both CII v2 and v1 (keys on `english_key`).

## Supersession trigger

If a future field model introduces an explicit single-valued "headline tax rate" business term distinct from the breakdown (or if the scorer gains a first-class `EXCLUDED`-with-reason mechanism), revisit to use that instead of the `is_present=True`+`normalized_value=None` carrier. Also revisit if a corpus invoice is found where multiple distinct header `ApplicableTradeTax` rates do correspond to a single visually-rendered headline rate.
