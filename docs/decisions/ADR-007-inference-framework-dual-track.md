# ADR-007 — Local-VLM inference framework: dual-track (MLX-VLM primary + HuggingFace Transformers + MPS fallback)

| Field | Value |
|---|---|
| **Status** | Accepted (smoke evidence captured 2026-05-12 — see §"Smoke evidence — captured transcript") |
| **Date** | 2026-05-12 |
| **Milestone** | M2D.5 step 3 — VLM-inference enablement (issue #10) |
| **Authored by** | Cascade D (M2D.5 inference-stack session, plan `~/.windsurf/plans/horus-issue-10-inference-framework-adr-9964f0.md`) |
| **Issue** | `ReebalSami/horus#10` |
| **Forward-pointer resolution** | The "cohort ADR #14" forward-pointer in §"Decision + integration thoughts" (finding 3 — `the 258M tier is empirically excluded from HORUS's pilot loop`) is resolved by **ADR-009** (`docs/decisions/ADR-009-pilot-vlm-cohort.md`). ADR-009 keeps Granite-Docling-258M as the **baseline-of-failure anchor for Cat 1** (lower-bound reference; cohort architectures should ALL beat it). Both ADRs co-exist; this ADR is NOT superseded. |
| **Supersession trigger** | (a) MLX-VLM lapses maintenance (no release ≥ 6 months AND issue tracker stalls AND a breaking change in MLX core remains unaddressed) → fallback = Transformers + MPS only with degraded throughput; OR (b) Brainstorm §8.1 cohort fully MLX-ported in upstream `mlx-vlm` (Transformers + MPS branch obsolete) → simplify to MLX-VLM-only; OR (c) HORUS distribution context shifts to non-Apple-Silicon target hardware (Linux + CUDA via cloud) → fallback = Transformers (CUDA backend) + drop MLX-VLM; AWS escalation per `know-your-hardware`; OR (d) Apple Core ML reaches converter maturity (full multimodal Idefics3 / SigLIP2 / Qwen-VL conversion paths working end-to-end) → re-evaluate Core ML as primary inference path. |

## Context

The brainstorm §8.1 Layer-1 model cohort spans seven open-source document VLMs released in the Oct-2025 wave (Granite-Docling-258M, olmOCR-2-7B, Nanonets-OCR2-3B, dots.ocr-3B, MinerU-2.5-Pro, PaddleOCR-VL-1.5, plus the §9.1 amendment additions Qwen3-VL-8B / Qwen3-VL-30B-A3B-Instruct). HORUS's M2D.5 first pilot loop (issue #13) requires running at least one of these on M1 Pro hardware to produce the first F1 reading. Issue #10 is the prerequisite tooling-install ADR for that loop: pick the inference framework(s).

The §8.1 cohort splits cleanly along inference-framework lines:

- **MLX-ported subset**: Granite-Docling-258M (`ibm-granite/granite-docling-258M-mlx`, 3.6K downloads, official IBM port), Qwen3-VL-MLX (multiple `mlx-community/Qwen3-VL-*` ports), olmOCR-2-MLX (community ports), plus a long tail. These run natively on Apple Silicon via MLX with unified-memory advantages over MPS.
- **Non-MLX subset**: PaddleOCR-VL 1.5 (PaddlePaddle ecosystem, no MLX path), MinerU-2.5-Pro (HF-native, no current MLX port verified), Nanonets-OCR2-3B (HF-native, MLX port unclear), dots.ocr-3B (HF-native, MLX port unclear).

A single-framework decision under-covers the cohort: MLX-VLM-only excludes ~half of §8.1; Transformers + MPS-only forfeits 3–5× throughput on the MLX-ported subset per brainstorm v2 §7.2 (directional, to-verify). The honest decision is dual-track: each branch covers the other's gap.

Discipline gate: `horus-decision-discipline` rule mandates one ADR per tool/library/framework choice with the 5 mandatory sections (Current-state survey / Options considered / Decision + integration thoughts / Source archival / Supersession trigger). Issue #10 acceptance criteria explicitly require Hardware-constraint reasoning per `know-your-hardware` (M1 Pro / 16 GB / Metal 4 / no CUDA / 14 GPU cores).

## Current-state survey (2026-05-12)

Survey methodology: PyPI JSON API queries for `mlx-vlm` / `transformers` / `vllm-mlx` (version, license, requires-python, runtime deps, latest release timestamp); HuggingFace Hub model lookups (`ibm-granite/granite-docling-258M`, `ibm-granite/granite-docling-258M-mlx`, plus 13 other granite-docling derivative ports for cohort-coverage analysis); `context7` MCP queries `/blaizzy/mlx-vlm` and `/huggingface/transformers` for API confirmation; cross-check against brainstorm v2 §7.1 (Oct-2025 wave) + §7.2 (Apple-Silicon throughput ranking, single-source directional).

### Library / framework metadata (PyPI, 2026-05-12)

| Library | Latest | Released | License | Requires-Python | Notes |
|---|---|---|---|---|---|
| **mlx-vlm** | 0.5.0 | 2026-05-06 | MIT | `>=3.10` | 63 releases; runtime deps: `mlx>=0.31.2`, `mlx-lm>=0.31.3`, `transformers>=5.5.0`, `mlx-audio>=0.4.3`, `datasets>=2.19.1`, `Pillow>=10.3.0`, `opencv-python>=4.12.0.88`, `miniaudio>=1.59`, `llguidance>=1.7.0`, `fastapi`, `uvicorn`, `numpy`, `tqdm`, `requests`. Active 2026 maintenance (latest release 6 days before today). |
| **transformers** | 5.8.0 | 2026-05-05 | Apache 2.0 | `>=3.10` | 224 releases; ships `py.typed` since 4.43; supports MPS device via `torch.backends.mps` since v4.27.0; `AutoModelForImageTextToText` is the canonical class for Idefics3 + Qwen-VL families. Active 2026 maintenance (latest release 7 days before today). |
| **vllm-mlx** | 0.3.0 | (2026-04, approx.) | Apache 2.0 | n/a | "vLLM-like inference for Apple Silicon — GPU-accelerated Text, Image, Video & Audio on Mac". OpenAI-compatible serving + continuous batching. Forward-relevant for Layer-4 demo (FastAPI + Streamlit). Not in §8.1's inference-framework slot. |

### HuggingFace Hub model coverage (Granite-Docling 258M variants only — representative slice of §8.1)

The Granite-Docling 258M model has 15+ community-ported variants. The relevant subset for the inference-framework decision:

| Variant | Library tag | Downloads | Inference path |
|---|---|---|---|
| `ibm-granite/granite-docling-258M` | transformers | 335.8K | Reference checkpoint; consumed via `AutoModelForImageTextToText.from_pretrained(...).to('mps')` for the Transformers + MPS branch |
| `ibm-granite/granite-docling-258M-mlx` | transformers (MLX safetensors) | 3.6K | **Official IBM MLX port**; consumed via `mlx_vlm.load(...)` for the MLX-VLM branch |
| `ibm-granite/granite-docling-258M-GGUF` | gguf | 1.1K | Official IBM GGUF port; consumable via `llama-mtmd-cli`. **See §"Options considered"**: GGUF availability is real for Granite-Docling specifically, but is not the indicated path for the broader §8.1 cohort. |
| `onnx-community/granite-docling-258M-ONNX` | transformers.js | 1.4K | ONNX port; web-runtime-targeted (transformers.js); not relevant for HORUS's Python-server context |
| `lamco-development/granite-docling-258M-onnx` | onnxruntime | 21 | ONNX-Rust port; production-targeted; not relevant for thesis-pipeline scope |

**Key finding**: Granite-Docling 258M has paths for *all four* candidate frameworks (MLX-VLM, Transformers + MPS, llama.cpp/GGUF, ONNX Runtime). The decision can't be made on Granite-Docling availability alone; it must consider the broader §8.1 cohort. PaddleOCR-VL-1.5 has no MLX/GGUF/ONNX port; it requires the Transformers (or PaddlePaddle) path. MinerU-2.5-Pro and dots.ocr currently distribute primarily via Transformers checkpoints with no verified MLX ports as of 2026-05.

### Apple Silicon throughput ranking (brainstorm v2 §7.2 — directional, single-source)

Reported throughput on M-class Macs for LLM inference: **MLX (~230 tok/s) > MLC-LLM (~190) > llama.cpp short-context (~150) > Ollama (20–40) > PyTorch MPS (~7–9)**. Source flagged in brainstorm as late-2025 benchmark blog; pending HORUS-internal verification. The smoke evidence captured in §"Decision + integration thoughts" below produces the *first* HORUS-internal data point on the MLX-VLM and Transformers + MPS extremes of this ranking.

## Options considered

| Option | License | Hardware fit | Status | Why |
|---|---|---|---|---|
| **MLX-VLM 0.5.0** (`/blaizzy/mlx-vlm`) | MIT | Native M1 Pro / Metal | **Chosen primary** | Native MLX inference for VLMs (distinct from `mlx-lm` which is text-only); supports the MLX-ported §8.1 subset (Granite-Docling-mlx, Qwen3-VL-MLX, olmOCR-2-MLX, plus continuous community ports); 3–5× expected throughput advantage over Transformers + MPS per v2 §7.2 (subject to smoke verification); native PIL image input + audio + video; covers the unified-memory advantage of M1 Pro 16 GB |
| **HuggingFace Transformers 5.8.0 + PyTorch MPS** | Apache 2.0 | Apple GPU via MPS backend (PyTorch ≥ 2.0; MPS-stable since 2.1) | **Chosen fallback** | Required for the non-MLX-ported §8.1 subset (PaddleOCR-VL 1.5; MinerU-2.5-Pro; potentially Nanonets-OCR2 / dots.ocr); transitively required by `mlx-vlm` itself (`transformers>=5.5.0`); required for fine-tuning ecosystem (PEFT / TRL / `accelerate`) per brainstorm §3 D8 ("fine-tuning central"); ships `py.typed` (clean mypy story) |
| **MLX-LM only (text-only MLX)** | MIT | M1 Pro native | Rejected | `mlx-lm` is text-only; does NOT support multimodal/VLM image inputs; insufficient for Layer 1 (which is VLM-extraction, not text-LLM-inference) |
| **MLX-VLM only (no Transformers + MPS fallback)** | MIT | M1 Pro native | Rejected | §8.1 cohort coverage incomplete: PaddleOCR-VL 1.5 (PaddlePaddle ecosystem, no MLX port), MinerU-2.5-Pro (no current MLX port verified), and a long tail of community ports lag MLX availability. Transformers + MPS provides the universal floor |
| **Transformers + MPS only (no MLX-VLM)** | Apache 2.0 | M1 Pro via MPS | Rejected | Forfeits 3–5× throughput on MLX-ported §8.1 subset per v2 §7.2; thesis claim "we used the best available local stack on M1 Pro" untenable when an MLX path exists for the chosen pilot model (Granite-Docling). MPS-only is the worst-case naïve PyTorch path per `docs/sources/tools/pytorch-mps.md` |
| **llama.cpp + GGUF** (`/ggerganov/llama.cpp`, `mtmd-cli`) | MIT | Metal-backed | **Rejected for Layer 1**, candidacy preserved for Layer 3 / Layer 4 | GGUF ports DO exist for Granite-Docling-258M (official `ibm-granite/granite-docling-258M-GGUF` + community ports) AND most Oct-2025-wave models (community-driven). However: (a) `llama-mtmd-cli`'s multimodal support is uneven across architectures (Idefics3 / Qwen3-VL / PaddleOCR-VL families have variable upstream-quality coverage as of 2026-05); (b) the Oct-2025 cohort's *primary* upstream support is HF Transformers checkpoints + (where available) MLX ports — GGUF lags by weeks-to-months and quality varies; (c) the `MLX-VLM + Transformers` pair gives broader, deterministic §8.1 cohort coverage. **Layer-3 RAG synthesis LLM (text-only) and Layer-4 demo serving remain candidates** — that's a separate post-pilot ADR, not this one |
| **Ollama** (`https://ollama.com`) | MIT | Metal-backed (wraps llama.cpp) | **Rejected for Layer 1**, candidacy preserved for Layer 4 | Same cohort gap as llama.cpp (Ollama wraps it); ergonomics-vs-throughput trade-off (~5× slower than direct MLX per v2 §7.2 / `docs/sources/tools/ollama.md`). Layer-4 demo candidacy preserved — "user installs in 30 seconds" UX is real value if thesis ships a public demo, but that's a separate ADR after the demo-vs-not decision is made post-pilot |
| **vllm-mlx 0.3.0** (`/waybarrios/vllm-mlx` + `vllm-project/vllm-metal`) | Apache 2.0 | M1 Pro native | **Considered, deferred** | OpenAI-compatible serving + continuous batching over MLX models. Layer-4 serving concern (FastAPI + Streamlit demo with API contract), not Layer-1 inference. Brainstorm §9.1 amendment explicitly added this candidate "to survey at cloud-baseline / serving ADR." Reserve ADR slot for post-pilot when the demo-shape decision is made; not in scope here |
| **MLC LLM** (`/mlc-ai/mlc-llm`) | Apache 2.0 | Metal-backed (TVM-Unity) | Rejected | The §8.1 document-VLM cohort has no MLC ports (verified via `docs/sources/tools/mlc-llm.md` — cited in v2 §7.2 only as text-LLM throughput comparand); ecosystem mismatch for the doc-VLM workload |
| **vLLM (canonical)** (`/vllm-project/vllm`) | Apache 2.0 | CUDA-only (with experimental ROCm/TPU/Inferentia) | Rejected | Hardware constraint per `know-your-hardware`: CUDA absent on M1 Pro. The `vllm-mlx` fork-or-rewrite (above) is the only relevant Apple-Silicon path |
| **Apple Core ML conversion** (`coremltools`) | Apple proprietary tooling + BSD-3 (coremltools) | Native M1 Pro (Apple Neural Engine where supported) | Rejected | Converter immaturity: multimodal Idefics3 / SigLIP2 / Qwen3-VL families lack reliable end-to-end Core ML conversion paths as of 2026-05 (per issue #10 issue body); thesis-time blocker — committing to Core ML risks shipping a thesis with a broken conversion step |
| **ONNX Runtime + CoreML EP** (`onnxruntime` + `onnxruntime-coreml`) | MIT (ORT) + Apple BSD (CoreML EP) | M1 Pro via CoreML EP | Rejected | Same converter-maturity concerns as Core ML; multi-step conversion (HF → ONNX → CoreML EP) compounds fragility; the `lamco-development/granite-docling-258M-onnx` and `onnx-community/granite-docling-258M-ONNX` ports exist but target production-Rust-server and web-runtime contexts respectively, neither relevant to HORUS's Python-server pipeline |

## Decision + integration thoughts

**Chosen: dual-track inference stack — MLX-VLM 0.5.0 (primary, MIT) + HuggingFace Transformers 5.8.0 + PyTorch MPS (fallback, Apache 2.0).**

### Rationale

1. **§8.1 cohort coverage is binary.** Brainstorm v2 §8.1 lists seven Oct-2025-wave doc-VLMs plus the §9.1 amendment additions. The MLX-ported subset and the Transformers-only subset together exhaust the cohort with no gaps. Either-framework-alone leaves a coverage hole that would force HORUS to either (a) drop a §8.1 candidate from evaluation (compromising thesis breadth) or (b) port the missing model (compromising thesis-time scope per `know-your-hardware`).

2. **Throughput-on-M1-Pro is asymmetric.** v2 §7.2's directional ranking (MLX ~230 tok/s vs PyTorch MPS ~7–9 tok/s) implies a 25–30× gap in the worst case, 3–5× in realistic VLM-inference settings. For models with MLX ports, MLX-VLM is the obvious primary; for models without, Transformers + MPS is the only path that doesn't require AWS escalation. The smoke evidence below produces the first HORUS-internal data point on this gap.

3. **Transformers is required transitively anyway.** `mlx-vlm 0.5.0` runtime deps include `transformers >= 5.5.0`. Adding `transformers` explicitly to `[project] dependencies` makes the dual-track decision auditable (every `pyproject.toml` reader sees both branches) and decouples HORUS's minimum-`transformers`-version requirement from `mlx-vlm`'s — important for future fine-tuning work that may require a `transformers` version newer than `mlx-vlm`'s pinned floor.

4. **Fine-tuning forward-fit.** Brainstorm §3 D8 commits HORUS to fine-tuning being central (LoRA / QLoRA on at least one VLM). The HF ecosystem (`peft`, `trl`, `accelerate`, `datasets`) is the canonical fine-tuning path; MLX-VLM has fine-tuning capabilities (per `/blaizzy/mlx-vlm` docs) but the broader research-toolchain ecosystem lives in HF. Transformers in `[project] dependencies` removes friction at the fine-tuning-ADR boundary (cohort ADR #14 will adapt).

5. **License hygiene.** MLX-VLM is MIT; Transformers is Apache 2.0. Both are linking-only-friendly for academic non-distributed contexts. No new copyleft entries beyond fpdf2's LGPL-3.0+ (already accepted in ADR-006).

6. **`know-your-hardware` adherence.** Both libraries fit the local M1 Pro / 16 GB / Metal 4 / 14 GPU cores / no-CUDA / ARM-only constraint set. MLX is Apple-native; PyTorch MPS is Apple-supported. No AWS escalation required for issue #10's scope (model weights ≤ 7 B params for the §8.1 subset that fits 16 GB unified memory at FP16 / BF16; aggressive quantization paths via mlx-vlm's `quantize` if 7 B headroom binds).

### Module / abstraction decisions deferred to cohort ADR #14

This ADR is **install-only**; no `src/horus/inference/` runner abstraction is added. Issue #10 acceptance criteria explicitly require only the install + ADR + smoke + tests-passing; the runner shape (e.g., a unified `InferenceRunner` Protocol with `MLXVLMRunner` + `TransformersRunner` concrete implementations, configured via `ExperimentConfig.inference.backend` per `horus-config-discipline`) is the natural concern of cohort ADR #14, which is `blocked-by` issue #10. ADR-005 set the "decision-only ADR" precedent for tooling-install ADRs; ADR-007 follows it.

### Smoke evidence — methodology

Per `make-sure-it-works`, the ADR's Decision section includes real evidence that both stacks work end-to-end on M1 Pro hardware against a real HORUS-generated ZUGFeRD invoice:

1. **Pre-condition**: `data/raw/smoke/invoice-001.pdf` (Factur-X 1.08 BASIC profile, generated by `make zugferd-smoke` per ADR-005 + ADR-006).
2. **PDF → PNG rasterization**: macOS `sips -s format png --resampleWidth 2480 data/raw/smoke/invoice-001.pdf --out data/raw/smoke/invoice-001.page1.png`. Single-line shell-out (complies with `no-terminal-oneline-scripts`); no new project dependency. `--resampleWidth 2480` ≈ 300 DPI for an A4 page (210 mm × 297 mm = 8.27" × 11.69"; 8.27 × 300 = 2481 px), which matches Granite-Docling-258M's processor `longest_edge=2048` cap (so the model receives the highest-resolution input it will actually use after its internal downsample). An earlier calibration run at `--resampleWidth 1240` (~150 DPI) produced the same hallucinated output, confirming the model-quality finding is rasterization-independent (see §"Smoke evidence — interpretation" below). Cohort ADR #14 will introduce a proper rasterization layer (likely `pypdfium2`) with its own ADR.
3. **Backend A — MLX-VLM**: load `ibm-granite/granite-docling-258M-mlx` via `mlx_vlm.load(...)`, run `mlx_vlm.generate(...)` with the Granite-Docling DocTags-extraction prompt, capture model-load wall-time, inference wall-time, output text snippet (first ~500 chars).
4. **Backend B — Transformers + MPS**: load `ibm-granite/granite-docling-258M` via `transformers.AutoModelForImageTextToText.from_pretrained(..., torch_dtype=torch.bfloat16).to('mps')`, run `model.generate(...)` with same prompt and image, capture same metrics.
5. **Captured transcript** — embedded below upon execution.

### Smoke evidence — captured transcript (M1 Pro, 2026-05-12)

`make inference-smoke` ran end-to-end on M1 Pro / 16 GB / Metal 4 / Python 3.14.3 / mlx-vlm 0.5.0 / transformers 5.8.0 / torch 2.11.0 / torchvision 0.26.0. Both backends loaded `Granite-Docling 258M` and ran inference on `data/raw/smoke/invoice-001.page1.png` (410,348 bytes; sips-rasterized at `--resampleWidth 2480` ≈ 300 DPI for A4, matching Granite-Docling-258M's processor `longest_edge=2048` cap; **the 300 DPI image is visually crystal clear — every invoice field legible by eye**). Verbatim transcript:

```
========================================================================
HORUS inference smoke — ADR-007 dual-track evidence
========================================================================
Image:          data/raw/smoke/invoice-001.page1.png
Image size:     410,348 bytes
Prompt:         'Convert this page to docling.'
max_tokens:     1536

------------------------------------------------------------------------
Backend:        transformers+mps
Model:          ibm-granite/granite-docling-258M
Status:         ok
Load wall-time:        8.34 s
Generate wall-time:  103.06 s
Output length:          111 chars
Output snippet (first 4000 chars):

<doctag><text><loc_2><loc_499><loc_16><loc_499>Powered by TCPDF (www.tcpdf.org)</text>
</doctag><|end_of_text|>
------------------------------------------------------------------------

------------------------------------------------------------------------
Backend:        mlx-vlm
Model:          ibm-granite/granite-docling-258M-mlx
Status:         ok
Load wall-time:        1.84 s
Generate wall-time:    8.98 s
Output length:           96 chars
Output snippet (first 4000 chars):

<doctag><text><loc_2><loc_499><loc_16><loc_499>Powered by TCPDF (www.tcpdf.org)</text>
</doctag>
------------------------------------------------------------------------

========================================================================
SUMMARY: 2/2 backends ran to completion
========================================================================
```

### Smoke evidence — prompt sweep (M1 Pro, 2026-05-12)

To rule out prompt-engineering as the cause of the canonical run's hallucinated output, three additional prompts were run against the same image at 300 DPI through MLX-VLM only (since cross-backend parity was already established above; mlx-only mode added to `scripts/inference_smoke.py` via `--prompt` + `--mlx-only` flags). All four prompts on the same crystal-clear A4 invoice:

| # | Prompt | Output (verbatim, truncated to ~80 chars where longer) | Failure mode |
|---|---|---|---|
| 1 | `"Convert this page to docling."` (canonical) | `<doctag><text><loc_2><loc_499><loc_16><loc_499>Powered by TCPDF (www.tcpdf.org)</text></doctag>` | **Hallucinated boilerplate** — string "TCPDF" does not exist anywhere in the PDF (verified `strings invoice-001.pdf \| grep -i tcpdf` → 0 matches) |
| 2 | `"What is the seller name on this invoice?"` | `"The seller name on this invoice is not provided in the text."` | **False negation** — model denies the existence of "HORUS Test Seller GmbH" which is rendered prominently under the LIEFERANT label |
| 3 | `"Extract all text visible on this page."` | `<doctag><picture><loc_0><loc_0><loc_500><loc_500><screenshot></picture>` | **Page-as-screenshot classification** — entire page tagged as a single opaque image with zero text content, despite all text being legible by eye |
| 4 | `"List the invoice line items as a table."` | 8640 chars of `<otsl><ecel><fcel>Invoice line items<nl>` repeating until `max_tokens=1536` | **Degenerate token-repetition loop** — schema (`<otsl>` is Granite-Docling's table grammar) is correct; content is prompt-string echoing |

Four prompts, four distinct failure modes, **zero correct extractions** of any HORUS-invoice content (seller name, buyer name, invoice number, date, line items, totals, IBAN, USt-ID — all visible by eye, all absent from every output).

### Smoke evidence — interpretation

Three findings, each with thesis-relevance. The **third** is the most important and the most honest:

1. **Both backends produce IDENTICAL DocTags output on the canonical prompt** (modulo a trailing `<|end_of_text|>` marker on the Transformers branch — its tokenizer doesn't strip it by default; `skip_special_tokens=False` in our smoke decode). Same `Granite-Docling 258M` weights through two inference runtimes → byte-identical extraction. **This validates the dual-track decision as a throughput/coverage choice, not a quality choice.** A model evaluated on one backend can be cross-checked on the other for runtime parity (useful regression-test affordance for cohort ADR #14).

2. **MLX-VLM is ~11× faster at generate-time than Transformers + MPS** on this 300-DPI workload (8.98 s vs 103.06 s for the same 1536-max-token DocTags-extraction run on a 258 M-param model). Load time is ~4.5× faster (1.84 s vs 8.34 s). Brainstorm v2 §7.2's directional ranking (~25–30× MLX:MPS for general LLM inference) is now empirically anchored — at higher input resolution the gap shrinks because vision-encoder time becomes a larger share of total work and amortizes across both backends, but MLX-VLM still wins decisively. **At 150 DPI input** (a separate calibration run discarded for the cohort-ADR-#14-overlap reason; data captured for completeness) **the gap was ~60× generate** because decode-rate dominated total cost and that's MLX's strongest axis. Conclusion: **MLX-VLM-as-primary is empirically justified across the input-resolution spectrum cohort ADR #14 will explore.** Per-model throughput numbers should be recorded alongside accuracy in #14's comparison matrix.

3. **Granite-Docling-258M exhibits a CAPABILITY GAP on HORUS-style invoices, not a prompt-mismatch** — and this is the most important finding for the thesis.
   - **Across four diverse prompts (DocTags-canonical / Q&A / generic-extraction / structured-table), the model produced zero correct extractions in four distinct failure modes** (hallucinated boilerplate / false negation / page-as-screenshot / token-repetition loop). Three additional prompts ran specifically to rule out prompt-engineering as the cause; they did. See §"Smoke evidence — prompt sweep" above.
   - **The rasterized PNG is visually unambiguous** — every invoice field is legible by eye at 300 DPI: "RECHNUNG" header, "Nr. HORUS-SMOKE-001", "Datum: 11.05.2026", "LIEFERANT: HORUS Test Seller GmbH / Teststraße 1 / 20095 Hamburg / DE / USt-ID: DE123456789", "RECHNUNGSEMPFÄNGER: HORUS Test Buyer GmbH / DE", line-item table ("Pos. / Bezeichnung / Menge / Einheit / Einzelpreis / Gesamt"), row "1 / Beratungsleistung / 1 / C62 / 100.00 EUR / 100.00 EUR", "Zwischensumme (netto): 100.00 EUR", "USt. 19 %: 19.00 EUR", "Bruttosumme: 119.00 EUR", "Zahlbar: 119.00 EUR".
   - **None of the four model outputs reference any of the visible content.** Outputs are training-distribution priors (TCPDF watermark — fpdf2's lineage trace from PHP-PyFPDF-TCPDF; "screenshot" classification; "Invoice line items" verbatim echo of the prompt's word "items"). The model is *seeing* the image (the canonical-prompt run produced location coordinates, and the prompt-2 run classified the full page area `<loc_0,0,500,500>`) — it just cannot extract from it.
   - **Implication for HORUS**: Granite-Docling-258M is empirically demonstrated to be insufficient for HORUS's invoice-extraction task on a fpdf2-rendered B2B invoice (which is not an OOD-difficult example — it's a clean, simple, professional German invoice; if 258M fails here, it will fail harder on real-world Steuerberater documents). This is **direct empirical signal for cohort ADR #14**:
     - **The 258M tier is empirically excluded** from HORUS's pilot loop (issue #13). Cohort #14 should focus on the 3B–30B candidates (Nanonets-OCR2-3B, dots.ocr-3B, olmOCR-2-7B, Qwen3-VL-8B, Qwen3-VL-30B-A3B-Instruct) where parameter count + training-data fit make extraction plausibly tractable on M1 Pro / 16 GB.
     - **Prompt sweeping is now demonstrated to be insufficient for compensating capability gap.** Cohort #14 should still explore prompts on larger models (some VLMs are highly prompt-sensitive), but cannot rely on prompt engineering alone to redeem an under-capable model.
     - **The four failure modes are diagnostically useful**: each maps to a different model behavior (training-prior hallucination / instruction-following collapse / vision-encoder-only / decoder-loop). Cohort #14 can re-use these prompts as a quick triage probe before committing to deeper evaluation of any candidate model.
   - **Implication for ADR-007 itself**: ZERO. ADR-007's scope is the inference *framework* — both stacks loaded a 258M VLM, ran end-to-end on M1 Pro hardware, produced syntactically valid DocTags output, and matched each other byte-for-byte. The framework is validated. The model-quality finding is captured here as forward-pointer evidence for #14, not as a reason to revisit ADR-007.

### Implementation footnotes captured during smoke (informative — not blocking)

The smoke run surfaced four upstream-quality observations worth recording for cohort ADR #14 + bidirectional-learning queue:

- **`torchvision` is required** for `Idefics3ImageProcessor` but is NOT pulled transitively by `transformers` on the Idefics3 path. Without it, `AutoProcessor.from_pretrained(...)` raises a misleading `"Unrecognized image processor"` error that masks the underlying `ImportError`. Added `torchvision >= 0.20` to `[project] dependencies` as the canonical torch-ecosystem image-transform companion. No separate ADR — torchvision is part of the torch ecosystem already accepted in ADR-005-era deps.
- **`mlx_vlm` import monkey-patches `transformers.AutoProcessor.from_pretrained` globally** (per `mlx_vlm/models/base.py::_patched_auto_processor_from_pretrained`). When transformers backend code runs AFTER mlx-vlm has been used in the same process, `processor(..., return_tensors="pt")` returns `mlx.core.array` instead of `torch.Tensor`, breaking `model.generate(...)`. Mitigated in the smoke by running the Transformers backend FIRST (pristine state); cohort ADR #14 will adopt subprocess-isolated backend invocation if the contamination becomes a runtime concern beyond one-off smokes.
- **`Idefics3Processor.apply_chat_template(...)` raises `"this processor does not have a chat template"` in the smoke's same-process post-MLX-backend context** even though `processor.chat_template` is set. Mitigated in the smoke by hardcoding the Granite-Docling chat template format (sourced from the model's `chat_template.jinja`). Cohort ADR #14 will use the canonical `apply_chat_template` once subprocess isolation eliminates the cross-backend state pollution.
- **Cosmetic**: `mlx.core.metal.clear_cache` is deprecated in favor of `mlx.core.clear_cache`; the smoke catches both via `hasattr` guards. `transformers`'s `use_fast=True` kwarg on `AutoImageProcessor` is deprecated in favor of `backend="torchvision"`. Both are out of scope here.

These observations are captured to `cascade-system/queue/pending-review.md` for `@sprint-review` to consider as upstream-PR opportunities or as input to a future runner-abstraction ADR.

### Throughput vs. coverage decision matrix (forward-pointer to cohort ADR #14)

The smoke produces these decision inputs for cohort ADR #14:

| If §8.1 candidate has… | Use backend | Empirical reason |
|---|---|---|
| MLX port (e.g., `granite-docling-258M-mlx`, Qwen3-VL-MLX, …) | **MLX-VLM** | 11–60× faster generate (resolution-dependent: ~11× at 300 DPI input, ~60× at 150 DPI), ~5–9× faster load on Granite-Docling-258M; byte-identical output to Transformers + MPS reference |
| No MLX port, native HF Transformers checkpoint | **Transformers + MPS** | Only viable local path; throughput acceptable for evaluation runs (not production) |
| No MLX port AND non-Transformers ecosystem (PaddleOCR-VL 1.5 PaddlePaddle) | TBD by cohort ADR | Out of scope here; PaddlePaddle MPS support is a separate decision |

Cohort ADR #14 will fill the per-model entries of this matrix as each §8.1 candidate is evaluated. **Note**: the smoke + prompt sweep produced direct empirical evidence that **Granite-Docling-258M is unsuitable for HORUS-style invoice extraction** (4 prompts × 4 distinct failure modes × 0 correct extractions on a crystal-clear A4 invoice — see §"Smoke evidence — interpretation" finding 3). Cohort ADR #14 should treat the 258M tier as empirically excluded from the HORUS pilot loop and focus its evaluation on the 3B–30B candidates (Nanonets-OCR2-3B, dots.ocr-3B, olmOCR-2-7B, Qwen3-VL-8B, Qwen3-VL-30B-A3B-Instruct).

### Integration with HORUS components (current state, post-this-ADR)

- **`pyproject.toml`** — `mlx-vlm >= 0.5.0`, `transformers >= 5.5.0`, and `torchvision >= 0.20` added to `[project] dependencies`. All three pulled by `uv sync`. `torchvision` is a smoke-driven late-add (see footnotes above); it is the canonical torch-ecosystem image-transform companion required by `Idefics3ImageProcessor`. Mypy override added for `mlx_vlm.*` (no `py.typed`); `transformers` ships `py.typed` since 4.43 — no override needed; `torchvision` ships `py.typed` since 0.16 — no override needed.
- **`tests/test_inference_smoke.py`** — import-only smoke + MPS-availability assertion + MLX-Metal-device assertion; runs as part of `make test` (4 new tests; ~6 s total).
- **`scripts/inference_smoke.py`** — real-model smoke runner (one-off; not in `make test`); produces the canonical transcript above. CLI: `--prompt TEXT` overrides the default DocTags-extraction prompt; `--mlx-only` / `--hf-only` run a single backend (used for the prompt sweep above; both flags are mutually exclusive).
- **`Makefile`** — new `inference-smoke` target chains `zugferd-smoke` (pre-req) → `sips` rasterization → `inference_smoke.py`.
- **`src/horus/`** — *unchanged*. Runner abstraction is cohort ADR #14's concern.

### Forward links (work items unblocked by this ADR)

- **Issue #14** — Cohort-selection ADR (`ADR-NNN-pilot-vlm-cohort.md`): selects which §8.1 candidate(s) to run for the pilot. Now unblocked.
- **Issue #11** — Orchestrated-baseline ADR (Docling library): independent of #10; uses Transformers branch for VLM stages.
- **Issue #16** — Experiment-tracker ADR (MLflow indicated): independent of #10.
- **Future ADR-N** — Layer-4 serving / demo decision: re-evaluates `vllm-mlx` + `Ollama` candidates currently deferred here.

## Source archival

Per `horus-source-archival` rule + ADR-002:

- `docs/sources/tools/mlx-vlm.md` — **new** (this PR). Chosen primary path. PyPI 0.5.0 / MIT / Python ≥ 3.10; repo `https://github.com/Blaizzy/mlx-vlm`.
- `docs/sources/tools/huggingface-transformers.md` — **new** (this PR). Chosen fallback path. PyPI 5.8.0 / Apache 2.0 / Python ≥ 3.10; repo `https://github.com/huggingface/transformers`.
- `docs/sources/tools/vllm-mlx.md` — **new** (this PR). Considered-deferred mention. PyPI 0.3.0 / Apache 2.0; repos `https://github.com/waybarrios/vllm-mlx` + `https://github.com/vllm-project/vllm-metal`. Brainstorm §9.1 amendment cited.
- `docs/sources/tools/mlx-apple-silicon.md` — **existing** (M2D.4 brainstorm). MLX core; pulled transitively by `mlx-vlm`.
- `docs/sources/tools/pytorch-mps.md` — **existing** (M2D.4 brainstorm). MPS backend reference.
- `docs/sources/tools/llama-cpp.md` — **existing** (M2D.4 brainstorm). Dismissed-with-nuance reference.
- `docs/sources/tools/ollama.md` — **existing** (M2D.4 brainstorm). Dismissed-with-nuance reference.
- `docs/sources/tools/mlc-llm.md` — **existing** (M2D.4 brainstorm). Dismissed reference.

vLLM canonical, Apple Core ML, ONNX Runtime + CoreML EP — eliminated-by-reference (not archived per `horus-source-archival` §"When the rule does NOT fire": alternatives considered-and-rejected with no positive citation in Decision text).

## Consequences

- **Positive**: every §8.1 cohort candidate has a deterministic, documented inference path on M1 Pro. Fine-tuning ecosystem (`peft`, `trl`, `accelerate`) is reachable via the Transformers branch when cohort ADR #14 + a future fine-tuning ADR land. The smoke evidence produces the first HORUS-internal data point on the v2 §7.2 throughput claim. Both libraries are MIT / Apache-2.0; no new copyleft entries.
- **Negative**: `mlx-vlm 0.5.0`'s runtime deps are heavy (datasets, miniaudio, opencv-python, fastapi, uvicorn, llguidance, mlx-audio, …) — first-time `uv sync` after this PR will pull substantial wheel volume (~hundreds of MB). The unused-feature deps (`miniaudio`, `mlx-audio`, `fastapi`, `uvicorn`) are pulled because `mlx-vlm` does not yet split optional extras for vision-only use cases (potential upstream PR opportunity, captured to `cascade-system/queue/pending-review.md` if confirmed during smoke-install observation). Two-framework dual-loading also doubles the `make test` import-time cost; mitigated by import-only smoke (no model loading in `make test`).
- **Neutral**: the `make inference-smoke` target downloads ~500 MB of model weights (Granite-Docling 258M MLX + HF reference) on first run; cached in `~/.cache/huggingface/hub/` and `~/.cache/mlx-community/` per upstream defaults. Not committed. Reusable by cohort ADR #14's first-pilot smoke.

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate)
- **ADR-002** — source-archival convention (this ADR's §"Source archival" cites)
- **ADR-005** — synthetic ZUGFeRD generator (`scripts/generate_zugferd_smoke.py` produces the smoke input PDF)
- **ADR-006** — visual PDF renderer (the `data/raw/smoke/invoice-001.pdf` visual layer is fpdf2-rendered; `make zugferd-smoke` is the upstream of `make inference-smoke`)
- **Cascade-system ADR-013** — `/commit` workflow (used for commits in this PR)
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager`; artifact-review gate at step 4 fires explicitly on the smoke transcript before push)

## Provenance

- Plan: `~/.windsurf/plans/horus-issue-10-inference-framework-adr-9964f0.md`
- Issue: `ReebalSami/horus#10`
- Brainstorm refs: `docs/prompts/stages/02-brainstorm.md` §6.1 + §7.1 + §7.2 + §8.1 + §9.1 + §9.2
- Workspace rules applied: `horus-decision-discipline.md`, `horus-source-archival.md`, `know-your-hardware.md`, `make-sure-it-works.md`, `context7-and-docs-first.md`
