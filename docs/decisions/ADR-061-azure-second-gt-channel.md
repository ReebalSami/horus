# ADR-061: Second held-out GT channel — Azure AI Document Intelligence `prebuilt-invoice`

**Status**: Accepted — executed on all 39 documents (62 page images, well inside the F0 free
quota, €0). Independence was the property bought and it paid: **178 cells reached
`two-channel-agreed` on Azure's testimony alone**, and those are almost entirely the Tier B
cells that no printed-evidence gate could ever have settled. Without this channel those 178
would have escalated to the author's desk on top of the 248 already there. The three-valued
coverage decision proved load-bearing — collapsing Azure's `NOT_COVERED` silence into "absent"
would have handed unearned confirmations to Tier B nulls. Feeds ADR-062 (adjudication) and
ADR-063 (grading scope).

**Context**

ADR-060 put a cloud vision judge (channel 1) on all 39 held-out Belege. The printed-evidence
gate then graded that output against each PDF's own embedded characters, and the result split
the corpus in two:

| Tier | Docs | Judge-asserted cells | Proven by printed evidence |
|---|---|---|---|
| A (usable text layer) | 26 | 752 | 575 (76.5 %) |
| A? (text layer belongs to a covering email page) | 1 | 27 | 3 |
| B (no text layer at all) | 12 | 338 | **0** |

Tier B's zero is structural, not a failure of the gate: with no embedded characters there is
nothing deterministic to check a reading against. Those 338 cells currently rest on one
unverifiable reading — which is exactly the situation that produced the retracted 0.5692
held-out figure.

Two further facts shape the decision. First, the gate proves a string is *printed on the
page*; it cannot prove that string belongs to the *field* it was assigned to. Second, the
judge asserts 752 Tier A cells where the earlier text-layer draft asserted 360, and most of
that gain is judge-only. So even on Tier A a large population of cells is single-channel on
the question of assignment.

**Decision**

Add **Azure AI Document Intelligence `prebuilt-invoice`** (F0 tier, EU region) as GT channel
2, read **per rasterized page as PNG**, over **all 39 documents**.

Chosen because it fails *differently*: a dedicated OCR stack plus an invoice-trained field
model is architecturally unlike a generalist VLM, and agreement between two systems that
share a failure mode is worth very little. Independence is the property being bought, not
accuracy.

Five sub-decisions carry the weight.

1. **All 39 documents, not Tier B only.** The corpus is 62 page-images against F0's
   500 pages/month — 12 % of quota, €0. Covering Tier A converts judge-only cells into
   two-channel-agreed ones, which is what makes them auto-acceptable; restricting to Tier B
   would leave hundreds of cells on the author's desk for no saving.

2. **`azure-ai-documentintelligence` as a direct dependency**, not hand-rolled REST.
   Analysis is a long-running operation (`Operation-Location` polling); a client that polls
   wrongly either burns quota or reads an unconverged result. Same posture as `anthropic`
   for channel 1.

3. **Per-page PNGs, never PDFs.** F0 truncates a document at 2 pages and rejects files over
   4 MB. One corpus PDF is 4.3 MB and is Tier B, so it cannot be skipped. One page per
   request dissolves both caps. Images come from `prepare_judge_images`, the same
   preparation channel 1 saw, so any difference between the readings is the model and not
   the pixels.

4. **Three-valued coverage.** Each field resolves to `VALUE` / `NOT_PRESENT` /
   **`NOT_COVERED`**. Azure has no concept of BT-46 `buyer_reference`, BT-81
   `payment_means_code`, or BT-118 category codes; if that silence collapsed into "absent",
   a Tier B null would gain a confirmation it never earned. `NOT_COVERED` is excluded from
   `is_evidence` because it describes Azure, not the document.

5. **`content`, never the typed value.** Held-out GT stores values as printed (ADR-058).
   `valueDate` would rewrite a printed `28.09.2022` into `2022-09-28` and destroy that
   contract. The one exception is BT-5 `invoice_currency_code`, which is never printed as
   its own field and is recovered from `valueCurrency.currencyCode`.

**Confidence is triage, not warrant.** Per-field `confidence` orders a review list and
nothing more. A confidently-wrong OCR read is the failure this design exists to catch — the
first live invoice returned a VAT id at 0.434 and a tax total at 0.536.

