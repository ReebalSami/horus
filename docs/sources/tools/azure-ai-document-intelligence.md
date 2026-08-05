---
source_url: "https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/"
source_title: "Azure AI Document Intelligence — prebuilt-invoice model, analyze-document API, Python SDK (azure-ai-documentintelligence)"
source_author: "Microsoft"
source_date: ""
retrieved_date: "2026-08-05"
extracted_concepts: []
tags: ["azure", "document-intelligence", "form-recognizer", "prebuilt-invoice", "ocr", "ground-truth", "second-channel", "horus-adr-061"]
archived_pdf: ""
status: stub
---

Azure AI Document Intelligence — the capabilities HORUS ADR-061 relies on for the **second**
held-out ground-truth channel. Retrieved 2026-08-05 via the `context7` MCP
(`/websites/learn_microsoft_en-us_azure_ai-services_document-intelligence` and
`/websites/azuresdkdocs_z19_web_core_windows_net_python_azure-ai-documentintelligence`), per
`context7-and-docs-first`; not from training-data recall.

Service naming: this was **Form Recognizer** and is now **Document Intelligence**. Older
tutorials use the former name for the same service, and the legacy Python package
(`azure-ai-formrecognizer`, class `DocumentAnalysisClient`) still appears in current docs
alongside the successor (`azure-ai-documentintelligence`, class
`DocumentIntelligenceClient`). HORUS uses the successor.

## 1. Analysis is an asynchronous (long-running) operation

> *"The Document Intelligence Analyze operation is an asynchronous process. Upon submission,
> the API returns an `Operation-Location` header containing a URL used to poll for the
> completion status of the document analysis."*
> — `concept/analyze-document-response`

Relevance to HORUS: this polling contract is the single strongest argument for taking the SDK
rather than hand-rolling REST. A client that polls wrongly either burns F0 request quota or
reports a result that has not converged. The SDK's `begin_analyze_document(...)` returns a
poller and `poller.result()` blocks until the operation completes.

## 2. Python SDK surface — local bytes, no upload URL needed

From the `azure-ai-documentintelligence` reference:

```python
with open(path_to_sample_documents, "rb") as f:
    poller = document_intelligence_client.begin_analyze_document(model_id=model_id, body=f)
result: AnalyzeResult = poller.result()
```

and the request model:

```APIDOC
## Class: AnalyzeDocumentRequest
### Attributes
- bytes_source (bytes): The document content as raw bytes.
- url_source  (str):    The URL of the document to be analyzed.
```

Relevance: HORUS sends **local page rasters as bytes**. `url_source` would require making
private invoices publicly reachable, which is disqualifying under ADR-040 — `bytes_source`
keeps the exposure to the single POST body.

Client construction, from `how-to-guides/use-sdk-rest-api`:

```python
client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
poller = client.begin_analyze_document("prebuilt-invoice", AnalyzeDocumentRequest(...))
```

