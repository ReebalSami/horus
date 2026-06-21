# ADR-047: Ground-truth completeness — free-text payment-terms fallback (net due date + Skonto)

**Status**: Accepted
**Date**: 2026-06-14
**Refs**: ADR-041 (BT-9 + Skonto group added), ADR-042 (repeating-group scoring), ADR-013/027 (scorer + honesty), ADR-043/045/046 (sibling ground-truth ruler fixes), ADR-035 (`validate_and_repair` normalizers)

## Context

`payment_due_date` (BT-9) is parsed from the structured `SpecifiedTradePaymentTerms/ram:DueDateDateTime`, and the Skonto group from the structured `ApplicableTradePaymentDiscountTerms`. The per-field audit (`scripts/inspect_arms.py`) plus direct CII inspection showed that the synthetic ZUGFeRD corpus carries **neither** structurally for most invoices — both live in the free-text `SpecifiedTradePaymentTerms/ram:Description`, e.g.:

> `Zahlbar innerhalb 30 Tagen netto bis 04.07.2018, 3% Skonto innerhalb 10 Tagen bis 15.06.2018`

Verified across the dev set: 5/6 invoices have `DueDateDateTime` count = 0 and `ApplicableTradePaymentDiscountTerms` count = 0, while 3 carry an explicit net-due-date + Skonto in the Description. The Skonto group comment in `ground_truth.py` already flagged this "structured-text fallback" as a documented follow-up.

Consequence for a **visual** extraction task: the page renders the due date and the Skonto, so a model that correctly reads them was scored **FP** (a precision/spurious-rate artifact), while a model that **missed** them was rewarded with a silent TN. Concretely, Arm-B `EN16931_Rabatte` `payment_due_date`=`2018-07-04` (the model read the net due date correctly) scored FP; `XRECHNUNG_Einfach` Skonto (`3% / 10 Tagen`, read correctly) scored FP. Rewarding misses and punishing correct reads inverts the metric — a broken ruler (cf. ADR-043/045/046).

## Decision

In `parse_cii_xml`, after the structured parse, add a **conservative free-text fallback** over `SpecifiedTradePaymentTerms/ram:Description`, applied **only** when the corresponding structured field is absent (structured data always wins):

1. **Net due date (BT-9)** — regex `netto\s+bis\s+(DD)\.(MM)\.(YYYY)` (case-insensitive). Matches the explicit *net* due phrasing only, so the Skonto deadline date is never mistaken for the due date. The captured date is validated via `datetime.date` (an impossible date → no GT, never a guess) and emitted as ISO `YYYY-MM-DD`.
2. **Skonto tiers** — regex `(\d+(?:[.,]\d+)?)\s*%\s*Skonto\s+innerhalb\s+(\d+)\s*Tagen` via `finditer` (one row per tier). `percent` is German-locale-canonicalized (comma→dot) then run through the same `_normalize_rate` as the structured path; `days` through `_normalize_string`; `basis_amount` is honest-absent (free text carries no basis). Rows match the `SKONTO_FIELDS` shape so scoring is route-identical.

Both patterns are deliberately narrow: a Description that does not match leaves the field **absent** — the fallback never fabricates a GT value. The structured route is unchanged and authoritative.

## Alternatives considered

- **Leave the GT structured-only.** Rejected: it systematically inverts the metric (rewards missing a printed field, punishes reading it). Directly contradicts the visual-extraction premise.
- **Mark BT-9 / Skonto EXCLUDED when only free-text exists.** Neutral and zero-risk, but discards real signal — a model that correctly reads "netto bis 04.07.2018" deserves credit, and one that hallucinates a due date deserves a penalty. Rejected in favour of the stronger, verifiable parse.
- **Adopt a general payment-terms NLP parser / LLM.** Rejected: over-engineered, non-deterministic, and a GT must be deterministic + auditable. The templated German phrasing is a bounded regex problem.
- **Broaden the due-date regex (e.g. any `bis DATE`).** Rejected: it would grab the Skonto deadline date as the due date. The `netto bis` anchor is the safe, unambiguous signal; non-standard phrasings stay absent (extensible later if a real invoice needs it).

## Consequences

- `EN16931_Rabatte` `payment_due_date` FP → **TP** (spurious_emission_rate 0.091 → 0.000); `XRECHNUNG_Einfach` Skonto FP → **TP** (group F1 → 1.000). Conversely, invoices where the model *missed* a now-present field correctly flip TN → FN (e.g. `EN16931_Rabatte` Skonto), so recall honestly reflects the miss.
- The metric now measures the visual extraction task faithfully on payment terms.
- Frozen closed-milestone baselines (ADR-037 `LEGACY_EXPERIMENT_FIELDS`, 16-field) are **unaffected** — neither BT-9 nor Skonto is in that set; the Skonto group is opt-in via `score(predicted_groups=...)`.
- Full suite green (no existing test asserted these corpus fields were absent), plus new regression tests: helper-level (`netto bis` match / no-match / invalid-date / single+multi-tier Skonto with comma decimals), end-to-end via `parse_cii_xml`, and a **structured-wins-over-free-text** guard.

## Source archival

EN16931 BT-9 (Payment due date) and the Skonto (Skontovereinbarung) convention; ZUGFeRD/Factur-X carry Skonto either structurally (`ApplicableTradePaymentDiscountTerms`) or, per the FeRD structured-text convention, inside the payment-terms `Description`. The corpus Descriptions parsed here are the canonical German templated phrasings.

## Supersession trigger

If a future corpus / the held-out real Belege set uses payment-terms phrasings the conservative regexes don't cover (e.g. `fällig am …`, English `due net 30`, multi-line tables), extend the patterns under this ADR — but never at the cost of fabricating a GT from an ambiguous match. If a structured-decoding GT source becomes available, prefer it and demote the free-text fallback.
