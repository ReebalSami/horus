---
source_url: "https://arxiv.org/abs/2509.04469"
source_title: "Multi-Modal Vision vs Text-Based Parsing: Benchmarking LLM Strategies for Invoice Processing"
source_author: "Berghaus, Berger, Hillebrand, Cvejoski, Sifa (Fraunhofer IAIS + Lamarr Institute)"
source_date: "2025-09"
retrieved_date: "2026-05-21"
extracted_concepts: []
tags: ["vlm", "invoice-extraction", "json-prompting", "zero-shot", "benchmark", "multimodal-llm", "duplicate-consolidated"]
archived_pdf: ""
status: stub
---

> **DUPLICATE — consolidated 2026-08-09.** This record and
> `berghaus-2025-multimodal-invoice-parsing.md` archive the **same paper** (arXiv 2509.04469);
> the two stubs were created independently in different sessions (2026-05-21 here, 2026-05-06
> there) under different working titles. The **canonical record is
> `berghaus-2025-multimodal-invoice-parsing.md`**, which carries the verified authorship and the
> verified headline figures. The thesis cites that one; the bibliography has a single entry.
> Retained rather than deleted per ADR-011 (supersession over deletion) because ADR-018's
> `Current-state survey` cites *this* path, and that citation must keep resolving. Authorship
> above back-filled from the canonical record so the two no longer disagree.

Zero-shot benchmark of 8 multi-modal LLMs (including GPT-5, Gemini 2.5, Gemma 3) on three invoice datasets via JSON-schema prompting. Cited in HORUS ADR-018 §"Current-state survey" as the **canonical methodology precedent** for prompt-only structured-output probing on invoices: establishes that zero-shot JSON instruction is a defensible baseline against which orchestrated / fine-tuned approaches can be compared. The probe in issue #53 + ADR-018 follows the same shape (zero-shot, prompt-only, per-field F1 vs ground-truth) on 7 LOCAL VLMs (M1 Pro / 16 GB; no API-bound models). First-author + arXiv ID confirmation deferred to the deep-read pass at probe Step 6 (ADR-018 finalize); cite-as-stub for now per `horus-source-archival` (stub-then-clip pattern matches Obsidian web-clipper output shape).
