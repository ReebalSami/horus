# ADR-049: Registry-driven structurer field glossary (totals + buyer references)

**Status**: Accepted
**Date**: 2026-06-21
**Refs**: ADR-035 (InvoiceFields schema), ADR-038 (read-then-structure arms + `structurer.py`), ADR-041 (full-coverage flat fields incl. the 5 totals + BT-13/BT-46), ADR-042 (repeating-group scoring), ADR-048 (the rejected ad-hoc prompt-guidance attempt this ADR's measured result contrasts against), ADR-039 (live demo path that also consumes the prompt)

## Context (current-state survey)

The structuring model (Gemma, `adapter_mode="structurer"`, both arms) turns the reader transcript into the canonical JSON schema. Its prompt (`prompt_template_override` in `configs/arm-{a,b}.yaml`) carried the field list as a **bare comma-separated English key list** — `..., line_total_amount, tax_basis_total_amount, ..., buyer_reference, ..., buyer_order_reference, ...` — with no anchor to the **German labels printed on the page**. The English key names are the EN16931 business-term names; the page never shows them.

The per-field audit (`scripts/inspect_arms.py --arm b --non-tp-only`) and the saved transcripts showed two systematic **comprehension** errors (the model read the page correctly — the values are all present and correct in the Granite transcript — but filed them under the wrong key):

1. **The 5 document totals collapsed to a subtotal.** On `EN16931_Einfach` the model put the 19%-VAT-rate subtotal (`198,00`) into `line_total_amount`/`tax_basis_total_amount` etc., instead of the whole-document `Belegsummen` values (`473,00` net / `56,87` VAT / `529,87` gross). The fields affected: `line_total_amount` (BT-106), `tax_basis_total_amount` (BT-109), `tax_total_amount` (BT-110), `grand_total_amount` (BT-112), `due_payable_amount` (BT-115).
2. **`buyer_reference` ↔ `buyer_order_reference` swapped.** The buyer's customer number (`Nummer: GE2020211` in the Käufer block, BT-46 *Kundennummer*) was filed under `buyer_order_reference` (BT-13 *Bestellnummer*) and vice-versa.

Root cause: the prompt gave the model no way to map the German label it reads (`Bruttosumme`, `Kundennummer`, …) to the abstract English key it must emit (`grand_total_amount`, `buyer_reference`, …). For the confusable fields — where the English key does **not** obviously correspond to the printed German label — this is a guessing game the model loses consistently.

This is distinct from the ADR-043..048 ruler-fix lineage: those corrected the **scorer / ground truth** (the model was right, the ruler was wrong). Here the **model's assignment is genuinely wrong**, so the fix belongs on the **prompt** side — but it must be generic (no ground-truth values, no invoice-specific instructions) to avoid manufacturing a leak or a HARKing confound.

## Decision

Anchor each confusable field's English key to its meaning + its printed German labels, sourced from the `FIELDS` registry (single source of truth), and inject it into the structuring prompt at one substitution point.

1. **Extend `FieldSpec`** (`src/horus/eval/ground_truth.py`) with two optional attributes, both defaulting to `None`:
   - `description: str | None` — one generic sentence of field **semantics** (e.g. *"Total VAT amount for the whole invoice, summed across all VAT rates … NOT a single rate's VAT amount"*).
   - `prompt_aliases: tuple[str, ...] | None` — example German **label** names as printed (e.g. `("Steuerbetrag", "Umsatzsteuer gesamt")`).
   Both hold field semantics + label names only — **never a ground-truth value** — so the rendered guide is byte-identical for every invoice and every locale.

2. **Populate the 7 confusable fields**: the 5 totals + `buyer_reference` + `buyer_order_reference`. All other fields keep `None` (the bare key list already names them; the glossary stays focused).

3. **Render from the registry** (`src/horus/eval/structurer.py`):
   - `render_field_glossary()` emits one `- key: description (printed as: label / label)` line per `FIELDS` entry that carries a `description`. Open/closed: adding a `description` to any future `FieldSpec` auto-extends the guide; the renderer special-cases nothing.
   - `render_structuring_prompt(template)` fills a `{field_glossary}` placeholder via `str.replace` (NOT `str.format`, so the literal JSON braces elsewhere in the prompt survive verbatim). A no-op when the placeholder is absent — so the frozen regex baseline and the OCR/markdown `COHORT_MANIFEST` defaults pass through unchanged.

4. **One substitution point, all paths.** `build_structuring_input` calls `render_structuring_prompt` before appending the reader transcript, so Arm B (`run_arm_b`) and the live demo (`live.run_read_then_structure`) render identically. Arm A (the harness, `adapter_mode="structurer"`) renders the per-model prompt through the same function at the prompt-selection site.

5. **Configs** carry a `{field_glossary}` placeholder line right after the key list in `configs/arm-a.yaml` + `configs/arm-b.yaml`; the rendered `- key: …` lines read as additional bullets in the existing rule list.

The guide describes **what each field means** and **what German label to look for** — it never says what value to extract. The model still has to read the page.

## Alternatives considered

- **Ad-hoc prompt guidance (the ADR-048 rejected path).** ADR-048 measured that hand-written category-vocabulary guidance fixed its target field but perturbed the whole generation — flat spurious-emission jumped 0.071 → 0.357 (the model invented VAT rows). A free-text instruction blob is an uncontrolled confound. **This ADR's registry-driven, declarative, label-anchoring guide is the disciplined alternative** — and the measured result (below) confirms it does **not** reproduce that regression (spurious unchanged on 5/6, improved on 1).
- **Few-shot examples in the prompt.** Rejected: examples risk leaking ground-truth-shaped values and bias the model toward the example's layout; they also bloat the prompt and risk truncating the JSON.
- **A predicted-side scorer normalizer (ADR-048 `predicted_normalize` hook).** Rejected for this class: a totals-subtotal mix-up or a buyer/order swap is a genuine **assignment** error, not a representation difference — no deterministic post-hoc normalizer can recover which page value the model *should* have put in `grand_total_amount` once it emitted the wrong one. The fix has to happen before generation.
- **Hardcode the German labels into the structurer module.** Rejected: violates single-source-of-truth (the labels belong with the field definition in `FIELDS`) and `horus-config-discipline`; the registry already owns `german_label`, and `prompt_aliases` extends it with the display variants models actually see.

## Consequences (integration + measured result)

- **Generic + declarative + no leakage.** The guide is identical across all 6 dev invoices and would be identical on the held-out Belege set and English-locale invoices. A regression test (`test_render_field_glossary_carries_no_ground_truth_values`) fails loudly if any future `description` embeds a ground-truth value.
- **Measured before/after** on the 6-invoice dev cohort (`make arm-b CFG=configs/pilot-13.yaml,configs/arm-b.yaml`; prior run 2026-06-14 → fixed run 2026-06-21), flat `micro_f1` / `spurious_emission_rate`:

  | Invoice | micro_f1 | Δ | spurious | Δ |
  |---|---|---|---|---|
  | EN16931_Einfach | 0.788 → 0.919 | +0.131 | 0.071 → 0.071 | 0 |
  | EN16931_Gutschrift | 0.750 → 0.914 | +0.164 | 0.071 → 0.000 | −0.071 |
  | EN16931_Innergemeinschaftliche | 0.857 → 0.857 | 0 | 0.091 → 0.091 | 0 |
  | EN16931_Miete | 0.810 → 0.837 | +0.028 | 0.400 → 0.400 | 0 |
  | EN16931_Rabatte | 0.878 → 0.930 | +0.052 | 0.000 → 0.000 | 0 |
  | XRECHNUNG_Einfach | 0.857 → 0.957 | +0.099 | 0.000 → 0.000 | 0 |

  **micro_f1 improved on 5/6, never regressed; `spurious_emission` never increased (improved on 1).** Post-fix per-field audit confirms all 5 totals + `buyer_reference` score TP on every invoice. This is the empirical contrast to ADR-048's rejected prompt-guidance attempt.
- **Frozen closed-milestone baselines unaffected.** The regex baseline + OCR defaults carry no `{field_glossary}` token, so `render_structuring_prompt` is a no-op for them; ADR-037 `LEGACY_EXPERIMENT_FIELDS` reproductions are untouched.
- **Tests.** `tests/test_structurer.py` covers the renderer (confusable-field content, exclusion of undescribed fields, no-GT-leakage guard, registry-sourced open/closed property, token substitution, JSON-brace preservation, no-op without token, `build_structuring_input` end-to-end). `tests/test_ground_truth.py` covers the `FieldSpec` description/alias contract. Full gate green: 883 passed, ruff clean, mypy clean.
- **Residual (out of scope, model-ceiling).** The same audit surfaces pre-existing non-comprehension misses unrelated to this fix (the `invoice_number` "Nr." label prefix; `payment_means_code` SEPA→58 code mapping; `seller_assigned_id` GTIN concatenation; reader OCR slips like IBAN DE→DF; genuine model misses). These are tracked separately and are not regressions introduced here.

## Source archival

EN16931 business terms anchored by this guide: BT-106 (sum of line net amounts), BT-109 (tax basis total), BT-110 (tax total), BT-112 (grand total incl. VAT), BT-115 (amount due for payment), BT-46 (buyer reference / *Kundennummer*), BT-13 (purchase order reference / *Bestellnummer*). The German display labels (`Positionssumme` / `Rechnungssumme ohne USt.` / `Steuerbetrag` / `Bruttosumme` / `Zahlbetrag`, and the FeRD `Belegsummen` summary-block convention) are the standard renderings on German B2B invoices, consistent with the ADR-028 Belegsummen label set.

## Supersession trigger

If the held-out real Belege set (or an added locale) prints these fields with labels not in `prompt_aliases`, extend the relevant `FieldSpec.prompt_aliases` under this ADR (registry edit, no renderer change). If a future structurer is robust enough that the bare key list suffices (measured: removing the glossary leaves micro_f1 + spurious unchanged), the `{field_glossary}` placeholder may be retired from the configs — the renderer stays a harmless no-op. If another field proves confusable in the same way, add its `description` + `prompt_aliases` (the renderer picks it up automatically) rather than writing a new mechanism.