**The vocabulary is measured, not asserted**

Microsoft documents the authoritative `prebuilt-invoice` field list behind a link rather than
inline. A table written from the quickstart samples would therefore be an unverified claim
about data — the mistake ADR-058 was written to stop, after 34 invented `prompt_alias`
entries turned out to match 0/146 documents.

So `AZURE_FIELD_MAP` holds *candidate* names, and `scripts/audit_azure_vocabulary.py` reports
every observed name that no table consumes. Each unknown is either a mapping we are missing
or a field we should consciously record as unused; leaving one unclassified means silently
discarding a reading the service offered.

**This immediately falsified three of my own claims.** The first pass declared 13 of 34
fields structurally uncoverable. The audit over the real corpus found:

- `PaymentDetails[]` carries **`IBAN`** (19 pages) and **`SWIFT`** (21 pages) — so BT-84
  `seller_iban` and BT-86 `seller_bic` are covered, not uncoverable. Left unmapped, every
  IBAN and BIC in the corpus would have rested on a single channel permanently.
- `Items[]` carries **`TaxRate`** (40 rows) — `line_items.vat_rate` is covered.
- `OrderNumber` is a real `buyer_order_reference` fallback; `TotalDiscount`,
  `ServiceStartDate`/`EndDate`, `VendorTaxId` and `CustomerTaxId` all exist as guessed.

Corrected count: **11 of 34** fields have no Azure candidate. Reading a flat field out of an
array cell required a second read path (`AZURE_ARRAY_FIELD_MAP`), which the initial design
did not have.

**Alternatives considered**

- **AWS Textract `AnalyzeExpense`** — comparable specialist quality, but no EU-region free
  tier for this workload and a heavier credential setup. Revisit only if Azure's coverage
  proves inadequate on Tier B.
- **A second VLM as channel 2** (e.g. a different frontier vision model) — rejected: two
  generalist VLMs share failure modes (same pretraining regime, same hallucination-under-
  ambiguity behaviour), so agreement between them would be far weaker evidence than it looks.
- **A custom-trained Azure model** — rejected: training it on this corpus would make the
  channel a second measurement of our own data rather than an independent reading.
- **Qwen3-VL transcripts already on disk** — disqualified outright. It is the pipeline's own
  reader; using it as GT would grade the model against itself.
- **Hand-rolled REST client** — rejected per sub-decision 2.

**Consequences**

- 21 of 34 flat fields can now receive a second independent reading; 11 cannot and are
  labelled so, which is itself reportable information rather than a silent gap.
- Tier B cells become adjudicable: a Tier B value with two agreeing channels is
  `two-channel-agreed` — weaker than `text-layer-proven`, and it stays visibly weaker in the
  final provenance breakdown rather than being absorbed into a headline.
- Raw responses are archived per document under `_azure/raw/`, making
  `azure_heldout_gt.py --rebuild` able to re-derive all GT with **zero API calls** whenever
  the mapping table changes. The archive is load-bearing, not decorative — it was used
  immediately, to apply the IBAN/SWIFT correction without re-spending quota.
- Two cloud channels can still fail together. Uncorrelated is not independent, and the
  adjudication step must keep `two-channel-agreed` distinct from deterministic proof.
- **Scope guard**: GT authoring only. Never on the inference path — the delivered pipeline
  stays fully local (ADR-057), which is the project's central privacy claim. Per parent-plan
  Phase 6, a tool that authors ground truth can never also appear as a measured baseline:
  instrument, not competitor.

**Source archival**

`docs/sources/tools/azure-ai-document-intelligence.md` — SDK surface, the
`Operation-Location` polling contract, `DocumentField` semantics, F0 limits, and the observed
field vocabulary. Retrieved 2026-08-05 via the `context7` MCP per `context7-and-docs-first`;
the wire shape of `as_dict()` was additionally verified against the installed SDK rather than
assumed.

**Supersession trigger**

Revisit if: Azure's Tier B coverage proves too thin to adjudicate (measured as escalation
rate after the review sheet lands); or F0 quota becomes binding; or the held-out corpus grows
past ~300 pages/month; or a third channel is needed because two-channel disagreement is
unresolvable at a rate that makes author adjudication the bottleneck.
