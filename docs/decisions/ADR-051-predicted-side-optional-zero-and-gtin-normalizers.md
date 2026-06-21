# ADR-051: Scoring fairness — predicted-side optional-zero totals + seller-assigned-id GTIN stripping

**Status**: Accepted
**Date**: 2026-06-21
**Refs**: ADR-043 (GT-side optional-zero totals), ADR-048 (the `FieldSpec.predicted_normalize` hook this reuses), ADR-050 (sibling predicted-side label-strip), ADR-013/027 (scorer + honesty contract), ADR-041 (full-coverage flat fields incl. the four optional totals), ADR-042 (repeating-group scoring incl. `seller_assigned_id`)

## Context (current-state survey)

Two systematic scoring artifacts surfaced in the per-field audit of the Arm-B structurer outputs (`scripts/inspect_arms.py --arm b`), both of the same class as the ADR-046/048/050 "as-printed-vs-as-stored" lineage: the model's output is faithful to the page, but a literal comparison against the canonical ground truth manufactures a false miss/spurious.

1. **Optional EN16931 totals echoed as a structural `0.00`.** ADR-043 established that the four optional document totals — `allowance_total_amount` (BT-107), `charge_total_amount` (BT-108), `prepaid_amount` (BT-113), `rounding_amount` (BT-114) — are conventionally **not rendered** on an invoice when zero, so the ground truth treats a structural `0.00` in the CII as **absent** (`is_present=False`). But the structuring model, prompted for these keys, sometimes emits `"0.00"` (a faithful reading of a zero subtotal, or a reasonable default). Scored literally, a predicted `0.00` against an absent GT is a **false positive** (precision artifact) — the model is penalized for honestly reporting zero on a field the GT rules as not-present.

2. **Line article number concatenated with its GTIN/EAN.** `seller_assigned_id` (BT-155, `field_type="CODE"`) is the seller's bare article id in the GT (`ram:SellerAssignedID`, e.g. `"PFA5"`). The model, reading the line, often appends the printed GTIN/EAN bar-code number with a marker — `"PFA5 4000001234578 (GTIN)"`. Scored literally, the faithfully-read article id is a **false negative** because of the appended bar code.

Both are representation mismatches, not comprehension errors: the model read the page correctly. The fix belongs on the **predicted-normalization** side (the ADR-048 hook), symmetric with the GT-side rule in ADR-043 — never on the model prompt (which would risk an honesty regression, cf. ADR-048's rejected prompt-guidance attempt) and never by loosening the scorer's equality (which would mask genuine errors).

## Decision

Add two predicted-side normalizers in `src/horus/eval/normalizers.py`, each wired through the existing `FieldSpec.predicted_normalize` hook (ADR-048) so the scorer applies them to the model's output before comparison. Both are **representation-only**: they never change a genuinely-wrong value into a right one.

1. **`_normalize_predicted_optional_zero_money(raw) -> str | None`** — for the four optional totals, a predicted `0` / `0.00` (after standard money normalization) returns `None` (absent), mirroring the GT-side ADR-043 convention. A non-zero predicted total is normalized as money and scored normally. Wired on the `FieldSpec` entries for `prepaid_amount`, `allowance_total_amount`, `charge_total_amount`, `rounding_amount` (each carries an inline `# ADR-051` comment next to `predicted_normalize=`).

2. **`_normalize_predicted_seller_assigned_id(raw) -> str | None`** — strips a trailing GTIN/EAN the model appended (a run of digits of EAN-8/12/13/14 length, optionally followed by a `(GTIN)`/`(EAN)` marker) so `"PFA5 4000001234578 (GTIN)"` → `"PFA5"`, then applies the standard predicted-CODE normalization. A bare article id with no appended bar code is unchanged; a value that is *only* a bar code is left as-is (it then scores against the GT honestly). Wired on the `seller_assigned_id` `FieldSpec` (line-item group cell).

## Alternatives considered

- **Loosen the scorer to treat any predicted `0.00` as absent globally.** Rejected: the *required* totals (BT-106/109/110/112/115) legitimately can be `0.00` in edge cases and must be scored; the absent-zero convention is specific to the four *optional* totals (ADR-043). A per-field normalizer keeps the rule where it belongs (the registry).
- **Fix it on the prompt** (tell the model "omit zero optional totals", "don't append the GTIN"). Rejected: ADR-048 measured that prompt-guidance perturbs the whole generation (spurious-emission blew up 0.071→0.357); a deterministic predicted-side normalizer is isolated and side-effect-free.
- **Substring-match the article id (accept a predicted value that contains the GT).** Rejected: substring matching is unsound for CODE fields (it would accept `"PFA5X"` for `"PFA5"`); explicit GTIN-suffix stripping is precise and auditable.

## Consequences (integration + measured result)

- **Representation-only, never masks errors.** A predicted optional total of `5.00` against a GT of `3.00` still scores FN/FP; a wrong article id still scores FN. The normalizers only collapse a known faithful-but-differently-formatted rendering onto the GT convention.
- **Symmetric with the GT side.** The optional-zero rule now reads identically on both sides of the comparison (ADR-043 GT-side; ADR-051 predicted-side), removing the asymmetry that caused the FP.
- **Closed-milestone baselines unaffected.** These four totals are outside the frozen 16-field `LEGACY_EXPERIMENT_FIELDS` (ADR-037); the regex baseline does not emit them. Predicted-normalization is a no-op when the field is absent.
- **Tests.** `tests/test_scorer.py` covers the predicted-side optional-zero rule (a predicted `0` on an optional total → absent, symmetric with ADR-043) and the `seller_assigned_id` GTIN stripping (a trailing EAN-13 + `(GTIN)` marker → bare article id). Full gate green: 927 passed, ruff clean, mypy clean.

## Source archival

EN16931 business terms: BT-107 (sum of allowances on document level), BT-108 (sum of charges on document level), BT-113 (paid amount), BT-114 (rounding amount), BT-155 (item seller's identifier). GTIN/EAN = GS1 Global Trade Item Number, the 8/12/13/14-digit bar-code identifier the article number is distinct from. The optional-zero rendering convention is the same one archived under ADR-043.

## Supersession trigger

If a future corpus legitimately renders one of the four optional totals as a printed `0.00` (so a model *should* report it), narrow the affected field's `predicted_normalize` (registry edit). If a model appends bar codes in a format the suffix stripper does not recognize (e.g. an unmarked GTIN of non-standard length), extend `_normalize_predicted_seller_assigned_id`. If the held-out Belege set shows a different article-id/bar-code rendering, revisit under this ADR.
