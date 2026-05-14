"""Cohort VLM extractor dispatcher — ADR-009 productionisation of ADR-007's smoke dispatcher.

Resolves the "cohort ADR #14" forward-pointer in ``scripts/inference_smoke.py:271``
("Cohort ADR #14 will adopt subprocess-isolated backend invocation if the
contamination becomes a runtime concern") and ADR-007's §"Module / abstraction
decisions deferred to cohort ADR #14".

## Architecture (per ADR-009 §3.3)

- **Protocol-based interface** (`VLMExtractor`): structural typing so
  third-party extractors can be added without inheritance hierarchies.
- **4 framework classes**: one per inference framework, NOT one per model
  architecture. Per-model variation lives in `COHORT_MANIFEST` as data,
  not in class subtypes:

  | Framework class            | Covers models with architecture     |
  |----------------------------|-------------------------------------|
  | `MLXVLMExtractor`          | idefics3, qwen2_vl, qwen2_5_vl,     |
  |                            | qwen3_vl, gemma4, deepseek_vl_v2    |
  |                            | (where an MLX port exists)          |
  | `TransformersMPSExtractor` | universal HF fallback (paligemma,   |
  |                            | molmo, any model lacking MLX port)  |
  | `PaddleOCRExtractor`       | paddleocr_vl only (PaddlePaddle     |
  |                            | ecosystem; PR(b) scope)             |
  | `GLMOCRExtractor`          | glm4v / GLM-OCR only (transformers  |
  |                            | <5 conflict; vLLM/Ollama path;      |
  |                            | PR(b) scope)                        |

- **`COHORT_MANIFEST`**: dict[`model_id`, dict] — single source of truth for
  per-model variation (extractor class, category, native prompt template,
  max_tokens, quant target, alternative MLX-port model_id, license,
  `trust_remote_code` flag, methodological note).
- **`get_extractor(model_id)`**: factory that resolves a manifest entry to
  an instantiated extractor. Smoke runners + production code use this; they
  read `prompt_template` / `max_tokens` from the manifest separately.
- **`validate_manifest()`**: runtime schema check; invoked at module import
  time. Fails fast if a manifest row is malformed.

## Inference contamination caveat (inherited from ADR-007)

`import mlx_vlm` monkey-patches `transformers.AutoProcessor` globally
(per `mlx_vlm/models/base.py::_patched_auto_processor_from_pretrained`).
Once contaminated, subsequent `transformers` processors return `mlx.core.array`
instead of `torch.Tensor`, breaking `model.generate(...)` device-attribute
lookup. Cohort smoke runners MUST either:

1. Run `TransformersMPSExtractor` models BEFORE any `MLXVLMExtractor` model
   loads in the same process (the ADR-007 `scripts/inference_smoke.py`
   pattern), OR
2. Use subprocess isolation per backend group.

This dispatcher does **not** enforce ordering — that's the smoke runner's
concern. The pattern is documented for callers.

## Refs

- ADR-007 (dual-track inference framework)
- ADR-008 (orchestrated baseline — install validity precedent)
- ADR-009 (this dispatcher's parent decision; 10-model cohort)
- ADR-018 of cascade-system (`branch-and-pr-required` enforcement)
- `scripts/inference_smoke.py` (ADR-007's dispatcher prototype; this module
  supersedes its responsibilities)
"""

from __future__ import annotations

import gc
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

# Repository root used for resolving relative paths in tests; not load-bearing
# at module-execution time.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_MAX_TOKENS: int = 2048
"""Default `max_new_tokens` for extract() calls when none is supplied."""

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionResult:
    """Single VLM extraction outcome.

    Mirrors the field shape of ADR-007's ``BackendResult`` for transcript-block
    parity with ``scripts/inference_smoke.py``. Frozen so smoke runners can
    safely store results across model boundaries without accidental mutation.

    Convention: `error is None` => success; `error is not None` => failure.
    `text` is always a string; on failure it is empty (errors carry the detail).
    """

    model_id: str
    backend_name: str
    text: str = ""
    load_seconds: float = 0.0
    extract_seconds: float = 0.0
    output_len_chars: int = 0
    error: str | None = None
    traceback_str: str | None = None

    @property
    def is_ok(self) -> bool:
        """True if the extraction completed without error."""
        return self.error is None


