---
source_url: "https://github.com/vllm-project/vllm-metal"
source_title: "vLLM-MLX / vllm-metal — vLLM-like inference for Apple Silicon (text + image + video + audio)"
source_author: "vLLM project + waybarrios + community contributors"
source_date: ""
retrieved_date: "2026-05-12"
extracted_concepts: []
tags: ["vllm", "vllm-mlx", "vllm-metal", "apple-silicon", "serving-framework", "openai-compatible-api", "considered-deferred", "layer-4", "adr-007"]
archived_pdf: ""
status: stub
---

vLLM-MLX (`waybarrios/vllm-mlx`) and vllm-metal (`vllm-project/vllm-metal`) — bring native Apple Silicon GPU acceleration (via MLX) to vLLM's serving infrastructure. Provides OpenAI-compatible API endpoints + continuous batching + paged-attention-like memory management over MLX-ported VLMs. PyPI `vllm-mlx 0.3.0` (Apache 2.0). Cited in HORUS as a **considered-deferred** candidate per ADR-007: not relevant for Layer-1 inference (M2D.5 pilot directly invokes `mlx_vlm.generate(...)`), but **forward-relevant for Layer 4** (FastAPI + Streamlit demo if the thesis ships an OpenAI-compatible-API surface with continuous batching). Per brainstorm v2 §9.1 amendment ("vllm-mlx Apple Silicon serving — verified ✅"), this candidate has explicit "to survey at cloud-baseline / serving ADR" reservation. ADR slot reserved for post-pilot, when the demo-shape decision is made — not introduced as a runtime dependency in ADR-007.
