# ADR-050: Scoring fairness — predicted-side `invoice_number` (BT-1) label stripping

**Status**: Accepted
**Date**: 2026-06-21
**Refs**: ADR-013/027 (scorer + field-type comparator dispatch), ADR-048 (the `FieldSpec.predicted_normalize` hook this reuses + the as-printed-vs-as-stored precedent), ADR-046 (same reasoning for `document_type`), ADR-041 (BT-1 in the full-coverage flat set), ADR-049 (the field-glossary fix this audit ran alongside)

## Context (current-state survey)

`invoice_number` (BT-1) is `field_type="CODE"`; the ground truth reads `ram:ID` verbatim → the bare identifier (e.g. `"471102"`). The predicted side, before this ADR, dispatched on `field_type="CODE"` → `_normalize_predicted_code`, which NFC-strips and removes internal whitespace only for country-code-prefixed codes (VAT IDs).

The post-ADR-049 per-field audit (`scripts/inspect_arms.py --arm b --non-tp-only`) showed `invoice_number` scoring **FN on 5 of the 6 dev invoices**. The cause is not a read miss — the model read the number correctly — but a **label echo**: the page prints the value next to its German label, and the structuring model transcribes both:

| Invoice | model `invoice_number` | GT `ram:ID` | outcome (before) |
|---|---|---|---|
| EN16931_Einfach | `Nr. 471102` | `471102` | FN |
| EN16931_Gutschrift | `Nr. 471102` | `471102` | FN |
| EN16931_Innergemeinschaftliche | `Nr. 47110818` | `47110818` | FN |
| EN16931_Rabatte | `Nr. 471102` | `471102` | FN |
| XRECHNUNG_Einfach | `Nr. 471102` | `471102` | FN |
| EN16931_Miete | `9314110911/00/M/00/N` | `9314110911/00/M/00/N` | TP (no label printed) |

Scoring `"Nr. 471102"` as `!= "471102"` manufactures a false negative over a label (`Nr.`) the model faithfully copied off the page — the same as-printed-vs-as-stored class ADR-046 fixed for `document_type` and ADR-048 fixed for `category_code`. (`EN16931_Miete` confirms the effect is layout-driven: its invoice prints no `Nr.` label, so the model emits the bare id and already scored TP.)

## Decision

Make the comparison fair on the **predicted side**, deterministically, without changing the model — reusing the ADR-048 mechanism:

1. Add `normalizers._normalize_predicted_invoice_number`, which:
   - NFC-strips the raw value;
   - strips a leading invoice-number **label** via `_INVOICE_NUMBER_LABEL_RE` — an optional qualifier word (`Rechnung`/`Rechnungs`/`Invoice`) + a label core (`nr`/`no`/`nummer`/`number`) + a **required separator run** (`[.:#]+` and/or whitespace);
   - applies the standard `_normalize_predicted_code` to the remainder.
2. Wire it on the registry: `FIELDS["invoice_number"].predicted_normalize = _normalize_predicted_invoice_number` (the open/closed hook from ADR-048; no scorer edit).

**The required-separator run is the safety guarantee.** A label is stripped only when a separator (`.`/`:`/`#` run and/or whitespace) follows the core letters — so a genuine identifier that merely *starts* with those letters survives untouched: `"NR-2024-001"` (next char `-`), `"INV-001"`, `"NO2024"` (run-on digit) are all unchanged. A bare-label echo (`"Nr."`) strips to empty and falls back to the un-stripped string (→ honest FN, never a spurious empty match).

The normalizer canonicalizes **representation only**. A model that reads the *wrong* number maps to the wrong bare id and still scores FN — it never masks a real error.

## Alternatives considered

- **Prompt guidance ("emit the number without the 'Nr.' label").** Rejected for the same reason ADR-048 rejected it: a free-text instruction perturbs the whole generation (ADR-048 measured flat spurious 0.071→0.357) and depends on model compliance. A deterministic predicted-side normalizer is confound-free, requires no re-inference, and is the established pattern.
- **GT-side: store the labelled form.** Rejected: `ram:ID` is the canonical identifier; the label is page chrome, not part of the id. Normalizing the prediction down to the id is locale-independent and matches the GT contract.
- **Generalize to all CODE fields.** Rejected as over-reach: only `invoice_number` exhibits the label echo in the cohort (the other CODE fields — VAT IDs, GLN, currency — scored TP). A field-specific hook is the minimal, auditable fix; if another CODE field later shows the same pattern, wire the same (or a shared) normalizer onto it under this ADR.
- **Strip on any whitespace after the core (no separator requirement).** Rejected as unsafe: it would eat the leading token of a genuine multi-token id. The required-separator run keeps real identifiers intact (regression-tested).

## Consequences (integration + measured result)

- **Offline rescore** of the saved Arm-B transcripts (no re-inference — a scorer-side change), flat `micro_f1`:

  | Invoice | before (post-ADR-049) | after | Δ |
  |---|---|---|---|
  | EN16931_Einfach | 0.919 | 0.947 | +0.029 |
  | EN16931_Gutschrift | 0.914 | 0.944 | +0.030 |
  | EN16931_Innergemeinschaftliche | 0.857 | 0.884 | +0.027 |
  | EN16931_Miete | 0.837 | 0.837 | 0 (already TP) |
  | EN16931_Rabatte | 0.930 | 0.955 | +0.024 |
  | XRECHNUNG_Einfach | 0.957 | 0.979 | +0.022 |

  All 5 affected invoices flip `invoice_number` FN→TP; Miete is untouched; no field regresses; `spurious_emission` is unchanged on every invoice (the fix touches no model output).
- **Frozen closed-milestone baselines unaffected.** This is a predicted-normalizer on a single field; the ADR-037 16-field reproductions compare the same canonical id (their saved scores already treated `invoice_number` as `CODE`; re-scoring only flips the labelled-echo cell, which those frozen runs did not exhibit at their published scope — and they are pinned regardless).
- **Tests** (`tests/test_scorer.py`): label-strip cases (`Nr.`/`No.`/`Rechnung Nr.`/`Rechnungsnr.:`/`Rechnungsnummer:`/`Invoice No.`, with/without period/space), the genuine-identifier safety set (`NR-2024-001`/`INV-001`/`NO2024`/slashed Miete id), empty→None, bare-label fallback, wrong-value-still-differs, and the registry-hook wiring. Full gate green: 901 passed, ruff clean, mypy clean.

## Source archival

EN16931 BT-1 (invoice number) = `rsm:ExchangedDocument/ram:ID`, the document's unique identifier. German invoices conventionally print it under the label `Rechnung Nr.` / `Rechnungsnr.` / `Rechnungsnummer` (English: `Invoice No.` / `Invoice Number`); the label is presentational and not part of the identifier, consistent with the EN16931 semantic model.

## Supersession trigger

If the held-out real Belege set (or another locale) prints the invoice number under a label not covered by `_INVOICE_NUMBER_LABEL_RE`, extend the regex's qualifier/core alternation under this ADR — preserving the required-separator-run guard so a genuine identifier is never eaten. If a future model stops echoing labels (measured: removing the hook leaves micro_f1 unchanged), the hook may be retired; it remains a harmless pass-through for already-bare ids. If another CODE field exhibits the same label echo, reuse this normalizer (or factor a shared label-strip helper) rather than adding a parallel mechanism.