@runtime_checkable
class VLMExtractor(Protocol):
    """Structural Protocol every cohort VLM extractor must satisfy.

    ``runtime_checkable`` so `isinstance(x, VLMExtractor)` works in tests +
    factory dispatch. Concrete extractors live in this module; third-party
    extractors only need to provide these attributes and methods.

    Lifecycle contract:
      1. ``__init__`` is cheap (no model load, no network calls).
      2. ``load()`` is where the heavy work happens (download + memory).
      3. ``extract()`` runs inference on a single image path.
      4. ``unload()`` releases backend resources (GPU memory, processor refs).

    Smoke runners and production code should always call ``load()`` before
    ``extract()`` and ``unload()`` between models to avoid OOM accumulation.
    """

    model_id: str
    backend_name: str

    def load(self) -> None: ...

    def extract(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ExtractionResult: ...

    def unload(self) -> None: ...


# ---------------------------------------------------------------------------
# Concrete extractor — MLX-VLM
# ---------------------------------------------------------------------------


class MLXVLMExtractor:
    """MLX-VLM backend extractor.

    Covers cohort models with an MLX port: Granite-Docling-258M (idefics3),
    olmOCR-2-7B (qwen2_5_vl 4-bit), DeepSeek-OCR-2 (deepseek_vl_v2 4-bit;
    `custom_code`), Gemma-4-E4B-it (gemma4 4-bit), and any other model whose
    ``COHORT_MANIFEST`` entry sets ``extractor_class=MLXVLMExtractor``.

    Implementation mirrors ``scripts/inference_smoke.py::_run_mlx_vlm`` but
    productionised: lifecycle methods are explicit, errors are captured in
    ``ExtractionResult.error`` (never raised past ``extract()``), and the
    MLX cache cleanup runs in ``unload()`` (not at the end of ``extract()``,
    so the model can be re-used for multiple ``extract()`` calls).

    Args:
        model_id: Canonical HF model ID for identity (e.g.,
            ``ibm-granite/granite-docling-258M-mlx``).
        alt_model_id: Effective HF ID to download from (e.g.,
            ``mlx-community/olmOCR-2-7B-1025-mlx-4bit`` for the quantised
            variant). Falls back to ``model_id`` when None.
        needs_trust_remote_code: Whether the model's load path requires
            ``trust_remote_code=True``. Currently informational — mlx-vlm
            handles trust_remote_code internally per model registration;
            this flag surfaces the security disclosure at COHORT_MANIFEST
            inspection time.
    """

    backend_name: ClassVar[str] = "mlx-vlm"

    def __init__(
        self,
        model_id: str,
        *,
        alt_model_id: str | None = None,
        needs_trust_remote_code: bool = False,
    ) -> None:
        self.model_id = model_id
        self._effective_model_id = alt_model_id or model_id
        self._needs_trust_remote_code = needs_trust_remote_code
        self._model: Any = None
        self._processor: Any = None
        self._load_seconds: float = 0.0
        self._loaded: bool = False

    def load(self) -> None:
        """Download (if needed) + load the MLX model into Metal memory.

        Idempotent: re-calling on an already-loaded extractor is a no-op.
        Sets ``self._load_seconds`` so ``extract()`` can populate the
        ``ExtractionResult.load_seconds`` field deterministically.
        """
        if self._loaded:
            return
        # Deferred import to keep module import cheap (mlx_vlm pulls in mlx
        # which is heavy on first import).
        from mlx_vlm import load as mlx_load

        load_start = time.perf_counter()
        self._model, self._processor = mlx_load(self._effective_model_id)
        self._load_seconds = time.perf_counter() - load_start
        self._loaded = True

    def extract(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ExtractionResult:
        """Run a single-image extraction.

        Catches all exceptions and bundles them into ``ExtractionResult.error``
        + ``traceback_str``. Smoke runners get usable transcript blocks even
        when individual models fail.
        """
        if not self._loaded:
            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                error="extractor not loaded — call load() before extract()",
            )
        try:
            from mlx_vlm import generate as mlx_generate
            from mlx_vlm.prompt_utils import apply_chat_template

            # Granite-Docling-258M = Idefics3 family; mlx-vlm's apply_chat_template
            # routes image tokens correctly per architecture.
            formatted_prompt = apply_chat_template(
                self._processor,
                self._model.config,
                prompt,
                num_images=1,
            )

            gen_start = time.perf_counter()
            output = mlx_generate(
                self._model,
                self._processor,
                formatted_prompt,
                [str(image_path)],
                max_tokens=max_tokens,
                verbose=False,
            )
            extract_seconds = time.perf_counter() - gen_start

            # mlx-vlm's `generate` may return str OR a GenerationResult
            # object depending on version. Normalize to string.
            text = output if isinstance(output, str) else getattr(output, "text", str(output))

            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                text=text,
                load_seconds=self._load_seconds,
                extract_seconds=extract_seconds,
                output_len_chars=len(text),
            )
        except Exception as exc:  # noqa: BLE001 — capture all backend failures
            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                load_seconds=self._load_seconds,
                error=f"{type(exc).__name__}: {exc}",
                traceback_str=traceback.format_exc(limit=6),
            )

    def unload(self) -> None:
        """Release the MLX model + processor refs and clear Metal cache.

        Idempotent. Must be called between models in a smoke loop to avoid
        Metal-cache accumulation across the 10-model cohort.
        """
        if not self._loaded:
            return
        del self._model
        del self._processor
        self._model = None
        self._processor = None
        # Clear MLX Metal cache (best-effort; varies across mlx versions).
        try:
            import mlx.core as mx

            if hasattr(mx, "metal") and hasattr(mx.metal, "clear_cache"):
                mx.metal.clear_cache()
        except Exception:  # noqa: BLE001 — cleanup is best-effort
            pass
        gc.collect()
        self._loaded = False


