"""Real-model inference smoke for the dual-track stack (ADR-007).

Loads Granite-Docling 258M through BOTH inference backends (mlx-vlm +
HuggingFace Transformers + MPS) and runs DocTags extraction on a single
rasterized ZUGFeRD invoice page. Captures the transcript that gets embedded
in ADR-007 §"Decision + integration thoughts" as evidence (per
`make-sure-it-works` + ADR-006 pattern).

NOT in `make test` — this is a one-off, ~10-minute run that downloads ~500
MB of model weights on first invocation. Subsequent runs are fast (cached
in `~/.cache/huggingface/hub/`).

Pipeline:
  1. Read rasterized PNG path from argv[1] (default:
     data/raw/smoke/invoice-001.page1.png).
  2. Backend A — mlx-vlm: load `ibm-granite/granite-docling-258M-mlx`,
     run generate, capture wall-time + output snippet.
  3. Free MLX model (clear Metal cache).
  4. Backend B — Transformers + MPS: load `ibm-granite/granite-docling-258M`,
     run generate on `device='mps'` with bfloat16, capture same metrics.
  5. Print formatted comparison block ready to paste into ADR-007.

Usage:
  uv run python scripts/inference_smoke.py [--prompt TEXT] [--mlx-only|--hf-only] [path/to/page.png]

Refs: ADR-007, brainstorm v2 §7.2, issue #10.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = REPO_ROOT / "data" / "raw" / "smoke" / "invoice-001.page1.png"

MLX_MODEL_ID = "ibm-granite/granite-docling-258M-mlx"
HF_MODEL_ID = "ibm-granite/granite-docling-258M"
PROMPT = "Convert this page to docling."
MAX_TOKENS = 1536
SNIPPET_CHARS = 4000


@dataclass
class BackendResult:
    """Captured evidence for a single backend run."""

    name: str
    model_id: str
    status: str = "pending"  # "ok" | "error"
    load_seconds: float = 0.0
    generate_seconds: float = 0.0
    output_len_chars: int = 0
    output_snippet: str = ""
    error: str = ""
    notes: list[str] = field(default_factory=list)


def _run_mlx_vlm(image_path: Path, prompt: str) -> BackendResult:
    """Backend A — mlx-vlm against ibm-granite/granite-docling-258M-mlx."""
    result = BackendResult(name="mlx-vlm", model_id=MLX_MODEL_ID)
    try:
        from mlx_vlm import generate, load
        from mlx_vlm.prompt_utils import apply_chat_template

        load_start = time.perf_counter()
        model, processor = load(MLX_MODEL_ID)
        result.load_seconds = time.perf_counter() - load_start

        # Granite-Docling = Idefics3 family. mlx-vlm's apply_chat_template
        # handles the Idefics3 image-token routing.
        formatted_prompt = apply_chat_template(processor, model.config, prompt, num_images=1)

        gen_start = time.perf_counter()
        output = generate(
            model,
            processor,
            formatted_prompt,
            [str(image_path)],
            max_tokens=MAX_TOKENS,
            verbose=False,
        )
        result.generate_seconds = time.perf_counter() - gen_start

        # mlx-vlm's `generate` may return either a string OR a GenerationResult
        # object depending on the version; normalize to string for transcript.
        text = output if isinstance(output, str) else getattr(output, "text", str(output))
        result.output_len_chars = len(text)
        result.output_snippet = text[:SNIPPET_CHARS]
        result.status = "ok"

        # Free the MLX model + clear Metal cache before backend B loads.
        del model, processor
        try:
            import mlx.core as mx

            if hasattr(mx, "metal") and hasattr(mx.metal, "clear_cache"):
                mx.metal.clear_cache()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
        gc.collect()
    except Exception as exc:  # noqa: BLE001 - capture for transcript
        result.status = "error"
        result.error = f"{type(exc).__name__}: {exc}"
        result.notes.append(traceback.format_exc(limit=4))
    return result


def _run_transformers_mps(image_path: Path, prompt: str) -> BackendResult:
    """Backend B — HuggingFace Transformers + PyTorch MPS against the
    Granite-Docling 258M reference checkpoint.
    """
    result = BackendResult(name="transformers+mps", model_id=HF_MODEL_ID)
    try:
        import torch
        from PIL import Image
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if not torch.backends.mps.is_available():
            raise RuntimeError(
                "PyTorch MPS backend not available — cannot run Transformers+MPS branch"
            )

        load_start = time.perf_counter()
        processor = AutoProcessor.from_pretrained(HF_MODEL_ID)
        model = AutoModelForImageTextToText.from_pretrained(HF_MODEL_ID, dtype=torch.bfloat16)
        # mypy mis-tracks the chained `.to(...)` through transformers' overload soup;
        # the runtime contract (nn.Module.to(str)) is well-established.
        model = model.to("mps")  # type: ignore[arg-type]
        result.load_seconds = time.perf_counter() - load_start

        image = Image.open(image_path).convert("RGB")
        # Granite-Docling 258M chat template (sourced from the model's
        # chat_template.jinja on HF). Hardcoded here because, when invoked
        # AFTER the mlx-vlm backend run in the same process, transformers'
        # `processor.apply_chat_template(...)` raises "this processor does not
        # have a chat template" — even though `processor.chat_template` is set.
        # The hardcoded form bypasses the processor-state quirk; the prompt
        # bytes are identical to what apply_chat_template produces in
        # isolation. This is acceptable for the one-off smoke; cohort ADR #14
        # will adopt the runtime-canonical pattern once the smoke evidence is
        # captured.
        formatted = (
            "<|start_of_role|>user<|end_of_role|>"
            f"<image>{prompt}<|end_of_text|>\n"
            "<|start_of_role|>assistant<|end_of_role|>"
        )
        # Image inputs stay float32; MPS handles dtype downcast on the model side.
        # Casting pixel_values to bfloat16 manually triggers MPS dtype mismatches.
        inputs = processor(text=formatted, images=[image], return_tensors="pt").to("mps")

        gen_start = time.perf_counter()
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=MAX_TOKENS,
                do_sample=False,
            )
        result.generate_seconds = time.perf_counter() - gen_start

        # Slice off the prompt prefix so the snippet is the generated text only.
        prompt_len = inputs["input_ids"].shape[-1]
        generated_only = generated_ids[:, prompt_len:]
        text = processor.batch_decode(generated_only, skip_special_tokens=False)[0]
        result.output_len_chars = len(text)
        result.output_snippet = text[:SNIPPET_CHARS]
        result.status = "ok"

        del model, processor
        gc.collect()
        if hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()
    except Exception as exc:  # noqa: BLE001 - capture for transcript
        result.status = "error"
        result.error = f"{type(exc).__name__}: {exc}"
        result.notes.append(traceback.format_exc(limit=4))
    return result


def _format_block(result: BackendResult) -> str:
    """Render a single backend's result as a transcript block."""
    border = "-" * 72
    lines = [
        border,
        f"Backend:        {result.name}",
        f"Model:          {result.model_id}",
        f"Status:         {result.status}",
    ]
    if result.status == "ok":
        lines += [
            f"Load wall-time:     {result.load_seconds:>7.2f} s",
            f"Generate wall-time: {result.generate_seconds:>7.2f} s",
            f"Output length:      {result.output_len_chars:>7d} chars",
            f"Output snippet (first {SNIPPET_CHARS} chars):",
            "",
            result.output_snippet,
        ]
    else:
        lines += [
            f"Error:          {result.error}",
            "Traceback (truncated):",
            *result.notes,
        ]
    lines.append(border)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="inference_smoke",
        description="HORUS inference smoke (ADR-007 dual-track evidence)",
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=str(DEFAULT_IMAGE),
        help="Path to rasterized invoice PNG (default: %(default)s)",
    )
    parser.add_argument(
        "--prompt",
        default=PROMPT,
        help="Prompt sent to the VLM (default: %(default)r)",
    )
    backend_group = parser.add_mutually_exclusive_group()
    backend_group.add_argument(
        "--mlx-only",
        action="store_true",
        help="Run mlx-vlm only (fast, ~10 s; for prompt-sweep runs)",
    )
    backend_group.add_argument(
        "--hf-only",
        action="store_true",
        help="Run Transformers + MPS only",
    )
    args = parser.parse_args(argv[1:])
    image_path = Path(args.image).resolve()
    if not image_path.exists():
        print(f"ERROR: image not found at {image_path}", file=sys.stderr)
        print(
            "Hint: run `make zugferd-smoke` first, then "
            "`sips -s format png --resampleWidth 2480 "
            "data/raw/smoke/invoice-001.pdf "
            "--out data/raw/smoke/invoice-001.page1.png` "
            "(both wired into `make inference-smoke`).",
            file=sys.stderr,
        )
        return 2

    print()
    print("=" * 72)
    print("HORUS inference smoke — ADR-007 dual-track evidence")
    print("=" * 72)
    print(f"Image:          {image_path.relative_to(REPO_ROOT)}")
    print(f"Image size:     {image_path.stat().st_size:,} bytes")
    print(f"Prompt:         {args.prompt!r}")
    print(f"max_tokens:     {MAX_TOKENS}")
    print()

    # Execution order: Transformers + MPS FIRST, mlx-vlm SECOND.
    # `import mlx_vlm` monkey-patches transformers' AutoProcessor globally
    # (per `mlx_vlm/models/base.py::_patched_auto_processor_from_pretrained`),
    # which contaminates subsequent `processor(..., return_tensors="pt")`
    # calls (returns mlx.core.array instead of torch.Tensor → breaks
    # `model.generate(...)` device-attribute lookup). Both backends import
    # lazily inside their functions, so running B first preserves pristine
    # transformers state. Cohort ADR #14 will adopt subprocess-isolated
    # backend invocation if the contamination becomes a runtime concern.
    results: list[BackendResult] = []
    if not args.mlx_only:
        results.append(_run_transformers_mps(image_path, args.prompt))
    if not args.hf_only:
        results.append(_run_mlx_vlm(image_path, args.prompt))

    for result in results:
        print(_format_block(result))
        print()

    n_ok = sum(1 for r in results if r.status == "ok")
    print("=" * 72)
    print(f"SUMMARY: {n_ok}/{len(results)} backends ran to completion")
    print("=" * 72)

    # Exit code: 0 only if all selected backends ran successfully.
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
