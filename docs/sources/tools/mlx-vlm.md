---
source_url: "https://github.com/Blaizzy/mlx-vlm"
source_title: "MLX-VLM — Vision-Language Model inference and fine-tuning on Apple Silicon"
source_author: "Prince Canuma (Blaizzy) + open-source contributors"
source_date: "2026-05-06"
retrieved_date: "2026-05-12"
extracted_concepts: []
tags: ["mlx", "mlx-vlm", "vlm", "apple-silicon", "inference-framework", "fine-tuning", "primary-stack", "adr-007"]
archived_pdf: ""
status: stub
---

MLX-VLM — specialized Python package for inference and fine-tuning of Vision Language Models (VLMs) and Omni Models (VLMs with audio + video support) on Mac via the MLX framework. Distinct from `mlx-lm` (text-only LLM inference). PyPI version 0.5.0 (released 2026-05-06; 63 releases total; active 2026 maintenance). MIT licensed. Requires Python ≥ 3.10. Runtime deps include `mlx >= 0.31.2`, `mlx-lm >= 0.31.3`, `transformers >= 5.5.0`, `mlx-audio >= 0.4.3`, `datasets`, `Pillow`, `opencv-python`, `miniaudio`, `llguidance`, `fastapi`, `uvicorn`. Supports a unified interface across Qwen2-VL / Qwen3-VL / LLaVA / Phi-4 / DeepSeek-VL / Gemma-3n / Idefics3 (Granite-Docling) / and others. Multiple deployment surfaces: Python API, CLI, Gradio chat UI, FastAPI server with OpenAI-compatible endpoints. Advanced features: model quantization, LoRA / QLoRA fine-tuning, batch processing. Cited in HORUS as the **chosen primary inference framework** for the MLX-ported subset of brainstorm §8.1 (Granite-Docling-258M-mlx, Qwen3-VL-MLX, olmOCR-2-MLX, …) per ADR-007.