# ---------------------------------------------------------------------------
# Concrete extractor — HF Transformers + PyTorch MPS
# ---------------------------------------------------------------------------


class TransformersMPSExtractor:
    """HuggingFace Transformers + PyTorch MPS extractor.

    Universal HF fallback for cohort models without an MLX port (PR(b) scope:
    MinerU-2.5-Pro VLM, PaliGemma-2-3B, Molmo-7B-D). Mirrors
    ``scripts/inference_smoke.py::_run_transformers_mps`` but uses HF-canonical
    ``processor.apply_chat_template(...)`` instead of the hardcoded Granite-Docling
    template string (which only existed in the smoke to bypass the
    mlx_vlm-monkey-patches-transformers contamination — see module docstring).

    Loading order MATTERS in shared-process smoke loops: call this extractor's
    ``load()`` BEFORE any ``MLXVLMExtractor.load()`` to keep transformers' state
    pristine.

    Args:
        model_id: Canonical HF model ID (e.g., ``opendatalab/MinerU2.5-Pro-2604-1.2B``).
        alt_model_id: Effective HF ID to download from. Falls back to ``model_id``.
        needs_trust_remote_code: Whether the model's load path requires
            ``trust_remote_code=True``. Wired through to ``AutoProcessor`` and
            ``AutoModelForImageTextToText.from_pretrained`` when True. Disclosed
            in COHORT_MANIFEST per ADR-009 §3.7.
    """

    backend_name: ClassVar[str] = "transformers-mps"

    def __init__(
        self,
        model_id: str,
        *,
        alt_model_id: str | None = None,
        needs_trust_remote_code: bool = False,
    ) -> None:
        self.model_id = model_id
        self._effective_model_id = alt_model_id or model_id
        self._needs_trust_remote_code = needs_trust_remote_code
        self._model: Any = None
        self._processor: Any = None
        self._load_seconds: float = 0.0
        self._loaded: bool = False

    def load(self) -> None:
        """Download (if needed) + load the model on MPS in bfloat16."""
        if self._loaded:
            return
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if not torch.backends.mps.is_available():
            raise RuntimeError(
                "PyTorch MPS backend not available — TransformersMPSExtractor "
                "requires Apple Silicon + Metal-capable PyTorch (>=2.5 per "
                "pyproject.toml)."
            )

        load_start = time.perf_counter()
        self._processor = AutoProcessor.from_pretrained(
            self._effective_model_id,
            trust_remote_code=self._needs_trust_remote_code,
        )
        model = AutoModelForImageTextToText.from_pretrained(
            self._effective_model_id,
            dtype=torch.bfloat16,
            trust_remote_code=self._needs_trust_remote_code,
        )
        # mypy mis-tracks the chained `.to(...)` through transformers' overload
        # soup; the runtime contract (nn.Module.to(str)) is well-established.
        self._model = model.to("mps")  # type: ignore[arg-type]
        self._load_seconds = time.perf_counter() - load_start
        self._loaded = True

    def extract(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ExtractionResult:
        """Run a single-image extraction via HF processor + model.generate.

        Uses ``processor.apply_chat_template`` (HF-canonical) when the
        processor advertises a chat template. Falls back to a minimal text
        formatting otherwise; per-model template overrides are a PR(b)
        concern (one signature-tweak per added model).
        """
        if not self._loaded:
            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                error="extractor not loaded — call load() before extract()",
            )
        try:
            import torch
            from PIL import Image

            image = Image.open(image_path).convert("RGB")

            # Try HF-canonical chat-template formatting; fall back to a plain
            # "<image>{prompt}" string if the processor doesn't expose one.
            try:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ]
                formatted = self._processor.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=False,
                )
            except AttributeError, ValueError, KeyError:
                # Processor lacks a chat template OR template rendering failed;
                # fall back to a minimal format. Per-model overrides land in
                # PR(b) of ADR-009 when MinerU / PaliGemma / Molmo bring their
                # own template conventions.
                formatted = f"<image>{prompt}"

            # Image inputs stay float32 — MPS handles dtype downcast on the
            # model side. Casting pixel_values to bfloat16 manually triggers
            # MPS dtype mismatches (observed in ADR-007 smoke).
            inputs = self._processor(text=formatted, images=[image], return_tensors="pt").to("mps")

            gen_start = time.perf_counter()
            with torch.no_grad():
                generated_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    do_sample=False,
                )
            extract_seconds = time.perf_counter() - gen_start

            # Slice off the prompt prefix so the snippet is the generated text only.
            prompt_len = inputs["input_ids"].shape[-1]
            generated_only = generated_ids[:, prompt_len:]
            text = self._processor.batch_decode(generated_only, skip_special_tokens=False)[0]

            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                text=text,
                load_seconds=self._load_seconds,
                extract_seconds=extract_seconds,
                output_len_chars=len(text),
            )
        except Exception as exc:  # noqa: BLE001
            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                load_seconds=self._load_seconds,
                error=f"{type(exc).__name__}: {exc}",
                traceback_str=traceback.format_exc(limit=6),
            )

    def unload(self) -> None:
        """Release the HF model + processor refs and clear MPS cache."""
        if not self._loaded:
            return
        del self._model
        del self._processor
        self._model = None
        self._processor = None
        try:
            import torch

            if hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
        except Exception:  # noqa: BLE001 — cleanup is best-effort
            pass
        gc.collect()
        self._loaded = False


