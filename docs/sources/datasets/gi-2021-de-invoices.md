---
source_url: "https://dl.gi.de/bitstreams/38f719d8-6af3-4dd7-a0c6-bdb08bb893c1/download"
source_title: "GI 2021 German invoice dataset — 977 real German invoices, 60+ annotated classes"
source_author: "Krieger et al. (2021) — GI 2021 / Wirtschaftsinformatik 2021"
source_date: "2021"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["gi-2021", "german-invoices", "real-world", "annotated", "dataset", "primary-corpus", "pending-user-action"]
archived_pdf: ""
status: stub
license_spdx: ""
license_url: ""
data_manifest: ""
acquisition_status: pending-user-action
---

GI 2021 German invoice dataset — 977 real German B2B invoice PDFs with rule-based annotations on 60+ document classes. From: Krieger, J. et al. "Extraction of Information from Invoices – Challenges in the Approach for Datasets with High Layout Variety." GI 2021 Proceedings (Wirtschaftsinformatik 2021). Cited in HORUS as a **primary German-domain evaluation corpus** (brainstorm v2 §9.1 — real-world German invoice distribution check alongside the synthetic ZUGFeRD corpus). Provides the real-world long-tail variety that Mustang-generated synthetic invoices cannot cover. The paper link above is to the proceedings PDF — the dataset itself is not bundled and requires direct author contact.

**Acquisition status**: Pending author request (sub-issue #26). Contact Krieger et al. via paper correspondence address. When received, place under `data/raw/german/gi-2021-de-invoices/` and run `make data-manifest SLUG=gi-2021-de-invoices LANG=german SOURCE_TYPE=author_request`.

- Paper: https://dl.gi.de/handle/20.500.12116/35795
- Dataset size: ~977 files (unknown MB)
- Sub-issue: ReebalSami/horus#26
