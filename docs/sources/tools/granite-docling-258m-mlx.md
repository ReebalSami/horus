---
source_url: "https://huggingface.co/ibm-granite/granite-docling-258M-mlx"
source_title: "Granite-Docling 258M (MLX port) — IBM Research compact document VLM"
source_author: "IBM Research"
source_date: "2025-09-17"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["granite-docling", "ibm", "idefics3", "mlx", "doctags", "cohort-2025", "apache-2", "cohort-cat-1", "baseline-of-failure"]
archived_pdf: ""
status: stub
---

Granite-Docling 258M — IBM Research's compact document VLM (`idefics3` arch, 315 M total params, Apache-2.0, EN-only). Official MLX port published at `ibm-granite/granite-docling-258M-mlx` for Apple Silicon Metal execution; canonical prompt is `"Convert this page to docling."` producing DocTags structured output that Docling can parse. arXiv 2501.17887. Cited in HORUS ADR-007 (dual-track inference framework) as the smoke-evidence target and in ADR-009 (this) as the **Cat 1 baseline-of-failure** anchor: ADR-007 §Decision finding 3 empirically excluded the 258M tier from primary candidacy; ADR-009 §3.9 re-includes it as the cohort's lower-bound reference point. Already in `pyproject.toml` deps via `mlx-vlm>=0.5.0` (Idefics3 routing); zero-friction smoke for PR(a) Step 5.
