# Azure AI Document Intelligence runbook — second GT channel for Tier B (issue #118 sibling; ADR-060 follow-on)

Purpose: 13 of the 39 held-out Belege documents have **no usable embedded text layer**, so
no deterministic source can settle their field values (measured:
`uv run python scripts/audit_heldout_evidence.py` → Tier B `0 / 338` proven). Those
documents need **two independent readings** plus author sign-off before their ground truth
may be trusted. Claude vision is channel 1 (already run, all 39). This runbook provisions
channel 2.

**Why Azure specifically, and not a second VLM**: `prebuilt-invoice` is a *specialist* —
dedicated OCR plus a field model trained on invoices — so its failure modes are
architecturally unlike a generalist VLM's. Agreement between two systems that fail the
same way is worth very little; agreement between two that fail differently is worth a lot.
A second general-purpose VLM would mostly duplicate Claude's mistakes.

**Scope guard**: this is for **authoring the answer key only**. It is *not* on the HORUS
inference path. The delivered pipeline stays fully local — that is the project's central
privacy claim (ADR-057) and nothing here touches it. Same posture as the Claude judge
(ADR-060).

Cost: **€0** on the free F0 tier for this corpus (see §5).

---

## 1. Create the resource

Azure renamed this service — it was **Form Recognizer**, it is now **Document
Intelligence**. Older tutorials and blog posts use the old name for the same thing.

1. Sign in at <https://portal.azure.com>
2. Top search bar → type **`Document Intelligence`** → under **Services** pick
   **Document Intelligence**

   > **There is no single-service/multi-service toggle to look for** — the distinction is
   > decided entirely by *which search result you click*. Landing on a blade headed
   > **Create Document Intelligence** means you have the single-service resource, which is
   > what you want: it keeps the key scoped to this one service and is the only kind that
   > supports Microsoft Entra auth later. The multi-service alternative is a separate blade
   > headed *Create Azure AI services* — if you see that title instead, back out and
   > re-search.
3. **+ Create**
4. Fill the **Basics** tab:
   - **Subscription** — your only one
   - **Resource group** → **Create new** → name it `horus-eval` (a dedicated group makes
     step 7 teardown a single click instead of a hunt)
   - **Region** — pick an **EU** region for data residency. Preference order, because
     Document Intelligence is not offered in every region:
     **Germany West Central** → **West Europe** → **Sweden Central**.
     Whichever you pick, **write it down** — the endpoint URL embeds it.
   - **Name** — `horus-docintel` (becomes part of the endpoint hostname; must be globally
     unique, so add a suffix if it collides)
   - **Pricing tier** → **Free F0**

   > If **Free F0** is greyed out or absent, you already have an F0 Document Intelligence
   > resource somewhere — Azure allows **one F0 per subscription**. Either reuse that
   > existing resource (skip to §2) or delete it. Do **not** silently accept **S0**; it is
   > pay-per-page and this runbook's €0 claim no longer holds.

5. **Review + create** → **Create**. Deployment takes ~30 seconds.
6. **Go to resource** when the deployment finishes.

## 2. Retrieve the endpoint and key

1. On the resource page, left sidebar → **Resource Management** → **Keys and Endpoint**
2. Copy **KEY 1** and **Endpoint**

The endpoint looks like `https://horus-docintel.cognitiveservices.azure.com/` — or
`https://<region>.api.cognitive.microsoft.com/` on older resources. Either is fine; copy
it **verbatim**, including the trailing slash and the `https://`.

> **KEY 1 vs KEY 2**: two keys exist only so you can rotate one while the other stays
> live. For our purposes they are interchangeable — use KEY 1.

## 3. Wire it into the repo

Both values go in `.env`, which is **gitignored** (`.gitignore` covers `.env`; only
`.env.example` is tracked). Append:

```sh
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://horus-docintel.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<paste KEY 1>
```

`src/horus/env_file.py` loads `.env` without overriding anything already exported in your
shell, so the runner picks these up automatically — same mechanism as `ANTHROPIC_API_KEY`.

