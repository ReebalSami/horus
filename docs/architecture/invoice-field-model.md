# Invoice field model — full-coverage extraction schema

> **Status:** draft for approval · **Author:** Cascade (schema-extension thinking session) ·
> **Date:** 2026-06-13 · **Ratified by:** ADR-041 (schema design) + ADR-042 (line-item
> scoring, authored at Step 2).
>
> This is the **living checklist** of every field HORUS extracts from a German B2B
> invoice, plus the data shapes and the exact places in the code that change when the
> field set grows. It is the user-approved foundation the decision record and the coding
> handoffs build on. Field names, German labels, and the existing 19-field rows are
> grounded in `src/horus/eval/ground_truth.py`; the business-term codes are EN16931
> (archived at `docs/sources/legal/zugferd-en16931.md`).

---

## 1. Why this exists

Today the tool is scored on **19 fields**. A real invoice carries far more. Reporting an
F1 score over only 19 fields is not an honest statement about the tool's ability — it
silently ignores everything it was never asked to read. This document defines the
**full** field universe so the score finally describes the whole job.

Scope (locked with the user): the **invoice family** — commercial invoice, credit note
(*Gutschrift*), correction / cancellation (*Korrektur / Storno*). These share one field
set. Till receipts (*Kassenbon*) and hospitality receipts (*Bewirtungsbeleg*) are a
separate schema for later, if ever needed.

---

## 2. The honesty contract (applies to every field)

