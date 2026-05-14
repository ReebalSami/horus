---
source_url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct"
source_title: "Qwen3-VL-4B-Instruct — Alibaba Qwen smaller VLM variant"
source_author: "Alibaba Qwen Team"
source_date: "2025-10-15"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["qwen3-vl", "alibaba", "qwen3_vl", "multilingual", "instruction-tuned", "apache-2", "cohort-2025", "cohort-cat-3"]
archived_pdf: ""
status: stub
---

Qwen3-VL-4B-Instruct — Alibaba's `qwen3_vl` arch, 4.44 B total params, apache-2.0, multilingual. Smaller variant of the Qwen3-VL family (8B / 30B-A3B-Instruct MoE variants exist for compute-permitted runs). Released Oct 15, 2025; arXiv 2505.09388 (Qwen3-VL family paper). Brainstorm v2 §9.1 originally specified the 8B + 30B-A3B variants; ADR-009 §3.2 narrows to the **4B variant** to fit M1 Pro 16 GB cohort comparability (the 8B + 30B compute exceeds local hardware ceiling per `know-your-hardware` rule). MLX port availability TBD at install time (PR(b)); if no MLX port, fall back to `TransformersMPSExtractor` per ADR-009 §8 O6 + COHORT_MANIFEST entry. Free-form prompt convention (Cat 3 standard). Cited in HORUS ADR-009 (this) as **Cat 3 — General multimodal VLMs** representative; tests whether a multilingual general VLM (HF tags include EN, zh) competes with doc-specialised models on German invoice extraction.
