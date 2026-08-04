# Field prompt-surface audit (ADR-058)

**Date**: 2026-08-04
**Scope**: every `FieldSpec` in `horus.eval.ground_truth.FIELDS` — `german_label`,
`prompt_aliases`, `description`, and the normalizer pairing
**Grounding corpus**: 146 invoices with GT + cached transcript, canonical reader lineage
`Qwen/Qwen3-VL-4B-Instruct` (ADR-057)
**Reproduce**: `make audit-prompts` · `make glossary` ·
`uv run python scripts/check_oracle_transcript_labels.py <field> --outputs <dir>`

**Trigger**: `eval/per-field-reporting-audit.md` left three fields at 0.000 on the *oracle*
arm (perfect ground-truth-rendered text). A zero on perfect text is never a reading failure,
so the defect had to be in the GT, the normalizer, the field definition, or the prompt. The
audit was then widened on user challenge — *"I'm pretty sure a lot of misleading mistakes are
in the prompts of the fields"* — which was correct and surfaced contamination worse than the
three zeros.

---

## Method

The glossary is a set of empirical claims: each `prompt_alias` asserts *"invoices print this
label"*, and each `description` asserts *"this is how to recognise the field"*. Written from
memory, such claims rot silently. Two diagnostics replace belief with measurement:

| script | question it answers |
|---|---|
| `scripts/check_oracle_transcript_labels.py` | Was the value **in the input** the model saw, and what did the model emit? Separates GT/renderer bug from prompt gap from scorer bug. |
| `scripts/audit_field_prompts.py` | Does each label/alias literally occur in the corpus? Does any description contain a GT value (in **printed** form, not just canonical)? |
| `scripts/dump_field_glossary.py` | What exactly does the model read, with per-alias corpus hit counts? |
| `scripts/compare_eval_reports.py` | Field-by-field before/after between two eval reports. |

Both audit scripts load `configs/finetune-structurer.yaml` explicitly, because a bare
`FinetuneConfig()` silently selects the **superseded** granite-258M reader (see Finding 4).

---

## Finding 1 — the three zeros have three different causes

The single "sign mismatch" hypothesis in `per-field-reporting-audit.md` was **wrong**. Each
field failed for its own reason:

### BT-119 `tax_rate` — flat key left null while the table was filled

The structurer populated `vat_breakdown[].rate_percent` and left the flat `tax_rate` null;
the flat scalar reads as redundant once the table is emitted. **Fix**: deterministic
single-rate backfill from the model's own emission (ADR-058 (a)).

### BT-113 `prepaid_amount` — emitted signed, as printed

Grepping the saved generations:

```
data/finetune/zeroshot-outputs/zugferd_2p0_EN16931_Rabatte.txt        "prepaid_amount": -50.0
data/finetune/zeroshot-outputs/zugferd_2p1_EN16931_Rabatte.txt        "prepaid_amount": -50.0
data/finetune/zeroshot-qwen-outputs/zugferd_2p0_EN16931_Rabatte.txt   "prepaid_amount": -50.00
data/finetune/zeroshot-qwen-outputs/zugferd_2p0_EXTENDED_Fremdwaehrung.txt  "prepaid_amount": -500.00
```

GT is `50.00` / `500.00`. The model was right and scored FN. **Fix**: sign fold (ADR-058 (b)).

### BT-107 / BT-108 — invisible to the prompt, not to the reader

No arm ever emitted a negative for these. The oracle arm emitted `0.00` (14×) or `null`
(10×). `check_oracle_transcript_labels.py allowance_total_amount` on all 6 signal-bearing
invoices:

```
field   : allowance_total_amount  (BT-107)
label   : 'Summe Nachlässe'

  ZUGFeRD_1p0_EXTENDED_Kostenrechnung
     gt='21.55' printed_as='21,55 €'
     label_in_transcript=True  value_in_transcript=True
     model_emitted: "allowance_total_amount": null
  ... (6/6 identical pattern)
```

The value **was in the text**, and the model emitted `null` — because
`allowance_total_amount` was never explained in the prompt. This is a **glossary gap**, and
per ADR-048 a prompt-fixable gap must **not** be handed to a LoRA.

---

## Finding 2 — four ground-truth values leaked into the prompt

Glossary descriptions embedded literal "example" values that are verbatim GT for real
invoices — handing the model the answer and inflating those invoices' scores.

