---
source_url: "https://e-invoice.be/en16931-mapper"
source_title: "EN 16931 mapper — Business term → CII / UBL XPath lookup"
source_author: "e-invoice.be (Belgian e-invoicing service provider)"
source_date: ""
retrieved_date: "2026-05-17"
extracted_concepts: []
tags: ["en16931", "cii", "ubl", "xpath", "bt-codes", "mapping-reference", "adr-012", "ground-truth-parser", "pilot-13"]
archived_pdf: ""
status: stub
---

Web reference: BT → CII/UBL XPath canonical lookup. The page provides a searchable table mapping EN 16931 business term codes (BT-1 through BT-160 + BG-* business groups) to their CII (UN/CEFACT CrossIndustryInvoice) XPath expressions and UBL (OASIS Universal Business Language) XPath expressions. Useful as a single-page reference during XPath authoring because the CEN-published EN 16931 documents themselves are spread across multiple PDFs (the standard + the syntax bindings + the validation artefacts).

**Role in HORUS (per ADR-012)**: consulted during the authoring of the 16-row `FIELDS` registry in `src/horus/eval/ground_truth.py`. Cross-referenced our hand-authored XPaths against the published mapping to catch:
- Container-path conventions (the EN 16931 CII binding consistently routes through `/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement` for seller/buyer, `/ram:ApplicableHeaderTradeDelivery` for delivery, `/ram:ApplicableHeaderTradeSettlement` for totals)
- `schemeID` predicate filtering for multi-row tax-registration / global-ID elements (BT-31 `schemeID="VA"` for VAT IDs, BT-32 `schemeID="FC"` for German Steuernummer, BT-29 `schemeID="0088"` for GS1 GLN)

**What it does NOT do**: validate XML against the bindings (Schematron + XSD jobs — handled by `factur-x` per ADR-005 / ADR-010), generate ground truth from extracted XML (the parser job — owned by `src/horus/eval/ground_truth.py` per ADR-012), or define the 16-field HORUS scope (decision made in the Socratic walk; this reference is only the lookup substrate).

**Stability**: the mapper page is published by e-invoice.be (the Belgian Peppol service provider); the underlying EN 16931 standard is published by CEN (European Committee for Standardization) and is comparatively stable. Supersession risk = low until EN 16931-2 lands (no public timeline as of 2026-05-17).

**Alternatives surveyed**: B2BRouter has a similar published mapping (see `docs/sources/tools/b2brouter-cii-xpath.md`) used as a second-opinion cross-check; the CEN/CENELEC TC 434 publications themselves are the authoritative source but are spread across paid + free documents and lack a single-page tabular form.
