# ADR-043: Ground-truth validity — optional-zero EN16931 totals treated as absent

**Status**: Accepted
**Date**: 2026-06-14
**Refs**: ADR-041 (full-coverage schema), ADR-012/013/027/042 (GT + scorer), ADR-037 (frozen-baseline scope), ADR-034 (honesty guardrail)

## Context

ADR-041 extended the scored schema to full EN16931 / §14-UStG coverage (16 → 34 flat fields), adding the optional total fields `allowance_total_amount` (BT-107), `charge_total_amount` (BT-108), `prepaid_amount` (BT-113) and `rounding_amount` (BT-114).

These four BT terms are **optional** in EN16931. ZUGFeRD / Factur-X generators nonetheless emit them in the CII XML as a structural `0.00` even when the invoice has no allowance / charge / prepaid / rounding and **prints nothing** on the page. `parse_cii_xml` therefore recorded `is_present=True, normalized="0.00"`, which `_gt_state` (scorer) classifies as `present_content`. A visual-extraction model that honestly returns `null` (nothing is on the page) is then scored **FN** — penalising the correct behaviour.

Measured impact on the Arm-A 3-invoice dev smoke (`arm-a-dev`, parent `b76a1657`): on the two simple invoices these three fields are all `0.00`, contributing ~3 spurious FN each and dragging flat micro-F1 down (`EN16931_Einfach` measured 0.58 against the flawed ruler vs 0.80 for the 19-field schema that lacked these fields). `EN16931_Rabatte`, which carries *real* non-zero allowances / charges / prepaid (14.73 / 5.80 / 50.00), is unaffected — those remain genuine misses. (Separately verified during this work: `EN16931_Rabatte.cii.xml` has **no** `ram:DueDateDateTime`, so the model's `payment_due_date=2018-03-01` is a genuine FP read from the free-text Skonto payment terms, not a GT bug — no GT change there.)

## Decision

In `parse_cii_xml`, an optional EN16931 total in `_OPTIONAL_ZERO_TOTALS = {allowance_total_amount, charge_total_amount, prepaid_amount, rounding_amount}` whose normalized value is exactly `"0.00"` is recorded as **absent** (`is_present=False`, `normalized_value=None`; `raw_value` preserved for audit). For a visual document-understanding task the page's ground truth for an un-rendered optional zero is "no value" (`null`); the honest model `null` therefore scores **TN**, and a model that invents `0.00` scores **FP** (consistent with the ADR-034 honesty guardrail). Mandatory totals (`line_total` / `tax_basis_total` / `tax_total` / `grand_total` / `due_payable`) are deliberately excluded — a `0.00` there is meaningful and must still be scored.

## Alternatives considered

- **Score the 0.00 fields as EXCLUDED (neutral, no count).** Removes the comparison without asserting a correct answer. Rejected: weaker signal (neither rewards the honest null nor penalises an invented 0.00) and reads as field-dropping to inflate scores.
- **Teach the model to emit `0.00` for these fields.** Rejected outright: it trains the model to write a value not on the page, destroying the precision ≈ 1.0 honesty guarantee and generalising to invoices that *do* carry allowances. Wrong for the tax domain.
- **Leave the GT unchanged.** Rejected: the measurement is invalid (penalises correct behaviour) and is the direct cause of the recall regression vs the 19-field schema.

## Consequences

- Recall on simple invoices recovers to reflect true performance; the headline flat F1 becomes a valid measure of visual extraction. Predicted dev effect from this fix alone: `EN16931_Einfach` 0.58 → ~0.64, `EN16931_Gutschrift` 0.52 → ~0.57. The remaining gap is genuine model misses (VAT/tax IDs, totals reading), addressed separately in Phase 2/3.
- A model that hallucinates `0.00` on these fields now scores FP — intended.
- Frozen closed-milestone baselines (ADR-037 `LEGACY_EXPERIMENT_FIELDS`, 16-field) are **unaffected** — none of BT-107/108/113/114 is in that set.
- Applies to both CII v2 and v1 (the rule keys on `english_key`, shared across `FIELDS` / `FIELDS_V1`).

## Limitation / scope

The rule is a principled heuristic ("optional total = `0.00` ⇒ not rendered ⇒ absent"), grounded in EN16931 optionality and corroborated by the model honestly returning `null`. The gold standard would verify visual rendering per document; that is future work.

**Supersession trigger**: if a corpus invoice is found that *visually renders* a `0.00` for one of these fields (so `null` would be the wrong answer), revisit this decision.