| field | leaked value | invoice | introduced by |
|---|---|---|---|
| `seller_vat_id` | `DE123456789` | `EN16931_1_Teilrechnung` | this branch's glossary extension |
| `seller_tax_id` | `201/113/40209` | `EN16931_1_Teilrechnung` | this branch's glossary extension |
| `payment_means_text` | `Überweisung` | `ZUGFeRD_1p0_COMFORT_Einfach` | this branch's glossary extension |
| `payment_means_text` | `bank transfer` | `MustangGnuaccountingBeispielRE-20201121_508` | **the fix for the previous row** |
| `billing_period_start` | `01.06.2018` (date-shaped) | — (no GT match, still removed) | this branch's glossary extension |

The fourth leak was introduced *while removing the third*, and was caught only after the
detector was strengthened to compare **printed variants** (`value_variants`) rather than only
ISO/canonical forms — a date written `01.06.2018` evades a comparison against `2018-06-01`.

**This class of contamination is trivially easy to reintroduce, so it is now gated, not
watched** — see *Gates* below.

---

## Finding 3 — 34 of 63 prompt aliases never occur in the corpus

Each was a false claim about what invoices print, costing prompt budget that ADR-048
measured as net-**negative** when spent on non-signal.

| field | present in | ungrounded (0/146) | corpus actually prints |
|---|---|---|---|
| `seller_vat_id` | 138/146 | `UID`, `VAT ID` | **`USt.-Id.-Nr` 91/146 — was missing**; listed `USt-IdNr.` hits 1 |
| `seller_tax_id` | 66/146 | `St.-Nr.`, `Steuer-Nr.` | `Steuernummer` 46, `Steuernr.` 4 |
| `seller_gln` | 65/146 | `ILN`, `GLN (Verkäufer)` | `GLN` 68, `Globale Nummer` 64 |
| `buyer_reference` | 76/146 | `Nummer (im Käufer-Block)` | `Kundennummer` 11, `Kunden-Nr.` 8 |
| `buyer_vat_id` | 44/146 | all 3 | `USt.-Id.-Nr` 91, `N° TVA client` 15, `Customer VAT Number` 4 |
| `line_total_amount` | 139/146 | `Summe der Nettobeträge` | `Positionssumme` 88, `Nettobetrag` 23 |
| `tax_basis_total_amount` | 145/146 | `Steuerlicher Bemessungsbetrag` | `Rechnungssumme ohne USt.` 88, `Net total` 10 |
| `tax_total_amount` | 146/146 | `Umsatzsteuer gesamt` | `Steuerbetrag` 90, `Total taxes` 15 |
| `grand_total_amount` | 146/146 | `Bruttobetrag` | `Bruttosumme` 89, `Gesamtbetrag` 99 |
| `tax_rate` | 115/146 | `Umsatzsteuersatz` | `Steuersatz` 27, `USt.` 108 |
| `buyer_order_reference` | 49/146 | `Auftragsnummer`, `Bestell-Nr.` | `Bestellung` 55, `Votre référence` 15 |
| `billing_period_start` | 21/146 | all 3 (`… Beginn/von`) | one range under `Abrechnungszeitraum` 13 |
| `billing_period_end` | 21/146 | all 3 (`… Ende/bis`) | same single heading |
| `payment_means_code` | 66/146 | `Zahlungsart (Code)`, `Zahlungsmittel-Code` | `Zahlungsart` 29 |
| `payment_means_text` | 32/146 | `Zahlungsweise`, `Zahlungsmittel` | `Zahlungsart` 29 |
| `seller_account_name` | 21/146 | `Konto lautend auf` | `Kontoinhaber` 12 |
| `payment_reference` | 48/146 | `Verwendungszweck` | `Referenz` 32, `Zahlungsreferenz` 7 |
| `prepaid_amount` | 31/146 | `Bereits gezahlt`, `Vorauszahlung` | `Anzahlung` 80 |
| `allowance_total_amount` | 26/146 | **`Summe Nachlässe`** | **`Gesamtbetrag der Abschläge` 88**, `Abschläge` 88 |
| `charge_total_amount` | 16/146 | **`Summe Zuschläge`** | **`Gesamtbetrag der Zuschläge` 88**, `Zuschläge` 88 |
| `rounding_amount` | 1/146 | all 3 | nothing |

The two fields that scored 0.000 were the two whose *only* German-label alias was the
EN16931-style name the corpus never prints. That is the mechanism behind Finding 1(c).

**After the fix**: 0 ungrounded aliases, 0 leaks. Glossary is 22 glossed fields / 34 total.

---

## Finding 4 — a bare `FinetuneConfig()` selects the superseded reader

