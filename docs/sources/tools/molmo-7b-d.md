---
source_url: "https://huggingface.co/allenai/Molmo-7B-D-0924"
source_title: "Molmo-7B-D — Allen AI general-purpose multimodal VLM"
source_author: "Allen Institute for AI"
source_date: "2025-12-15"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["molmo", "allenai", "pixmo", "qwen2-base", "custom-code", "english-only", "apache-2", "cohort-2024-25", "cohort-cat-3", "within-lab-pair-with-olmocr2"]
archived_pdf: ""
status: stub
---

Molmo-7B-D-0924 — Allen AI's `molmo` arch, 8.02 B total params (base = Qwen2-7B + Molmo VL training on the PixMo dataset). Apache-2.0. **EN-only** per HF `language: en` tag. **Requires `trust_remote_code=True`** (`custom_code` flag); honest-disclosure surface per ADR-009 §3.7. arXiv 2409.17146 (Molmo paper). The `-D` variant = Dense (vs `-O` = Olmo-base variant; we pick D for the apples-to-apples Qwen2-base comparison with olmOCR-2's Qwen2.5-VL-7B base). Cited in HORUS ADR-009 (this) as **Cat 3 — General multimodal VLMs** representative; specifically chosen as the **within-lab pair to olmOCR-2** (both Allen AI; same lab philosophy + general engineering quality; one specialised for documents via RLVR, one general multimodal via PixMo). The pair is a **methodological control** for HORUS's H1 (within-lab variation tests whether doc-specialisation outweighs general-multimodal scale at the 7-8 B tier on German invoice extraction). bf16 on 8 B may OOM on M1 Pro 16 GB; if MLX port exists at install time (PR(b)), switch to 4-bit per ADR-009 §3.6; otherwise document OOM as a Cat 3 failure mode (per ADR-009 §3.6 non-comparability footnote).
