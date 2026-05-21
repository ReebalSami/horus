---
source_url: "https://artificialanalysis.ai/methodology/performance-benchmarking"
source_title: "Artificial Analysis — Language Model API Performance Benchmarking Methodology"
source_author: "Artificial Analysis"
source_date: ""
retrieved_date: "2026-05-20"
extracted_concepts: []
tags: ["benchmark-methodology", "tokens-per-second", "throughput", "llm-evaluation", "horus-adr-017"]
archived_pdf: ""
status: stub
---

Artificial Analysis Language Model API Performance Benchmarking Methodology page — verbatim canonical definitions used in HORUS ADR-017 (Amendment 1) for the dual-TPS metric design.

**Verified definitions** (full text quoted in ADR-017 §"Amendment 1"; web-fetched 2026-05-20):

> **Output Speed (output tokens per second)**: The average number of tokens received per second, **after the first token is received**.

> **End-to-End Response Time**: The total time to receive a complete response, including input processing time, model reasoning time, and answer generation time.

> **Token Measurement**: All measurements of 'tokens' on Artificial Analysis are measured as OpenAI GPT-4 tokens as counted by OpenAI's tiktoken library (o200k_base). This standardizes the number of tokens counted across different models (with different tokenizers).

**Key implications for HORUS** (cited in ADR-017 Amendment 1):

1. **AA "Output Speed" is decode-only** — measured AFTER the first token arrives. Maps to HORUS's `perf.decode_tps_mean` (when the backend exposes decode-only timing). MLX-VLM's `GenerationResult.generation_tps` IS decode-only and matches this definition; Transformers-MPS cannot expose decode-only timing via public `transformers.generate(...)` API → `decode_tps = 0.0` sentinel + `perf.decode_tps_available = "false"` tag.
2. **AA standardises on tiktoken `o200k_base`** for cross-model comparability — different model tokenizers fragment the same text into different counts. HORUS uses native per-model tokenizers for `decode_tps` and `inference_tps` (within-model + same-tokenizer-cohort comparison); cross-model standardised TPS via tiktoken is **deferred to the H4 hypothesis test** per ADR-017 Amendment 1 §"Cross-model standardisation (still deferred)".
3. **Output Speed is time-weighted across the generation phase**, not arithmetic mean. HORUS implements this as `total_gen_tokens / sum(gen_tokens / gen_tps)` per page (page-level decode_seconds derived from per-page MLX-VLM-reported gen_tps).

**Pre-Amendment-1 misuse**: the original ADR-017 §"Decision 5 (D1.A)" cited this page as authority for `total_gen_tokens / extract_seconds_pages_total`. That formula is END-TO-END (includes prompt encoding) and uses native tokenizers — it doesn't match AA's "Output Speed" on either axis. Amendment 1 corrects the misuse by splitting the metric into two with explicit, separately-named semantics.
