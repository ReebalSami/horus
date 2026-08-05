---
source_url: "https://www.ferd-net.de/publikationen-produkte/publikationen/detailseite/zugferd-25-deutsch"
source_title: "ZUGFeRD 2.5 / Factur-X 1.09 — Technischer Anhang (deutschsprachig, je Profil)"
source_author: "FeRD (Forum elektronische Rechnung Deutschland) / FNFE-MPE"
source_date: ""
retrieved_date: "2026-08-06"
extracted_concepts: []
tags: ["zugferd", "factur-x", "en-16931", "e-invoicing", "german-business-terms", "primary-legal-standard", "prompt-grounding"]
archived_pdf: ""
status: stub
---

# ZUGFeRD / Factur-X — Technischer Anhang (German-language technical annex)

The **German-language** per-profile technical annex of the ZUGFeRD / Factur-X specification,
published by FeRD (the German national e-invoicing body) jointly with FNFE-MPE. Its release
package contains, per the publisher's own contents list: the unified specification PDF, a
**Technischer Anhang in deutscher Sprache (separat für jedes Profil)**, an Excel sheet of every
EN 16931 code list, schema + XSLT files, and sample invoices.

## Why this source is needed — and what it corrects

HORUS's structurer prompt anchors each field to a German label. Those labels were grounded
**only** by occurrence in the 146-invoice synthetic FeRD corpus (ADR-058 / ADR-059), i.e.
against one publisher's house wording. `make audit-prompts` *gates* on that occurrence, so a
correct German term that this one corpus happens not to print is rejected as unfounded.

The intended fix was to admit a second warrant: "the standard's own German business-term
name". Researching this source **corrected the premise**:

> **EN 16931-1 business-term names are ENGLISH, not German.** The XRechnung specification —
> itself a German-language document — states that every information element of the CIUS
> XRechnung *"besitzt ein Pendant mit gleicher Kennung und gleichem Namen im semantischen
> Datenmodell der EN 16931-1"*, and it refers to elements by their English names throughout
> (e.g. `BT-72 Actual delivery date`, `BT-1 Invoice number`). There is therefore **no
> normative German BT name in EN 16931 itself**.

The German business-term vocabulary comes instead from **this** document — the FeRD
German-language Technischer Anhang. That is a *better* warrant for HORUS than EN 16931 would
have been, because ZUGFeRD is precisely the format the project's synthetic corpus implements,
so the annex's German names are the normative German vocabulary for the very standard being
measured.

Crucially, it is independent of both grounding corpora: it is neither the synthetic FeRD
invoice set nor the private held-out Belege set. Justifying a prompt label from it is
therefore **not** test-set fitting.

## Verified content (from the annex's EN16931-profile field tables)

Spot-checked German business-term names, EN16931 profile:

| BT | German name (annex) | English name (EN 16931-1) |
|---|---|---|
| BG-13 | `LIEFERINFORMATIONEN` | DELIVERY INFORMATION |
| BT-72 | **`Tatsächliches Lieferdatum`** | Actual delivery date |
| BT-72-00 | `Tatsächlicher Lieferungszeitpunkt` | (container) |
| BT-71 | `Kennung des Lieferorts` | Deliver-to location identifier |
| BT-75 | `Zeile 1 der Lieferanschrift` | Deliver-to address line 1 |
| BT-77 | `Stadt der Lieferanschrift` | Deliver-to city |
| BT-78 | `Postleitzahl der Lieferanschrift` | Deliver-to post code |
| BT-80 | `Ländercode der Lieferanschrift` | Deliver-to country code |
| BG-15 | `LIEFERANSCHRIFT` | DELIVER TO ADDRESS |

`Tatsächliches Lieferdatum` is the annex's full BT-72 name; **`Lieferdatum`** is its short
form and the wording German invoices actually print. Measured relevance: `Lieferdatum` occurs
in **0 / 146** synthetic corpus transcripts — so the current gate would reject it — while
appearing on **6 of the 13** real invoices where HORUS misses BT-72 (ADR-063 held-out set).

## Outstanding — needed before the field-by-field vocabulary walk

**This stub is not yet sufficient to justify aliases across all 34 fields.** It records only
the spot-checked delivery-information block. What is still required:

1. The full BT → German-name table for every field in HORUS's registry, read from the
   EN16931-profile annex (not reconstructed from vendor summaries).
2. `archived_pdf` populated. The canonical download at `ferd-net.de` is registration-gated;
   third-party mirrors of the 2.3.2 and 2.4 annexes exist and were used for the spot-check
   above, but a mirror is not an archive — the release package should be obtained from FeRD
   and stored.
3. A decision on which ZUGFeRD version to pin, since the project's corpus predates 2.5.

Until (1) and (2) are done, **no alias may cite this source as its warrant.** Recording the
gap explicitly rather than letting a stub imply coverage it does not have — the same failure
mode as ADR-058's citation of a `docs/sources/standards/` directory that never existed.

## Related

- `docs/sources/legal/zugferd-en16931.md` — the pre-existing ZUGFeRD/EN 16931 stub (Mustang
  Project landing page; also `status: stub`, no term list)
- ADR-058 — the audit that grounded every alias on the single synthetic corpus, and whose
  §"Known limitation" records that 22 of 34 `german_label` values occur in 0 corpus transcripts
- ADR-059 — `printed_label` / `rendered_label` and the corpus-occurrence gate this source is
  intended to give a second, standards-based warrant alongside
- ADR-002 — this archival convention (`legal/` is the taxonomy slot for EN 16931; there is no
  `standards/` type)

## Secondary source consulted

The BVBS **ZUGFeRD-Implementierungs-Leitfaden 2.2** states the BT-72 default explicitly:
*"Wenn der Knoten nicht vorhanden ist, dann entspricht das Leistungsdatum dem
Rechnungsdatum"* — if the element is absent, the service date equals the invoice date, since
German VAT law admits only one service date per invoice. Relevant context for BT-72, though
**not** load-bearing for the HORUS fix: 7 of the 8 held-out invoices whose delivery date
equals the invoice date do print a delivery label, so the gap there is vocabulary, not a
missing convention.
