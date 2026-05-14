---
source_url: "https://arxiv.org/abs/2601.20552"
source_title: "DeepSeek-OCR-2: improved Contexts Optical Compression"
source_author: "DeepSeek AI"
source_date: "2026-02"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["deepseek-ocr-2", "contexts-optical-compression", "deepseek_vl_v2", "token-compression", "vlm", "cohort-2026", "paper-v2", "supersedes-v1"]
archived_pdf: ""
status: stub
---

DeepSeek-OCR-2 — Feb 2026 follow-up paper from DeepSeek AI building on v1's Contexts Optical Compression (CoC). Improvements over v1: license upgraded to apache-2.0 (v1 was MIT), accuracy gains on OmniDocBench, expanded multilingual coverage. arXiv 2601.20552. Architecture preserved (`deepseek_vl_v2`; still requires `trust_remote_code=True`). Model card at `deepseek-ai/DeepSeek-OCR-2` (5.4 M downloads + 953 likes at ADR-009 authoring; **heavily adopted within 3 months** of release). Cited in HORUS ADR-009 §"Current-state survey" + §"Decision" as the **Cat 2 — Architecturally innovative** representative (replacing v1 per user's expanded-scope §3.2 swap; the CoC innovation that motivates inclusion is preserved/improved in v2). Smoke target = `mlx-community/DeepSeek-OCR-2-4bit` MLX 4-bit port (cohort ADR-009 §3.6 quant target). Tool stub: `docs/sources/tools/deepseek-ocr-2.md`.