# ---------------------------------------------------------------------------
# Concrete extractor — PaddleOCR-VL (skeleton; PR(b) scope)
# ---------------------------------------------------------------------------


class PaddleOCRExtractor:
    """PaddleOCR-VL native-path extractor — skeleton; production install lands in PR(b).

    PaddleOCR-VL (``PaddlePaddle/PaddleOCR-VL``) uses the PaddlePaddle ecosystem
    rather than HuggingFace Transformers. Adding this dispatcher's production
    behavior requires:

    1. Adding ``paddlepaddle`` to ``pyproject.toml`` (large wheel; ARM64 wheels
       exist for M1 but version-pinning needs an ADR per `horus-decision-discipline`).
    2. Wiring PaddleOCR's pipeline API (``PaddleOCR(...)``); the API is not
       a prompt-template VLM but a pipeline-call ("OCR this", structured output).
    3. Reconciling the prompt-vs-pipeline asymmetry — PaddleOCR-VL takes no
       free-form prompt, so this extractor will IGNORE ``prompt`` and pass-through
       the pipeline default.

    Currently raises ``NotImplementedError`` on ``load()`` with a sub-issue
    reference. ``extract()`` propagates the same error.
    """

    backend_name: ClassVar[str] = "paddleocr"

    def __init__(
        self,
        model_id: str,
        *,
        alt_model_id: str | None = None,
        needs_trust_remote_code: bool = False,
    ) -> None:
        self.model_id = model_id
        self._effective_model_id = alt_model_id or model_id
        self._needs_trust_remote_code = needs_trust_remote_code
        self._loaded: bool = False

    def load(self) -> None:
        raise NotImplementedError(
            "PaddleOCRExtractor.load() not implemented in PR(a) of ADR-009. "
            "Production wiring requires `paddlepaddle` dep (PR(b) scope per "
            "ADR-009 §3.8 + §3.7 install-conflict disclosure). "
            "Tracking: ReebalSami/horus#14 PR(b)."
        )

    def extract(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ExtractionResult:
        return ExtractionResult(
            model_id=self.model_id,
            backend_name=self.backend_name,
            error="PaddleOCRExtractor not implemented (PR(b) scope per ADR-009 §3.8)",
        )

    def unload(self) -> None:
        return


# ---------------------------------------------------------------------------
# Concrete extractor — GLM-OCR (skeleton; PR(b) scope)
# ---------------------------------------------------------------------------


class GLMOCRExtractor:
    """GLM-OCR via vLLM / Ollama / SGLang path — skeleton; PR(b) scope.

    GLM-OCR (``zai-org/GLM-OCR``) is the OmniDocBench V1.5 SOTA at 0.9B params
    (94.62 score, Feb 2026 release from Zhipu AI / Z.ai). The model card
    requires ``pip install "transformers<5.0.0"``, which conflicts with HORUS's
    ``transformers>=5.5.0`` pin. Production wiring must use one of the
    alternative inference paths:

    1. vLLM (likely best on Apple Silicon Metal via vLLM's MPS support, TBD verify)
    2. Ollama (GGUF model card already exists for some Z.ai variants)
    3. SGLang (less M1-tested)
    4. Direct MLX port (TBD; no community port at the time of ADR-009 authoring)

    The PR(b) install attempt follows the §3.7 escalation rule: if no clean
    path works, file a ``ReebalSami/horus#15+`` sub-issue rather than silently
    dropping GLM-OCR from the cohort. The 0.9B-tier SOTA claim is too important
    to omit without explicit sprint-review decision.

    Currently raises ``NotImplementedError`` on ``load()`` with escalation
    reference.
    """

    backend_name: ClassVar[str] = "glm-ocr"

    def __init__(
        self,
        model_id: str,
        *,
        alt_model_id: str | None = None,
        needs_trust_remote_code: bool = False,
    ) -> None:
        self.model_id = model_id
        self._effective_model_id = alt_model_id or model_id
        self._needs_trust_remote_code = needs_trust_remote_code
        self._loaded: bool = False

    def load(self) -> None:
        raise NotImplementedError(
            "GLMOCRExtractor.load() not implemented in PR(a) of ADR-009. "
            "Production wiring requires resolving the transformers<5.0.0 "
            "conflict via vLLM/Ollama/SGLang/MLX path (PR(b) scope per "
            "ADR-009 §3.7 escalation rule). "
            "Tracking: ReebalSami/horus#14 PR(b)."
        )

    def extract(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ExtractionResult:
        return ExtractionResult(
            model_id=self.model_id,
            backend_name=self.backend_name,
            error="GLMOCRExtractor not implemented (PR(b) scope per ADR-009 §3.7)",
        )

    def unload(self) -> None:
        return


# ---------------------------------------------------------------------------
# Cohort manifest — single source of truth for per-model variation
# ---------------------------------------------------------------------------

# Category framing (per ADR-009 §3.1):
#   1 = End-to-end doc-VLMs (purpose-trained on document parsing)
#   2 = Architecturally innovative (compression / SOTA OCR on minimal params)
#   3 = General multimodal VLMs (not purpose-trained for docs; transfer test)
CohortCategory = Literal[1, 2, 3]

# Quant target enum — informational; the manifest documents what the
# `alt_model_id` corresponds to (e.g., "mlx-4bit" => the MLX 4-bit community
# port at `alt_model_id`).
QuantTarget = Literal["bf16", "fp16", "mlx-4bit", "mlx-6bit", "mlx-8bit", "native"]

# License enum — surfaces the gated-vs-open distinction for §3.7 disclosure.
LicenseTag = Literal["apache-2.0", "mit", "gemma", "unknown"]

COHORT_MANIFEST: dict[str, dict[str, Any]] = {
    # ---- Category 1 — End-to-end doc-VLMs --------------------------------
    "ibm-granite/granite-docling-258M-mlx": {
        "extractor_class": MLXVLMExtractor,
        "category": 1,
        "prompt_template": "Convert this page to docling.",
        "max_tokens": 1536,
        "quant_target": "bf16",
        "alt_model_id": None,
        "license": "apache-2.0",
        "needs_trust_remote_code": False,
        "note": (
            "Cat 1 baseline-of-failure (per ADR-007 §Decision finding 3 + "
            "ADR-009 §3.9 reconciliation). 315 M total params; en-only."
        ),
    },
    "opendatalab/MinerU2.5-Pro-2604-1.2B": {
        "extractor_class": TransformersMPSExtractor,
        "category": 1,
        "prompt_template": "OCR this document.",
        "max_tokens": 2048,
        "quant_target": "bf16",
        "alt_model_id": None,
        "license": "apache-2.0",
        "needs_trust_remote_code": False,
        "note": (
            "qwen2_vl arch; 1.16 B params; OmniDocBench v1.6 = 95.69 (ADR-008 "
            "forward-pointer). PR(b) scope per ADR-009 §3.8."
        ),
    },
    "allenai/olmOCR-2-7B-1025": {
        "extractor_class": MLXVLMExtractor,
        "category": 1,
        "prompt_template": "Recognize all the text in the image.",
        "max_tokens": 2048,
        "quant_target": "mlx-4bit",
        "alt_model_id": "mlx-community/olmOCR-2-7B-1025-mlx-4bit",
        "license": "apache-2.0",
        "needs_trust_remote_code": False,
        "note": (
            "qwen2_5_vl arch; 8.29 B params; RLVR-fine-tuned on doc tasks. "
            "Built on Qwen2.5-VL-7B-Instruct. EN-only per HF tags. PR(b) scope."
        ),
    },
    # ---- Category 2 — Architecturally innovative -------------------------
    "deepseek-ai/DeepSeek-OCR-2": {
        "extractor_class": MLXVLMExtractor,
        "category": 2,
        "prompt_template": "<image>\nFree OCR.",
        "max_tokens": 2048,
        "quant_target": "mlx-4bit",
        "alt_model_id": "mlx-community/DeepSeek-OCR-2-4bit",
        "license": "apache-2.0",
        "needs_trust_remote_code": True,
        "note": (
            "deepseek_vl_v2 arch; 3.39 B params; Contexts Optical Compression "
            "(arXiv 2601.20552, Feb 2026). Supersedes DeepSeek-OCR v1. "
            "custom_code => trust_remote_code=True (security disclosure)."
        ),
    },
    "PaddlePaddle/PaddleOCR-VL": {
        "extractor_class": PaddleOCRExtractor,
        "category": 2,
        # PaddleOCR-VL takes no free-form prompt; pipeline default is used.
        # The prompt_template field is present for manifest-schema uniformity.
        "prompt_template": "(unused — PaddleOCR pipeline default)",
        "max_tokens": 2048,
        "quant_target": "native",
        "alt_model_id": None,
        "license": "apache-2.0",
        "needs_trust_remote_code": True,
        "note": (
            "paddleocr_vl arch; 0.96 B params; OmniDocBench v1.5 = 94.5 "
            "(SOTA at the tier when released). PaddlePaddle ecosystem — "
            "adds paddlepaddle dep in PR(b) per ADR-009 §3.7."
        ),
    },
    "zai-org/GLM-OCR": {
        "extractor_class": GLMOCRExtractor,
        "category": 2,
        "prompt_template": "Recognize all text in the image and output in markdown format",
        "max_tokens": 2048,
        "quant_target": "native",
        "alt_model_id": None,
        "license": "unknown",  # GitHub repo confirmed apache-2.0/mit-like; verify at install time
        "needs_trust_remote_code": False,
        "note": (
            "glm4v arch (likely); 0.9 B params; OmniDocBench v1.5 = 94.62 "
            "(SOTA at the tier, Feb 2026 release from Z.ai). transformers<5 "
            "conflict => vLLM/Ollama/SGLang/MLX path required in PR(b). "
            "Per ADR-009 §3.7 escalation rule: if no path works, file sub-issue."
        ),
    },
    # ---- Category 3 — General multimodal VLMs ----------------------------
    "google/gemma-4-E4B-it": {
        "extractor_class": MLXVLMExtractor,
        "category": 3,
        "prompt_template": "Extract all text and structure from this invoice. Return as markdown.",
        "max_tokens": 2048,
        "quant_target": "mlx-4bit",
        "alt_model_id": "lmstudio-community/gemma-4-E4B-it-MLX-4bit",
        "license": "apache-2.0",
        "needs_trust_remote_code": False,
        "note": (
            "gemma4 arch; 7.99 B total params, 4 B effective via Matformer; "
            "native multimodal (text+image+audio+video); Apr 2026 release."
        ),
    },
    "Qwen/Qwen3-VL-4B-Instruct": {
        "extractor_class": MLXVLMExtractor,
        "category": 3,
        "prompt_template": "Extract all text and structure from this invoice. Return as markdown.",
        "max_tokens": 2048,
        "quant_target": "mlx-4bit",
        # alt_model_id resolved at PR(b) install time; if no MLX port,
        # switch extractor_class to TransformersMPSExtractor (per ADR-009 §3.8 O6).
        "alt_model_id": None,
        "license": "apache-2.0",
        "needs_trust_remote_code": False,
        "note": (
            "qwen3_vl arch; 4.44 B params; multilingual. v2 §9.1 smaller variant "
            "(replaces 8B/30B-A3B per ADR-009 §3.2 delta)."
        ),
    },
    "google/paligemma2-3b-mix-448": {
        "extractor_class": TransformersMPSExtractor,
        "category": 3,
        # PaliGemma uses task-prefix convention; "caption en" + custom suffix.
        # Free-form prompt below is HORUS-canonical for invoice extraction;
        # may need per-model override in PR(b) when smoke surfaces failure mode.
        "prompt_template": (
            "caption en\nExtract all text and structure from this invoice as markdown."
        ),
        "max_tokens": 2048,
        "quant_target": "bf16",
        "alt_model_id": None,
        "license": "gemma",
        "needs_trust_remote_code": False,
        "note": (
            "paligemma arch; ~3 B params; SOTA table-structure benchmarks. "
            "GATED — requires Google T&C acceptance on HF account before "
            "PR(b) install. Per ADR-009 §3.7 precondition."
        ),
    },
    "allenai/Molmo-7B-D-0924": {
        "extractor_class": TransformersMPSExtractor,
        "category": 3,
        "prompt_template": "Extract all text and structure from this invoice. Return as markdown.",
        "max_tokens": 2048,
        # If no MLX port at install time, bf16 on 8B may OOM on M1 Pro 16 GB —
        # documented as a Cat 3 failure mode per ADR-009 §3.6.
        "quant_target": "bf16",
        "alt_model_id": None,
        "license": "apache-2.0",
        "needs_trust_remote_code": True,
        "note": (
            "molmo arch; 8.02 B total params; built on Qwen2-7B. EN-only. "
            "Within-lab pair with olmOCR-2 (both Allen AI) — methodological "
            "control per ADR-009 §8 O5. custom_code => trust_remote_code=True."
        ),
    },
}


# ---------------------------------------------------------------------------
# Factory + manifest validation
# ---------------------------------------------------------------------------

_REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "extractor_class",
        "category",
        "prompt_template",
        "max_tokens",
        "quant_target",
        "alt_model_id",
        "license",
        "needs_trust_remote_code",
        "note",
    }
)

