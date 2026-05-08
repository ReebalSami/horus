---
source_url: "https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion"
source_title: "Granite-Docling: end-to-end document conversion (announcement)"
source_author: "IBM Research"
source_date: "2025-10"
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["vlm", "ocr-free", "single-shot", "apple-silicon", "mlx", "doctags", "apache-2"]
archived_pdf: ""
status: stub
---

IBM Granite-Docling 258M (Apache 2.0). Single-pass document parsing into DocTags markup. Built on Idefics3 + SigLIP2 + Granite 165M LLM (which itself succeeds SmolDocling 256M). Native MLX support for Apple Silicon. Released Oct 2025 as part of IBM's Docling open-source pipeline (see `docs/sources/tools/docling.md`). Cited in HORUS as a **primary Layer-1 candidate** for the local document-VLM thesis: small parameter count + permissive licence + MLX inference path + DocTags structured-output format make it a frontrunner for the M1-Pro local-inference scenario (per brainstorm v2 §7.1 + §7.8). To be evaluated against olmOCR-2, Nanonets-OCR2, and the larger §7.1 cohort at the experiment phase.
