---
source_url: "https://huggingface.co/deepseek-ai/DeepSeek-OCR-2"
source_title: "DeepSeek-OCR 2: Visual Causal Flow"
source_author: "Wei, Haoran; Sun, Yaofeng; Li, Yukun (DeepSeek-AI)"
source_date: "2026-02-03"
retrieved_date: "2026-05-14"
verified_date: "2026-08-18"
extracted_concepts: []
tags: ["deepseek-ocr-2", "deepseek_vl_v2", "visual-causal-flow", "deepencoder-v2", "custom-code", "multilingual", "apache-2", "cohort-2026", "cohort-cat-2", "supersedes-v1"]
archived_pdf: ""
status: verified
verified: [authors, title, arxiv-id, contribution-claim]
---

> **Corrected 2026-08-18** (fifth-pass audit, F2). This record previously carried
> the title "DeepSeek-OCR-2 — improved Contexts Optical Compression OCR model"
> and `source_author: "DeepSeek AI"`. Both were wrong, and the title was the same
> class of defect as the `deepseekocr2026` bibliography entry it fed: "improved
> Contexts Optical Compression" appears nowhere in the work — it paraphrased the
> 2025 sibling's subtitle. The real subtitle is **Visual Causal Flow**, and the
> contribution is **DeepEncoder V2**, which dynamically reorders visual tokens by
> image semantics rather than feeding them to the LLM in raster-scan order. That
> is an ordering claim, not a compression increment. Verified against arXiv
> 2601.20552 and the Hugging Face papers record (paper authors as above; model
> `deepseek-ai/DeepSeek-OCR-2`, 3.39 B parameters).

DeepSeek-OCR-2 — Feb 2026 successor to DeepSeek-OCR v1 (Oct 2025). `deepseek_vl_v2` arch, 3.39 B params, apache-2.0 license (upgraded from MIT in v1), multilingual. **Architectural innovation** = DeepEncoder V2, which dynamically reorders a page's visual tokens according to image semantics instead of the rigid raster-scan order (top-left to bottom-right) conventional VLMs feed to the LLM — the paper's framing is that 2D understanding may be reachable through two cascaded 1D causal structures. It inherits, but does not itself advance, v1's Contexts Optical Compression (~20× token reduction). arXiv 2601.20552. **Requires `trust_remote_code=True`** (`custom_code` flag on HF); honest-disclosure surface per ADR-009 §3.7. Canonical prompt is `"<image>\nFree OCR."` (deepseek_vl_v2 token convention). MLX 4-bit quant available at `mlx-community/DeepSeek-OCR-2-4bit` (cohort ADR-009 §3.6 quant target for this row). Cited in HORUS ADR-009 (this) as **Cat 2 — Architecturally innovative** representative. Supersedes v1 cohort entry per user's expanded-scope §3.2 swap: v2 preserves the Contexts Optical Compression motivation while upgrading to apache-2.0 + improving downstream accuracy. Paper: `docs/sources/papers/deepseek-2026-deepseek-ocr-2.md`.