_VALID_CATEGORIES = frozenset({1, 2, 3})
_VALID_QUANT_TARGETS = frozenset({"bf16", "fp16", "mlx-4bit", "mlx-6bit", "mlx-8bit", "native"})
_VALID_LICENSES = frozenset({"apache-2.0", "mit", "gemma", "unknown"})


def get_extractor(model_id: str) -> VLMExtractor:
    """Instantiate the right extractor for a cohort model_id.

    Reads ``COHORT_MANIFEST[model_id]`` to determine the extractor class +
    wiring args. Smoke runners and production code call this; they read
    the manifest separately for prompt_template / max_tokens (which are
    extraction-call parameters, not extractor-construction parameters).

    Raises:
        KeyError: if ``model_id`` is not in ``COHORT_MANIFEST``.
    """
    if model_id not in COHORT_MANIFEST:
        known = sorted(COHORT_MANIFEST.keys())
        raise KeyError(f"Model {model_id!r} not in COHORT_MANIFEST. Known cohort: {known}")
    entry = COHORT_MANIFEST[model_id]
    cls = entry["extractor_class"]
    return cls(
        model_id=model_id,
        alt_model_id=entry.get("alt_model_id"),
        needs_trust_remote_code=entry.get("needs_trust_remote_code", False),
    )


