---
source_url: "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
source_title: "CORD-v2 — Consolidated Receipt Dataset (version 2)"
source_author: "NAVER CLOVA"
source_date: "2022"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["cord", "receipts", "dataset", "huggingface", "ocr-eval", "korean", "cc-by-4.0"]
archived_pdf: ""
status: stub
license_spdx: "CC-BY-4.0"
license_url: "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
data_manifest: "data/raw/korean/cord-v2/MANIFEST.md"
acquisition_status: completed
---

CORD-v2 (Consolidated Receipt Dataset, v2) — NAVER CLOVA's curated receipt-image dataset on Hugging Face. Annotated for receipt-information extraction (line items, totals, taxes, dates). Cited in HORUS as a **secondary cross-domain benchmark** (per brainstorm v2 §15 Datasets) — receipts are a related-but-distinct document class from German B2B invoices. Useful for: (a) calibrating Layer-1 VLM performance on a well-established benchmark before running on the German-invoice domain; (b) confirming the VLM cohort generalizes beyond the European invoice format; (c) sanity-check on training-time familiarity (most modern document VLMs include CORD in pre-training). Primary evaluation domain remains German B2B invoices.
