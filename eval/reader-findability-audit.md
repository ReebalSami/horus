# Reader findability audit — manual judge pass over every val miss (#114)

**Method**: after the ADR-056 ruler fix, the winner candidate (olmOCR-2-7B) still showed
52 "missing" GT values across the 29 sealed val invoices (17/29 invoices already at
1.00). Each of the 52 was judged **by hand** against the rasterized page image
(`data/raw/smoke/multipage/<stem>/`) and both finalists' transcripts
(`data/finetune/bakeoff/`). Classification:

- **R** — real reader miss (value printed on the page; transcript lacks it)
- **V** — ruler variant gap (value printed AND transcribed; ruler failed to match)
- **P** — value NOT findable on the page (not printed / XML-vs-page contradiction /
  degenerate or invalid GT) — no vision system can extract these

## Verdict table (52 misses)

| invoice | field | GT value | judged | evidence |
|---|---|---|---|---|
| Mustang…505 | seller_vat_id | DE136695976 | **R** (olmOCR) | printed in footer "USt-ID:…"; olmOCR transcript has NO footer block; Qwen read it |
| Mustang…505 | seller_iban | DE88 2008 … | **R** (olmOCR) | printed compact in footer; olmOCR dropped footer |
| Mustang…505 | seller_bic | COBADEFFXXX | **R** (olmOCR) | printed in footer; olmOCR dropped footer |
| Mustang…505 | seller_tax_id | 22/815/0815/4 | **P** not-printed | nowhere on the page |
| Mustang…505 | buyer_vat_id | DE999999999 | **P** not-printed | nowhere on the page |
| Mustang…505 | payment_means_text | Überweisung | **P** not-printed | page has only the verb "…überweisen Sie bis…" — the value label is not rendered |
| Mustang…506 | (same 6 fields) | — | **3×R, 3×P** | identical layout + identical transcript behavior |
| fail3 | (same 6 fields) | — | **3×R, 3×P** | identical layout + identical transcript behavior |
| Avoir_FR_380 | seller_name | Au bon moulin | **R** (olmOCR) | printed in letterhead; olmOCR transcript starts BELOW the letterhead; Qwen read it |
| Avoir_FR_380 | seller_vat_id | FR11999999998 | **R** (both) | printed "TVA : FR11999999998"; olmOCR dropped letterhead; Qwen wrote FR11**9**999999998 (extra digit — digit-run slip) |
| Avoir_FR_380 | seller_address | 1242 chemin de l'olive… | **R** (olmOCR) | printed in letterhead; dropped |
| Avoir_FR_380 | prepaid_amount | -0.00 | **P** → parser-fixed | signed structural zero; ADR-043 rule extended to "-0.00" |
| Avoir_FR_381 | seller_name / seller_vat_id | — | **2×R** | same letterhead drop (olmOCR) + same digit-run slip (both) |
| Avoir_FR_381 | seller_address / buyer_address | "FR" | **2×P** degenerate-GT | GT is only the 2-char country code; not a rendered address |
| Facture_UE | issue_date / payment_due_date | 2017-11-03 / 2017-12-03 | **2×V** → fixed | page prints US month-first "11/03/2017" / "12/03/2017"; variant added |
| Facture_UE | line_total / tax_basis / grand_total / due_payable | 2076.76 ×3, 1453.76 | **4×V** → fixed | page prints Anglo "2,076.76 €" / "1,453.76 €"; variant added |
| Facture_UE | seller_name / seller_vat_id / seller_address | — | **3×R** | letterhead drop (olmOCR); VAT digit-run slip (both) |
| SEPA_Prenotification | delivery_date | 2013-03-05 | **P** xml-vs-page | page prints "Leistungsdatum 05.03.**2014**" — fixture XML/visual disagree |
| SEPA_Prenotification | payment_reference | 2013-471102 | **P** xml-vs-page | page prints "**2014**-471102" |
| SEPA_Prenotification | tax_total_amount | 56.87 | **P** not-printed | only per-rate rows (19,25 / 37,62) are printed; the sum is not |
| SEPA_Prenotification | payment_means_code | 49 | **P** not-printed | page prints prose "per SEPA-Lastschrift"; the UNTDID code never appears |
| Kostenrechnung (v1 EXTENDED) | invoice_number | KR87654321012 | **R** (olmOCR) | printed "Beleg-Nr : KR…"; olmOCR transcript lacks the whole header block; Qwen read it |
| Kostenrechnung (v1 EXTENDED) | issue_date | 2013-10-06 | **R** (olmOCR) | printed "Beleg-Datum : 06.10.2013"; same header-block drop |
| Kostenrechnung (v1 EXTENDED) | billing_period_start | 20139102 | **P** invalid-GT | month "91" — defective fixture XML (page prints "01.09.13 – 30.09.13") |
| fully_compliant_complete | currency/tax_total/grand_total/due_payable/due_date/iban/bic | EUR, 6239.22, 39077.22, …, NL13RABO… | **7×P** xml-vs-page | the PAGE is a 1997 **DEM** SAP sample (Total 37.763,70 DEM, German banks); the XML describes a different EUR/Dutch-bank invoice. Fixture fundamentally contradictory (lives under `ZUGFeRDv2/fail/`) |
| Elektron / Elektron_embedded | document_type | 204 | **2×P** → parser-fixed | page prints "Baurechnung"; code 204 now mapped → invoice (ADR-046 extension) |
| Sachversicherung (2p1) | document_type | 575 | **P** → parser-fixed | page prints "Rechnung des Versicherers"; 575 mapped → invoice |

