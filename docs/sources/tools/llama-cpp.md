---
source_url: "https://github.com/ggerganov/llama.cpp"
source_title: "llama.cpp — C/C++ inference for LLMs"
source_author: "Georgi Gerganov + open-source contributors"
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["llama-cpp", "inference-framework", "gguf", "metal", "apple-silicon", "benchmark-comparand"]
archived_pdf: ""
status: stub
---

llama.cpp — pure-C/C++ LLM-inference engine; the de-facto runtime for GGUF-quantized model checkpoints. Apple-Silicon-optimized via Metal backend. Reported throughput on M-class Macs ~150 tok/s for short context (per brainstorm v2 §7.2 — directional). Cited in HORUS as a **fallback inference path** if MLX support for a target VLM is incomplete or if the quantization recipe (Q4_K_M, Q5_K, etc.) is only available in GGUF. Relevant especially for the larger §7.1-cohort VLMs (≥3B params) where unified-memory pressure on M1 Pro 8 GB might force aggressive quantization.
