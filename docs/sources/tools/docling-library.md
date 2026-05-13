---
source_url: "https://github.com/docling-project/docling"
source_title: "Docling — open-source document parsing library"
source_author: "IBM Research / Linux Foundation Agentic AI Foundation"
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["docling", "document-parsing", "ocr", "layout", "tables", "pipeline", "open-source", "apache-2", "ibm-research", "linux-foundation"]
archived_pdf: ""
status: stub
---

Docling open-source library (Apache 2.0). Customizable ensemble pipeline (parse + OCR + layout/tables + optional VLM). Self-hostable, MLX-capable. Originally IBM Research; now part of Linux Foundation's Agentic AI Foundation. Two pipeline classes — `StandardPdfPipeline` (orchestrated specialists: layout + OCR + table-recognition stages composed) and `VlmPipeline` (single-shot, Granite-Docling-258M default) — reachable via `PdfFormatOption(pipeline_cls=...)`. Pipeline-stage knobs via `PdfPipelineOptions(do_ocr=..., do_table_structure=...)`. CLI: `docling <input> --to md --to json --no-ocr`.

Cited in HORUS ADR-008 as the **chosen primary orchestrated baseline** (`StandardPdfPipeline` mode; the `VlmPipeline`-with-Granite-Docling-258M mode is empirically excluded by ADR-007's smoke evidence on HORUS-style invoices). The Docling library represents the orchestrated-specialist arm of brainstorm v2 §6 H2's directional-flip prediction: single-shot wins on clean ZUGFeRD invoices, orchestrated wins on degraded real-world Belege where validator-driven retry can correct extraction errors. Berghaus 2025 (`docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md`) measured Docling at 64.03% on Scanned Invoices and 47.00% on Scanned Receipts — HORUS replicates this comparison on the Oct-2025 *local open-source* cohort which Berghaus excluded.