## Classification totals

| class | count | resolution |
|---|---|---|
| **R** real reader misses | **19** (olmOCR) / **3** (Qwen, all FR-VAT digit-run) | stays on record — this is the reader's true error rate |
| **V** ruler variant gaps | 6 | fixed (US dates, Anglo grouping) + tests |
| **P** not findable on page | 27 | 4 parser-fixed (doc-type 204/575, "-0.00"); 23 excluded via `data/finetune/findability-exclusions.json` with reason codes |

## Symmetric judge pass (Qwen's remaining misses) + second ruler wave

The same treatment applied to Qwen's residual list exposed two further ruler gaps —
markdown bold markers breaking containment, and Ü↔UE transliteration (page prints
`DUESSELDORF`, the model normalizes to `Düsseldorf`) — both fixed in `_canon`
(information-preserving; applied to both sides of the containment). Qwen's remaining
**16 real misses** decompose into:

- **12 × character misreads of one recurring word**: `Lieferant`/`Lieferantenstraße`
  transcribed as `Lieberant`/`Lieberantenstraße` (f→b) on the stylesheet-rendered
  intarsys/symtrax fixtures (seller_name + seller_address on 7 invoices);
- **3 × FR-VAT digit-run slip** (`FR11999999998` → one extra 9) — shared failure with
  every model that read the letterhead at all;
- **1 × dropped reference** (`COMPRA0832`, Facture_UE).

## The decisive mechanism finding

The finalists are **statistically tied on corrected findability** but fail in
**opposite modes**:

| reader | corrected findability | real misses | failure mechanism |
|---|---|---|---|
| Qwen3-VL-4B | **0.970** | 16 | reads every margin block; rare character-level slips INSIDE values (f→b, extra digit) |
| olmOCR-2-7B | 0.965 | 19 | flawless characters, but silently DROPS letterhead/footer/header blocks — exactly where IBAN, BIC, USt-ID, seller identity, Beleg-Nr live |
| PDF text layer (ceiling) | 0.995 | 3 | stylesheet quirks (2 fixture names not in text layer) |
| granite (canonical) | 0.830 | 92 | prior baseline, same corrected ruler |
| MinerU-2604 / 2605 | 0.925 / 0.753 | 40 / 129 | third place / loop collapse (ADR-056) |

Endpoint zero-shot F1 with the blank-page guard applied to both: olmOCR **0.8335**,
Qwen **0.8118** (raw 0.7829 was carrying the guarded-away blank-page hallucination:
that invoice alone scores 0.047 → 0.885 with the guard-equivalent transcript).

The reader decision (with the domain-weighting argument — silent loss of banking
fields vs rare in-value character slips) is ratified in ADR-057.

Provenance: #114, ADR-056 (ruler fix), ADR-057 (reader selection), session audit
2026-08-02. All judged against `data/raw/smoke/multipage/` rasters at 300 DPI.
