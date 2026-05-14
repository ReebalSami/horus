---
source_url: "https://huggingface.co/google/paligemma2-3b-mix-448"
source_title: "PaliGemma-2 3B (mix-448) — Google document-finetune VLM"
source_author: "Google DeepMind"
source_date: "2025-02-07"
retrieved_date: "2026-05-14"
extracted_concepts: []
tags: ["paligemma-2", "google", "paligemma", "task-prefix", "table-structure", "gemma-licensed-gated", "cohort-2025", "cohort-cat-3"]
archived_pdf: ""
status: stub
---

PaliGemma-2 3B (mix-448) — Google DeepMind's `paligemma` arch, ~3 B params, **`gemma` license (gated)**. Released Feb 7, 2025. arXiv 2412.03555 (PaliGemma-2 paper). The `mix-448` variant is the multi-task instruction-tuned model at 448×448 image resolution. Reported SOTA on table-structure benchmarks at its parameter tier. Uses **task-prefix prompt convention** (e.g., `"caption en"` + custom suffix) rather than free-form chat. **GATED on HF** — requires Google Gemma T&C acceptance on the user's HF account before download; ADR-009 §3.7 precondition for PR(b) Step 5. Per cohort ADR-009 §3.6 + COHORT_MANIFEST: bf16 on M1 Pro 16 GB fits comfortably; routes through `TransformersMPSExtractor` (no MLX port at the time of ADR-009 authoring). Cited in HORUS ADR-009 (this) as **Cat 3 — General multimodal VLMs** representative; tests whether table-structure-strong VLMs transfer to invoice-table extraction.
