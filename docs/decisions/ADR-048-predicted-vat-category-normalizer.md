# ADR-048: Scoring fairness — predicted-side `category_code` (BT-118) normalizer

**Status**: Accepted
**Date**: 2026-06-14
**Refs**: ADR-013/027 (scorer + field-type comparator dispatch), ADR-041 (VAT-breakdown group + category_code), ADR-042 (repeating-group scoring), ADR-046 (the same as-coded-vs-as-printed reasoning for `document_type`), ADR-043/045/047 (sibling ground-truth ruler fixes)

## Context

`vat_breakdown[*].category_code` (BT-118) is the EN16931 VAT-category code — a controlled vocabulary: `S` (standard), `Z` (zero-rated), `E` (exempt), `AE` (reverse charge), `K` (intra-community supply), `G` (export), `O` (out of scope), plus `L`/`M` (Canary Islands / Ceuta-Melilla). The GT side reads `ram:CategoryCode` verbatim → e.g. `"S"`. The predicted side, before this ADR, dispatched on `field_type="CODE"` → `_normalize_predicted_code`, which only NFC-strips.

The per-field audit (`scripts/inspect_arms.py`, both arms) showed `category_code` scoring **FN on every invoice**: the model emits `"Umsatzsteuer (S)"` (or, when re-prompted, the German word alone) and `_normalize_predicted_code("Umsatzsteuer (S)") != "S"`. Because each VAT-breakdown row has 4 cells, one guaranteed-FN cell capped every group's F1 (e.g. a perfect single-rate row scored 3/4). The code letter `S` is **never printed on the page** — the invoice renders "Umsatzsteuer 19 %". This is the same as-coded-vs-as-printed class ADR-046 fixed for `document_type` (page shows "Rechnung", not `380`): scoring the model's reading against a code it cannot see off the page manufactures a false negative.

## Decision

Make the comparison fair on the **predicted side**, deterministically, without changing the model:

1. Add an optional `FieldSpec.predicted_normalize: Callable[[str], str | None] | None = None` hook. When set, the scorer (`_score_against_spec`) uses it instead of the `field_type`-based predicted-normalizer dispatch. Open/closed registry extension — mirrors the existing GT-side `normalize` hook; no edit to the dispatch cascade for future fields.
2. Add `normalizers._normalize_predicted_vat_category`, which recovers the EN16931 code from the model's rendering, in priority order:
   - bare code already (`"S"`, `"ae"` → `"S"`, `"AE"`);
   - parenthesized code (`"Umsatzsteuer (S)"` → `"S"`);
   - German/English category phrase via a **specific-first** substring scan (`"reverse charge"`/`"Steuerschuldnerschaft des Leistungsempfängers"` → `AE`; `"innergemeinschaftliche Lieferung"` → `K`; `"steuerfrei"` → `E`; `"Umsatzsteuer"`/`"Regelsteuersatz"`/`"ermäßigter Steuersatz"` → `S`; …). Specific-first because a reverse-charge line also contains "Umsatzsteuer"; the haystack is `str.casefold()`ed (ß→ss) so the one ß-bearing key is stored in its ss form to match both spellings.
   - otherwise return the stripped string (honest: FN unless it equals the GT code).
3. Wire `VAT_BREAKDOWN_FIELDS["category_code"].predicted_normalize = _normalize_predicted_vat_category`.

The normalizer canonicalizes **representation only**. A model that names the *wrong* category in German maps to the wrong code and still scores FN — it never masks a real error.

## Alternatives considered

- **Prompt guidance (tell the model the category vocabulary + "output only the code").** Measured live on Arm B: it *did* fix `category_code` (model emitted `S`/`K` directly → all TP, several VAT groups to F1=1.000) — **but** it perturbed the model's whole generation, raising flat spurious-emission from 0.071 to 0.357 (e.g. `EN16931_Rabatte` invented 4 VAT rows vs the GT's 2). A ruler-correctness fix must not change model behavior or introduce a precision regression. Rejected as the *ruler* fix; it remains a legitimate, separately-measured model-improvement experiment. The deterministic normalizer achieves the same category_code fairness with zero behavioral confound and no re-inference.
- **GT-side: store the German word as the GT.** Rejected: the EN16931 code is the canonical, language-independent truth; the held-out English-locale set would need a parallel word list. Normalizing the prediction to the code space is cleaner and locale-independent.
- **Drop `category_code` from scoring.** Rejected: the VAT category is a real, gradable extraction target (it drives §13b reverse-charge and intra-community treatment); the field is fine — only the literal-code comparison was unfair.
- **Code-extraction only (no German synonym map).** Rejected as too strict: a model that correctly reads "Umsatzsteuer" but omits the parenthetical code would FN, even though it identified the category. The synonym map credits semantic correctness, which is what the field measures.

## Consequences

- Every VAT-breakdown row whose other cells match now scores `category_code` TP (the audit's universal FN is gone); group F1 reflects genuine extraction quality. No model re-run required — re-scoring existing saved outputs flips the cell to TP.
- Model behavior is unchanged (prompts reverted): flat spurious-emission stays at the honest baseline; no invented VAT rows.
- The new `predicted_normalize` hook is a general, reusable mechanism for any future controlled-vocabulary-but-not-printed field.
- Frozen closed-milestone baselines (ADR-037 `LEGACY_EXPERIMENT_FIELDS`, 16-field flat) are **unaffected** — `category_code` lives only in the opt-in `vat_breakdown` group (ADR-042), never in the flat 16/19/34 set.
- Regression tests cover the normalizer (bare/paren/synonym/specific-first/ß-spelling/unknown/empty) and the end-to-end group-scoring path (`"Umsatzsteuer (S)"` → TP against GT `"S"`).

## Source archival

EN16931 BT-118 (VAT category code) → UNTDID 5305 code list (`S`/`Z`/`E`/`AE`/`K`/`G`/`O`/`L`/`M`). German category phrasings ("Umsatzsteuer", "Steuerschuldnerschaft des Leistungsempfängers" = §13b reverse charge, "innergemeinschaftliche Lieferung" = §4 Nr. 1b intra-community supply, "steuerfrei") are the standard renderings on German B2B invoices.

## Supersession trigger

If the held-out real Belege set renders VAT categories with phrasings not in the synonym map (or in other locales beyond DE/EN), extend `_VAT_CATEGORY_SYNONYMS` under this ADR — keeping the specific-first ordering and never mapping an ambiguous phrase to a code it doesn't unambiguously denote. If a future model is deliberately prompted to emit codes (a measured model-improvement experiment), the normalizer remains a harmless safety net (bare codes pass straight through).
