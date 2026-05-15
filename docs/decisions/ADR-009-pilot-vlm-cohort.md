# ADR-009 — Pilot VLM cohort selection (10-model, 3-category single-shot bake-off)

| Field | Value |
|---|---|
| **Status** | Accepted (PR(a) smoke evidence captured 2026-05-14 — see §"Decision + integration thoughts" §"Smoke evidence — PR(a) cohort entries"; PR(b) cohort completion captured 2026-05-14 — see §"Decision + integration thoughts" §"Smoke evidence — PR(b) results"; full 10/10 cohort smoke evidence on disk per §"Source archival" §"Transcripts"; **amended 2026-05-15** — see §"Note on evidence limitations (Amendment 1)" inserted above the PR(a) smoke evidence header; mid-sprint amendment per cascade-system ADR-018 precedent) |
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

### Quantization strategy (mixed) — post-PR(b) authoritative state

| Model | Dispatcher | Quant | Quant source / fallback | PR(b) pivot |
|---|---|---|---|---|
| Granite-Docling-258M | MLXVLMExtractor | bf16 | official `ibm-granite/granite-docling-258M-mlx` | — (PR(a)) |
| MinerU-2.5-Pro VLM 1.2B | TransformersMPSExtractor | bf16 | HF Transformers + MPS (ADR-007 path); tied-embeddings rescue per ba9dac7 | — (PR(b) Step 1 wired the tied-embeddings rescue) |
| olmOCR-2-7B | MLXVLMExtractor | **4-bit** | `mlx-community/olmOCR-2-7B-1025-mlx-4bit` | — |
| DeepSeek-OCR-2 | MLXVLMExtractor | **4-bit** | `mlx-community/DeepSeek-OCR-2-4bit` (`custom_code`) | — (PR(a)) |
| PaddleOCR-VL | MLXVLMExtractor | **4-bit** | `mlx-community/PaddleOCR-VL-4bit` (`custom_code`) | **PIVOTED**: skeleton-to-MLX (Step 8). mlx-vlm 0.5.0 ships `paddleocr_vl` arch built-in; sidesteps the heavy `paddlepaddle` dep entirely. `PaddleOCRExtractor` skeleton retained for the alternative paddlepaddle-native path. |
| GLM-OCR | MLXVLMExtractor | **4-bit** | `mlx-community/GLM-OCR-4bit` (mit) | **PIVOTED**: skeleton-to-MLX (Step 9). mlx-vlm 0.5.0 ships `glm_ocr` arch built-in; sidesteps the documented `transformers<5.0.0` conflict at the `pyproject.toml` level entirely. `GLMOCRExtractor` skeleton retained for the alternative vLLM / Ollama / SGLang path. |
| Gemma-4-E4B-it | MLXVLMExtractor | **4-bit** | `lmstudio-community/gemma-4-E4B-it-MLX-4bit` | — (PR(a)) |
| Qwen3-VL-4B-Instruct | TransformersMPSExtractor | **bf16** | base model `Qwen/Qwen3-VL-4B-Instruct` (no alt port) | **TRIPLE-FAIL ESCALATION**: MLX 4-bit (degenerate null-byte output) → MLX 8-bit (Metal watchdog SIGABRT) → bf16 TransformersMPSExtractor (35.10 GiB Metal buffer-cap) — see Step 5 below. M1 Pro 16 GB hardware ceiling for this 4 B-param Qwen3-VL family. |
| PaliGemma-2-3B-mix-448 | TransformersMPSExtractor | bf16 | HF Transformers + MPS (gated; requires Google T&C) | — quant unchanged; prompt overridden (see §"Per-model native prompt strategy" table below) |
| Molmo-7B-D-0924 | MLXVLMExtractor | **4-bit** | `mlx-community/Molmo-7B-D-0924-4bit` (`custom_code`) | **PIVOTED**: TBD-at-install → MLX 4-bit attempted (Step 7); hit MLX core `metal::malloc` 14.4 GB buffer-size bug (mlx#3054 same failure mode); not escalated to higher quant tiers per Step 5 precedent. |

**Non-comparability footnote** (verbatim — pilot #13 must internalise):

> Per-model quant level varies in this cohort smoke. Runtime numbers (load_seconds, extract_seconds) are NOT directly comparable across models — a 4-bit olmOCR-2 will be faster than a bf16 PaliGemma, but this says nothing about the underlying architectures. **Pilot #13's first design constraint should be uniform quantization** (e.g., all models in MLX 4-bit, or all in fp16 transformers). The mixed-quant choice here is a `make-sure-it-works` concession: ADR-008 established that smoke is install-validity proof, not eval-grade benchmarking, and the same scope applies to ADR-009's smoke.

### Per-model native prompt strategy — post-PR(b) authoritative state

| Model | Native prompt | Source | PR(b) override |
|---|---|---|---|
| Granite-Docling-258M | `"Convert this page to docling."` | ADR-007 (DocTags output convention) | — |
| MinerU-2.5-Pro VLM | `"OCR this document"` | OmniDocBench eval convention | — |
| olmOCR-2-7B | `"Extract all text and structure from this invoice. Return as markdown."` | Cohort-canonical (free-form; cohort-comparability default per ADR-009 §"Smoke evidence — PR(b) results") | — kept free-form; semantic-failure profile captured (see Step 4) |
| DeepSeek-OCR-2 | `"<image>\nFree OCR."` | HF model card (deepseek_vl_v2 token convention) | — (PR(a) blocked at Type B) |
| PaddleOCR-VL | `"OCR:"` | Official vLLM PaddleOCR-VL recipe (TASKS dict: `ocr` / `Table Recognition:` / `Formula Recognition:` / `Chart Recognition:`) | **OVERRIDE**: free-form HORUS-canonical → `"OCR:"` after first attempt produced chart-task degenerate-refusal loop (Step 8 — see §"Smoke evidence — PR(b) results"). Architecturally task-prefix-sensitive same as PaliGemma. |
| GLM-OCR | `"Recognize all text in the image and output in markdown format"` | HF model card usage example | — kept (semantic) |
| Gemma-4-E4B-it | `"Extract all text and structure from this invoice. Return as markdown."` | Free-form (Cat 3 convention) | — (PR(a)) |
| Qwen3-VL-4B-Instruct | `"Extract all text and structure from this invoice. Return as markdown."` | Free-form (Cat 3 convention) | — (model never reached generation across all three quant tiers; see Step 5) |
| PaliGemma-2-3B-mix-448 | `"ocr"` | PaliGemma 2 mix task-prefix vocabulary (`caption en` / `ocr` / `detect <class>` / `segment <class>` / `answer en` / `question en`) | **OVERRIDE**: free-form HORUS-canonical → `"ocr"` after first attempt produced canonical out-of-distribution refusal (`Sorry, as a base VLM I am not trained to answer this question.<eos>`); see Step 6. |
| Molmo-7B-D-0924 | `"Extract all text and structure from this invoice. Return as markdown."` | Free-form (Cat 3 convention) | — (model crashed at first generation token; see Step 7) |

**Forward-pointer note for pilot #13** (verbatim, expanded post-PR(b)):

> Per-model native prompts used for smoke evidence (model-card-canonical or HORUS-canonical free-form, whichever surfaced). PR(b) demonstrated that **prompt-prefix sensitivity is the dominant Cat 2 + Cat 3 failure mode for HORUS-canonical free-form prompts**: PaliGemma + PaddleOCR-VL both required canonical task-prefix overrides (`ocr` / `OCR:`); HORUS-canonical free-form prompts triggered refusal or wrong-task routing in both. Pilot #13 must per-model-optimize prompts for at least Cat 2 specialized-VLM and Cat 3 task-prefix-sensitive-VLM rows, OR commit to the cohort-canonical free-form prompt and accept the asymmetric prompt-shape coverage in the H2 single-shot-vs-orchestrated comparison. The two-prompt arm originally proposed (cohort-canonical + per-model-native) remains the most defensible methodological framing.

### Smoke methodology (page-1-only, ADR-007 pattern)

- **PDF**: `data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf` (a real German EN16931 invoice — substrate-shift vs ADR-007's synthetic fpdf2 invoice; the shift is methodologically informative since real-world invoice rendering quality varies and synthetic substrates over-simplify per brainstorm v2 §13.5)
- **Pages**: 2; smoke uses **page 1 only** (ADR-007 / ADR-008 convention)
- **Rasterisation**: `sips -s format png --resampleWidth 2480 EN16931_Einfach.pdf --out EN16931_Einfach.page1.png` (matches ADR-007 invocation pattern); cached at `data/raw/smoke/EN16931_Einfach.page1.png`
- **Runner**: `scripts/cohort_smoke.py` (PR(a) Step 3); CLI `--model M`, `--prompt P` (override), `--max-tokens N`, `--out <path>`, `--ordering {transformers-first|mlx-first|model-listed}`
- **Make target**: `make cohort-smoke MODEL=<id> OUT=<path>` (Makefile target authored in PR(a) Step 3; depends on the rasterized PNG; modelled after the existing `inference-smoke` target)
- **Transcript externalization**: per-model output written to `docs/sources/transcripts/<model-slug>.txt`; this ADR's §"Smoke evidence" embeds **snippets** (first ~500-1000 chars of model output) and links to the full transcripts. Per plan §8 O1.

### Note on evidence limitations (Amendment 1, 2026-05-15)

This subsection was inserted by Amendment 1 (mid-sprint, per cascade-system ADR-018 precedent) and applies to every per-model verdict in the §"Smoke evidence — PR(a) cohort entries" and §"Smoke evidence — PR(b) results" subsections below, plus the §"Cross-Cat field-level comparison" table.

1. **Authoritative ground truth is the embedded factur-x XML** of `EN16931_Einfach.pdf`. Two routes give identical content: (a) `facturx.get_xml_from_pdf(...)` — the canonical Python route for any factur-x PDF; (b) the parallel standalone sidecar `data/raw/german/zugferd-corpus/XML-Rechnung/CII/EN16931_Einfach.cii.xml` shipped by FeRD alongside the PDF. Either is authoritative; both were checked during this amendment. The XML conforms to the EN16931 profile, schematron-validates, and contains every header-level field the smoke verdicts touch (invoice ID, IssueDateTime, SellerTradeParty.Name + PostcodeCode + ID + GlobalID + Steuernummer + USt-IdNr, BuyerTradeParty.Name + ID + PostcodeCode, Currency, Notes).
2. **Pre-amendment verdicts were graded against cohort-majority-vote, not the XML.** Where the cohort majority disagreed with the XML, the pre-amendment verdict followed the majority. Amendment 1 inverts the rows where XML differs from majority; corrections are applied in-line in the §"Smoke evidence — PR(b) results" subsections below and reflected in the §"Cross-Cat field-level comparison" table caveat.
3. **All n=1 cross-model verdicts in this ADR are install-validity proof + hypothesis-generating, NOT eval-grade conclusions** (per ADR-007 + ADR-008 framing of smoke scope). The pre-amendment §"Whole-cohort observations" headline findings ("Smallest model wins on field-level accuracy", "Cat 2 architectural specialization beats Cat 3 raw parameter count", "within-lab control isolates purpose-training-on-docs effect") read as eval-grade conclusions but rest on n=1 evidence. The §"Whole-cohort observations" subsection below has been reorganised by Amendment 1 into two groups (install-validity observations defensible from n=1 vs. eval-grade hypotheses deferred to pilot #13 for confirmation with XML-grounded F1).
4. **Visual page-1 rasterization and the XML agree on every field checked during this amendment.** The header reads `Handelsrechnung (380) Nr. 471102 vom 05.03.2018`; the seller postcode reads `DE 80333 München`; the seller name reads `Lieferant GmbH` (one `t`). The shared misreading of the invoice date as `05.08.2018` by 4 of 7 deploying models (MinerU-2.5-Pro VLM, PaddleOCR-VL, Gemma-4-E4B-it as `05.09`, PaliGemma-2-3B) is an OCR-style failure mode consistent with digit-shape ambiguity (`3` vs `8`) at the 2480 px raster width — **not** a corpus visual-vs-XML inconsistency. Pilot #13 must XML-ground and treat shared misreadings as data, not consensus.
5. **The non-comparability footnote** under §"Quantization strategy" (above) flags runtime numbers as non-comparable due to mixed quant. Amendment 1 extends the same discipline to **quality** verdicts: cross-model field-level comparisons in this ADR are non-eval-grade because the cohort is mixed-quant + single-substrate + n=1. Pilot #13's first eval-harness design constraint should be uniform quantization + XML-grounded F1 + multi-substrate (full ZUGFeRD corpus, not just `EN16931_Einfach.pdf`).

Amendment trigger: Claude Code review of ADR-009 against the embedded factur-x XML (2026-05-15). Cascade D verified the XML sidecar, the PNG raster, and all 10 transcripts during planning. Plan: `~/.windsurf/plans/adr-009-amendment-1-evidence-rigor-eddc73.md`.

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
- **Field-level extraction (Amendment 1 corrected)**: ✓ on invoice number (`471102`), seller GLN (`4000001123452`), buyer name (`Kunden AG Mitte`), buyer address postcode + city (`DE 69876 Frankfurt`), Steuernummer (`201/113/40209`). **✗ Invoice date `05.09.2018` WRONG vs XML** (`<ram:IssueDateTime>20180305` = `05.03.2018`); shared-misreading family with MinerU-2.5-Pro VLM, PaddleOCR-VL, PaliGemma-2-3B (each read `05.08`/`05.09`). The pre-amendment `✓ accurate on ... date (05.09.2018)` framing was the cohort-majority error; only olmOCR-2 and GLM-OCR read the date correctly.
- **Absence-marking behaviour (Amendment 1 reframe)**: present, but a **false negative on the seller name**: `[Name fehlt]` for `Verkäufer` (transcript line 27) despite `Lieferant GmbH` being in the source (XML `<ram:SellerTradeParty><ram:Name>Lieferant GmbH</ram:Name>`; visual page-1; extracted correctly by GLM-OCR, recognisably by MinerU as `Lieferent`, partially by PaddleOCR-VL as Unicode-corrupted `Unหมด QmbH`). The model also marks `Käufer/Leistungsempfänger` as `[Name fehlt]` (transcript line 33) but contradicts itself one line later with `**Name:** Kunden AG Mitte` (line 35) — the buyer-name self-contradiction is itself a calibration failure, not a virtue. Marking present fields as missing is a Type II failure mode. The comparison to Granite-Docling-258M's `"Händlungschemung (3000) Nr. 471102 vom 05.08.2018"` fabrication holds **only on the failure-mode-taxonomy axis** (refusal-style vs hallucination-style); on field-extraction accuracy this is still a wrong answer.
- **Markdown structure**: ✓ clean H1 / H2 / bullet hierarchy; respects the user's `Return as markdown` instruction
- **Meta-awareness**: ✓ closes with an explanatory note about field-level absence; useful affordance for downstream RAG validation per brainstorm v2 §13.5

This is the **upper-region anchor** for the cohort cross-section. Cat 3's transfer-learning hypothesis is positively evidenced at the 4-B-effective scale on a real German invoice with apache-2.0 licensing — a clean thesis-distribution datapoint.

#### Observability gap captured for follow-up

`scripts/cohort_smoke.py` currently bundles HF download time + model load time into a single `load_seconds` measurement. The Gemma 989.35 s figure conflates a 16-min one-time download with a sub-10-second cache-hit load. Disambiguating this in the runner is a known follow-up; the current measurement is fine for install-validity proof (the smoke purpose) but pilot #13 must use a separate mechanism (e.g., warm-cache loop or explicit cache-warm pre-step) for runtime measurement that is comparable across models.

### Smoke evidence — PR(b) results (7 of 10)

PR(b) covers the remaining 7 cohort entries: MinerU-2.5-Pro VLM 1.2B + olmOCR-2-7B (Cat 1 fill-out), PaddleOCR-VL + GLM-OCR (Cat 2 fill-out), and Qwen3-VL-4B-Instruct + PaliGemma-2-3B-mix-448 + Molmo-7B-D-0924 (Cat 3 fill-out). End of PR(b) Step 9 = end of cohort smoke evidence collection: 10 of 10 transcripts on disk, full per-Cat narrative below.

PR(b) surfaced four architectural-pattern observations not visible in PR(a)'s 3-point cross-section, each load-bearing for the cohort's interpretability in pilot #13:

1. **Hardware ceiling at 4 B-effective on M1 Pro 16 GB** — Cat 3 has 50% deployability rate (2/4); plain 4 B+ multimodal VLMs (Qwen3-VL 4 B, Molmo 7 B) are blocked by RAM-cliff and/or upstream MLX bugs. Matformer (Gemma-4 4-B-effective via routing) and small task-tuned (PaliGemma 3 B with prompt override) are the deployable patterns.
2. **Prompt-prefix sensitivity is the dominant Cat 2 + Cat 3 free-form-prompt failure mode** — PaliGemma + PaddleOCR-VL both required canonical task-prefix overrides (`ocr` / `OCR:`); HORUS-canonical free-form prompts triggered refusal or wrong-task routing.
3. **Smallest model wins on field-level accuracy** — PaddleOCR-VL at 0.96 B params extracts more unique fields than 7 B olmOCR-2; GLM-OCR at 0.9 B has the highest per-character precision in cohort. Cat 2 architectural specialization beats Cat 3 raw parameter count for document parsing.
4. **MLX-vs-PyTorch-MPS runtime path matters at the same parameter count** — Qwen3-VL-4B's triple-fail showed MLX 4-bit (degenerate) vs MLX 8-bit (Metal watchdog) vs PyTorch-MPS bf16 (35.10 GiB Metal buffer-cap) all hit different walls. Pilot #13 hardware (M3 Max 64+ GB / Linux + CUDA / hosted inference) needs to re-evaluate every Cat 3 entry that failed on M1 Pro 16 GB.

#### Cat 1 — MinerU-2.5-Pro VLM 1.2B (strongest Cat 1 cohort entry)

Full transcript: `docs/sources/transcripts/mineru-2-5-pro-vlm.txt`. Summary:

```text
Status:                ok
Load wall-time:       19.50 s   (cached + tied-embeddings rescue applied per ba9dac7)
Extract wall-time:    14.45 s
Output length:           940 chars
Backend:               transformers-mps
Quant:                 bf16
Prompt:                "OCR this document"  (max_tokens=2048)
```

Quality profile (qualitative; pilot #13 quantifies):

- **Structural format**: ✓ valid DocTags with `<page>` / `<text bbox="...">` annotations — model speaks its native protocol cleanly
- **Field-level extraction (Amendment 1 corrected)**: ✓ on document type (`Handelsrechnung 380` UN/EDIFACT), invoice number (`471102`), Liefer-/Leistungsdatum (`05.03.2018`), currency (`EUR` explicit), seller GLN (`4000001123452` EXACT vs XML), Steuernummer (`201/113/40209` EXACT vs XML), seller street (`Lieferantenstraße 20`), seller city (`München`), buyer name (`Kunden AG Mitte`), buyer city (`Frankfurt`). **✗ Invoice date `05.08.2018` WRONG vs XML** (`<ram:IssueDateTime>20180305` = `05.03.2018`); shared-misreading family with PaddleOCR-VL, Gemma-4, PaliGemma-2-3B. **✗ Seller postcode**: transcript line 27 reads `<ecel><fcel>DE 0389 München` — the digit string MinerU emitted is `0389`, NOT `90893`. XML truth: `<ram:PostcodeCode>80333</ram:PostcodeCode>`. The pre-amendment claim that MinerU got `DE 90893 München` was unsupported by the transcript (the `90893` was probably mistakenly carried from PaddleOCR-VL's output) — and `90893` itself is also wrong against XML.
- **OCR errors**: seller name `Lieferent` — 1-letter OCR error vs XML `Lieferant`; previously presented as "(should be 'Lieferant'; 1-letter OCR error)" — the framing was correct but propagated the misspelling as if it were ground-truth elsewhere in the ADR; XML-grounded reading: model output `Lieferent` vs XML truth `Lieferant`.
- **Output coherence**: clean; no degenerate-tail or repetition
- **Tied-embeddings rescue**: PR(b) Step 1 (commit `ba9dac7`) wired the tied-embeddings rescue for nested-`text_config` VLMs; required for MinerU's particular `state_dict` packaging quirk where `lm_head.weight` is missing and must be tied from `embed_tokens.weight`. Documented inline in `MLXVLMExtractor.load()` for potential reuse with Molmo / PaliGemma if they exhibit the same packaging.

This is the **strongest Cat 1 entry** in the cohort — best-in-class structural protocol + field-level accuracy at 1.2 B params (5x smaller than olmOCR-2 at 7 B; orchestrated-pipeline VLM stage from ADR-008). The PR(b) Step 1 tied-embeddings rescue is the dispatcher's first non-trivial cross-model affordance (PR(a)'s rescue work was DeepSeek-OCR-2-specific via mlx_vlm's hidden silent-swallow chain).

#### Cat 1 — olmOCR-2-7B (truncated output with header-content mismatch; date + (380) actually correct vs XML — Amendment 1 reframe)

Full transcript: `docs/sources/transcripts/olmocr-2-7b.txt`. Summary:

```text
Status:                ok
Load wall-time:      960.30 s   (first-time download dominates 4.62 GB)
Extract wall-time:    35.40 s
Output length:           314 chars
Backend:               mlx-vlm
Quant:                 mlx-4bit (mlx-community/olmOCR-2-7B-1025-mlx-4bit)
Prompt:                "Extract all text and structure from this invoice. Return as markdown."  (cohort-canonical)
```

Quality profile (Amendment 1 corrected against embedded factur-x XML):

- **Document type**: ✓ EXACT — transcript line 19 reads `Handelsrechnung (380) Nr. 471102 vom 05.03.2018`; UN/EDIFACT code `(380)` is present. The pre-amendment claim that olmOCR-2 "missed UN/EDIFACT code (380)" was unsupported by the transcript.
- **Invoice number**: ✓ `471102` (matches XML `<ram:ID>471102</ram:ID>`).
- **Invoice date (Amendment 1 inversion)**: ✓ CORRECT vs XML — `05.03.2018` matches `<ram:IssueDateTime>20180305`. The pre-amendment verdict ("WRONG — actual invoice date is 05.08.2018") followed cohort-majority-vote (4/7 deploying models read `05.08`/`05.09`); the XML inverts this. olmOCR-2's Liefer-/Leistungsdatum (`05.03.2018`) is also XML-correct (XML `<ram:ActualDeliverySupplyChainEvent>` = `20180305`); the two dates are coincidentally identical in this corpus example, which the pre-amendment narrative misread as "model collapsed two date fields onto a single label".
- **Header-content mismatch (catastrophic; was "role-swap")**: ✗ — the model emits the `Käufer/Leistungsempfänger` header (transcript line 24) and populates the block with **seller** data: `Nummer: 549910` (XML SellerTradeParty.ID), `Name: Lieferant GmbH` (XML SellerTradeParty.Name), `Anschrift: Lieferantenstraße 20` (XML SellerTradeParty.PostalTradeAddress.LineOne). `Kunden AG Mitte` does **not** appear in the transcript at all; the buyer block is fully omitted (premature EOS after the mislabeled seller block — total output 314 chars). The pre-amendment claim that olmOCR-2 "labels seller as `Kunden AG Mitte (Frankfurt)`" was unsupported by the transcript. The actual failure mode is a section-header-application error (right content under wrong heading) coupled with truncation, **not** a buyer↔seller content swap. Still a critical semantic failure profile; still the kind of error that corrupts downstream RAG validation; but the diagnostic is different.
- **Steuernummer (Amendment 1 correction)**: ✗ label-value misclassification — transcript line 28 reads `Steuernummer: DE 80333 München`; the model emitted the seller postcode + city into the Steuernummer field. The actual XML Steuernummer (`201/113/40209`) is missing from output entirely. The pre-amendment claim of "fabricated `12-345-6789`" is unsupported — that string appears nowhere in the transcript. Note: the postcode `80333` itself is XML-correct (matches `<ram:PostcodeCode>80333</ram:PostcodeCode>`); olmOCR-2 read the postcode correctly but applied the wrong label.
- **USt-IdNr (Amendment 1 addition)**: ✗ cross-field swap — transcript line 29 reads `Ust.-Id.-Nr.: GE2020211`; the model emitted the **buyer** ID (XML BuyerTradeParty.ID `GE2020211`) into the seller's USt-IdNr field. The actual XML seller USt-IdNr (`DE123456789`, schemeID `VA`) is missing from output. Compounds with the header-content mismatch: the seller block is populated with seller data (correctly read) AND with one buyer-ID value (cross-field misplacement), under a buyer-block header.
- **Buyer block**: ✗ omitted entirely (XML buyer name `Kunden AG Mitte`, address `Kundenstraße 15 / 69876 Frankfurt` are in the source but never reach the output).
- **Output coherence**: clean (no degenerate tail) but TRUNCATED — only 314 chars, model emitted EOS prematurely after the mislabeled seller block.

**Net XML-graded summary**: olmOCR-2 reads more fields correctly than the pre-amendment verdict suggested (date and `(380)` were both right), BUT the header-content mismatch + cross-field swap + buyer-block omission + Steuernummer label-value confusion still constitute a critical semantic-failure profile. The output is syntactically clean and would pass naive label-presence validation while encoding wrong relationships. olmOCR-2 at 7 B params is still out-performed by 0.96 B PaddleOCR-VL and 0.9 B GLM-OCR on **field-coverage breadth** against XML, but the date + `(380)` corrections move olmOCR-2 closer to the cohort-leaders on the fields it does emit. The within-Cat-1 hypothesis (purpose-training-on-docs at 7 B does not guarantee correctness on German substrate) survives as a hypothesis (n=1; pilot #13 confirms) — the English-only training caveat per HF model card remains the proposed mechanism. Pilot #13 must measure semantic-failure rate (header-content match + buyer-vs-seller field placement) in addition to field-presence F1 to surface this profile.

#### Cat 2 — PaddleOCR-VL (STRONGEST cross-Cat field coverage)

Full transcript: `docs/sources/transcripts/paddleocr-vl.txt`. Two-attempt prompt-prefix escalation chain — see PR(b) Step 8 commit `d26685d` for full first-attempt evidence.

```text
Status:                ok
Load wall-time:        0.98 s   (warm cache after Step 8 first attempt's 715 MB download)
Extract wall-time:    40.78 s
Output length:         2354 chars
Backend:               mlx-vlm
Quant:                 mlx-4bit (mlx-community/PaddleOCR-VL-4bit)
Prompt:                "OCR:"  (canonical task prefix per official vLLM PaddleOCR-VL recipe)
First attempt prompt:  "Extract all text and structure from this invoice. Return as markdown."
                       → 8047 chars degenerate refusal-loop ("*Note: The image is a
                       photograph of a product, not a chart or graph...")
```

Quality profile (lines 19-50 of transcript — production-tier portion):

- **Document type**: ✓ EXACT — `Handelsrechnung (380)` (matches GLM-OCR; better than MinerU's omitted code; better than PaliGemma's "Handelerstellung 2400" garble)
- **Invoice number + Liefer-/Leistungsdatum (Amendment 1 split)**: ✓ invoice number `471102`; ✓ Liefer-/Leistungsdatum `05.03.2018` (matches XML `<ram:ActualDeliverySupplyChainEvent>20180305`).
- **Invoice date (Amendment 1 inversion)**: ✗ `05.08.2018` WRONG vs XML (`<ram:IssueDateTime>20180305` = `05.03.2018`). Shared-misreading family with MinerU-2.5-Pro VLM, Gemma-4 (`05.09`), PaliGemma-2-3B. The pre-amendment framing ("date matches MinerU and PaliGemma; better than olmOCR-2 + GLM-OCR which got the date wrong") was the cohort-majority error — olmOCR-2 and GLM-OCR were the only two models that read the date correctly.
- **Currency**: ✓ explicit `Wahrung: EUR`
- **UNIQUE FIELDS** captured (no other model in cohort got these):
  - `Verkäufer Number: 549910` — seller number from EN16931 schema
  - `Käufer Number: GE2020211` — buyer number from EN16931 schema
- **GLN**: ✓ EXACT `4000001123452` (PaliGemma had 1-digit error to `0001123452`)
- **Seller address (Amendment 1 split)**: ✓ street + city `Lieferantenstraße 20 ... München` (PaliGemma garbled to "Liebwartestraße"; olmOCR-2 omitted street; MinerU read street correctly). ✗ **Postcode `90893` WRONG vs XML** (`<ram:PostcodeCode>80333</ram:PostcodeCode>`); olmOCR-2 (in mislabeled Steuernummer field) and GLM-OCR are the only two cohort models that read the postcode correctly as `80333`.
- **Buyer block**: ✓ FULL with `Kunden AG Mitte / Kundenstraße 15 DE 69876 Frankfurt`
- **Errors / partial fields (Amendment 1 corrected)**: seller name `Unหมด QmbH` Unicode-corrupted (Thai-script bleed-through; XML truth: `Lieferant GmbH` — one `t`; pre-amendment text said "should be `Lieferent GmbH`" which propagated MinerU's 1-letter OCR error as if it were ground truth); USt-IdNr `DE12456789` 1-digit short vs XML `DE123456789`.
- **Degenerate-zero-tail (line 53)**: `Schreibung: 200000...0000` (~700 zeros) — typical late-generation token-distribution collapse. Doesn't degrade the meaningful 90% of the output. Truncating at first sustained zero-stream yields clean production output.

Architectural readout (Amendment 1 reframed against XML): **strongest single-shot extraction in the cohort on field-coverage breadth** for the German EN16931 invoice substrate — PaddleOCR-VL emits the highest count of EN16931 schema fields (Verkäufer-Number `549910`, Käufer-Number `GE2020211`, full buyer block, full seller GLN, currency, document type) even after Amendment 1 corrections shift its invoice-date and seller-postcode verdicts to wrong-vs-XML. PaddleOCR-VL is officially designed as STAGE 2 of a `PP-DocLayoutV2` (layout detection) → per-region call to PaddleOCR-VL with task-appropriate prompt; feeding a full invoice page is OOD per Baidu's vLLM recipe. The fact that 0.96 B params extracts more unique fields than 7 B olmOCR-2 EVEN OUTSIDE its canonical pipeline is the strongest evidence in the cohort for the hypothesis that **Cat 2 architectural specialization may beat Cat 3 raw parameter count** for the document-parsing task — explicit qualifier: n=1 on `EN16931_Einfach.pdf`, mixed-quant runtime, hypothesis-grade not eval-grade. Pilot #13 should evaluate the canonical PP-DocLayoutV2 + PaddleOCR-VL pipeline for the field-level-accuracy upper bound and confirm or refute the hypothesis with XML-grounded F1 across the broader corpus.

#### Cat 2 — GLM-OCR (cleanest output with partial coverage; date + postcode actually correct vs XML — Amendment 1 reframe)

Full transcript: `docs/sources/transcripts/glm-ocr.txt`. Summary:

```text
Status:                ok
Load wall-time:      174.97 s   (1.25 GB download dominates)
Extract wall-time:    33.75 s
Output length:           276 chars
Backend:               mlx-vlm
Quant:                 mlx-4bit (mlx-community/GLM-OCR-4bit, mit license)
Prompt:                "Recognize all text in the image and output in markdown format"
                       (HF model card example)
```

Quality profile (full 276-char output):

- **Document type**: ✓ EXACT (matches PaddleOCR-VL)
- **Invoice number**: ✓
- **Invoice date (Amendment 1 inversion)**: ✓ CORRECT vs XML — `05.03.2018` matches XML `<ram:IssueDateTime>20180305`. Pair with olmOCR-2 as the only two cohort models that read the date correctly. The pre-amendment verdict ("WRONG — same error pattern as olmOCR-2") was the cohort-majority error; against XML, GLM-OCR + olmOCR-2 share the correct reading while MinerU + PaddleOCR + Gemma-4 + PaliGemma share the misreading.
- **Currency**: ✓ explicit
- **`Verkäufer Nummer 549910`**: ✓ (matches PaddleOCR-VL — only 2 cohort entries got this)
- **Seller GLN**: ✓ EXACT
- **Seller name (Amendment 1 XML-grounded)**: ✓✓ **`Lieferant GmbH`** matches XML truth `<ram:SellerTradeParty><ram:Name>Lieferant GmbH</ram:Name>` (one `t`) — the only cohort model to read the seller name exactly. MinerU had `Lieferent` (1-letter OCR error vs XML); PaliGemma garbled to `Werkbuffet`; PaddleOCR-VL had Unicode-corrupted `Unหมด QmbH` (Thai-script bleed-through). Gemma-4 false-negated as `[Name fehlt]`. olmOCR-2 actually read `Lieferant GmbH` correctly (transcript line 26) but emitted it under the wrong section header. **Distinction matters**: the pre-amendment text framed GLM-OCR as the "only model to get the seller name COMPLETELY CORRECT" — against the XML this remains literally true at the **string** level (only GLM-OCR's emission matches `Lieferant GmbH` exactly); but at the **read** level, olmOCR-2 also read it correctly, just placed it wrong.
- **Steuernummer**: ✓
- **Errors (Amendment 1 inversion on postcode)**: seller ZIP `DE 80333 München` ✓ **CORRECT vs XML** — matches `<ram:PostcodeCode>80333</ram:PostcodeCode>`. The pre-amendment verdict ("WRONG (real is `DE 90893 München`)") propagated PaddleOCR-VL's misreading as if authoritative; XML inverts. Remaining error: USt-IdNr label-only with no value (XML truth `DE123456789` is in the source but model did not emit the value).
- **Buyer block + Bemerkungen**: ENTIRELY OMITTED — model stopped after seller block (likely premature EOS or training-distribution coverage gap)
- **Output coherence**: CLEANEST IN COHORT. Zero degenerate-repetition tail. Zero hallucinations. Zero zero-stream collapse.

Architectural readout (Amendment 1 reframed against XML): GLM-OCR's profile is the **inverse of PaddleOCR-VL's** — premature-stop (incomplete coverage but zero tail) vs over-generation-with-tail (full coverage but zero-tail at end). At nearly identical parameter count (0.9 B vs 0.96 B) and same Cat 2 classification, the two models exhibit OPPOSITE failure modes — a methodologically valuable within-Cat-2 architecture-vs-architecture comparison at fixed parameter count. Against the XML, **GLM-OCR is the cohort's highest per-field-precision model** on the fields it does emit: every field GLM-OCR emits matches the XML (document type, invoice number, **invoice date** correctly as `05.03.2018`, currency, Verkäufer-Number, seller GLN, seller name `Lieferant GmbH` exact, seller street, **seller postcode `80333` correct**, Steuernummer) — the only XML-mismatches are USt-IdNr (label-only, value missing) and the entirely-omitted buyer block and Bemerkungen. The Amendment 1 inversions on date + postcode move GLM-OCR's net XML-grounded ranking up sharply: pre-amendment it was framed as "cleanest output with partial coverage but wrong on date + postcode"; post-amendment it is **cleanest output with high precision on emitted fields + correct on date and postcode + incomplete coverage**. Multilingual support per HF tags (zh/en/fr/es/ru/de/ja/ko) is a clean fit for HORUS's German invoice substrate. mit license is a clean thesis-distribution path. Pilot #13's quantitative evaluation should bracket precision-vs-recall on this Cat 2 pair: GLM-OCR maximises precision; PaddleOCR-VL maximises recall — explicit qualifier: n=1 on `EN16931_Einfach.pdf`, hypothesis-grade not eval-grade.

#### Cat 3 — PaliGemma-2-3B-mix-448 (partial-success with prompt override + degenerate repetition)

Full transcript: `docs/sources/transcripts/paligemma2-3b-mix-448.txt`. Two-attempt prompt-prefix escalation — see PR(b) Step 6 commit `f56b2b7` for full first-attempt evidence.

```text
Status:                ok
Load wall-time:       32.42 s   (warm cache after first attempt's 6.07 GB download)
Extract wall-time:    47.01 s
Output length:           942 chars
Backend:               transformers-mps
Quant:                 bf16  (gated; user accepted gemma-license at PR(b) gate-acceptance time)
Prompt:                "ocr"  (canonical PaliGemma 2 mix task prefix)
First attempt prompt:  "caption en\nExtract all text and structure from this invoice. Return as markdown."
                       → 67 chars: "Sorry, as a base VLM I am not trained to answer
                       this question.<eos>"  (canonical out-of-distribution refusal)
```

Quality profile:

- **Correct fields (Amendment 1 corrected)**: invoice number (`471102`), Liefer-/Leistungsdatum (`05.03.2018` matches XML `<ram:ActualDeliverySupplyChainEvent>20180305`), Steuernummer (`201/113/40209` matches XML `<ram:SpecifiedTaxRegistration><ram:ID schemeID="FC">201/113/40209</ram:ID>` — correct, where olmOCR-2 had label-value misclassification), buyer name (`Kunden AG Mitte`), buyer postcode + city (`DE 69876 Frankfurt`), Bemerkungen detected.
- **Invoice date (Amendment 1 inversion)**: ✗ `05.08.2018` WRONG vs XML (`<ram:IssueDateTime>20180305` = `05.03.2018`). Shared-misreading family with MinerU-2.5-Pro VLM, PaddleOCR-VL, Gemma-4 (`05.09`). The pre-amendment framing ("got this right where olmOCR-2 + GLM-OCR didn't") was the cohort-majority error — olmOCR-2 and GLM-OCR were the only two models that read the date correctly.
- **Seller GLN (Amendment 1 graded vs XML)**: ✗ PaliGemma emitted GLN fragment `0001123452` — 1-digit short of XML `<ram:GlobalID schemeID="0088">4000001123452</ram:GlobalID>`. Previously framed as a coverage item under "correct fields" with a parenthetical 1-digit short — against XML this is a wrong field value, not a partial correct field. Moved out of the correct-fields bullet for clarity.
- **OCR transcription errors typical of doc-VLMs on German**: `Handelerstellung (2400)` ← `Handelsrechnung (380)` (UN/EDIFACT code completely garbled), `Liebwartestraße 20` ← `Lieferantenstraße 20` (street name garbled phonetically), `Büffer/Leistungsempfänger` ← `Käufer/Leistungsempfänger` (Käufer mangled), `Bemerkingen` ← `Bemerkungen`, `REG Regulatory Information` hallucinated English text not in source
- **Degenerate loop (lines 42-75)**: model emits the buyer block once correctly (lines 30-37), then restarts and produces 3-4 lightly-varying copies of the same Anschrift / Steuernummer / Telefon / Käufer / Kunden-AG-Frankfurt block. Milder than Granite-Docling's degenerate token loop — the looped content is COHERENT (real field content with OCR errors), not identical-line fabrication.

Architectural readout (Amendment 1 reframed against XML): PaliGemma-2-3B is **task-prefix-sensitive** — free-form prompts trigger the canonical out-of-distribution refusal `Sorry, as a base VLM I am not trained to answer this question.<eos>`; canonical `ocr` task-prefix produces partial extraction. The pre-amendment claim that PaliGemma was "better than olmOCR-2 on date + Steuernummer despite 2-3x smaller param count" is partially correct after Amendment 1: PaliGemma did read the Steuernummer correctly under the right label (whereas olmOCR-2 had label-value misclassification), but **PaliGemma read the invoice date WRONG vs XML** while olmOCR-2 read the invoice date CORRECT vs XML — so the "better than olmOCR-2 on date" claim inverts. The mix-tuned variant retains the prefix-sensitivity property — "mix" expands the prefix vocabulary, not the prompt format. Within-Cat-3 finding: a 3 B task-tuned model with prompt-prefix override produces deploy-and-extract on M1 Pro 16 GB while a 4.44 B free-form-trained model (Qwen3-VL — see below) fails to deploy at all — explicit qualifier: n=1, deployability-axis observation; XML-grounded quality comparison between PaliGemma and Qwen3-VL is impossible here because Qwen3-VL produced no output.

#### Cat 3 — Qwen3-VL-4B-Instruct (RAM-cliff — triple-fail escalation)

Full transcript: `docs/sources/transcripts/qwen3-vl-4b-instruct.txt`. **Triple-fail escalation chain across all three viable quant tiers** — see PR(b) Step 5 commit `1a19086` for the full evidence record.

```text
Final-attempt status:           error
Final-attempt load wall-time:  1323.24 s
Final-attempt error:            RuntimeError: Invalid buffer size: 35.10 GiB
                                (transformers/generation/utils.py:_prefill →
                                 model forward → MPS backend → buffer rejected)
```

Three-tier escalation chain (all on M1 Pro 16 GB):

| Tier | Backend | Wall | Outcome | Failure mode |
|---|---|---|---|---|
| MLX 4-bit (`lmstudio-community/Qwen3-VL-4B-Instruct-MLX-4bit`, 163.3K downloads) | mlx-vlm | 626 s (load 457 + extract 168) | degenerate output | quantization-vs-capacity — 2048 chars of `\x00` null bytes; community consensus on r/LocalLLaMA confirms 4-bit too aggressive for this 4 B-param Qwen3-VL family |
| MLX 8-bit (`lmstudio-community/Qwen3-VL-4B-Instruct-MLX-8bit`, 158.6K downloads) | mlx-vlm | ~13 min (download) + SIGABRT | macOS Metal command-buffer watchdog | `kIOGPUCommandBufferCallbackErrorImpactingInteractivity` — first-token forward-pass kernel exceeded the per-Metal-command-buffer interactivity threshold on M1 Pro / 14 GPU cores. Hardware-OS-level constraint, NOT a model bug. |
| bf16 (`Qwen/Qwen3-VL-4B-Instruct`, no alt port) | transformers-mps | 1323 s (download 21 min + load 1 min) | RuntimeError | `Invalid buffer size: 35.10 GiB` — prefill activations + KV cache for 8602-token image prompt require a single 35.10 GB Metal buffer, which exceeds Metal's per-buffer allocation cap. PyTorch MPS does NOT chunk attention across multiple buffers for this kernel. Hardware ceiling cleanly hit. |

Architectural readout: **Qwen3-VL-4B-Instruct is undeployable on M1 Pro 16 GB at any production-viable quant tier.** Three orthogonal failure modes (quantization-vs-capacity, OS-watchdog, Metal-buffer-cap) demonstrate the hardware-ceiling is real and structural — not a single-config bug. This is the first hard Cat 3 hardware-ceiling finding. Pilot #13's evaluation matrix must bracket: (a) larger Apple Silicon configurations (M3 Max 64+ GB), (b) non-Apple GPU hardware (Linux + CUDA), or (c) accept architecture-restricted Cat 3 sampling (only Matformer / MoE / sub-4-B-effective models run on M1 Pro 16 GB). The within-family pair Qwen3-VL-4B (free-form prompt) vs Gemma-4-E4B-it (Matformer 4-B-effective via routing) is the cohort's clearest architecture-vs-architecture comparison at fixed effective-param count: Matformer wins on this hardware.

#### Cat 3 — Molmo-7B-D-0924 (MLX core bug — RAM-cliff confirmation)

Full transcript: `docs/sources/transcripts/molmo-7b-d-0924.txt`. Summary:

```text
Status:                error
Load wall-time:      821.49 s   (5.32 GB download dominates ~13.6 min)
Backend:               mlx-vlm
Quant:                 mlx-4bit (mlx-community/Molmo-7B-D-0924-4bit, custom_code)
Error:                 RuntimeError: [metal::malloc] Attempting to allocate
                       15458107392 bytes which is greater than the maximum
                       allowed buffer size of 9534832640 bytes.
Crash site:            mlx_vlm/generate.py:1340 generate_step → mx.async_eval
                       (first-token forward pass)
```

This is the **same failure mode** documented in upstream [ml-explore/mlx#3054](https://github.com/ml-explore/mlx/issues/3054) for `mlx-community/Qwen2-VL-2B-Instruct-4bit`. Both share: identical error string format, identical crash site (`generate.py:generate_step → mx.async_eval`), allocation requested orders-of-magnitude larger than the model's parameter footprint can justify (Molmo 7 B at 4-bit ≈ 3.5 GB weights; a 14.4 GB single buffer for first-generation activations is computationally implausible — MLX's tensor-size calculation for some VLM attention shapes is incorrect).

This is **NOT a horus-side wiring bug** (DeepSeek-OCR-2 with the identical `needs_trust_remote_code=True` + custom_code path succeeded in PR(a) Step 6), **NOT a port-specific issue** (the 168-download mlx-community port has been on HF since 2024-11-20 with no reported correctness issues), and **NOT a quantization-vs-capacity issue** (4-bit weights load fine; the crash is in activation buffer allocation during forward pass).

Decision-not-to-escalate rationale: Step 5 (Qwen3-VL-4B) already established the M1 Pro 16 GB hardware ceiling via the triple-fail escalation chain. Molmo at 7 B is a strict superset of the failure surface — 6-bit / 8-bit / bf16 attempts would add gauge-redundant evidence (same conclusion at higher cost). The acceptance criterion for cohort smoke is HONEST EVIDENCE of model deployability on M1 Pro 16 GB; we have it. Pilot #13 on different hardware can re-run.

Within-lab pair comparison (per ADR-009 §"Decision — Cat 1" + §"Decision — Cat 3" methodological control): olmOCR-2-7B (Cat 1, purpose-trained-on-docs) and Molmo-7B-D-0924 (Cat 3, general-multimodal) are both Allen AI, both `qwen2_5_vl` lineage, same 7-8 B param count, same MLX 4-bit quant tier. olmOCR-2 RUNS at MLX 4-bit on M1 Pro 16 GB with the identical extractor pattern; Molmo CRASHES at the same quant tier on the same hardware. The lab effect is held constant, the architecture is held constant — the **purpose-training-on-docs effect** isolates as the load-bearing variable for deployability at this parameter count on this hardware.

#### Cross-Cat field-level comparison (best-prompt-per-model + best-quant-per-model) — Amendment 1 XML-grounded

**Caveat (Amendment 1, 2026-05-15)**: Verdicts in this table are graded against the embedded factur-x XML (`data/raw/german/zugferd-corpus/XML-Rechnung/CII/EN16931_Einfach.cii.xml`), not against cohort-majority-vote. Pre-amendment verdicts followed the cohort majority on several rows; Amendment 1 inverts those rows (notably **Invoice date** — XML truth `05.03.2018`, not `05.08.2018` — and **Seller postcode** — XML truth `80333`, not `90893`) and reframes others (olmOCR-2's "role-swap" was a header-content mismatch + cross-field swap, not buyer-as-seller content swap; MinerU's `DE 90893 München` claim was unsupported by the transcript which actually reads `DE 0389 München`; `Lieferent` was propagated as ground-truth-name despite XML saying `Lieferant`). All verdicts remain n=1 on `EN16931_Einfach.pdf` only; pilot #13 will re-score the full cohort against XML across the broader ZUGFeRD corpus at uniform quant.

Full table on the German EN16931 invoice substrate, 10/10 cohort entries:

| Field (XML truth) | Granite 0.3 B (Cat 1) | MinerU 1.2 B (Cat 1) | olmOCR-2 7 B (Cat 1) | DeepSeek 3.4 B (Cat 2) | PaddleOCR 0.96 B (Cat 2) | GLM-OCR 0.9 B (Cat 2) | Gemma-4 4 B-eff (Cat 3) | PaliGemma 3 B (Cat 3) | Qwen3-VL 4 B (Cat 3) | Molmo 7 B (Cat 3) |
|---|---|---|---|---|---|---|---|---|---|---|
| Doc type `Handelsrechnung (380)` | hallucinated | ✓ EXACT | ✓ EXACT | Type B | ✓ EXACT | ✓ EXACT | ✓ | ✗ `Handelerstellung (2400)` | RAM-cliff | MLX bug |
| Invoice number `471102` | hallucinated | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — |
| **Invoice date `05.03.2018`** (Amendment 1 inverted) | hallucinated | ✗ (`05.08`) | ✓ | — | ✗ (`05.08`) | ✓ | ✗ (`05.09`) | ✗ (`05.08`) | — | — |
| Liefer-/Leistungsdatum `05.03.2018` | hallucinated | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | — | — |
| Currency `EUR` | hallucinated | ✓ | ✓ | — | ✓ explicit | ✓ explicit | — | ✗ omitted | — | — |
| Seller name `Lieferant GmbH` (Amendment 1 XML-grounded) | hallucinated | ≈ `Lieferent` (1-letter OCR) | ≈ value `Lieferant GmbH` correct, emitted under `Käufer/Leistungsempfänger` header | — | ≈ `Unหมด QmbH` Unicode-corrupt | ✓✓ EXACT | ✗ `[Name fehlt]` (false negative) | ✗ `Werkbuffet` | — | — |
| Seller GLN `4000001123452` | hallucinated | ✓ | ✗ omitted | — | ✓ EXACT | ✓ EXACT | ✓ EXACT | ✗ `6000001123452` (digit-flip) | — | — |
| **Seller postcode `80333`** (Amendment 1 added + inverted) | hallucinated | ✗ (`0389`) | ≈ value `80333` correct, emitted in mislabeled `Steuernummer` field | — | ✗ (`90893`) | ✓ | ✗ omitted | ✗ omitted | — | — |
| Seller Steuernummer `201/113/40209` | hallucinated | ✓ | ✗ label-value misclass (field shows `DE 80333 München`) | — | ✓ | ✓ | ✓ | ✓ | — | — |
| Seller USt-IdNr `DE123456789` | hallucinated | ✓ | ✗ cross-field swap (field shows buyer ID `GE2020211`) | — | ≈ `DE12456789` (1-digit short) | ✗ label-only | ✗ omitted | ✗ omitted | — | — |
| **Verkäufer-ID `549910`** | hallucinated | ✓ | ≈ value `549910` correct, emitted under `Käufer/Leistungsempfänger` header | — | ✓ | ✓ | ✗ `[Nummern fehlen]` | ✗ | — | — |
| Buyer name `Kunden AG Mitte` | hallucinated | ✓ | ✗ omitted | — | ✓ | ✗ omitted | ✓ | ✓ | — | — |
| Buyer address (`Kundenstraße 15 / 69876 Frankfurt`) | hallucinated | ✓ | ✗ omitted | — | ✓ | ✗ omitted | ≈ `69876 Frankfurt` only (street omitted) | ≈ `69876 Frankfurt` only (street garbled) | — | — |
| **Käufer-ID `GE2020211`** | hallucinated | ≈ `GE202011` (1-char short) | ≈ value `GE2020211` correct, emitted in mislabeled `USt-IdNr` field | — | ✓ | ✗ omitted | ✗ | ✗ | — | — |
| Output length (chars) | 3743 (with loop) | 940 | 314 | 0 (Type B) | 2354 | 276 | 974 | 942 | 0 / 2048 nulls | 0 |
| Output coherence | degenerate loop | clean | clean (truncated) | — | clean + zero-tail | cleanest | clean | repetition tail | — | — |
| Total params | 0.3 B | 1.2 B | 7 B | 3.4 B | 0.96 B | 0.9 B | 4 B effective | 3 B | 4.4 B | 7 B |

**Notation (Amendment 1)**: All ✓ / ✗ verdicts are graded against the XML field listed in the row header. `✓ EXACT` = extracted exactly as in source (XML-string match, character-for-character); `✓✓` = exact-string match where the rest of the cohort had OCR-level errors (kept as a within-table superlative); `✓` = correct value (may have minor formatting variation that does not change the field value); `≈` = single-digit / single-character OCR error OR value correct but emitted in the wrong field / under the wrong header; `✗` = wrong field value, omitted, hallucinated, or label-only (no value); `—` = model did not reach this field due to upstream blocker (Type B install conflict / RAM-cliff / MLX core bug). The Amendment 1 inversions are flagged with **bold row headers** so the reader can see at a glance which verdicts changed.

#### Whole-cohort observations (Amendment 1 reorganised: install-validity vs eval-grade hypotheses)

Per the §"Note on evidence limitations (Amendment 1)" above. Pre-amendment, this subsection presented 8 flat observations that mixed install-validity findings (defensible from n=1 smoke; no XML grounding required) with eval-grade conclusions (requiring XML-grounded F1 across a broader corpus). Amendment 1 splits them into two groups and qualifies the eval-grade members. Pilot #13 confirms or refutes Group B with the proper eval harness.

##### Group A — Install-validity observations (defensible from n=1 smoke)

These observations are observable at install / load / single-extract time and do **not** depend on field-level XML-grounded F1. They survive intact from the pre-amendment list and are joined by one new finding (A.6) added by Amendment 1.

1. **Hardware ceiling at 4 B-effective on M1 Pro 16 GB.** Cat 3 has 50% deployability rate (2/4); plain 4 B+ multimodal VLMs (Qwen3-VL 4 B, Molmo 7 B) are blocked by RAM-cliff and/or upstream MLX bugs. Matformer (Gemma-4 4-B-effective via routing) and small task-tuned (PaliGemma 3 B with prompt override) are the deployable Cat 3 patterns.
2. **Prompt-prefix sensitivity is the dominant Cat 2 + Cat 3 free-form-prompt failure mode.** PaliGemma + PaddleOCR-VL both required canonical task-prefix overrides (`ocr` / `OCR:`); HORUS-canonical free-form prompts triggered refusal or wrong-task routing in both. Pilot #13 must per-model-optimize prompts for at least these two model-classes, OR commit to the cohort-canonical free-form prompt and accept the asymmetric prompt-shape coverage.
3. **MLX-vs-PyTorch-MPS runtime path matters at the same parameter count.** Step 5's Qwen3-VL-4B triple-fail showed MLX 4-bit (degenerate) vs MLX 8-bit (Metal watchdog) vs PyTorch-MPS bf16 (35.10 GiB Metal buffer-cap) all hit different walls. Pilot #13 hardware (M3 Max 64+ GB / Linux + CUDA / hosted inference) needs to re-evaluate every Cat 3 entry that failed on M1 Pro 16 GB.
4. **DeepSeek-OCR-2 Type B install-conflict remains unresolved at PR(b) merge.** Cat 2 representation at PR(b) merge time = PaddleOCR-VL + GLM-OCR; the `mlx-community/DeepSeek-OCR-2-4bit` `LlamaFlashAttention2` import gap (PR(a) Step 6) requires either a model-side fix from upstream or a HORUS-side transformers downgrade incompatible with the rest of the cohort. Pilot #13 inherits the documented Type B and re-evaluates the Contexts Optical Compression hypothesis with v2.
5. **Skeleton extractor pattern proved over-broad.** 2 of 3 PR(b)-scoped skeletons (`PaddleOCRExtractor`, `GLMOCRExtractor`) became unnecessary at PR(b) merge time because mlx-vlm 0.5.0 ships built-in support for both `paddleocr_vl` and `glm_ocr` archs. Both skeletons are RETAINED in the codebase for the documented alternative paths (paddlepaddle / vLLM / Ollama / SGLang) that pilot #13 may want for cross-runtime validation of the same models. Methodological lesson: install-time architecture discovery should precede skeleton design in future ADRs.
6. **Shared OCR-style misreading on the invoice-date character (Amendment 1 new finding).** 4 of 7 deploying cohort models (MinerU-2.5-Pro VLM, PaddleOCR-VL, PaliGemma-2-3B as `05.08`; Gemma-4-E4B-it as `05.09`) misread the invoice date `05.03.2018` as `05.08.2018` or `05.09.2018`. The visual page-1 raster and the embedded factur-x XML both confirm `05.03.2018`; the shared misreading is **not** a corpus visual-vs-XML inconsistency — it is consistent with a digit-shape ambiguity (3 vs 8 vs 9) at the 2480 px raster width, plausibly amplified by font hinting or sub-pixel rendering on the FeRD example PDF. olmOCR-2 and GLM-OCR were the only two deploying models to read the date correctly. Pilot #13 must XML-ground and **treat shared misreadings as data, not consensus** — a 4/7 cohort-majority can be wrong against authoritative ground truth, as this case demonstrates.

##### Group B — Eval-grade hypotheses (n=1 on `EN16931_Einfach.pdf`; pilot #13 confirms with XML-grounded F1 across the broader corpus)

These observations were presented pre-amendment as conclusions; Amendment 1 reframes them as hypotheses. They depend on field-level grading and on multi-substrate evidence that this smoke does not provide.

1. **Hypothesis — Smallest model wins on field-level accuracy.** PaddleOCR-VL at 0.96 B params emits the highest count of EN16931 schema fields in the cohort (Verkäufer-ID, Käufer-ID exclusive to Cat 2 ≤1 B); GLM-OCR at 0.9 B has the highest per-emitted-field precision against XML (every field GLM-OCR emits matches XML truth, including the Amendment-1-inverted date `05.03.2018` and postcode `80333`); both Cat 2 ≤1 B models outperform 7 B olmOCR-2 on field-coverage breadth. **The hypothesis: Cat 2 architectural specialization may beat Cat 3 raw parameter count for document parsing on this substrate**, single-shot, even outside the canonical 2-stage pipeline. Qualifiers: n=1 on `EN16931_Einfach.pdf`, mixed-quant runtime (PaddleOCR + GLM-OCR + olmOCR-2 all at MLX 4-bit so the comparison is quant-controlled at that tier; the comparison to other models at other quants is confounded). Pilot #13 confirms with XML-grounded F1 across the broader ZUGFeRD corpus at uniform quant.
2. **Hypothesis — Within-lab control isolates the purpose-training-on-docs effect on DEPLOYABILITY (Amendment 1 reframe).** olmOCR-2-7B (Cat 1, purpose-trained-on-docs) and Molmo-7B-D-0924 (Cat 3, general-multimodal) — same lab (Allen AI), same architecture (`qwen2_5_vl`), same parameter count (7 B), same MLX 4-bit quant tier, same dispatcher path — split as: olmOCR-2 RUNS (with header-content mismatch + cross-field swap + buyer-block omission semantic failures); Molmo CRASHES (MLX core tensor-size bug). Lab + architecture held constant; purpose-training-on-docs isolates as the load-bearing variable for **deployability** at this tier on this hardware. **The pre-amendment claim that this also isolates the effect on QUALITY was unsupported**: Molmo crashed before producing any output, so the cohort has zero data points to compare quality between the two within-lab models. The quality-axis hypothesis is deferred to pilot #13 on hardware that runs both models.
3. **Hypothesis — Granite-Docling-258M lower-bound holds on real German invoice substrate.** PR(a)'s synthetic-fpdf2-invoice baseline-of-failure profile (hallucinated content + degenerate token loop) reproduces on `EN16931_Einfach.pdf` (one real-but-FeRD-synthetic German EN16931 invoice; same outcome). Qualifier: n=1 on `EN16931_Einfach.pdf` (a FeRD reference example, not a field-encountered real-world invoice). Pilot #13 confirms with broader corpus including non-FeRD real-world invoices.

#### PR(b) commit graph

8 commits on `feat/adr-009-cohort-completion`:

| SHA | Step | Headline |
|-----|------|----------|
| `ba9dac7` | 1 | tied-embeddings rescue for nested-`text_config` VLMs (MinerU + future) |
| `591aa92` | 2-3 | MinerU-2.5-Pro VLM smoke (Cat 1 success) |
| `3bec415` | 4 | olmOCR-2-7B smoke (Cat 1 partial-success with role-swap) |
| `1a19086` | 5 | Qwen3-VL-4B triple-fail escalation chain (Cat 3 RAM-cliff) |
| `f56b2b7` | 6 | PaliGemma-2-3B prompt-prefix-fix (Cat 3 partial-success) |
| `5847414` | 7 | Molmo-7B-D MLX core bug (Cat 3 RAM-cliff confirmation) |
| `d26685d` | 8 | PaddleOCR-VL OCR-prefix-fix + skeleton-to-MLX pivot (Cat 2 strongest) |
| `04d79b1` | 9 | GLM-OCR mlx-pivot (Cat 2 cleanest) — cohort smokes complete |

End of PR(b) Step 9 = end of cohort smoke evidence collection. Step 10 (this commit) is the ADR amendment; Step 11 is PR push + merge via `@release-manager`.

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

**Transcripts — PR(a) smoke evidence (3 of 10; new directory per plan §8 O1)**:

- `docs/sources/transcripts/README.md` — **new** (PR(a) Step 5). Convention doc for the transcript directory.
- `docs/sources/transcripts/granite-docling-258m.txt` — **new** (PR(a) Step 5). Cat 1 baseline-of-failure transcript.
- `docs/sources/transcripts/deepseek-ocr-2.txt` — **new** (PR(a) Step 6). Cat 2 Type B install-conflict outer transcript.
- `docs/sources/transcripts/deepseek-ocr-2.diagnostic.md` — **new** (PR(a) Step 6). Cat 2 Type B inner-exception bisection diagnostic.
- `docs/sources/transcripts/gemma-4-e4b-it.txt` — **new** (PR(a) Step 7). Cat 3 success transcript.

**Transcripts — PR(b) cohort completion (7 of 10; one per remaining cohort model)**:

- `docs/sources/transcripts/mineru-2-5-pro-vlm.txt` — **new** (PR(b) Step 2-3). Cat 1 success — strongest Cat 1 entry (commit `591aa92`). bf16 / TransformersMPSExtractor + tied-embeddings rescue per `ba9dac7`.
- `docs/sources/transcripts/olmocr-2-7b.txt` — **new** (PR(b) Step 4). Cat 1 partial-success with role-swap + Steuernummer wrong (commit `3bec415`). MLX 4-bit / `mlx-community/olmOCR-2-7B-1025-mlx-4bit`.
- `docs/sources/transcripts/paddleocr-vl.txt` — **new** (PR(b) Step 8). Cat 2 success — STRONGEST cross-Cat field coverage (commit `d26685d`). MLX 4-bit / `mlx-community/PaddleOCR-VL-4bit`. Two-attempt prompt-prefix escalation (free-form refusal → canonical `OCR:`).
- `docs/sources/transcripts/glm-ocr.txt` — **new** (PR(b) Step 9). Cat 2 success — cleanest output, partial coverage (commit `04d79b1`). MLX 4-bit / `mlx-community/GLM-OCR-4bit`.
- `docs/sources/transcripts/qwen3-vl-4b-instruct.txt` — **new** (PR(b) Step 5). Cat 3 RAM-cliff — final-attempt bf16 transcript (commit `1a19086`). Triple-fail escalation chain (MLX 4-bit / 8-bit / bf16) documented in commit + manifest note.
- `docs/sources/transcripts/paligemma2-3b-mix-448.txt` — **new** (PR(b) Step 6). Cat 3 partial-success with prompt override + degenerate repetition (commit `f56b2b7`). bf16 / TransformersMPSExtractor. Two-attempt prompt-prefix escalation (free-form refusal → canonical `ocr`).
- `docs/sources/transcripts/molmo-7b-d-0924.txt` — **new** (PR(b) Step 7). Cat 3 MLX core bug — `metal::malloc` 14.4 GB buffer-size cliff (commit `5847414`). MLX 4-bit / `mlx-community/Molmo-7B-D-0924-4bit`. Same failure mode as upstream `mlx-community/Qwen2-VL-2B-Instruct-4bit` per `ml-explore/mlx#3054`.

End of PR(b) Step 9 = 10/10 cohort transcripts on disk; per-Cat narrative + cross-Cat field-level comparison + whole-cohort observations all amended into §"Decision + integration thoughts" §"Smoke evidence — PR(b) results (7 of 10)" above.

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
- Smoke evidence captured: 2026-05-14 (PR(a) — 3 of 10 cohort entries; PR(b) — 7 of 10 remaining cohort entries; full 10/10 cohort smoke evidence on disk under `docs/sources/transcripts/`)
- Cascade D / M2D.5 / `fbbfa0`
- PR(b) plan: `~/.windsurf/plans/horus-adr-009-prb-kickoff-ba69f3.md` (kickoff handoff at `~/.windsurf/handoffs/horus-adr-009-prb-202605141837-coding.md`)
- PR(b) commit graph (8 commits on `feat/adr-009-cohort-completion`): `ba9dac7` → `591aa92` → `3bec415` → `1a19086` → `f56b2b7` → `5847414` → `d26685d` → `04d79b1` (cohort smokes complete)
- **Amendment 1 (2026-05-15)** — Evidence-limitation reframing + XML-grounded factual corrections. Triggered by Claude Code review of ADR-009 against the embedded factur-x XML; Cascade D verified the XML sidecar (`data/raw/german/zugferd-corpus/XML-Rechnung/CII/EN16931_Einfach.cii.xml`), the page-1 PNG raster (`data/raw/smoke/EN16931_Einfach.page1.png`), and all 10 transcripts in `docs/sources/transcripts/` during planning. Claude Code's "visual-vs-XML inconsistency" hypothesis was **disproved** during verification (the PNG header reads `Handelsrechnung (380) Nr. 471102 vom 05.03.2018`, matching XML exactly; the 4-model shared misreading of `05.08` is an OCR-style failure mode, not a corpus property); replaced by the §"Shared OCR-style misreading on the invoice-date character" finding in Group A of §"Whole-cohort observations". Two additional ADR errors caught during Cascade D's verification that Claude Code's review missed: (i) ADR's claim that MinerU emitted seller postcode `DE 90893 München` was contradicted by the MinerU transcript line 27 reading `DE 0389 München`; (ii) ADR's claim that olmOCR-2 "labels seller as `Kunden AG Mitte (Frankfurt)`" was contradicted by the olmOCR-2 transcript (which contains no `Kunden AG Mitte` at all — the actual failure is a header-content mismatch under the `Käufer/Leistungsempfänger` header populated with seller data, coupled with a cross-field swap on USt-IdNr → buyer-ID). One spelling propagation caught: `Lieferent` was used as ground-truth seller name throughout the ADR, propagating MinerU's 1-letter OCR error; XML truth is `Lieferant`. Mid-sprint amendment per cascade-system ADR-018 precedent. Plan: `~/.windsurf/plans/adr-009-amendment-1-evidence-rigor-eddc73.md`. Single PR titled `docs(adr-009): amendment 1 — install-validity scope reframing + XML-grounded factual corrections`.
