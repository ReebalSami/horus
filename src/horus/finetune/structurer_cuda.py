"""CUDA text-only structurer for evaluating PEFT adapters (ADR-068).

Why this exists
---------------
`finetune.evaluate.evaluate_structurer` requires an `MLXVLMExtractor` and fuses adapters
with `mlx_vlm.trainer.utils.apply_lora_layers`. Both are Apple-Silicon-only, so on the
rented GPU box the adapters produced by `train_cuda.py` would be unscoreable — we would be
training something we cannot measure.

This is deliberately a separate, narrow class rather than an `extract_text` bolted onto
`TransformersMPSExtractor`: that class is an image-first cohort extractor (max_pixels,
repetition_penalty, image-token plumbing) whose `COHORT_MANIFEST` contract is about readers.
The structurer pass is text-only and needs exactly one thing the cohort extractors do not
have — optional PEFT adapter application.

Matched-precision warning (ADR-068)
-----------------------------------
The committed baseline `data/finetune/eval-zeroshot-qwen-adr059-val.json` (0.8257) was
produced by MLX **4-bit** inference on Apple Silicon. This class runs **bf16** on CUDA. A
fine-tuned-vs-baseline delta measured across those two stacks would conflate the adapter's
effect with a quantisation change. So the zero-shot baseline MUST be re-measured with this
class before any adapter number is compared against it — see ADR-068's matched-stack clause.

Conforms structurally to `horus.eval.live.TextExtractor`.

Refs: ADR-068 (venue + matched-stack baseline), ADR-067 (the 2x2 arms this scores).
"""

from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path
from typing import Any, ClassVar

from horus.vlm_extractor import DEFAULT_MAX_TOKENS, ExtractionResult

__all__ = ["CudaStructurerExtractor"]

_LOGGER = logging.getLogger(__name__)


class CudaStructurerExtractor:
    """Text-only bf16 structurer on CUDA, with optional PEFT LoRA adapter.

    Args:
        model_id: HF repo of the base structurer (e.g. ``google/gemma-4-E4B-it``). Note
            this is the CANONICAL repo, not the MLX mirror `COHORT_MANIFEST` maps it to.
        adapter_dir: PEFT adapter directory to apply. ``None`` = zero-shot baseline.
        dtype_name: kept explicit so the eval report can record the precision the number
            was measured at; bf16 matches the training dtype.
    """

    backend_name: ClassVar[str] = "transformers-cuda"

    def __init__(
        self,
        model_id: str,
        *,
        adapter_dir: Path | None = None,
        dtype_name: str = "bfloat16",
    ) -> None:
        self.model_id = model_id
        self._adapter_dir = adapter_dir
        self._dtype_name = dtype_name
        self._model: Any = None
        self._tokenizer: Any = None
        self._load_seconds: float = 0.0

    def load(self) -> None:
        import torch
        from transformers import AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CudaStructurerExtractor requires a visible CUDA device "
                "(use the MLX path on Apple Silicon)"
            )

        started = time.perf_counter()
        dtype = getattr(torch, self._dtype_name)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)

        # AutoModelForCausalLM matches the training path (`train_cuda.py`), so the adapter's
        # module names line up with what it is being applied to.
        from transformers import AutoModelForCausalLM

        # `Any`-typed: this is either the bare base model or a `PeftModel` wrapping it, and
        # the two are unrelated types. Only `.generate` / `.device` / `.eval` are used here,
        # which both expose.
        model: Any = AutoModelForCausalLM.from_pretrained(
            self.model_id, dtype=dtype, device_map="auto"
        )

        if self._adapter_dir is not None:
            from peft import PeftModel

            adapter = Path(self._adapter_dir)
            if not (adapter / "adapter_config.json").exists():
                raise FileNotFoundError(
                    f"{adapter} has no adapter_config.json — not a PEFT adapter directory. "
                    "(An MLX adapter from scripts/finetune_train.py is NOT loadable here.)"
                )
            model = PeftModel.from_pretrained(model, str(adapter), dtype=dtype)
            _LOGGER.info("applied PEFT adapter from %s", adapter)

        model.eval()
        self._model = model
        self._load_seconds = time.perf_counter() - started

    def extract_text(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> ExtractionResult:
        """Generate a completion for a text-only prompt.

        Never raises: failures are bundled into ``ExtractionResult.error``, matching the
        contract the MLX extractors follow, so one bad invoice cannot abort a 29-invoice run.
        """
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("load() must be called before extract_text()")

        started = time.perf_counter()
        try:
            import torch

            # Greedy decoding: the eval must be deterministic, and every committed report
            # this will be compared against was produced greedily (ADR-053 relied on it).
            messages = [{"role": "user", "content": prompt}]
            inputs = self._tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            ).to(self._model.device)

            prompt_len = int(inputs["input_ids"].shape[-1])
            with torch.no_grad():
                output_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    do_sample=False,
                    pad_token_id=self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
                )
            generated = output_ids[0][prompt_len:]
            text = self._tokenizer.decode(generated, skip_special_tokens=True)
            elapsed = time.perf_counter() - started
            n_generated = int(generated.shape[-1])

            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                text=text,
                load_seconds=self._load_seconds,
                extract_seconds=elapsed,
                output_len_chars=len(text),
                generation_tokens=n_generated,
                generation_tps=(n_generated / elapsed if elapsed > 0 else 0.0),
                peak_memory_gb=torch.cuda.max_memory_allocated() / 1e9,
            )
        except Exception as exc:  # noqa: BLE001 — bundled, never raised past extract_text
            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                text="",
                load_seconds=self._load_seconds,
                extract_seconds=time.perf_counter() - started,
                error=str(exc),
                traceback_str=traceback.format_exc(),
            )

    def unload(self) -> None:
        import gc

        import torch

        self._model = None
        self._tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
