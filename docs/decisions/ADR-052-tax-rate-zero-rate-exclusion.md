# ADR-052: Ground-truth validity — flat `tax_rate` (BT-119) EXCLUDED for single 0%-rate invoices

**Status**: Accepted
**Date**: 2026-06-21
**Refs**: ADR-045 (the multi-distinct-rate exclusion this extends), ADR-035 (the flat `tax_rate` field's stated single-rate intent), ADR-043/046/047 (sibling GT-validity ruler fixes), ADR-042 (the `vat_breakdown` repeating group that carries the per-rate truth)

## Context (current-state survey)

ADR-045 established that the document-level flat `tax_rate` (BT-119) is well-defined only for **single-rate** invoices, and marked it EXCLUDED (neutral — scored as neither right nor wrong) when the CII carries multiple distinct VAT rates, because there is then no single "the rate" on the page (the per-rate truth lives in the `vat_breakdown` group, BG-23).

The Innergem (`EN16931_Innergemeinschaftliche_Lieferungen`) audit surfaced the **single-zero-rate** case that ADR-045 did not cover: an intra-community supply (and reverse-charge / exempt invoices generally) carries exactly **one** VAT rate, and that rate is **0**. ADR-045's multi-rate guard does not fire (there is only one distinct rate), so the flat `tax_rate` was being scored — against a literal `0`. This is ill-posed for the same reason as the multi-rate case:

- The page renders no positive "tax rate"; it shows "0 %" / "steuerfrei" / "innergemeinschaftliche Lieferung" / "Reverse Charge".
- The literal `0` is already captured, per-rate, in the `vat_breakdown` group (`rate_percent`).
- Scoring a flat scalar `0` therefore rewards or penalizes a **redundant, ill-posed** field — a model that omits the flat zero rate (correctly judging there is no positive rate to report) is wrongly scored FN, and one that emits `0` is rewarded for echoing a structural artifact rather than reading the page.

## Decision

Extend the ADR-045 exclusion to the single-zero-rate case. In `parse_cii_xml` (`src/horus/eval/ground_truth.py`), after normalization, when `english_key == "tax_rate"` and the normalized value is `"0"`, mark the field EXCLUDED via the neutral path already used by the multi-rate exclusion:

```python
GroundTruthField(bt_code=..., raw_value=raw_str, normalized_value=None, xpath=..., is_present=True)
```

`is_present=True` + `normalized_value=None` is the scorer's EXCLUDED contract (ADR-045): the field counts as neither TP/FP/FN — it is removed from the metric, not scored as absent. A **positive** single rate (e.g. `19`) is unaffected and still scored normally; the multi-rate exclusion above is unchanged.

## Alternatives considered

- **Score the flat `0` literally** (status quo). Rejected: penalizes the honest "no positive rate" reading; rewards echoing a structural zero — the same ill-posedness ADR-045 already rejected for the multi-rate case.
- **Treat single-zero-rate `tax_rate` as ABSENT** (`is_present=False`). Rejected: ABSENT would score a model that emits `0` as a false positive, which over-corrects — the field is not "missing", it is "not meaningfully scoreable". EXCLUDED (neutral) is the honest treatment, consistent with ADR-045.
- **Drop the flat `tax_rate` field entirely** and rely only on `vat_breakdown`. Rejected (out of scope): the flat field is still meaningful and scored for single-positive-rate invoices (the common case); only the zero-rate degenerate case is ill-posed.

## Consequences (integration)

- **Consistent with ADR-045.** The flat `tax_rate` is now EXCLUDED for *all* ill-posed cases (multi-distinct-rate **and** single-zero-rate); scored only when there is exactly one positive rate to read.
- **Innergem.** The intra-community invoice's flat `tax_rate` is EXCLUDED rather than scored against `0`; the per-rate `0%` remains scored in `vat_breakdown`. (Note: the Innergem residual misses tracked in ADR-053 are line-item/reader-ceiling issues, independent of this fix.)
- **No effect on positive-rate invoices.** Single 19%/7% invoices score `tax_rate` exactly as before.
- **Tests.** `tests/test_schema.py` covers the single-zero-rate exclusion (a 0%-rate invoice → `tax_rate` EXCLUDED; a model that omits it scores EXCLUDED, not FN). Full gate green: 927 passed, ruff clean, mypy clean.

## Source archival

EN16931: BT-119 (VAT category rate, the document-level/line VAT percentage), BG-23 (VAT breakdown). Zero-rate German invoice renderings: "steuerfrei" (§4 UStG exemptions), "innergemeinschaftliche Lieferung" (§4 Nr. 1b / §6a UStG intra-community supply), "Reverse Charge" / "Steuerschuldnerschaft des Leistungsempfängers" (§13b UStG). The exclusion mechanism is the same neutral GT path archived under ADR-045.

## Supersession trigger

If a future scoring policy decides the flat `tax_rate` should report `0` for zero-rate invoices (e.g. a downstream consumer requires it), revert to scoring under this ADR. If the `vat_breakdown` group is ever removed (so the per-rate `0` is no longer captured elsewhere), reconsider whether the flat field must carry it. If a corpus appears with a single rate that is neither 0 nor a standard positive rate, revisit the exclusion condition.
