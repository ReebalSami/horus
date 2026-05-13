---
source_url: "https://arxiv.org/abs/2509.04469"
source_title: "Multi-Modal Vision vs. Text-Based Parsing for Invoice Processing"
source_author: "Berghaus, Berger, Hillebrand, Cvejoski, Sifa (Fraunhofer IAIS + Lamarr Institute)"
source_date: "2025-09"
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["invoice-processing", "vlm", "benchmark", "german-b2b", "fraunhofer", "literature-gap", "scanned-invoices", "scanned-receipts", "docling-baseline", "h2-clean-arm"]
archived_pdf: ""
status: stub
---

Berghaus et al. 2025 (Fraunhofer IAIS + Lamarr Institute, arXiv 2509.04469). Benchmarks GPT-5, Gemini 2.5, and Gemma 3 (native multi-modal vision) against Docling library (text-based parsing) on invoice-extraction tasks. Cited in HORUS as the **direct literature gap** (per brainstorm v2 §7.5): the paper benchmarks proprietary cloud VLMs but does NOT include any of the Oct-2025 specialized open-source document VLMs (Granite-Docling, olmOCR-2, Nanonets-OCR2, dots.ocr, MinerU 2.5, etc.). HORUS fills this gap on the open-source local-inference cohort under the §203-StBerG legal frame.

**Verified key numbers** (from arXiv abstract via web verification 2026-05-13):
- **Scanned Invoices**: native multi-modal processing reached **92.71%** vs Docling-parsed text-based baseline **64.03%** — a ~29-percentage-point gap.
- **Scanned Receipts**: native processing reached **87.46%** vs Docling-parsed maximum **47.00%** — a ~40-percentage-point gap.

These numbers anchor HORUS ADR-008's framing of brainstorm v2 §6 H2's *clean-document* arm: Berghaus's "Scanned Invoices" benchmark establishes the prior that single-shot wins on clean structured invoices. The *degraded-document* arm of H2 (where orchestrated + validator-retry is predicted to flip the lead) is less established in literature and is where HORUS aims for the more original empirical contribution. Also cited as the source for the inv-cdip (Tobacco subset) reference (per brainstorm v2 §15 Datasets).