**Never** paste the key into a chat message, a commit, a notebook cell, or an ADR. If it
leaks, rotate it: **Keys and Endpoint** → **Regenerate Key1**.

## 4. Verify before spending

The channel-2 runner does not exist yet — it is the next session's task. Once it lands,
its `--dry-run` will confirm credential wiring without making billable calls, mirroring
`scripts/judge_heldout_gt.py`.

Until then, a one-line reachability check (returns the model list; not billable):

```sh
curl -s -H "Ocp-Apim-Subscription-Key: $AZURE_DOCUMENT_INTELLIGENCE_KEY" "${AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT}documentintelligence/documentModels?api-version=2024-11-30" | head -c 400
```

A JSON body listing `prebuilt-invoice` among the models means endpoint + key are correct.
`401` means the key is wrong; `404` means the endpoint host or trailing slash is wrong.

## 5. Why F0's limits do not bind us — and the one place they would

The free tier has two hard caps that look fatal and are not:

| F0 limit | Naive impact | Why it does not apply |
|---|---|---|
| **First 2 pages only** per document | `belege-de-scan-002` is 4 pages | We send **one rasterized page per request**, so no request is ever multi-page |
| **4 MB** max file size | `24-09-05_PK_KösterPumpen_Rechnung.pdf` is **4.3 MB** — over the cap | A single downscaled page PNG is far under 4 MB |

Both are dissolved by the same decision: **send per-page rasters, not the PDF.** We
already have that pipeline — `rasterize_pdf` plus `prepare_judge_images`
(`src/horus/eval/judge_images.py`), which the Claude judge uses and which already enforces
sane dimensions. Channel 2 should reuse it rather than uploading PDFs.

That 4.3 MB scan is the concrete proof this matters: uploading it as a PDF would fail on
F0 outright, and it is a Tier B document, so it is precisely one we cannot skip.

The remaining F0 constraints, as stated verbatim in the portal's tier dropdown, are
**500 pages/month** and **20 calls/minute**. The 13 Tier B documents come to roughly 15–20
page-images, so the monthly page quota has ~25× headroom and is a non-issue even with
re-runs. The per-minute cap means one short pause; the runner should rate-limit rather than
retry-storm into `429`s.

## 6. What channel 2 must reconcile (field-name mismatch is expected)

Azure returns its **own** field vocabulary (`VendorName`, `InvoiceTotal`, `InvoiceDate`,
`CustomerAddress`, …), which is *not* EN16931/CII. It must be mapped onto our 34-field
registry (`src/horus/eval/ground_truth.py` `FIELDS`) before any comparison — e.g.
`VendorName` → `seller_name`, `InvoiceTotal` → `grand_total_amount`,
`InvoiceId` → `invoice_number`.

Two consequences worth planning for rather than discovering:

- Azure's invoice model does **not** cover every EN16931 field we score (no
  `buyer_reference`, no `payment_means_code`, no VAT-breakdown category codes). Absence in
  Azure's output is therefore **not** evidence of absence on the page — it is silence, and
  must be recorded as such rather than as a disagreement with Claude.
- Azure returns a **confidence** per field. That is a useful triage signal for ordering the
  review list, but it is *not* a warrant: a confidently-wrong OCR read is exactly the
  failure mode this whole two-channel design exists to catch.

## 7. Teardown

F0 costs nothing, so there is no billing reason to rush. But once the held-out GT is signed
off, the resource has no further purpose:

Portal → **Resource groups** → `horus-eval` → **Delete resource group** → type the group
name to confirm.

Deleting the group removes the resource and its keys together, which is why §1 put it in
its own group.

---

## Provenance

- Facts verified against Microsoft Learn via `context7` (2026-08-05): F0 availability,
  4 MB / 2-page F0 limits, `prebuilt-invoice` model id, `2024-11-30` API version,
  **Keys and Endpoint** portal location, single-service-vs-multi-service distinction.
- Corpus measurements (`4.3 MB` outlier, 13 Tier B documents) are reproducible:
  `uv run python scripts/audit_heldout_evidence.py`.
- Runbook shape follows `scripts/gpu/README.md` (exact-click console steps, explicit
  teardown step, budget stated up front).
