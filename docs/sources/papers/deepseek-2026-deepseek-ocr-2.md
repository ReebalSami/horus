---
source_url: "https://arxiv.org/abs/2601.20552"
source_title: "DeepSeek-OCR 2: Visual Causal Flow"
source_author: "Wei, Haoran; Sun, Yaofeng; Li, Yukun (DeepSeek-AI)"
source_date: "2026-01-28"
retrieved_date: "2026-05-14"
verified_date: "2026-08-18"
extracted_concepts: []
tags: ["deepseek-ocr-2", "visual-causal-flow", "deepencoder-v2", "visual-token-ordering", "deepseek_vl_v2", "vlm", "cohort-2026", "paper-v2", "supersedes-v1"]
archived_pdf: ""
status: verified
verified: [authors, title, arxiv-id, published-date, contribution-claim]
---

> **Corrected 2026-08-18** (fifth-pass audit, F2). Title was **invented**:
> "improved Contexts Optical Compression" appears nowhere in the paper and
> paraphrased the 2025 sibling's subtitle. Author was the corporate placeholder
> "DeepSeek AI". This record is what fed the same two defects into the
> `deepseekocr2026` bibliography entry — the bib was repaired in the same pass.
> Verified against arXiv 2601.20552 and the Hugging Face papers record.

The paper's actual contribution is **DeepEncoder V2**: an encoder that dynamically
reorders visual tokens according to image semantics, instead of the raster-scan
order (top-left to bottom-right) with fixed positional encoding that conventional
VLMs use when feeding visual tokens to an LLM. The motivation is that human
reading follows semantically coherent scan paths, especially on complex layouts,
so the paper asks whether 2D understanding can be achieved through two cascaded
1D causal structures. Published 2026-01-28; weights at
`deepseek-ai/DeepSeek-OCR-2` (3.39 B parameters).

**Not a compression paper.** It inherits v1's Contexts Optical Compression
framing but does not advance the compression ratio; the claim is about token
*order*. Conflating the two is the error this record previously made.

DeepSeek-OCR-2 — Feb 2026 follow-up paper from DeepSeek AI building on v1's Contexts Optical Compression (CoC). Improvements over v1: license upgraded to apache-2.0 (v1 was MIT), accuracy gains on OmniDocBench, expanded multilingual coverage. arXiv 2601.20552. Architecture preserved (`deepseek_vl_v2`; still requires `trust_remote_code=True`). Model card at `deepseek-ai/DeepSeek-OCR-2` (5.4 M downloads + 953 likes at ADR-009 authoring; **heavily adopted within 3 months** of release). Cited in HORUS ADR-009 §"Current-state survey" + §"Decision" as the **Cat 2 — Architecturally innovative** representative (replacing v1 per user's expanded-scope §3.2 swap; the CoC innovation that motivates inclusion is preserved/improved in v2). Smoke target = `mlx-community/DeepSeek-OCR-2-4bit` MLX 4-bit port (cohort ADR-009 §3.6 quant target). Tool stub: `docs/sources/tools/deepseek-ocr-2.md`.