def validate_manifest() -> None:
    """Verify ``COHORT_MANIFEST`` schema. Invoked at module import time.

    Fails fast on:
      - missing required key (any of _REQUIRED_MANIFEST_KEYS)
      - invalid category (must be 1/2/3)
      - invalid quant_target (must be in _VALID_QUANT_TARGETS)
      - invalid license tag
      - extractor_class not a recognized concrete extractor

    Raises:
        ValueError: with the offending model_id + the specific schema violation.
    """
    valid_classes = (
        MLXVLMExtractor,
        TransformersMPSExtractor,
        PaddleOCRExtractor,
        GLMOCRExtractor,
    )
    for model_id, entry in COHORT_MANIFEST.items():
        missing = _REQUIRED_MANIFEST_KEYS - set(entry.keys())
        if missing:
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] missing required keys: {sorted(missing)}"
            )
        if entry["category"] not in _VALID_CATEGORIES:
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] category must be one of "
                f"{sorted(_VALID_CATEGORIES)}, got {entry['category']!r}"
            )
        if entry["quant_target"] not in _VALID_QUANT_TARGETS:
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] quant_target must be one of "
                f"{sorted(_VALID_QUANT_TARGETS)}, got {entry['quant_target']!r}"
            )
        if entry["license"] not in _VALID_LICENSES:
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] license must be one of "
                f"{sorted(_VALID_LICENSES)}, got {entry['license']!r}"
            )
        if not isinstance(entry["max_tokens"], int) or entry["max_tokens"] <= 0:
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] max_tokens must be a positive int, "
                f"got {entry['max_tokens']!r}"
            )
        if not isinstance(entry["prompt_template"], str):
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] prompt_template must be str, "
                f"got {type(entry['prompt_template']).__name__}"
            )
        if not isinstance(entry["needs_trust_remote_code"], bool):
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] needs_trust_remote_code must be bool, "
                f"got {type(entry['needs_trust_remote_code']).__name__}"
            )
        if not isinstance(entry["extractor_class"], type) or not issubclass(
            entry["extractor_class"], valid_classes
        ):
            raise ValueError(
                f"COHORT_MANIFEST[{model_id!r}] extractor_class must be a subclass of "
                f"one of {[c.__name__ for c in valid_classes]}, got "
                f"{entry['extractor_class']!r}"
            )


# Run manifest validation at import time. If a future edit corrupts the
# manifest schema, the failure surfaces at `import horus.vlm_extractor`, not
# at the first `get_extractor()` call (fail-fast per `horus-config-discipline`
# spirit, even though this manifest is not Pydantic-validated).
validate_manifest()


__all__ = [
    "COHORT_MANIFEST",
    "DEFAULT_MAX_TOKENS",
    "ExtractionResult",
    "GLMOCRExtractor",
    "MLXVLMExtractor",
    "PaddleOCRExtractor",
    "TransformersMPSExtractor",
    "VLMExtractor",
    "get_extractor",
    "validate_manifest",
]