`FinetuneConfig.reader_model` defaults to `ibm-granite/granite-docling-258M-mlx`, while
ADR-057 made `Qwen/Qwen3-VL-4B-Instruct` canonical — a fact recorded only in
`configs/finetune-structurer.yaml`. The first audit run therefore measured against the wrong
lineage (a weak reader makes genuinely-printed labels look ungrounded). Both new scripts now
load the canonical YAML and document why. **The stale default remains a live footgun for any
future script that constructs the config bare.**

---

## Finding 5 — the sign fold was asymmetric (bug found in this branch's own fix)

The initial implementation folded the sign on the **predicted side only**, on the stated
premise that "the GT side stores them unsigned". That premise is false:

```
zugferd_2p0_BASIC_Rechnungskorrektur   BT-107 gt='-0.23'
```

A credit note carries a negative allowance. A one-sided fold turns a correct `-0,23` into
`0.23` and scores it FN — the exact failure mode the fix existed to remove. **Fix**: fold on
both sides (`_normalize_nonneg_money` + `_normalize_predicted_nonneg_money`), scoped to
BT-107/108/113; BT-114 rounding stays signed.

Guarded by `test_nonneg_money_fold_is_two_sided` and `test_signed_totals_keep_their_sign`.

---

## Measured effect (Tier 1 — frozen generations)

Offline re-score via `scripts/finetune_evaluate.py --score-only`, so generations are
byte-identical and the delta is attributable to the scorer/normalizer changes alone:

| field | granite | qwen3-vl-4b | oracle |
|---|---|---|---|
| `tax_rate` | 0.182 → **0.778** | 0.182 → **0.900** | 0.000 → **0.952** |
| `prepaid_amount` | 0.000 → **0.750** | 0.333 → **0.750** | 0.750 → 0.750 |
| `allowance_total_amount` | 0.000 → 0.000 | 0.000 → 0.000 | 0.000 → 0.000 |
| `charge_total_amount` | 0.571 → 0.571 | 0.889 → 0.889 | 0.000 → 0.000 |
| **overall_micro_f1** | 0.6771 → **0.6856** | 0.8141 → **0.8189** | 0.9608 → **0.9676** |

`allowance_total_amount` / `charge_total_amount` cannot move here — their cause is the
prompt, and a prompt fix cannot change a frozen generation. **They are the Tier-2
measurement.**

---

## Gates added

| gate | scope | runs in |
|---|---|---|
| `test_glossary_descriptions_embed_no_concrete_identifiers` | blocks value-shaped strings (VAT-id / Steuernummer / IBAN / date / decimal-amount) in any description; corpus-free | `make test` |
| `make audit-prompts` | **fails** on any ungrounded alias or leaked GT value; corpus-backed | manual / pre-merge |
| `test_nonneg_money_fold_is_two_sided` | fold symmetry, incl. the real `-0.23` credit-note case | `make test` |
| `test_signed_totals_keep_their_sign` | fold stays scoped; required totals + BT-114 stay signed | `make test` |
| `test_tax_rate_*` (5 tests) | backfill fires on one rate, refuses on several, never overwrites | `make test` |

Import-time registry binding in `structurer.py` converts a future rename of `tax_rate` /
`vat_breakdown` / `rate_percent` from a silent no-op into a `RuntimeError`.

---

## Verification

```
make lint         All checks passed! · 148 files already formatted
make typecheck    Success: no issues found in 148 source files
make test         982 passed, 2 warnings
make audit-prompts  UNGROUNDED ALIASES: 0 · LEAKED GT VALUES: 0 · RESULT: PASS
```

---

## Open / deferred

1. **22 of 34 `german_label` values never occur in the corpus.** They are canonical EN16931
   terms used for reporting *and* by `render_oracle_transcript`, so the oracle arm presents
   labels real pages never print — a more synthetic upper bound than its docstring implies.
   Deferred because rewriting them re-baselines the oracle arm and would confound the Tier-2
   measurement. The LoRA gate uses real reader transcripts and is unaffected.
2. **`FinetuneConfig.reader_model` default is stale** (granite, vs ADR-057's Qwen3-VL-4B).
   Every caller that matters passes YAML, but the default is a trap.
3. **`rounding_amount` is untested** — present on 1/146 invoices, 0 signal-bearing outcomes
   on val, and no grounded label exists. Reported as untested rather than scored.
4. **Tier 2 not yet run.** BT-107/108 remain unmeasured until the three arms are
   re-generated with the corrected glossary.

## Next step

Re-generate all three arms with the corrected prompt, then re-evaluate the ADR-054 LoRA gate
(< 0.90 on the re-baselined zero-shot arm) against the *new* baseline. Handoff:
`docs/handoffs/structurer-regeneration-tier2.md`.
