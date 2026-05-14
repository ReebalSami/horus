# ADR-009 — Pilot VLM cohort selection (10-model, 3-category single-shot bake-off)

| Field | Value |
|---|---|
| **Status** | Proposed (smoke evidence captured 2026-05-14; flips to Accepted on PR(a) merge) |
| **Date** | 2026-05-14 |
| **Milestone** | M2D.5 step 3 — Pilot-loop cohort enablement (issue #14, sub of #13) |
| **Authored by** | Cascade D (M2D.5 cohort-selection session, plan `~/.windsurf/plans/adr-009-pilot-vlm-cohort-fbbfa0.md`) |
| **Issue** | `ReebalSami/horus#14` (sub of #13) |
| **PR scope** | 2-PR split: PR(a) — foundation (this ADR + dispatcher + 3 PR(a)-tier smokes); PR(b) — cohort completion (remaining 7 smokes appended via mid-sprint amendment per ADR-018) |
| **Supersession trigger** | (a) Pilot #13 demonstrates one of the 3 categories is empirically dead-on-arrival across all its candidates → ADR-009 superseded by ADR-NNN-pilot-cohort-revision; OR (b) A new architectural family emerges between PR(b) merge and pilot #13 freeze that the cohort cannot represent → cohort extended via §"Decision" amendment, ADR not superseded; OR (c) The 3-category framework proves taxonomically inadequate during pilot #13 → ADR-009 superseded by ADR-NNN-pilot-cohort-recategorisation; OR (d) HORUS hardware target shifts away from M1 Pro / 16 GB → cohort quant-policy + Type-B blocklist re-evaluated; cohort identity preserved. |

## Context

ADR-007 (local-VLM inference framework: dual-track MLX-VLM + Transformers + MPS) and ADR-008 (orchestrated-baseline document pipeline: Docling + MinerU cross-check) both forward-pointed module / abstraction decisions and pilot-loop cohort selection to "cohort ADR #14". That ADR is **ADR-009** in our INDEX numbering (issue #14 in GitHub).

The pilot loop (sub-issue #13) needs a locked cohort of single-shot VLM candidates for the zero-shot baseline run that produces the initial F1 + field-level error heatmap evidence. This cohort decision is **the load-bearing methodological choice** that determines:

- which models §11 vertical slices later evaluate
- which architectures Säring sees in the first thesis meeting
- the data substrate for the H1 / H2 single-shot-vs-orchestrated experiment
- the `src/horus/vlm_extractor.py` Protocol shape that productionises ADR-007's `scripts/inference_smoke.py` dispatcher prototype

### Cohort delta vs brainstorm v2 §8.1 + §9.1 (honest disclosure)

The original issue #14 body listed 7 candidates from brainstorm v2 §8.1. The cohort in this ADR is **scope-expanded** to 10 candidates across 3 architectural categories. Deltas:

| Change | Rationale |
|---|---|
| DROP `dots.ocr` (v2 §8.1) | Cat 2 representation now carried by DeepSeek-OCR-2, PaddleOCR-VL, GLM-OCR; dots.ocr's 3B Mistral-arch rationale collapses into Cat 3 |
| DROP `Nanonets-OCR2-3B` (v2 §8.1) | 3B Nanonets niche overlaps with both olmOCR-2 (purpose-trained) and Qwen3-VL-4B (general) without distinct architectural lineage |
| SHRINK `Qwen3-VL-8B / 30B-A3B` (v2 §9.1) → `Qwen3-VL-4B-Instruct` | M1 Pro / 16 GB ceiling per `know-your-hardware`; 4B is cohort-comparable; 30B-A3B exceeds local capacity |
| SWAP `DeepSeek-OCR` (v1) → `DeepSeek-OCR-2` (v2, Feb 2026) | v2 supersedes v1 upstream; license upgraded MIT → apache-2.0 (clean for thesis distribution); same `deepseek_vl_v2` arch preserves Contexts Optical Compression motivation for Cat 2 |
| ADD `GLM-OCR` (Cat 2) | Feb 2026; 94.62 OmniDocBench V1.5 SOTA at 0.9 B params; architecturally distinct from DeepSeek-OCR-2 + PaddleOCR-VL |
| ADD `Gemma-4-E4B-it` (Cat 3) | Apr 2026; native multimodal (text + image + audio + video) via Matformer; apache-2.0; 368.4K downloads on `lmstudio-community` MLX-4bit port |
| ADD `PaliGemma-2-3B-mix-448` (Cat 3) | SOTA table-structure benchmarks per upstream paper; gemma-license gating informative within-family vs Gemma-4-E4B's apache-2.0 |
| ADD `Molmo-7B-D-0924` (Cat 3) | Within-lab pair with olmOCR-2 (both Allen AI, both `qwen2_5_vl`); methodological control isolating purpose-training-on-docs effect from lab + arch effects |

### 3-category methodological framework

The cohort organises around three architectural categories:

- **Cat 1 — End-to-end document-VLMs.** Purpose-trained on document parsing benchmarks (DocLayNet, OmniDocBench V1.5). Members: Granite-Docling-258M, MinerU-2.5-Pro VLM 1.2B, olmOCR-2-7B. Hypothesis: purpose-training is the dominant lever for invoice-extraction quality at small parameter counts.
- **Cat 2 — Architecturally innovative compression / hybrid.** Models that earn their slot via an architectural choice rather than parameter scaling. Members: DeepSeek-OCR-2 (Contexts Optical Compression), PaddleOCR-VL (hybrid OCR + VLM), GLM-OCR (glm4v at 0.9 B SOTA OmniDocBench V1.5). Hypothesis: the architectural lever can match purpose-training at smaller parameter counts.
- **Cat 3 — General-purpose multimodal VLMs.** Not purpose-trained for documents; included to test transfer-learning hypothesis. Members: Gemma-4-E4B-it, Qwen3-VL-4B-Instruct, PaliGemma-2-3B-mix-448, Molmo-7B-D-0924. Hypothesis: parameter scale + general-multimodal training compensates for absent purpose-training.

The 3-category framework is the load-bearing decomposition. The Cat-1-baseline-of-failure / Cat-3-general-success spread captured in PR(a) gives pilot #13 the empirical bracket within which Cat 2's architectural-innovation hypothesis is tested.

### ADR-007 baseline-of-failure framing reconciliation

ADR-007 §"Decision" finding 3 said: *"the 258M tier is empirically excluded from HORUS's pilot loop."* This ADR keeps Granite-Docling-258M as Cat 1's **baseline-of-failure anchor**. Reconcilable, not contradictory:

- ADR-007's "empirically excluded" = excluded as a **primary candidate** (i.e., 258M won't be the HORUS production model)
- ADR-009's "baseline-of-failure" = INCLUDED as the **lower-bound reference point** (i.e., 258M defines "what no-good looks like"; cohort architectures should ALL beat it)

ADR-007 is NOT superseded; both ADRs co-exist. The baseline-of-failure inclusion is enabled by the 3-Cat decomposition, which post-dates ADR-007.

Discipline gate: `horus-decision-discipline` rule mandates the 5 mandatory sections (Current-state survey / Options considered / Decision + integration thoughts / Source archival / Supersession trigger). The plan `~/.windsurf/plans/adr-009-pilot-vlm-cohort-fbbfa0.md` is the source-of-truth for scope, locked decisions, and PR split (ratified via `exitplanmode`).
## Current-state survey (2026-05-14)

Survey methodology: HuggingFace Hub direct ID lookups (`hf_hub_download` for `config.json` reads to extract `model_type` + `architectures` fields, not search-ranker heuristics) for all 10 candidate model IDs; `mcp4_hub_repo_search` + `mcp4_hub_repo_details` calls confirming download counts, licenses, MLX port availability; brainstorm v2 §8.1 + §9.1 cited as upstream context; ADR-007 + ADR-008 cited as immediate prior framework decisions.

### Cohort identity — verified HF Hub data

All 10 model identifiers verified against HuggingFace Hub on 2026-05-14:

| # | Cat | HF ID | Real params | License | Architecture | MLX 4-bit port |
|---|---|---|---|---|---|---|
| 1 | 1 | `ibm-granite/granite-docling-258M-mlx` | 315 M | apache-2.0 | idefics3 | ✅ official |
| 2 | 1 | `opendatalab/MinerU2.5-Pro-2604-1.2B` | 1.16 B | apache-2.0 | qwen2_vl | TBD at install time (PR(b)) |
| 3 | 1 | `allenai/olmOCR-2-7B-1025` | 8.29 B | apache-2.0 | qwen2_5_vl | ✅ `mlx-community/olmOCR-2-7B-1025-mlx-4bit` |
| 4 | 2 | `deepseek-ai/DeepSeek-OCR-2` | 3.39 B | apache-2.0 | deepseek_vl_v2 | ✅ `mlx-community/DeepSeek-OCR-2-4bit` (`custom_code`) |
| 5 | 2 | `PaddlePaddle/PaddleOCR-VL` | 0.96 B | apache-2.0 | paddleocr_vl | ❌ requires `paddlepaddle` dep |
| 6 | 2 | `zai-org/GLM-OCR` | 0.9 B | likely MIT (TBD at PR(b) install) | glm4v | ❌ `transformers<5.0.0` conflict; needs vLLM/Ollama/SGLang |
| 7 | 3 | `google/gemma-4-E4B-it` | 7.99 B (4 B effective via Matformer) | apache-2.0 | gemma4 | ✅ `lmstudio-community/gemma-4-E4B-it-MLX-4bit` (368.4K downloads) |
| 8 | 3 | `Qwen/Qwen3-VL-4B-Instruct` | 4.44 B | apache-2.0 | qwen3_vl | TBD at install time (PR(b)) |
| 9 | 3 | `google/paligemma2-3b-mix-448` | ~3 B | gemma (gated) | paligemma | TBD; gated — requires Google T&C accepted on HF account |
| 10 | 3 | `allenai/Molmo-7B-D-0924` | 8.02 B | apache-2.0 | molmo | TBD (`custom_code`) |

### ADR-007 + ADR-008 inheritance

ADR-007 ratified the dual-track inference stack (MLX-VLM 0.5.0 primary + HF Transformers 5.8.0 + PyTorch MPS fallback). This ADR inherits both branches; cohort dispatch routes per-model via the `COHORT_MANIFEST` registry (see §"Decision + integration thoughts" §"Dispatcher architecture"). ADR-008 ratified the orchestrated-baseline pipeline (Docling primary + MinerU pipeline backend cross-check) — that path runs in parallel to this cohort's single-shot extraction; both feed pilot #13's H1 / H2 comparison.

### Hardware envelope (per `know-your-hardware`)

M1 Pro / 16 GB unified memory / 14 GPU cores / Metal 4 / no CUDA. Smoke runs page-1-only at 1 PNG per model (image footprint ~700 KB at 2480 px width). Quantization is mixed (see §"Decision + integration thoughts" §"Quantization strategy"): bf16 for ≤2 B params, MLX 4-bit for ≥3 B. No model in the cohort is loaded twice; each extractor's `unload()` is called between models in the smoke loop. Headroom verified empirically — the 6.86 GB Gemma-4-E4B-it download + load + extract completes without OOM.

## Options considered

| Option | Cohort size | Cat coverage | Status | Why |
|---|---|---|---|---|
| **3-model cohort** (Granite-Docling + olmOCR-2 + Gemma-4-E4B-it) | 3 | 1 per Cat | Rejected | Forfeits within-Cat comparison (e.g., Cat 2's 3 architectural lineages — DeepSeek-OCR-2 / PaddleOCR-VL / GLM-OCR — collapse into a single representative; thesis claim "the architectural lever was tested" reduces to "we tried one architecturally-innovative model" which is too narrow to support generalization) |
| **5-model cohort** (Cat 1 × 2 + Cat 2 × 1 + Cat 3 × 2) | 5 | Asymmetric | Rejected | Same within-Cat-comparison gap as 3-model cohort; asymmetric coverage smuggles a hypothesis (more Cat 1 + Cat 3 = more evaluation budget on those vs Cat 2) without justifying it; the architectural-lever hypothesis Cat 2 tests is weakened by single-representation |
| **7-model cohort** (issue #14 original body) | 7 | Pre-3-Cat-framework | Rejected | Predates the 3-Cat methodological re-cut; mixes Cat 1 (Granite-Docling, olmOCR-2, Nanonets-OCR2, MinerU) and Cat 2 (dots.ocr, PaddleOCR-VL) and Cat 3 (Qwen3-VL-8B / 30B) without explicit category bracketing — pilot #13's evaluation matrix would inherit the un-cut shape and lose the architectural-axis interpretability |
| **Single-Cat focus** (e.g., Cat 1 only — 3 models) | 3 | Single Cat | Rejected | Defensible thesis path (purpose-trained-on-docs hypothesis is narrowest and most rigorous to test) but forfeits Cat 2 (architectural-innovation finding) and Cat 3 (transfer-learning finding) — both are Säring-relevant per brainstorm v2 §3 D8. Single-Cat focus is sub-issue territory if pilot #13's H2 narrows to one Cat post-bake-off |
| **Skip zero-shot bake-off** (jump directly to fine-tuning) | 0 | None | Rejected | Forfeits the H1 (single-shot-vs-orchestrated) experimental arm entirely; "we fine-tuned the model that worked best in zero-shot" requires zero-shot to have run; brainstorm §3 D8 + ADR-007's forward-pointer to #14 both require zero-shot evidence first |
| **No-quantization cohort** (all bf16, with OOM tolerance) | 10 | 3 Cats | Rejected | bf16 7-8 B models exceed 16 GB unified memory ceiling under VLM workload (~2 GB activation footprint atop weights + image-encoder state); ADR-007's smoke evidence at 258 M is not generalizable to 7 B-tier; uniform-bf16-and-fail-on-OOM produces "OOM at load time" as the dominant failure mode and would obscure architectural signal |
| **Uniform 4-bit cohort** (all MLX 4-bit) | 10 | 3 Cats | Rejected | Cat 1's smallest member (Granite-Docling-258M) has no community 4-bit port (the official IBM port is bf16; quantization to 4-bit at 258M would degrade quality without a memory benefit since bf16-258M = 0.5 GB and fits trivially); MinerU-2.5-Pro-1.2B has no MLX port and forces Transformers + MPS at bf16; uniform-4-bit is operationally infeasible |
| **10-model 3-Cat cohort with mixed quantization** (chosen) | 10 | 3 Cats × 3-4 models each | **Chosen** | Maximises within-Cat and across-Cat comparison; covers the 3-architectural-lever decomposition (purpose-training / architectural-innovation / general-multimodal); fits the M1 Pro / 16 GB ceiling via mixed quantization (bf16 for ≤2 B; MLX 4-bit for ≥3 B); produces the tooling spine (`COHORT_MANIFEST` + dispatcher) that pilot #13 inherits without re-design |

## Decision + integration thoughts

**Chosen: 10-model cohort across 3 architectural categories, mixed-quantization, dispatched via a 4-class `VLMExtractor` Protocol with a `COHORT_MANIFEST` registry. Smoke methodology mirrors ADR-007 (page-1-only, transcript blocks, ADR-008-style honest disclosure of install conflicts).**

### Decision — Cat 1: End-to-end document-VLMs

**Members**: Granite-Docling-258M (baseline-of-failure), MinerU-2.5-Pro VLM 1.2B (purpose-trained mid-tier), olmOCR-2-7B (purpose-trained large).

**Rationale**:

- **Granite-Docling-258M** earns the baseline-of-failure slot per ADR-007 §"Decision" finding 3 (4 prompts × 4 distinct failure modes × 0 correct extractions on synthetic invoice). PR(a) §"Smoke evidence" extends ADR-007's evidence to a real German EN16931 invoice (`EN16931_Einfach.pdf`); the failure profile reproduces (hallucinated content + degenerate token loop). Per `docs/sources/tools/granite-docling-258m-mlx.md`.
- **MinerU-2.5-Pro VLM 1.2B** is the orchestrated-baseline pipeline's VLM-stage backend per ADR-008; its inclusion as a Cat 1 cohort entry adds the purpose-trained mid-tier reading to the architectural matrix (ADR-008 evaluates MinerU as an orchestrated pipeline; ADR-009 evaluates the same VLM backend in single-shot mode — the H1 single-shot-vs-orchestrated comparison Säring asks about). Per `docs/sources/tools/mineru-2-5.md`.
- **olmOCR-2-7B** is Allen AI's Oct 2025 purpose-trained-on-docs benchmark-leader; the within-lab pair with Molmo-7B-D-0924 (Cat 3) is methodological control — same lab, same `qwen2_5_vl` lineage, one purpose-trained-on-docs and one general-multimodal isolates the purpose-training-on-docs effect from the lab effect. English-only training caveat noted; pilot #13 produces German-substrate evidence. Per `docs/sources/tools/olmocr-2-7b.md` + `docs/sources/papers/poznanski-2025-olmocr2.md`.

### Decision — Cat 2: Architecturally innovative compression / hybrid

**Members**: DeepSeek-OCR-2 (Contexts Optical Compression), PaddleOCR-VL (hybrid OCR + VLM), GLM-OCR (glm4v at 0.9 B SOTA OmniDocBench V1.5 score).

**Rationale**:

- **DeepSeek-OCR-2** earns its slot via the Contexts Optical Compression architectural innovation (vision-encoder produces compressed tokens consumed by the LLM, reducing inference memory at the cost of architectural specialization). v2 supersedes v1 from `docs/sources/tools/deepseek-ocr.md` (kept for retention per ADR-011); `docs/sources/papers/deepseek-2025-contexts-optical-compression.md` is the v1 architectural precedent; `docs/sources/papers/deepseek-2026-deepseek-ocr-2.md` is v2. License upgrade MIT → apache-2.0 cleans the thesis-distribution path. Per `docs/sources/tools/deepseek-ocr-2.md`. **PR(a) outcome: Type B install-conflict (see §"Smoke evidence — PR(a) cohort entries").**
- **PaddleOCR-VL** earns its slot via the hybrid architecture — OCR-stage produces token-aware bounding boxes consumed by a small VLM stage, distinct from the end-to-end Cat 1 path. The PaddlePaddle ecosystem dependency is a real cost (large wheel; ARM64 wheels exist for M1) — installed in PR(b) per §"Install constraints" §"Type A taxonomy". Per `docs/sources/tools/paddleocr-vl.md`.
- **GLM-OCR** earns its slot via the glm4v architecture's claimed 94.62 OmniDocBench V1.5 SOTA at 0.9 B params — the strongest mid-2026-wave 0.9-B-tier benchmark result in the cohort. The transformers<5.0.0 install conflict is the dominant friction; resolution path attempted via vLLM / Ollama / SGLang per §"Install constraints" §"Type B taxonomy". Per `docs/sources/tools/glm-ocr.md`.

### Decision — Cat 3: General-purpose multimodal VLMs

**Members**: Gemma-4-E4B-it, Qwen3-VL-4B-Instruct, PaliGemma-2-3B-mix-448, Molmo-7B-D-0924.

**Rationale**:

- **Gemma-4-E4B-it** is the canonical Cat 3 entry — Apr 2026 release; native multimodal (text + image + audio + video) via the Matformer 4-B-effective-from-7.99-B-params technique; apache-2.0 (no gemma-license gating despite the family name). The 368.4K downloads on `lmstudio-community/gemma-4-E4B-it-MLX-4bit` is the cohort's strongest single-port adoption signal. Per `docs/sources/tools/gemma-4-e4b-it.md`. **PR(a) outcome: Cat 3 success (see §"Smoke evidence — PR(a) cohort entries").**
- **Qwen3-VL-4B-Instruct** is the Mistral-family Cat 3 entry; the parameter-shrink from v2 §9.1's Qwen3-VL-8B / 30B-A3B reflects the M1 Pro / 16 GB ceiling per `know-your-hardware`. Per `docs/sources/tools/qwen3-vl-4b-instruct.md`.
- **PaliGemma-2-3B-mix-448** is the Cat 3 entry with SOTA table-structure-recognition benchmarks per upstream paper. The gemma-license gating (Google T&C) vs Gemma-4-E4B-it's apache-2.0 within the same family is a methodologically informative within-family license-vs-architecture decoupling. The "caption en" / task-prefix prompt convention is preserved per HF model card. Per `docs/sources/tools/paligemma-2-3b-mix.md`.
- **Molmo-7B-D-0924** is the within-lab control pair with olmOCR-2 — both Allen AI; both `qwen2_5_vl` lineage. Same lab, same architecture, one purpose-trained-on-docs (olmOCR-2 → Cat 1) and one general-multimodal (Molmo → Cat 3). The pair isolates the purpose-training-on-docs effect from the lab and architecture effects in pilot #13's H2 evaluation. Per `docs/sources/tools/molmo-7b-d.md`.

### Dispatcher architecture — `src/horus/vlm_extractor.py` Protocol + 4 framework classes

The dispatcher productionises ADR-007's `scripts/inference_smoke.py` prototype into the cohort-spanning shape. Authored in PR(a) Step 2:

```python
@runtime_checkable
class VLMExtractor(Protocol):
    model_id: str
    backend_name: str  # "mlx-vlm" | "transformers-mps" | "paddleocr" | "glm-ocr"
    def load(self) -> None: ...
    def extract(self, image_path: Path, prompt: str, max_tokens: int) -> ExtractionResult: ...
    def unload(self) -> None: ...

@dataclass(frozen=True)
class ExtractionResult:
    model_id: str
    backend_name: str
    text: str = ""
    load_seconds: float = 0.0
    extract_seconds: float = 0.0
    output_len_chars: int = 0
    error: str | None = None
    traceback_str: str | None = None

class MLXVLMExtractor: ...        # idefics3, qwen2_5_vl, qwen3_vl, gemma4, deepseek_vl_v2 (via MLX port)
class TransformersMPSExtractor: ...# universal HF fallback; bf16 on MPS (ADR-007 pattern); skeleton for PR(b)
class PaddleOCRExtractor: ...     # PaddleOCR-VL only (PaddlePaddle ecosystem); skeleton for PR(b)
class GLMOCRExtractor: ...        # GLM-OCR only (vLLM/Ollama; transformers<5 conflict); skeleton for PR(b)

COHORT_MANIFEST: dict[str, dict] = { ... 10 rows ... }

def get_extractor(model_id: str) -> VLMExtractor: ...
```

Constraints:

- `extract()` returns RAW model output text — no per-model schema parsing (downstream concern of pilot #13's evaluation harness)
- Each extractor handles its own load / unload lifecycle (cleanup before next model loads to avoid OOM and Metal-cache accumulation)
- `COHORT_MANIFEST` is the single source of truth for per-model variation: prompt template, max_tokens, quant target, alt model ID, license, `needs_trust_remote_code` flag, free-form note field
- `MLXVLMExtractor` propagates `trust_remote_code=True` through `mlx_vlm.load(...)` `**kwargs` to the underlying `AutoProcessor.from_pretrained` call (mlx_vlm/utils.py:563); see PR(a) Step 6 commit for the trust-propagation discovery via DeepSeek-OCR-2 install bisection

### Quantization strategy (mixed)

| Model | Dispatcher | Quant | Quant source / fallback |
|---|---|---|---|
| Granite-Docling-258M | MLXVLMExtractor | bf16 | official `ibm-granite/granite-docling-258M-mlx` |
| MinerU-2.5-Pro VLM 1.2B | TransformersMPSExtractor | bf16 | HF Transformers + MPS (ADR-007 path) |
| olmOCR-2-7B | MLXVLMExtractor | **4-bit** | `mlx-community/olmOCR-2-7B-1025-mlx-4bit` |
| DeepSeek-OCR-2 | MLXVLMExtractor | **4-bit** | `mlx-community/DeepSeek-OCR-2-4bit` (`custom_code`) |
| PaddleOCR-VL | PaddleOCRExtractor | whatever PaddleOCR provides | PaddlePaddle native quant |
| GLM-OCR | GLMOCRExtractor | depends on backend | vLLM / Ollama / SGLang (TBD per install attempt) |
| Gemma-4-E4B-it | MLXVLMExtractor | **4-bit** | `lmstudio-community/gemma-4-E4B-it-MLX-4bit` |
| Qwen3-VL-4B-Instruct | MLXVLMExtractor (if port) or TransformersMPSExtractor | 4-bit or bf16 | TBD at install time (PR(b)) |
| PaliGemma-2-3B-mix-448 | TransformersMPSExtractor | bf16 | HF Transformers + MPS (gated; requires Google T&C) |
| Molmo-7B-D-0924 | TransformersMPSExtractor (or MLXVLMExtractor if port) | **4-bit if MLX port** else bf16 with OOM risk | TBD at install time (PR(b)) |

**Non-comparability footnote** (verbatim — pilot #13 must internalise):

> Per-model quant level varies in this cohort smoke. Runtime numbers (load_seconds, extract_seconds) are NOT directly comparable across models — a 4-bit olmOCR-2 will be faster than a bf16 PaliGemma, but this says nothing about the underlying architectures. **Pilot #13's first design constraint should be uniform quantization** (e.g., all models in MLX 4-bit, or all in fp16 transformers). The mixed-quant choice here is a `make-sure-it-works` concession: ADR-008 established that smoke is install-validity proof, not eval-grade benchmarking, and the same scope applies to ADR-009's smoke.

### Per-model native prompt strategy

| Model | Native prompt | Source |
|---|---|---|
| Granite-Docling-258M | `"Convert this page to docling."` | ADR-007 (DocTags output convention) |
| MinerU-2.5-Pro VLM | `"OCR this document"` | OmniDocBench eval convention |
| olmOCR-2-7B | `"Recognize all the text in the image."` | HF model card usage example |
| DeepSeek-OCR-2 | `"<image>\nFree OCR."` | HF model card (deepseek_vl_v2 token convention) |
| PaddleOCR-VL | (no prompt — pipeline call) | PaddleOCR API convention |
| GLM-OCR | `"Recognize all text in the image and output in markdown format"` | HF model card usage example |
| Gemma-4-E4B-it | `"Extract all text and structure from this invoice. Return as markdown."` | Free-form (Cat 3 convention) |
| Qwen3-VL-4B-Instruct | (free-form, same as Gemma) | Cat 3 convention |
| PaliGemma-2-3B-mix-448 | `"caption en"` or task-prefix | PaliGemma task-prefix convention |
| Molmo-7B-D-0924 | (free-form, same as Gemma) | Cat 3 convention |

**Forward-pointer note for pilot #13** (verbatim):

> Per-model native prompts used for smoke evidence (model-card-canonical usage). The choice of prompt strategy for the full pilot evaluation (#13) — single canonical / per-model native / two-prompt sweep / per-category — is a separate methodological question deferred to pilot #13's design. **Pilot #13 should consider a two-prompt arm** to disentangle prompt-strategy effects from architecture effects in the H2 single-shot-vs-orchestrated comparison.

### Smoke methodology (page-1-only, ADR-007 pattern)

- **PDF**: `data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf` (a real German EN16931 invoice — substrate-shift vs ADR-007's synthetic fpdf2 invoice; the shift is methodologically informative since real-world invoice rendering quality varies and synthetic substrates over-simplify per brainstorm v2 §13.5)
- **Pages**: 2; smoke uses **page 1 only** (ADR-007 / ADR-008 convention)
- **Rasterisation**: `sips -s format png --resampleWidth 2480 EN16931_Einfach.pdf --out EN16931_Einfach.page1.png` (matches ADR-007 invocation pattern); cached at `data/raw/smoke/EN16931_Einfach.page1.png`
- **Runner**: `scripts/cohort_smoke.py` (PR(a) Step 3); CLI `--model M`, `--prompt P` (override), `--max-tokens N`, `--out <path>`, `--ordering {transformers-first|mlx-first|model-listed}`
- **Make target**: `make cohort-smoke MODEL=<id> OUT=<path>` (Makefile target authored in PR(a) Step 3; depends on the rasterized PNG; modelled after the existing `inference-smoke` target)
- **Transcript externalization**: per-model output written to `docs/sources/transcripts/<model-slug>.txt`; this ADR's §"Smoke evidence" embeds **snippets** (first ~500-1000 chars of model output) and links to the full transcripts. Per plan §8 O1.

### Smoke evidence — PR(a) cohort entries (3 of 10)

PR(a) covers Granite-Docling-258M (Cat 1 baseline-of-failure), DeepSeek-OCR-2 (Cat 2 representative), Gemma-4-E4B-it (Cat 3 representative). The 3-point cross-section spans the relevant architectural and outcome phenomena: tier-too-small failure, ABI install-conflict failure, large-multimodal success.

#### Cat 1 — Granite-Docling-258M-mlx (baseline-of-failure)

Full transcript: `docs/sources/transcripts/granite-docling-258m.txt`. Summary:

```text
Status:                ok
Load wall-time:        0.96 s   (HF cache hit; ADR-007 install)
Extract wall-time:    10.80 s
Output length:         3,743 chars
Backend:               mlx-vlm
Quant:                 bf16 (official IBM port)
Prompt:                "Convert this page to docling."   (max_tokens=1536)
```

Output snippet (first ~500 chars):

```text
<doctag><page_header><loc_47><loc_8><loc_174><loc_14>Möglichst nach dem Anschluss vom 2.02.2, (g)Möglichst vom 2.02.2</page_header>
<text><loc_54><loc_32><loc_323><loc_40>Händlungschemung (3000) Nr. 471102 vom 05.08.2018</text>
<text><loc_54><loc_55><loc_72><loc_61>Würmer:</text>
<text><loc_54><loc_66><loc_155><loc_73>Liefer- und Leistungsdatum:</text>
<text><loc_54><loc_95><loc_94><loc_102>Verkaufer:</text>
<text><loc_54><loc_106><loc_86><loc_112>Nummern:</text>
...
<text><loc_54><loc_499><loc_72><loc_499>Bemerkungen</text>      [× 50+ identical lines — degenerate token loop]
```

Failure profile (textbook ADR-007 finding 3 baseline-of-failure):

- **Structural format**: ✓ valid DocTags (`<doctag>`, `<page_header>`, `<text><loc_X><loc_Y>...`) — model speaks its native protocol
- **Content fidelity**: ✗ **hallucinated** — `"Händlungschemung (3000) Nr. 471102 vom 05.08.2018"` is fabricated; the real invoice has different numbers / dates
- **Failure mode**: ✗ **degenerate loop** — 50+ identical `<text><loc_54><loc_499><loc_72><loc_499>Bemerkungen</text>` lines (classic VLM token-collapse on a single repeated token)

This reproduces ADR-007's synthetic-corpus 258M failure profile on a real German EN16931 invoice (substrate-shift; same outcome). Granite-Docling-258M's slot in the cohort is **load-bearing for the Cat 1 lower-bound** — the 258M tier defines "what no-good looks like" against which all other Cat 1 cohort entries (MinerU-2.5-Pro VLM, olmOCR-2) must out-perform in pilot #13's evaluation.

#### Cat 2 — DeepSeek-OCR-2 (Type B install-conflict-blocked)

Full transcript: `docs/sources/transcripts/deepseek-ocr-2.txt`. Diagnostic addendum: `docs/sources/transcripts/deepseek-ocr-2.diagnostic.md`.

```text
Status:                error
Load wall-time:        0.00 s   (failed before model weights loaded)
Extract wall-time:     N/A
Output length:         0 chars
Backend:               mlx-vlm (intended; never reached load)
Quant:                 mlx-4bit (intended)
Error:                 ValueError: Unrecognized processing class in <cache-path>.
                       (generic; outer error of a silent-swallow chain)
```

Real root cause (per the diagnostic addendum bisection):

- mlx_vlm's `_patched_auto_processor_from_pretrained` (`mlx_vlm/models/base.py:443-475`) wraps the matched-model branch in `try/except Exception: pass` — the inner exception is silently swallowed, the outer recursion falls through to the unmodified `AutoProcessor.from_pretrained` which fails with a generic message
- Direct invocation of `DeepseekOCR2Processor.from_pretrained()` reveals the inner exception chain: missing remote-code deps (`addict`, `matplotlib`, `einops` — added to `pyproject.toml` at PR(a) Step 6) and finally `ImportError: cannot import name 'LlamaFlashAttention2' from 'transformers.models.llama.modeling_llama'`
- `LlamaFlashAttention2` was **removed in transformers ≥4.45** (HF PR #32827, attention-implementation refactor consolidating per-implementation classes into the unified `attn_implementation` config-driven system); HORUS pins `transformers>=5.5.0` per ADR-007 and is currently on 5.8.0 — 15+ minor versions ahead of the model's last-working version
- All five `mlx-community/DeepSeek-OCR-2-{4,5,6,8}bit + bf16` ports ship the same remote code (uploaded the same day by the same author); switching ports does not resolve the ABI break. The original `deepseek-ai/DeepSeek-OCR-2` repo would face the same import via the Transformers + MPS path

**Type B classification** per §"Install constraints" §"Type taxonomy": the model installs cleanly via `uv add` / `huggingface_hub`; the failure surfaces at runtime *load* time as an ABI-incompatibility between the model's remote-code-imported transformers symbols and our pinned transformers version. Distinct from Type A (install-blocked at package-resolver time) and Type C (runtime-blocked after successful load).

**Resolution at PR(a) time**: documented as Type B per plan §6 A2; **does NOT block ADR-009 ratification**; remains in the cohort table as a documented entry. Cat 2 representation at PR(b) merge time is carried by **PaddleOCR-VL** (smoke evidence due in PR(b) per Step 6); GLM-OCR's transformers<5 conflict is a separate Type B that PR(b) §"Install constraints" §"Type B taxonomy" §"GLM-OCR escalation rule" handles via the vLLM / Ollama / SGLang path or sub-issue file.

#### Cat 3 — Gemma-4-E4B-it (Cat 3 success)

Full transcript: `docs/sources/transcripts/gemma-4-e4b-it.txt`. Summary:

```text
Status:                ok
Load wall-time:      989.35 s   (first-time 6.86 GB download dominates;
                                 cached load on subsequent runs is ~5-10 s)
Extract wall-time:    19.01 s
Output length:           974 chars
Backend:               mlx-vlm
Quant:                 mlx-4bit (lmstudio-community/gemma-4-E4B-it-MLX-4bit; 368.4K downloads)
Prompt:                "Extract all text and structure from this invoice. Return as markdown."  (max_tokens=2048)
```

Output snippet (first ~500 chars):

```markdown
# Handelsrechnung (380) Nr. 471102 vom 05.09.2018

## Kopfzeile
* **Dokumenttyp:** Handelsrechnung (380)
* **Rechnungsnummer:** 471102
* **Datum:** 05.09.2018

## Angaben zum Verkäufer
* **Verkäufer:** [Name fehlt]
* **Nummern:** [Nummern fehlen]
* **Globale Nummer:** 4000001123452 (GLN)
* **Anschrift:** Lieferantenstraße 20

## Angaben zum Käufer/Leistungsempfänger
* **Käufer/Leistungsempfänger:** [Name fehlt]
* **Nummern:** [Nummern fehlen]
* **Name:** Kunden AG Mitte
...
```

Quality profile (qualitative read; quantitative eval is pilot #13's concern):

- **Document type**: ✓ correctly identifies `"Handelsrechnung (380)"` — UN/EDIFACT code 380 is correct for a commercial invoice
- **Field-level extraction**: ✓ accurate on invoice number (471102), date (05.09.2018), seller GLN (4000001123452), buyer name (Kunden AG Mitte), address (69876 Frankfurt), Steuernummer (201/113/40209)
- **Honest absence-marking**: ✓ uses `[Name fehlt]`, `[Nummern fehlen]`, `[ID fehlt]` for missing fields — does NOT hallucinate fabricated values, in direct contrast to Granite-Docling-258M's `"Händlungschemung (3000) Nr. 471102 vom 05.08.2018"` fabrication on the same input
- **Markdown structure**: ✓ clean H1 / H2 / bullet hierarchy; respects the user's `Return as markdown` instruction
- **Meta-awareness**: ✓ closes with an explanatory note about field-level absence; useful affordance for downstream RAG validation per brainstorm v2 §13.5

This is the **upper-region anchor** for the cohort cross-section. Cat 3's transfer-learning hypothesis is positively evidenced at the 4-B-effective scale on a real German invoice with apache-2.0 licensing — a clean thesis-distribution datapoint.

#### Observability gap captured for follow-up

`scripts/cohort_smoke.py` currently bundles HF download time + model load time into a single `load_seconds` measurement. The Gemma 989.35 s figure conflates a 16-min one-time download with a sub-10-second cache-hit load. Disambiguating this in the runner is a known follow-up; the current measurement is fine for install-validity proof (the smoke purpose) but pilot #13 must use a separate mechanism (e.g., warm-cache loop or explicit cache-warm pre-step) for runtime measurement that is comparable across models.

### Install constraints — Type taxonomy (Type A / B / C)

Per plan §6 A2 escalation lemma. Honest disclosure of the taxonomy:

- **Type A (install-blocked)** — package fails to install via `uv add` / `pip install` due to dependency-resolver constraints, ABI mismatch at wheel level, missing platform wheel, or registry unavailability. Resolution: file sub-issue, document, replace ONLY if replacement is in the same Cat. **Cohort exposure**: PaddleOCR-VL adds `paddlepaddle` dep — a large wheel; ARM64 wheels for M1 exist but pinning is required. PR(b) Step 6 attempts the install; if it fails, file `ReebalSami/horus#15+` sub-issue.
- **Type B (compat-blocked)** — package installs cleanly but fails at runtime *load* time due to ABI incompatibility between the model's remote code and our pinned dependency versions. Resolution: identical to Type A. **Cohort exposure**: DeepSeek-OCR-2 (PR(a) Step 6 — `LlamaFlashAttention2` removed in transformers ≥4.45); GLM-OCR (likely PR(b) — `transformers<5.0.0` requirement vs HORUS's `transformers>=5.5.0` pin).
  - **GLM-OCR escalation rule (locked)**: if vLLM / Ollama / SGLang fails to bridge the GLM-OCR install via custom backend, file `ReebalSami/horus#15+` sub-issue rather than silently dropping. The 0.9-B-tier OmniDocBench V1.5 SOTA claim is too load-bearing for the cohort's Cat 2 architectural-innovation hypothesis to drop without explicit Sprint review.
- **Type C (runtime-blocked)** — model loads successfully but fails during inference (OOM / dtype mismatch / generation-side error). Resolution: document the failure profile in §"Smoke evidence" + the model's source stub; pilot #13 inherits the failure profile as evidence for that model's unfitness on M1 Pro / 16 GB. **Cohort exposure**: Molmo-7B-D-0924 at bf16 risks OOM on 16 GB; PR(b) checks for MLX 4-bit port at install time; if no port, document OOM as honest Type C.

**`custom_code` security disclosure**: DeepSeek-OCR-2, PaddleOCR-VL, Molmo-7B-D-0924 all require `trust_remote_code=True`. The dispatcher propagates this through `MLXVLMExtractor.load()` (PR(a) Step 6 fix). For a thesis-grade pipeline, this is an honest cost surfaced rather than hidden — each model's bundled .py code runs as part of the Transformers / MLX-VLM load, and a malicious upload to `mlx-community` / Paddle / Allen-AI's HF org would reach our process. The thesis context accepts this; production pipelines should isolate via subprocess + pinned-revision policies.

### Forward links (work items unblocked by this ADR)

- **Pilot #13** — single-shot zero-shot bake-off evaluation (this cohort + pilot #13's evaluation harness)
- **ADR-NNN-validator-loop** — RAG-based field-validator (sibling forward-pointer; consumes this cohort's outputs)
- **ADR-NNN-layer-1-architecture** — single-shot vs orchestrated comparison decision (sibling; H1 hypothesis)
- **ADR-NNN-cloud-baselines** — commercial API comparand (sibling; brainstorm v2 §8.2)
- **ADR-NNN-layer-2-storage** — graph store decision (sibling; brainstorm v2 §13)
- **Issue #14** closes on PR(b) merge (cohort completion); ADR-007 + ADR-008 frontmatter forward-pointer notes update with "ADR-009 resolves the cohort ADR #14 forward-pointer"

## Source archival

Per `horus-source-archival` rule + ADR-002. PR(a) Step 4 authored 8 new stubs + verified 6 existing:

**Tools (10 cohort models)**:

- `docs/sources/tools/granite-docling-258m-mlx.md` — **new** (PR(a) Step 4). Cat 1 baseline-of-failure. Apache-2.0 / 315 M / idefics3 / official IBM MLX port.
- `docs/sources/tools/mineru-2-5.md` — **existing** (M2D.5 ADR-008 era). Cat 1 mid-tier purpose-trained. Apache-2.0 / 1.16 B / qwen2_vl. Verified content matches the Pro VLM variant.
- `docs/sources/tools/olmocr-2-7b.md` — **new** (PR(a) Step 4). Cat 1 large purpose-trained. Apache-2.0 / 8.29 B / qwen2_5_vl / `mlx-community/olmOCR-2-7B-1025-mlx-4bit`.
- `docs/sources/tools/deepseek-ocr-2.md` — **new** (PR(a) Step 4). Cat 2 architectural-innovation (Contexts Optical Compression v2). Apache-2.0 / 3.39 B / deepseek_vl_v2 / `mlx-community/DeepSeek-OCR-2-4bit` / `custom_code`.
- `docs/sources/tools/deepseek-ocr.md` — **existing** (M2D.5 ADR-007 era). DeepSeek-OCR v1; superseded by v2 in cohort but retained per ADR-011 supersession-over-deletion.
- `docs/sources/tools/paddleocr-vl.md` — **existing** (M2D.5 ADR-008 era). Cat 2 hybrid OCR + VLM. Apache-2.0 / 0.96 B / paddleocr_vl.
- `docs/sources/tools/glm-ocr.md` — **new** (PR(a) Step 4). Cat 2 SOTA-claim. Likely MIT (TBD) / 0.9 B / glm4v / transformers<5.0.0 conflict.
- `docs/sources/tools/gemma-4-e4b-it.md` — **new** (PR(a) Step 4). Cat 3 large multimodal. Apache-2.0 / 7.99 B (4 B effective) / gemma4 / `lmstudio-community/gemma-4-E4B-it-MLX-4bit`.
- `docs/sources/tools/qwen3-vl-4b-instruct.md` — **new** (PR(a) Step 4). Cat 3 mid-tier multimodal. Apache-2.0 / 4.44 B / qwen3_vl.
- `docs/sources/tools/paligemma-2-3b-mix.md` — **new** (PR(a) Step 4). Cat 3 mid-tier multimodal. Gemma-license-gated / ~3 B / paligemma.
- `docs/sources/tools/molmo-7b-d.md` — **new** (PR(a) Step 4). Cat 3 large multimodal (within-lab pair with olmOCR-2). Apache-2.0 / 8.02 B / molmo / `custom_code`.

**Papers (architectural / methodological precedents)**:

- `docs/sources/papers/ibm-2025-granite-docling.md` — **existing**. Granite-Docling architectural paper.
- `docs/sources/papers/poznanski-2025-olmocr2.md` — **existing**. olmOCR-2 architectural paper.
- `docs/sources/papers/deepseek-2025-contexts-optical-compression.md` — **new** (PR(a) Step 4). DeepSeek-OCR v1 architectural paper (Contexts Optical Compression precedent).
- `docs/sources/papers/deepseek-2026-deepseek-ocr-2.md` — **new** (PR(a) Step 4). DeepSeek-OCR-2 paper (v2 evolution + license upgrade).

**Transcripts (PR(a) smoke evidence; new directory per plan §8 O1)**:

- `docs/sources/transcripts/README.md` — **new** (PR(a) Step 5). Convention doc for the transcript directory.
- `docs/sources/transcripts/granite-docling-258m.txt` — **new** (PR(a) Step 5). Cat 1 baseline-of-failure transcript.
- `docs/sources/transcripts/deepseek-ocr-2.txt` — **new** (PR(a) Step 6). Cat 2 Type B install-conflict outer transcript.
- `docs/sources/transcripts/deepseek-ocr-2.diagnostic.md` — **new** (PR(a) Step 6). Cat 2 Type B inner-exception bisection diagnostic.
- `docs/sources/transcripts/gemma-4-e4b-it.txt` — **new** (PR(a) Step 7). Cat 3 success transcript.

PR(b) will add 7 transcripts (one per remaining cohort model) to this directory + amend §"Decision + integration thoughts" §"Smoke evidence" with per-Cat narrative.

## Consequences

- **Positive**: every architectural lever (purpose-training / architectural-innovation / general-multimodal) is represented by 3-4 cohort entries; per-Cat within-comparison and across-Cat between-comparison both possible in pilot #13's evaluation matrix; the dispatcher (`COHORT_MANIFEST` + 4-class Protocol) is the spine pilot #13 inherits without re-design; smoke methodology proven on the real German EN16931 invoice substrate (vs ADR-007's synthetic substrate); the within-lab pair (olmOCR-2 + Molmo-7B-D) gives pilot #13 a methodological control to isolate the purpose-training-on-docs effect from the lab and architecture effects; install-conflict honesty (Type A / B / C taxonomy) preserves the discipline ADR-008 established for the orchestrated-baseline pipeline.
- **Negative**: 10-model cohort is wider than the 7 originally scoped in issue #14 — PR(b) carries 7 model installs, each with its own potential install-conflict friction; the GLM-OCR transformers<5 conflict is the highest-risk PR(b) item (Type B with sub-issue escalation possible per §"Install constraints" §"GLM-OCR escalation rule"); the `custom_code` security cost is real (3 cohort models require `trust_remote_code=True`) and must be re-evaluated if HORUS distribution context shifts to multi-tenant deployment; the mixed-quantization choice means runtime numbers from the smoke are not directly comparable across models, and pilot #13 inherits the burden of a uniform-quant rerun for fair architecture comparison.
- **Neutral**: PR(b) `paddlepaddle` dep adds a large wheel to `pyproject.toml` if PaddleOCR-VL installs cleanly; transcript artifacts (`docs/sources/transcripts/`) accumulate at one file per model but each is small (~1-5 KB) and gitignore-friendly within `docs/sources/`; the substrate-shift from ADR-007's synthetic invoice to ADR-009's real German EN16931 invoice is methodologically informative but introduces a confounder for direct ADR-007 vs ADR-009 quality comparison (mitigated by the cohort's Cat-1 lower-bound being the same `Granite-Docling-258M` model in both ADRs).

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate)
- **ADR-002** — source-archival convention (this ADR's §"Source archival" cites)
- **ADR-003** — strict docs structure (this ADR placed under `docs/decisions/`)
- **ADR-005** — synthetic ZUGFeRD generator (`scripts/generate_zugferd_smoke.py` produces the rasterized smoke input)
- **ADR-007** — local-VLM inference framework (dual-track MLX-VLM + Transformers + MPS; this ADR inherits both branches)
- **ADR-008** — orchestrated-baseline pipeline (Docling + MinerU; this ADR's MinerU-2.5-Pro VLM single-shot evaluation pairs with ADR-008's orchestrated path for pilot #13's H1 comparison)
- **ADR-011** — supersession over deletion (DeepSeek-OCR v1 stub retained alongside v2)
- **Cascade-system ADR-013** — `/commit` workflow (used for commits in this PR)
- **Cascade-system ADR-018** — `@release-manager` discipline (PR(a) + PR(b) both land via `@release-manager`; mid-sprint amendment of §"Decision" in PR(b) follows ADR-018 precedent)

## Provenance

- Plan: `~/.windsurf/plans/adr-009-pilot-vlm-cohort-fbbfa0.md` (ratified via `exitplanmode`)
- Issue: `ReebalSami/horus#14` (sub of #13)
- Brainstorm refs: `docs/prompts/stages/02-brainstorm.md` §3 D8 (multi-architecture comparison) + §6.1 (purpose-training hypothesis) + §7.1 (Oct-2025 wave) + §7.2 (Apple-Silicon throughput) + §8.1 (initial cohort) + §9.1 (Qwen3-VL amendment) + §13 (RAG validator forward-pointer)
- Workspace rules applied: `horus-decision-discipline.md`, `horus-source-archival.md`, `know-your-hardware.md`, `make-sure-it-works.md`, `context7-and-docs-first.md`, `branch-and-pr-required.md`, `no-terminal-oneline-scripts.md`
- Smoke evidence captured: 2026-05-14 (PR(a) — 3 of 10 cohort entries)
- Cascade D / M2D.5 / `fbbfa0`
