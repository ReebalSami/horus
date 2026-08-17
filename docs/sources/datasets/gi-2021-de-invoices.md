---
source_url: "https://dl.gi.de/bitstreams/38f719d8-6af3-4dd7-a0c6-bdb08bb893c1/download"
source_title: "German invoice dataset of Thiée et al. 2023 — 977 real German invoices, 60+ annotated classes"
source_author: "Lukas-Walter Thiée, Felix Krieger, Burkhardt Funk (INFORMATIK 2023)"
source_date: "2023"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["informatik-2023", "german-invoices", "real-world", "annotated", "dataset", "primary-corpus", "deferred"]
archived_pdf: ""
status: stub
license_spdx: ""
license_url: ""
data_manifest: ""
acquisition_status: deferred
---

> **ATTRIBUTION CORRECTED 2026-08-17 (fourth-pass thesis review).** This record's original text carried a chimera citation: a fused title ("Extraction of Information from Invoices – Challenges in the **Approach for Datasets with High Layout Variety**"), the wrong authors ("Krieger, J. et al."), the wrong venue/year ("GI 2021 / WI 2021"), and a "Paper:" link to an unrelated BTW 2021 database paper (handle 20.500.12116/35795). The `source_url` bitstream was right all along: it is `09_01_06_Thiee.pdf` — **Thiée, Krieger & Funk (2023), "Extraction of Information from Invoices — Challenges in the Extraction Pipeline", INFORMATIK 2023 (LNI P337), pp. 1777–1792, DOI 10.18420/inf2023_180**. Verified paper record: `docs/sources/papers/thiee-2023-invoice-extraction-pipeline.md`.

German invoice dataset of Thiée et al. 2023 — 977 real German B2B invoice PDFs with rule-based annotations on 60+ document classes, 494 vendors / 531 recipients. Cited in HORUS as a **primary German-domain evaluation corpus** (brainstorm v2 §9.1 — real-world German invoice distribution check alongside the synthetic ZUGFeRD corpus). Provides the real-world long-tail variety that Mustang-generated synthetic invoices cannot cover. The `source_url` above is the proceedings PDF — the dataset itself is not bundled and requires direct author contact.

**Acquisition status**: Deferred (decision 2026-05-13 closing sub-issue #26 not-planned). The HORUS first pilot (`#13`) runs against data already on disk: 151 ZUGFeRD German B2B PDFs + 88 ZUGFeRD German XMLs + 2.1 GB of CORD-v2 Korean receipts + 1.4 GB of OmniDocBench multilingual documents. If the pilot results indicate insufficient real-world German long-tail variety to surface failure-mode diversity, this dataset is the first re-acquisition target — contact Thiée et al. via paper correspondence address, place received files under `data/raw/german/gi-2021-de-invoices/`, and run `make data-manifest SLUG=gi-2021-de-invoices LANG=german SOURCE_TYPE=author_request`.

- Paper: https://dl.gi.de/items/5c508847-1654-434b-8097-0e87f1a6798a (DOI 10.18420/inf2023_180)
- Dataset size: ~977 files (unknown MB)
