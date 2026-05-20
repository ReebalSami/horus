---
source_url: "https://artificialanalysis.ai/methodology/intelligence-benchmarking-methodology"
source_title: "Artificial Analysis — Intelligence Benchmarking Methodology (Output Tokens per Second)"
source_author: "Artificial Analysis"
source_date: ""
retrieved_date: "2026-05-20"
extracted_concepts: []
tags: ["benchmark-methodology", "tokens-per-second", "throughput", "llm-evaluation", "horus-adr-017"]
archived_pdf: ""
status: stub
---

Artificial Analysis methodology page defining **Output Tokens per Second (TPS)** as the canonical end-to-end throughput metric for LLM/VLM inference. Definition: "TPS measures the rate at which the model generates output tokens, calculated as total output tokens divided by end-to-end inference time (input sent → final output token received)." Critically, this is **time-weighted throughput** (`total_tokens / total_seconds`), NOT the arithmetic mean of per-step or per-page TPS values — the latter biases toward short / fast outputs. Cited in HORUS ADR-017 §"Decision 5 (D1.A)" as the authoritative source for the `mean_tps = total_gen_tokens / extract_seconds_pages_total` formula in `src/horus/eval/harness.py`. The methodology also notes that **per-model native tokenizers produce non-comparable TPS values across models** — different tokenizers fragment the same text into different counts. HORUS reports native TPS for within-model comparison and chars/sec as the cross-model proxy (per ADR-017 §D4); cross-model standardised TPS via a fixed tokenizer (e.g., `cl100k_base` via `tiktoken`) is deferred to the H4 hypothesis test.
