---
source_url: "https://developer.b2brouter.net/docs/mapping_json_invoice_to_cii"
source_title: "Mapping JSON invoice to CII — B2BRouter developer docs"
source_author: "B2BRouter (Invinet Sistemes, Barcelona — Peppol Authority access point)"
source_date: ""
retrieved_date: "2026-05-17"
extracted_concepts: []
tags: ["en16931", "cii", "xpath", "bt-codes", "mapping-reference", "vendor-docs", "second-opinion", "adr-012", "ground-truth-parser"]
archived_pdf: ""
status: stub
---

Vendor developer documentation: B2BRouter's mapping table from their internal JSON invoice schema to UN/CEFACT CII XML. Published as part of their integration docs for SaaS customers, but publicly accessible. The mapping table covers EN 16931 business term codes (BT-*) and their CII XPath targets — useful as an **independent second-opinion source** when cross-checking the canonical e-invoice.be reference (per `docs/sources/tools/e-invoice-be-en16931-mapper.md`).

**Role in HORUS (per ADR-012)**: consulted as a second-opinion cross-check during XPath authoring for ambiguous fields. Notably:
- **BT-46 buyer reference disambiguation** — EN 16931 ships TWO related concepts that both translate to a "customer-side identifier": `BuyerTradeParty/ID` (the buyer's internal customer number issued by the seller) and `ApplicableHeaderTradeAgreement/BuyerReference` (a free-form purchaser-side reference). The two have different ZUGFeRD profiles in different places; B2BRouter's published table sided with `BuyerTradeParty/ID` for the BT-46 canonical render, which matches the FeRD-shipped corpus content (the `EN16931_Einfach.pdf` fixture has `<ram:BuyerTradeParty><ram:ID>GE2020211</ram:ID>` and no `<ram:BuyerReference>`).
- **BT-31 / BT-32 / BT-48 schemeID predicate behaviour** — B2BRouter's docs confirmed that the `schemeID="VA"` (VAT) vs `schemeID="FC"` (German Steuernummer) predicate is the canonical disambiguation pattern for `ram:SpecifiedTaxRegistration/ram:ID` elements; this matches the FeRD-shipped corpus and the e-invoice.be reference.

**Why a vendor source**: independent vendor implementations of the same standard surface practical interpretation choices that the CEN/CENELEC TC 434 standard documents don't always elaborate. Cross-checking two independent mappings (e-invoice.be + B2BRouter) raises confidence in the authored XPaths beyond what a single reference would.

**What it does NOT do**: implement a parser (B2BRouter is a SaaS — the mapping doc explains how their JSON-to-CII converter handles each field), define normalization rules (theirs are CII-output-side; HORUS's are CII-input-side and need to handle anomalies in arbitrary supplier-generated XMLs), or cover line items / per-VAT-rate breakdown (out of scope for ADR-012 per §"What this ADR does NOT decide").

**Stability**: developer docs change without notice. The mapping shape itself is anchored to EN 16931, so structural divergence is unlikely; specific XPath strings may be revised. Re-verify the cited XPaths if this page is updated post-`retrieved_date`.
