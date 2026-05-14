---
source_url: "https://huggingface.co/allenai/olmOCR-2-7B-1025"
source_title: "olmOCR-2 7B — Allen AI RLVR-trained document VLM"
source_author: "Allen Institute for AI"
source_date: "2025-10-22"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["olmocr-2", "allenai", "qwen2_5_vl", "rlvr", "document-vlm", "english-only", "cohort-2025", "apache-2", "cohort-cat-1", "within-lab-pair-with-molmo"]
archived_pdf: ""
status: stub
---

olmOCR-2 7B — Allen AI's `qwen2_5_vl` document VLM (8.29 B total params; base = Qwen2.5-VL-7B-Instruct + RLVR fine-tuning on doc tasks). Apache-2.0; **EN-only** per HF `language: en` tag (verified by web research at brainstorm v2 §9.1 cohort-update table). Canonical prompt is `"Recognize all the text in the image."` returning raw text. MLX 4-bit quant available at `mlx-community/olmOCR-2-7B-1025-mlx-4bit` (cohort ADR-009 §3.6 quant target for this row to fit M1 Pro 16 GB). Cited in HORUS ADR-009 (this) as **Cat 1 — End-to-end doc-VLMs**, methodologically informative for HORUS's RQ on architectural fitness because it forms a **within-lab pair with Molmo-7B-D** (both Allen AI; olmOCR-2 = doc-specialised, Molmo = general multimodal). Paper: `docs/sources/papers/poznanski-2025-olmocr2.md`. EN-skew is a known caveat for German invoice extraction — pilot #13 evidence.
