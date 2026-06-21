# ADR-046: Ground-truth validity — `document_type` code map covers the full EN16931 invoice family

**Status**: Accepted
**Date**: 2026-06-14
**Refs**: ADR-035 (`document_type` added), ADR-041 (full-coverage schema), ADR-013/027 (scorer + CODE field type), ADR-043/045 (sibling ground-truth ruler fixes)

## Context

`document_type` (BT-3) is a CODE field. The GT side maps the CII `ExchangedDocument/ram:TypeCode` (a UNTDID-1001 numeric code) to a coarse HORUS token via `_normalize_doctype` → `_DOCTYPE_CODE_TO_TOKEN`; the prediction side emits the token directly (the structurer prompt constrains output to `{invoice, credit_note, correction}`). The original map covered only `{380→invoice, 389→invoice, 381→credit_note, 384→correction}`.

The per-field audit (`scripts/inspect_arms.py`, Arm B dev set) surfaced `EN16931_Miete` scoring `document_type` **FN**: GT=`387`, predicted=`invoice`. `387` is the UNTDID-1001 code for a **hire invoice** (a rental invoice — exactly a car-rental Miete). Because `387` was unmapped, `_normalize_doctype("387")` fell through to the raw-passthrough branch and returned `"387"`, which never matches the model's correct `"invoice"`. The page renders the German word "Rechnung" (or a generic invoice layout); the numeric subtype code is **never printed**, so the model cannot — and should not be expected to — discriminate `387` from `380`. The model read "invoice" correctly; the GT normalizer manufactured a false negative. This is a broken ruler (cf. ADR-043/045), not a model weakness.

## Decision

Extend `_DOCTYPE_CODE_TO_TOKEN` to the full EN16931 / UNTDID-1001 invoice family, mapping every "this is an invoice document" subtype to `invoice`, the credit-note subtypes to `credit_note`, and the correction subtype to `correction`:

- `invoice`: 380 (commercial), 386 (prepayment), 387 (hire/rental), 388 (tax), 389 (self-billed), 393 (factored), 395 (consignment)
- `credit_note`: 381, 396 (factored credit note)
- `correction`: 384

An out-of-family code still passes through stripped (honest present-but-unmapped, never silently dropped), preserving the existing contract.

## Alternatives considered

- **Add only `387`.** Fixes the observed case but leaves the same latent FN for every other invoice-family subtype (388 tax, 393 factored, …). Rejected: the audit revealed a class of bug, not a single instance; a complete family map is the principled fix and is no riskier.
- **Score `document_type` against the raw numeric code.** Rejected: the code is never on the page; it would measure the model's knowledge of UNTDID-1001 sub-typing, not its reading — exactly the as-coded-vs-as-printed error ADR-043 warns against.
- **Drop `document_type` from scoring.** Rejected: the coarse class (invoice vs credit note vs correction) IS visually determinable ("Rechnung" vs "Gutschrift") and is a useful, fair target.

## Consequences

- `EN16931_Miete` `document_type` becomes TP; no model behaviour changed (the model already emitted `invoice`).
- The map now reflects the EN16931 invoice family, so future corpus/held-out invoices using any common subtype score correctly without further edits.
- Frozen closed-milestone baselines (ADR-037 `LEGACY_EXPERIMENT_FIELDS`, 16-field) are **unaffected** — `document_type` is not in that set.
- Regression test `test_doctype_invoice_family_maps_to_token` pins every family code → token; `test_doctype_unknown_code_passes_through` pins the honest-passthrough contract.

## Source archival

UNTDID-1001 (UN/EDIFACT Document/message name code list) invoice-family subtypes; EN16931 BT-3 references this code list for the invoice type code. The mapping is the standard coarse-classification used across e-invoicing tooling (e.g. Mustang / Factur-X type-code handling).

## Supersession trigger

If HORUS later needs to distinguish invoice subtypes (e.g. report "prepayment invoice" vs "commercial invoice" as separate classes), this coarse family-collapse must be revisited — the schema would need a finer `document_subtype` field, and `_normalize_doctype` would no longer collapse the family.