1. **On-document only.** A field is captured only when its value is actually present on
   the document (or in the invoice's embedded XML). We never infer a value the document
   does not show.
2. **Honest null.** Absent field → blank / `null`. A generative model must never invent a
   value (the tax-domain guardrail). This mirrors the existing present/absent/empty
   tristate in `ground_truth.py`.
3. **Values as printed, keys canonical.** Field *keys* are canonical English/EN16931;
   *values* are as printed in any language. No German-keyword matching on the critical
   path — this is what keeps the multilingual held-out evaluation valid.

---

## 3. Two kinds of fields (this is the core design distinction)

- **Flat single-value fields** — one value per invoice (e.g. invoice number, IBAN, due
  date). These slot into the existing field machinery (`FIELDS` registry). **Cheap and
  low-risk.** All of Step 1's scalars are this kind.
- **Repeating groups** — a *list* of rows per invoice. There are three:
  - **VAT breakdown** (one row per tax rate) — **Step 1**; row alignment is trivial
    (match by the rate value), so it is the low-risk place to build the repeating-group
    machinery.
  - **Skonto tiers** (early-payment discount; usually one row, sometimes two) — **Step 1**;
    alignment trivial (by due date / order).
  - **Line items** (the product/service table) — **Step 2**; alignment is the one hard
    problem (see §7), handled by smart content matching.

Repeating groups do **not** fit the flat `FIELDS` dict. They get their own container
structures on both the ground-truth side and the prediction side, and their own scoring.

---

## 4. Step 1 — flat single-value fields

Legend — **field_type** drives the scorer's comparison (already implemented):
`CODE` exact match · `STRING` fuzzy (ANLS\*, OCR-tolerant) · `MONEY` exact 2-dp ·
`DATE` exact ISO · `RATE` exact numeric percent. **group** is the scorer/display group.

### 4.1 Already covered (19 — for reference, unchanged)

| key | German | EN16931 | type | group |
|---|---|---|---|---|
| `invoice_number` | Rechnungsnummer | BT-1 | CODE | document |
| `issue_date` | Rechnungsdatum | BT-2 | DATE | document |
| `invoice_currency_code` | Währung | BT-5 | CODE | document |
| `delivery_date` | Liefer-/Leistungsdatum | BT-72 | DATE | document |
| `tax_rate` | Umsatzsteuersatz (Standardsatz) | BT-119 (first) | RATE | document |
| `seller_name` | Verkäufer | BT-27 | STRING | seller |
| `seller_address` | Anschrift (Verkäufer) | BG-5 | STRING | seller |
| `seller_vat_id` | USt-IdNr. (Verkäufer) | BT-31 | CODE | seller |
| `seller_tax_id` | Steuernummer | BT-32 | CODE | seller |
| `seller_gln` | GLN (Verkäufer) | BT-29 | CODE | seller |
| `buyer_name` | Käufer | BT-44 | STRING | buyer |
| `buyer_address` | Anschrift (Käufer) | BG-8 | STRING | buyer |
| `buyer_vat_id` | USt-IdNr. (Käufer) | BT-48 | CODE | buyer |
| `buyer_reference` | Kundennummer | BT-46 | CODE | buyer |
| `line_total_amount` | Summe Nettobeträge | BT-106 | MONEY | totals |
| `tax_basis_total_amount` | Steuerlicher Bemessungsbetrag | BT-109 | MONEY | totals |
| `tax_total_amount` | Umsatzsteuer gesamt | BT-110 | MONEY | totals |
| `grand_total_amount` | Bruttobetrag | BT-112 | MONEY | totals |
| `due_payable_amount` | Zahlbetrag | BT-115 | MONEY | totals |

### 4.2 New flat fields (Step 1)

| key | German | EN16931 | type | group | CII element family | notes |
|---|---|---|---|---|---|---|
| `document_type` | Belegart | BT-3 | CODE | document | `ExchangedDocument/ram:TypeCode` | EN16931 code: 380 invoice / 381 credit note / 384 correction / 389 self-billed. Build-time: store the code vs a canonical label — decide (see §9). Hand-draft: dropdown. |
| `buyer_order_reference` | Bestellnummer | BT-13 | CODE | document | `…HeaderTradeAgreement/ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID` | purchase-order number. |
| `billing_period_start` | Abrechnungszeitraum Beginn | BT-73 | DATE | document | `…HeaderTradeSettlement/ram:BillingSpecifiedPeriod/ram:StartDateTime/udt:DateTimeString` | optional; present on recurring invoices. |
| `billing_period_end` | Abrechnungszeitraum Ende | BT-74 | DATE | document | `…/ram:BillingSpecifiedPeriod/ram:EndDateTime/udt:DateTimeString` | optional. |
| `payment_due_date` | Fälligkeitsdatum (Zahlungsziel) | BT-9 | DATE | payment | `…HeaderTradeSettlement/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString` | the date payment is due. |
| `payment_means_code` | Zahlungsart (Code) | BT-81 | CODE | payment | `…/ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode` | UN/ECE 4461: 58 SEPA credit transfer / 59 SEPA direct debit / 30 credit transfer / 48 card / 10 cash / 97 clearing. |
| `payment_means_text` | Zahlungsart (Text) | BT-82 | STRING | payment | `…/ram:SpecifiedTradeSettlementPaymentMeans/ram:Information` | free text — captures "PayPal", "Überweisung", "bar" when the code does not. |
| `payment_status` | Zahlungsstatus | (derived) | CODE | payment | derived | controlled vocab `paid` / `partially_paid` / `open`. XML route: derive from prepaid vs due amount. Hand-draft: dropdown. See §9. |
| `seller_iban` | IBAN (Zahlungsempfänger) | BT-84 | CODE | payment | `…/ram:SpecifiedTradeSettlementPaymentMeans/ram:PayeePartyCreditorFinancialAccount/ram:IBANID` | exact match (legal account number). |
| `seller_bic` | BIC | BT-86 | CODE | payment | `…/ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID` | |
| `seller_account_name` | Kontoinhaber | BT-85 | STRING | payment | `…/ram:PayeePartyCreditorFinancialAccount/ram:AccountName` | |
| `payment_reference` | Verwendungszweck | BT-83 | STRING | payment | `…HeaderTradeSettlement/ram:PaymentReference` | remittance info / structured reference. |
| `prepaid_amount` | Bereits gezahlt | BT-113 | MONEY | totals | `…SpecifiedTradeSettlementHeaderMonetarySummation/ram:TotalPrepaidAmount` | already-paid amount. |
| `allowance_total_amount` | Summe Nachlässe | BT-107 | MONEY | totals | `…HeaderMonetarySummation/ram:AllowanceTotalAmount` | document-level discounts. |
| `charge_total_amount` | Summe Zuschläge | BT-108 | MONEY | totals | `…HeaderMonetarySummation/ram:ChargeTotalAmount` | document-level surcharges. |
| `rounding_amount` | Rundungsbetrag | BT-114 | MONEY | totals | `…HeaderMonetarySummation/ram:RoundingAmount` | |

> **Exact leaf XPaths to be verified at build time** against a real corpus fixture
> (`factur-x` extraction of a ZUGFeRD invoice that carries each field). The BT codes and
> element families above are correct; the precise path strings get pinned + tested before
> they are trusted, exactly as the existing 19 were.

### 4.3 Step 1 — VAT breakdown (repeating group, simple alignment)

One row per VAT rate (an invoice with 19 % + 7 % has two rows). Source: each
`…HeaderTradeSettlement/ram:ApplicableTradeTax` element.

| sub-field | German | EN16931 | type |
|---|---|---|---|
| `category_code` | Steuerkategorie | BT-118 | CODE (S/Z/E/AE/K/G/O/L/M) |
| `rate_percent` | Steuersatz | BT-119 | RATE |
| `taxable_amount` | Bemessungsgrundlage | BT-116 | MONEY |
| `tax_amount` | Steuerbetrag | BT-117 | MONEY |

**Scoring:** rows aligned by `rate_percent` (a natural key); then each cell scored like a
flat field. A missing rate row hurts recall; an invented one hurts precision. The flat
`tax_rate` / `tax_basis_total_amount` / `tax_total_amount` summaries **stay** (frozen,
single-rate view); this breakdown is additive detail.

### 4.4 Step 1 — Skonto tiers (repeating group, small)

Early-payment discount. Usually one tier, sometimes two ("3 % in 7 days, 2 % in 14 days").

| sub-field | German | type |
|---|---|---|
| `percent` | Skonto-Prozentsatz | RATE |
| `due_date` | Skonto-Zahlungsziel | DATE |
| `days` | Skonto-Tage | numeric (build-time type) |
| `amount` | Skonto-Betrag | MONEY (when stated) |

> **Build-time note:** in ZUGFeRD, Skonto lives either in
> `ram:SpecifiedTradePaymentTerms/ram:ApplicableTradePaymentDiscountTerms` (structured) or
> as a FeRD-convention structured string inside the terms `ram:Description`
> (`#SKONTO#TAGE=14#PROZENT=2.00#`). The parser must handle both. Alignment by `due_date`
> (or tier order).

---

## 5. Step 2 — line-item table (repeating group, hard alignment)

One row per product/service line. Source: each
`…SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem`.

| sub-field | German | EN16931 | type |
|---|---|---|---|
| `line_id` | Position | BT-126 | CODE |
| `article_number` | Artikelnummer | BT-155 | CODE |
| `description` | Beschreibung | BT-153 | STRING |
| `quantity` | Menge | BT-129 | numeric (build-time type) |
| `unit_code` | Einheit | BT-130 | CODE (UN/ECE Rec 20, e.g. C62/HUR/KGM) |
| `unit_price` | Einzelpreis (netto) | BT-146 | MONEY |
| `line_net_amount` | Zeilensumme (netto) | BT-131 | MONEY |
| `line_vat_rate` | Steuersatz (Zeile) | BT-152 | RATE |

**Scoring (ADR-042, smart content matching):** pair each predicted row with the true row
it most resembles (description + amounts), independent of order; use `line_id` /
`article_number` as a tie-breaker when present. Then score each cell within matched rows.
Missed rows hurt recall; invented rows hurt precision. This is the accepted standard for
line-item recognition (DocILE LIR / maximum-weight bipartite matching; the project already
cites the DocILE-aligned arXiv 2510.15727). The exact matching algorithm + how the
line-item score folds into the overall number is decided in ADR-042 at Step 2 start.

---

## 6. The places that change (touchpoint map)

Confirmed against the code. For **each new flat field**, all of these change together —
three of them have **import-time asserts that crash** if they disagree (a useful guard):

| # | File | What changes | Guard |
|---|---|---|---|
| 1 | `src/horus/eval/ground_truth.py` | add a `FieldSpec` row to `FIELDS` (key, BT, German, XPath, normalizer, type) | `FIELDS_V1` auto-derives; absent-in-v1 → honest `is_present=False` |
| 2 | `src/horus/eval/normalizers.py` | add a prediction-side normalizer **only if** a new `field_type` is introduced (the Step 1 scalars all reuse existing types) | — |
| 3 | `src/horus/eval/schema.py` | add the field to the `InvoiceFields` Pydantic model (the `_coerce_one` dispatch already covers existing types) | `to_scored_dict` iterates `FIELDS` |
| 4 | `src/horus/eval/scorer.py` | add the key to `FIELD_GROUPS[<group>]` or `DOCUMENT_FIELDS` | **assert** `FIELD_GROUPS ∪ DOCUMENT_FIELDS == FIELDS` |
| 5 | `app/data/fields.py` | add to `LABELS` + `FIELD_ORDER` | **assert** `set(FIELD_ORDER) == partition` |
| 6 | `src/horus/eval/ground_truth.py` | **rework the frozen-16 set** (see §8) | **assert** `len == 16` |
| 7 | `configs/arm-a.yaml` / `arm-b.yaml` | extend the structurer prompt to request the new fields | — |
| 8 | `tests/` | add reading + normalization + scoring tests per field | CI |

Adding a **new scorer/display group** (`payment`) also touches `FIELD_GROUPS`,
`GROUP_DISPLAY`, and the held-out review page's group list.

For **repeating groups** (VAT breakdown, Skonto, line items) the changes are different:
they get **new container types** (not `FIELDS` rows), so they do **not** touch the flat
partition asserts. They need:

- a `…GT` dataclass + an optional `list[…]` field on `GroundTruth` (the line-item hook
  already documented there), and XML parsing of the repeating element;
- a `list[…]` submodel on `InvoiceFields` (the before-validator must stop dropping nested
  lists — it currently ignores them);
- a new scoring path in `scorer.py`;
- the `gt_document` JSON shape in `heldout.py` must carry the list (the hand-draft route);
- a variable-length entry grid on the review page (today it is a fixed list of single
  boxes).

---

## 7. The two answer-key routes (one shape)

- **Synthetic ZUGFeRD invoices:** answers read automatically from the embedded XML
  (`parse_cii_xml`). New flat fields = add the XPath; repeating groups = parse the
  repeating element.
- **The 39 real Belege:** answers filled in by hand on the review page; saved as JSON
  under the git-ignored private tree. New flat fields appear automatically (the page
  iterates the field order); repeating groups need the new entry grid + the JSON shape.

Both routes produce the identical `GroundTruth` shape so the scorer cannot tell them
apart.

---

## 8. Frozen-baseline rework (must-do in Step 1)

The set that keeps closed-milestone published numbers frozen at 16 fields is currently
**subtractive** (`FIELDS` minus the 3 later additions, `assert len == 16`). The moment
`FIELDS` grows, that assert breaks. Rework it to an **explicit positive list** of the 16
original keys:

```python
_LEGACY_16_KEYS = frozenset({ ... the 16 original keys ... })
LEGACY_EXPERIMENT_FIELDS = {k: FIELDS[k] for k in _LEGACY_16_KEYS}
assert len(LEGACY_EXPERIMENT_FIELDS) == 16
```

No new freeze snapshot is needed for the larger schema: **nothing has been scored at 19
or more fields yet** (the held-out run has not happened), so no published number can
shift. New work always scores the full current `FIELDS`.

---

## 9. Build-time decisions to finalize (small, recorded in ADR-041)

- **Document type representation** — store the EN16931 numeric code (`380`/`381`/`384`)
  vs a canonical label (`invoice`/`credit_note`/`correction`). Recommendation: canonical
  label (readable for hand-drafting + display), with the XML route mapping the code.
- **Quantity / Skonto-days numeric type** — quantities can be fractional and unit-less, so
  the 2-dp money normalizer is wrong. Add a light `NUMBER` type or reuse a decimal
  normalizer without currency quantization. Decide + test.
- **Unit representation** — store the UN/ECE unit code (`HUR`) vs the printed unit
  (`Std.`/`hours`). Recommendation: the printed unit as `STRING` for the hand-route's
  honesty, with the code captured from XML when present.
- **Exact CII leaf XPaths** for every §4.2 field — pin + test against a corpus fixture.

---

## 10. Scientific-correctness notes

- **No goalpost-moving.** The held-out 39 have not been scored (answer keys not even
  verified). Extending the schema now changes no reported number. We lock the schema
  first, then score the held-out set once per approach.
- **Practice vs final stays separate.** Prompts/extraction tuned on the synthetic practice
  invoices; the 39 real invoices scored once, after the schema is final.
- **Legal-importance weights carried, not locked.** Each field can carry an optional
  legal-importance level (the thesis draft tiers), but the reported F1 stays **unweighted**
  until the supervisor signs off on a weighting. The weight is metadata, not yet a metric.

---

## 11. Provenance

- Plan: `~/.windsurf/plans/horus-invoice-schema-full-coverage-68a4ac.md`
- Grounded in: `src/horus/eval/ground_truth.py`, `schema.py`, `scorer.py`,
  `app/data/fields.py`, `heldout.py`, the held-out datasheet.
- Standard: EN16931 / ZUGFeRD-Factur-X (`docs/sources/legal/zugferd-en16931.md`).
- Prior schema decisions: the original 16-field contract, the 16→19 extension, the
  forward-only scoring-scope freeze, and the held-out-set methodology
  (ADR-012 / ADR-035 / ADR-037 / ADR-040).
