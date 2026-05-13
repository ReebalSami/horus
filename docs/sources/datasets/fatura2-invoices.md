---
source_url: "https://huggingface.co/datasets/mathieu1256/FATURA2-invoices"
source_title: "FATURA 2 invoices — synthetic invoice dataset from 50 templates"
source_author: "Mathieu Brandt (mathieu1256)"
source_date: "2024-02-15"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["fatura2", "invoices", "synthetic", "dataset", "huggingface", "cc-by-4.0", "english", "templates"]
archived_pdf: ""
status: stub
license_spdx: "CC-BY-4.0"
license_url: "https://huggingface.co/datasets/mathieu1256/FATURA2-invoices"
data_manifest: "data/raw/english/fatura2-invoices/MANIFEST.md"
acquisition_status: completed
---

FATURA 2 invoices — 10,000 invoice images on white backgrounds + 10,000 on coloured backgrounds (50 templates × 400 images each), with 3×10,000 JSON annotation files (per-image NER tags, word tokens, bounding boxes). Published by Mathieu Brandt on Hugging Face. Cited in HORUS as a **secondary synthetic invoice benchmark** (per brainstorm v2 §9 amendment — FATURA on HF, arXiv 2311.11856). English-language synthetic invoices; 50 distinct invoice layouts provide template-variety coverage. Pairs well with ZUGFeRD corpus (real German invoices with XML ground truth) to distinguish template-variety from domain-specific extraction challenges. Parquet format on HF: train split 8.6K rows (292.7 MB) + test split 1.4K rows (50.1 MB) with embedded images.

- Paper: arXiv 2311.11856
- License: CC-BY-4.0
- HF size category: 10K<n<100K (parquet, with embedded images)
