---
source_url: "https://github.com/huggingface/transformers"
source_title: "🤗 Transformers — model-definition framework for state-of-the-art ML across text, vision, audio, video, and multimodal"
source_author: "Hugging Face Inc. + open-source contributors"
source_date: "2026-05-05"
retrieved_date: "2026-05-12"
extracted_concepts: []
tags: ["transformers", "huggingface", "vlm", "mps", "apple-silicon", "inference-framework", "fine-tuning", "fallback-stack", "adr-007"]
archived_pdf: ""
status: stub
---

HuggingFace Transformers — model-definition framework for state-of-the-art ML across text, vision, audio, video, and multimodal models, for both inference and training. PyPI version 5.8.0 (released 2026-05-05; 224 releases; active 2026 maintenance). Apache 2.0 licensed. Requires Python ≥ 3.10. Ships `py.typed` since 4.43 (clean mypy story). Apple GPU support via PyTorch's MPS backend (`device='mps'`) since 4.27.0 / PyTorch 2.0+. Canonical class for Idefics3 + Qwen-VL families: `AutoModelForImageTextToText`. Cited in HORUS as the **chosen fallback inference framework** for the non-MLX-ported subset of brainstorm §8.1 (PaddleOCR-VL 1.5, MinerU-2.5-Pro, Nanonets-OCR2 / dots.ocr where MLX ports are absent) per ADR-007. Also transitively required by `mlx-vlm` (`transformers >= 5.5.0`) and forward-required by the fine-tuning ecosystem (`peft`, `trl`, `accelerate`, `datasets`) per brainstorm §3 D8 ("fine-tuning central").
