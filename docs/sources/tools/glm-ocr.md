---
source_url: "https://huggingface.co/zai-org/GLM-OCR"
source_title: "GLM-OCR 0.9B — Zhipu AI OmniDocBench V1.5 SOTA OCR"
source_author: "Zhipu AI (Z.ai)"
source_date: "2026-02-15"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["glm-ocr", "zhipu", "z-ai", "glm4v", "omnidocbench-v15-sota", "0_9b", "cohort-2026", "cohort-cat-2", "transformers-v5-conflict", "install-risk"]
archived_pdf: ""
status: stub
---

GLM-OCR — Zhipu AI / Z.ai's 0.9 B param document OCR model released Feb 2026. **94.62 OmniDocBench V1.5** = `#1 overall` (beats Qwen3-VL-235B at 260× the parameter count; closes the gap to Gemini 3 Pro at 90.33). Likely `glm4v` arch. License: likely MIT (HF model card load + GitHub `zai-org/GLM-OCR` repo confirmed accessible; pending direct verification). **Critical install risk per ADR-009 §3.7**: official model card pins `transformers<5.0.0`, which conflicts with HORUS's `transformers>=5.5.0` pyproject pin. Resolution paths to attempt in PR(b) order: vLLM → Ollama → SGLang → direct MLX port (TBD community port at the time of ADR-009 authoring). **Escalation rule (locked)**: if no path works, file `ReebalSami/horus#15+` sub-issue rather than silently dropping; the 0.9B-tier SOTA claim is too load-bearing to omit without explicit sprint review. Cited in HORUS ADR-009 (this) as **Cat 2 — Architecturally innovative** representative (sub-billion-param SOTA via novel training; not yet a publicly-claimed architectural novelty beyond efficient training).
