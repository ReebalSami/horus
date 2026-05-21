---
source_url: "https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/generate.py"
source_title: "MLX-VLM `GenerationResult` dataclass — return contract of `mlx_vlm.generate(...)`"
source_author: "Prince Canuma (Blaizzy / MLX-VLM)"
source_date: ""
retrieved_date: "2026-05-20"
extracted_concepts: []
tags: ["mlx-vlm", "mlx", "apple-silicon", "vlm-inference", "api-contract", "horus-adr-017"]
archived_pdf: ""
status: stub
---

MLX-VLM `GenerationResult` dataclass — the return type of `mlx_vlm.generate(model, processor, prompt, image_paths, max_tokens, ...)`. Defined at `mlx_vlm/generate.py:375-385`. Fields:

- `text: str` — generated text (excluding the prompt).
- `prompt_tokens: int` — tokens in the input prompt (encoder side).
- `generation_tokens: int` — tokens generated (decoder side).
- `prompt_tps: float` — prompt-encoding throughput (tokens/sec).
- `generation_tps: float` — generation throughput (tokens/sec) computed as `generation_tokens / generation_seconds` (time-weighted, matches Artificial Analysis methodology).
- `peak_memory: float` — peak MLX device memory in **GB** (populated via `mx.get_peak_memory() / 1024**3`).

**Older versions** of MLX-VLM (pre-0.4) returned only `str` from `generate(...)` instead of `GenerationResult`. HORUS's `MLXVLMExtractor.extract()` (`src/horus/vlm_extractor.py`) handles both shapes via `isinstance(output, str)` fallback to preserve backward compatibility.

Cited in HORUS as the authoritative source for ADR-017 §"Decision 1" (per-page perf fields populated from MLX backends) and ADR-017 §"Decision 2 (MLX-routed)" (true peak memory via `peak_memory` field). The supersession trigger for ADR-017 includes "MLX-VLM removes / renames `GenerationResult.peak_memory` / `generation_tokens` / `generation_tps`" — if those fields disappear in a 1.0 breaking change, HORUS must adopt a different approach. Sister stub: `mlx-vlm.md` (library-level overview, ADR-007 citation).
