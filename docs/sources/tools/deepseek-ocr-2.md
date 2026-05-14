---
source_url: "https://huggingface.co/deepseek-ai/DeepSeek-OCR-2"
source_title: "DeepSeek-OCR-2 — improved Contexts Optical Compression OCR model"
source_author: "DeepSeek AI"
source_date: "2026-02-03"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["deepseek-ocr-2", "deepseek_vl_v2", "contexts-optical-compression", "custom-code", "multilingual", "apache-2", "cohort-2026", "cohort-cat-2", "supersedes-v1"]
archived_pdf: ""
status: stub
---

DeepSeek-OCR-2 — Feb 2026 successor to DeepSeek-OCR v1 (Oct 2025). `deepseek_vl_v2` arch, 3.39 B params, apache-2.0 license (upgraded from MIT in v1), multilingual. **Architectural innovation** = Contexts Optical Compression (~20× token reduction by feeding the VLM with a vision-encoded representation of the document instead of native vision-language tokens). arXiv 2601.20552. **Requires `trust_remote_code=True`** (`custom_code` flag on HF); honest-disclosure surface per ADR-009 §3.7. Canonical prompt is `"<image>\nFree OCR."` (deepseek_vl_v2 token convention). MLX 4-bit quant available at `mlx-community/DeepSeek-OCR-2-4bit` (cohort ADR-009 §3.6 quant target for this row). Cited in HORUS ADR-009 (this) as **Cat 2 — Architecturally innovative** representative. Supersedes v1 cohort entry per user's expanded-scope §3.2 swap: v2 preserves the Contexts Optical Compression motivation while upgrading to apache-2.0 + improving downstream accuracy. Paper: `docs/sources/papers/deepseek-2026-deepseek-ocr-2.md`.