`locale` is an accepted keyword (`locale="en-US"` in the docs' sample). HORUS leaves it unset:
the corpus is mixed German + English, and pinning one locale on a German invoice would bias
the reading of exactly the documents that matter most.

## 3. `DocumentField` — `content` is as-printed, `confidence` is per field

```APIDOC
## DocumentField
### Properties
- type (str | DocumentFieldType) - Required. Known values: "string", "date", "time",
  "phoneNumber", "number", "integer", "selectionMark", "countryRegion", "signature",
  "array", "object", "currency", "address", "boolean", "selectionGroup".
- value_string / value_date / value_number / value_integer / value_currency /
  value_address / value_array (list[DocumentField]) / value_object (dict[str, DocumentField]) …
- content (str, optional) - Field content.
- bounding_regions (list[BoundingRegion]) - Bounding regions covering the field.
- spans (list[DocumentSpan])
- confidence (float, optional) - Confidence of correctly extracting the field.
```

Two properties decide HORUS's mapping design:

- **`content` is the literal page text for the field**, while `value_*` is Azure's *typed*
  interpretation. The docs' own Python sample reads `vendor_name.get('content')`. Held-out GT
  stores values **as printed** (ADR-058), so `content` is the value HORUS records and
  `value_*` is at most a cross-check. Taking `value_date` would silently re-format a German
  `28.09.2022` into `2022-09-28` and destroy the as-printed contract.
- **`confidence` is per field, not per document.** Useful only for *ordering* a review list.
  It is explicitly **not** a warrant in HORUS: a confidently-wrong OCR read is the precise
  failure mode the two-channel design exists to catch (runbook §6).

`bounding_regions` carries a page index, which lets an escalated cell point at the page it
came from — the page context requirement in the review sheet.

## 4. Result shape

```APIDOC
## AnalyzeResult
- api_version (str), model_id (str), content (str), pages (list[DocumentPage]),
  tables, figures, paragraphs, sections, key_value_pairs, styles, languages,
  documents (list[AnalyzedDocument]), warnings (list[DocumentIntelligenceWarning])
- as_dict(exclude_readonly=False) -> dict   # JSON-serializable

## AnalyzedDocument
- doc_type (str) Required · confidence (float) Required · spans Required
- bounding_regions · fields (dict[str, DocumentField])
```

`as_dict()` is what HORUS persists as the raw audit trail per document. `warnings` must be
surfaced rather than swallowed — a warning on a Tier B scan is diagnostic information about
the only reading available for that document.

## 5. `prebuilt-invoice` field vocabulary — Azure's names, not EN16931

Confirmed present in the retrieved samples (flat): `VendorName`, `VendorAddress`,
`VendorAddressRecipient`, `CustomerName`, `CustomerId`, `CustomerAddress`,
`CustomerAddressRecipient`, `BillingAddress`, `BillingAddressRecipient`, `ShippingAddress`,
`ShippingAddressRecipient`, `InvoiceId`, `InvoiceDate`, `DueDate`, `PurchaseOrder`,
`SubTotal`, `TotalTax`, `InvoiceTotal`, `AmountDue`, `PreviousUnpaidBalance`.

Confirmed present as an array: `Items`, whose per-row cells are `Description`, `Quantity`,
`Unit`, `UnitPrice`, `ProductCode`, `Date`, `Tax`, `Amount`.

The docs point at `https://aka.ms/formrecognizer/invoicefields` for the authoritative full
list and do not enumerate it inline. **HORUS therefore treats the vocabulary as something to
measure, not to assume**: the mapping table holds candidate Azure keys per HORUS field, and
the runner reports every Azure key it observed that the table does not map. Any additional
field the service returns (tax ids, service dates, payment terms, per-rate tax details)
surfaces empirically in that report instead of being hardcoded from memory. This is the
ADR-058 discipline applied to a vocabulary claim: an alias table is an assertion about data
and must be measured against the data.

`InvoiceTotal` returns a **currency** field —
`Invoice Total: CurrencyValue(amount=110.0, symbol=$)` in the docs' sample output — so its
`content` (the printed amount) and its `value_currency.currency_code` are different pieces of
information, and the currency code is the only place a currency identifier appears at all.

**What the model does not cover.** `prebuilt-invoice` has no concept of an EN16931
`buyer_reference` (BT-46), `payment_means_code` (BT-81), VAT-breakdown `category_code`
(BT-118), IBAN/BIC (BT-84/86), or GLN (BT-29). Azure's silence on those is **not** evidence
of absence on the page; HORUS records `not-covered` as a state distinct from `not-present`,
so a Tier B null never gains a false second-channel confirmation.

## 6. Free tier (F0) limits, and why per-page rasters dissolve them

Verified for the runbook on 2026-08-05 (see `scripts/azure/README.md` §5): F0 processes only
the **first 2 pages** of a submitted document, caps file size at **4 MB**, and allows
**500 pages/month** at **20 calls/minute**. One F0 resource per subscription.

HORUS submits **one rasterized page per request**, so no request is ever multi-page and no
request approaches 4 MB — including the 4.3 MB corpus PDF that would fail outright as a PDF
upload and is a Tier B document that cannot be skipped. The 39-document corpus is 58 pages
(~65 images after tall-page tiling), so the monthly page quota has roughly 8× headroom and
the per-minute cap costs one short pause. The runner rate-limits rather than retry-storming
into `429`s.

## 7. Auth + region

`DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))`. HORUS reads
`AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY` from the
environment via `horus.env_file.load_env_file()`, keeping them in the git-ignored `.env`
exactly as `ANTHROPIC_API_KEY` is kept — never in `ExperimentConfig`, because everything
reaching that model is logged to MLflow as a run parameter.

Resource is provisioned in an **EU region** for data residency (Germany West Central / West
Europe / Sweden Central), per the runbook. The reachability check that proves endpoint + key
without spending quota:

```sh
curl -s -H "Ocp-Apim-Subscription-Key: $AZURE_DOCUMENT_INTELLIGENCE_KEY" "${AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT}documentintelligence/documentModels?api-version=2024-11-30" | head -c 400
```

`401` = wrong key; `404` = wrong endpoint host or missing trailing slash.

## Scope guard

This service authors the **answer key** only. It is never on the HORUS inference path — the
delivered pipeline stays fully local (ADR-057), which is the project's central privacy claim.
Same posture as the Claude vision judge (ADR-060), and per parent-plan Phase 6 a tool that
authors ground truth can never also appear as a measured baseline: instrument, not competitor.
