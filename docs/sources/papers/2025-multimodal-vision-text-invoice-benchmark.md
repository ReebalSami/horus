---
source_url: "https://arxiv.org/abs/2509.04469"
source_title: "Multi-Modal Vision vs Text-Based Parsing: Benchmarking LLM Strategies for Invoice Processing"
source_author: "(TBD — first-author + co-authors to confirm at deep-read prior to thesis-citation)"
source_date: "2025-09"
retrieved_date: "2026-05-21"
extracted_concepts: []
tags: ["vlm", "invoice-extraction", "json-prompting", "zero-shot", "benchmark", "multimodal-llm"]
archived_pdf: ""
status: stub
---

Zero-shot benchmark of 8 multi-modal LLMs (including GPT-5, Gemini 2.5, Gemma 3) on three invoice datasets via JSON-schema prompting. Cited in HORUS ADR-018 §"Current-state survey" as the **canonical methodology precedent** for prompt-only structured-output probing on invoices: establishes that zero-shot JSON instruction is a defensible baseline against which orchestrated / fine-tuned approaches can be compared. The probe in issue #53 + ADR-018 follows the same shape (zero-shot, prompt-only, per-field F1 vs ground-truth) on 7 LOCAL VLMs (M1 Pro / 16 GB; no API-bound models). First-author + arXiv ID confirmation deferred to the deep-read pass at probe Step 6 (ADR-018 finalize); cite-as-stub for now per `horus-source-archival` (stub-then-clip pattern matches Obsidian web-clipper output shape).
