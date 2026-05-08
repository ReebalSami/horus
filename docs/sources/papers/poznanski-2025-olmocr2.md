---
source_url: "https://allenai.org/blog/olmocr2"
source_title: "olmOCR-2 (release)"
source_author: "AllenAI / Jake Poznanski et al."
source_date: "2025-10"
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["vlm", "ocr-free", "rlvr", "open-source", "benchmark", "olmocr-bench"]
archived_pdf: ""
status: stub
---

olmOCR-2-7B (AllenAI). RLVR-trained (Reinforcement Learning from Verifiable Rewards) document VLM. Reports ~82.5 on olmOCR-Bench. Strongest open-source single-model document VLM as of late 2025 (per brainstorm v2 §7.1). Cited in HORUS as a **primary Layer-1 candidate** for the local document-VLM cohort comparison; the strong-baseline reference for both the VLM cohort and the orchestrated-Docling pipeline. Larger than Granite-Docling (7B vs 258M) — relevant for the M1-Pro inference-budget question (8 GB unified RAM — possibly tight for 7B at fp16 even with MLX). To be benchmarked at the experiment phase. arXiv preprint and full technical report: search arXiv 2025 (specific arxiv ID to be confirmed at deep-read; release blog provides primary handle).
