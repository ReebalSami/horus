---
source_url: "https://arxiv.org/abs/2510.18234"
source_title: "DeepSeek-OCR: Contexts Optical Compression"
source_author: "DeepSeek AI"
source_date: "2025-10"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["deepseek-ocr", "contexts-optical-compression", "deepseek_vl_v2", "token-compression", "vlm", "cohort-2025", "paper-v1"]
archived_pdf: ""
status: stub
---

DeepSeek-OCR (v1) — Oct 2025 paper from DeepSeek AI introducing **Contexts Optical Compression** (CoC): the document image is first encoded into a compact visual representation that is then routed through the LM as ~20× fewer tokens than the equivalent vision-language token sequence. The compression makes 1000-page document processing tractable on consumer GPUs while preserving downstream OCR accuracy. arXiv 2510.18234. Architecture: `deepseek_vl_v2` (custom code; `trust_remote_code=True`). Model card at `deepseek-ai/DeepSeek-OCR` (24.5 M downloads at ADR-009 authoring). Cited in HORUS ADR-009 §"Current-state survey" as the **architectural-innovation precedent** that motivates Cat 2 cohort inclusion; superseded operationally by DeepSeek-OCR-2 (Feb 2026, see `deepseek-2026-deepseek-ocr-2.md`) which improves the same compression scheme. Both papers cited together to capture the lineage.
