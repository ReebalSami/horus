---
source_url: "https://huggingface.co/google/gemma-4-E4B-it"
source_title: "Gemma 4 E4B-it — Google native-multimodal instruction-tuned VLM"
source_author: "Google DeepMind"
source_date: "2026-05-07"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["gemma-4", "google", "gemma4", "native-multimodal", "matformer", "instruction-tuned", "apache-2", "cohort-2026", "cohort-cat-3", "mlx-port-adopted"]
archived_pdf: ""
status: stub
---

Gemma 4 E4B-it — Google DeepMind's instruction-tuned variant of the Gemma 4 base. `gemma4` arch (new family, **NOT** gemma3 or gemma3n). 7.99 B total params, **4 B effective via Matformer** (dynamic param routing per request). **License: apache-2.0** (NOT gated, unlike PaliGemma-2 or Gemma 3n which are gemma-licensed). Native multimodal: text + image + audio + video (any-to-any task tag on HF). Released April 2, 2026 (base) / May 7, 2026 (instruction-tuned); 7.6 M downloads on `gemma-4-E4B-it` at the time of ADR-009 authoring = heavily adopted in the few weeks since release. MLX 4-bit community port at `lmstudio-community/gemma-4-E4B-it-MLX-4bit` (368 K downloads); per ADR-009 §3.6 the chosen quant for this row to fit M1 Pro 16 GB. Free-form prompt convention (Cat 3 standard). Family: E2B / E4B / 26B-A4B (MoE) / 31B (Dense) per `huggingface.co/blog/gemma4`. Cited in HORUS ADR-009 (this) as **Cat 3 — General multimodal VLMs** representative; tests whether a general-purpose native-multimodal frontier model competes with purpose-trained doc-VLMs on German invoice extraction.

**Errata note**: HORUS researcher's initial spec at ADR-009 §3 Socratic walk Q1 said "Gemma-4-E4B 4B, April 2026, Apache 2.0" — verified correct against `huggingface.co/google/gemma-4-E4B` (HF MCP `repo_details` lookup, 2026-05-14). The authoring Cascade D's first HF API search for "Gemma 4 multimodal vision" returned empty (search-ranker heuristic miss); direct ID lookup confirmed existence. Lesson captured: direct `repo_details` checks trump search-ranker results.
