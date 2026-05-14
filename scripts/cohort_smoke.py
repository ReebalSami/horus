"""Cohort smoke runner — ADR-009 §Decision evidence generator.

PR(a) Step 3 per the ADR-009 plan. Loads each cohort model in turn, runs an
extraction against a single rasterized PDF page (default:
``data/raw/smoke/EN16931_Einfach.page1.png``), and emits ADR-007-style
transcript blocks suitable for embedding in ADR-009 §Decision.

The runner is a thin wrapper over `horus.vlm_extractor`:

  1. Resolve the target model_id(s) — single via ``--model``, subset via
     ``--models``, or the full cohort via no flag (or ``--all``).
  2. Apply the loading-order policy per the module docstring's contamination
     caveat (TransformersMPSExtractor models load FIRST when ordering would
     otherwise contaminate ``transformers.AutoProcessor`` state). The default
     ordering policy is "transformers-first".
  3. For each model:
       a. ``get_extractor(model_id)`` instantiates the right concrete class.
       b. ``extractor.load()`` downloads (if needed) + loads into memory.
       c. ``extractor.extract(image_path, prompt=manifest_prompt,
          max_tokens=manifest_max_tokens)`` runs inference.
       d. ``extractor.unload()`` releases backend memory before the next model.
  4. Format each ``ExtractionResult`` as a transcript block (mirrors ADR-007's
     ``_format_block`` shape: border + key-value rows + snippet).
  5. Summary: N_ok / N_total. Exit code = 0 iff all selected models succeeded.

NOT in ``make test`` — this is a multi-model run that downloads tens of GB of
weights on first invocation and takes ~20-40 minutes on M1 Pro for the full
cohort. The ``make cohort-smoke`` Makefile target wires up the rasterization
preconditioning + per-model invocation.

Usage:
    uv run python scripts/cohort_smoke.py [path/to/image.png]
        # runs the full cohort

    uv run python scripts/cohort_smoke.py --model ibm-granite/granite-docling-258M-mlx
        # runs a single model (typical PR(a) per-model commit-cycle invocation)

    uv run python scripts/cohort_smoke.py \
        --models ibm-granite/granite-docling-258M-mlx,deepseek-ai/DeepSeek-OCR-2 \
        --out /tmp/transcripts.txt
        # runs a subset; redirects transcripts to a file

Refs: ADR-009 §3.5 (smoke PDF), §3.6 (mixed quantization),
`scripts/inference_smoke.py` (transcript format precedent from ADR-007).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from horus.vlm_extractor import (
    COHORT_MANIFEST,
    DEFAULT_MAX_TOKENS,
    ExtractionResult,
    MLXVLMExtractor,
    TransformersMPSExtractor,
    get_extractor,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = REPO_ROOT / "data" / "raw" / "smoke" / "EN16931_Einfach.page1.png"

# How much of the model output to include in the transcript snippet.
SNIPPET_CHARS = 4000


def _format_block(result: ExtractionResult, category: int) -> str:
    """Render a single ExtractionResult as a transcript block.

    Mirrors ``scripts/inference_smoke.py::_format_block`` for ADR-007 lineage
    continuity. The category prefix is the ADR-009 §3.1 framework tag.
    """
    border = "-" * 72
    lines = [
        border,
        f"Model:          {result.model_id}",
        f"Category:       Cat {category}",
        f"Backend:        {result.backend_name}",
        f"Status:         {'ok' if result.is_ok else 'error'}",
    ]
    if result.is_ok:
        lines += [
            f"Load wall-time:     {result.load_seconds:>7.2f} s",
            f"Extract wall-time:  {result.extract_seconds:>7.2f} s",
            f"Output length:      {result.output_len_chars:>7d} chars",
            f"Output snippet (first {SNIPPET_CHARS} chars):",
            "",
            result.text[:SNIPPET_CHARS],
        ]
    else:
        lines += [
            f"Load wall-time:     {result.load_seconds:>7.2f} s",
            f"Error:          {result.error}",
        ]
        if result.traceback_str:
            lines += [
                "Traceback (truncated):",
                result.traceback_str,
            ]
    lines.append(border)
    return "\n".join(lines)


def _select_models(
    *,
    single: str | None,
    subset_csv: str | None,
    run_all: bool,
) -> list[str]:
    """Resolve CLI flags into a concrete list of model_ids to run.

    Precedence: ``--model`` > ``--models`` > ``--all`` > full-cohort default.
    Validates that every requested model_id exists in ``COHORT_MANIFEST``.
    """
    if single is not None:
        if single not in COHORT_MANIFEST:
            raise SystemExit(
                f"ERROR: model {single!r} not in COHORT_MANIFEST. "
                f"Known: {sorted(COHORT_MANIFEST.keys())}"
            )
        return [single]
    if subset_csv is not None:
        subset = [m.strip() for m in subset_csv.split(",") if m.strip()]
        unknown = [m for m in subset if m not in COHORT_MANIFEST]
        if unknown:
            raise SystemExit(
                f"ERROR: unknown model(s) in --models: {unknown}. "
                f"Known: {sorted(COHORT_MANIFEST.keys())}"
            )
        return subset
    # Default + --all: full cohort.
    _ = run_all  # accepted but informational; full-cohort is the implicit default
    return list(COHORT_MANIFEST.keys())


def _order_models(model_ids: list[str], policy: str) -> list[str]:
    """Apply the loading-order policy.

    "transformers-first" (default): load TransformersMPSExtractor models BEFORE
    any MLXVLMExtractor model in the same process, per the contamination
    caveat documented in ``horus.vlm_extractor`` module docstring.

    "manifest-order": preserve manifest insertion order (Cat 1 → Cat 2 → Cat 3).
    Used when the smoke is single-model or when the user explicitly wants
    category-order traversal.

    Other backends (PaddleOCR, GLMOCR) are appended last — they currently
    raise NotImplementedError but the order keeps them out of the
    contamination-sensitive zone.
    """
    if policy == "manifest-order":
        return model_ids

    def _group(model_id: str) -> int:
        cls = COHORT_MANIFEST[model_id]["extractor_class"]
        if cls is TransformersMPSExtractor:
            return 0  # load first
        if cls is MLXVLMExtractor:
            return 1  # load after Transformers
        return 2  # PaddleOCR / GLMOCR — load last

    return sorted(model_ids, key=_group)


def _run_one(
    model_id: str,
    image_path: Path,
    max_tokens_override: int | None,
) -> ExtractionResult:
    """Run a single cohort model end-to-end (load → extract → unload).

    Reads ``prompt_template`` + ``max_tokens`` from ``COHORT_MANIFEST``.
    CLI override of ``max_tokens`` takes precedence when provided.
    """
    manifest_entry = COHORT_MANIFEST[model_id]
    prompt = manifest_entry["prompt_template"]
    max_tokens = (
        max_tokens_override if max_tokens_override is not None else manifest_entry["max_tokens"]
    )

    extractor = get_extractor(model_id)
    try:
        extractor.load()
    except NotImplementedError as exc:
        # Skeleton extractor (PaddleOCR / GLMOCR) — surface the PR(b) deferral
        # as a structured error result; don't propagate.
        return ExtractionResult(
            model_id=model_id,
            backend_name=extractor.backend_name,
            error=f"NotImplementedError: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 — capture install failures as transcript evidence
        import traceback as tb

        return ExtractionResult(
            model_id=model_id,
            backend_name=extractor.backend_name,
            error=f"{type(exc).__name__}: {exc}",
            traceback_str=tb.format_exc(limit=6),
        )

    result = extractor.extract(image_path=image_path, prompt=prompt, max_tokens=max_tokens)
    extractor.unload()
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cohort_smoke",
        description="HORUS cohort smoke runner — ADR-009 §Decision evidence generator",
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=str(DEFAULT_IMAGE),
        help="Path to rasterized invoice PNG (default: %(default)s)",
    )
    selection_group = parser.add_mutually_exclusive_group()
    selection_group.add_argument(
        "--model",
        metavar="MODEL_ID",
        help="Run a single cohort model (must be a key in COHORT_MANIFEST)",
    )
    selection_group.add_argument(
        "--models",
        metavar="M1,M2,...",
        help="Run a comma-separated subset of cohort models",
    )
    selection_group.add_argument(
        "--all",
        action="store_true",
        help="Run the full 10-model cohort (default when no selection flag is given)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=(
            "Override max_tokens for every model "
            f"(default: per-model from COHORT_MANIFEST; module default: {DEFAULT_MAX_TOKENS})"
        ),
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="Write transcripts to PATH instead of stdout",
    )
    parser.add_argument(
        "--ordering",
        choices=["transformers-first", "manifest-order"],
        default="transformers-first",
        help=(
            "Loading-order policy. 'transformers-first' (default) avoids the "
            "mlx_vlm-monkey-patches-transformers contamination caveat; "
            "'manifest-order' preserves Cat 1/2/3 traversal."
        ),
    )
    args = parser.parse_args(argv[1:])

    image_path = Path(args.image).resolve()
    if not image_path.exists():
        print(f"ERROR: image not found at {image_path}", file=sys.stderr)
        print(
            "Hint: run `make cohort-smoke` first; it rasterizes "
            "data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf "
            "to the expected PNG path via `sips` (macOS).",
            file=sys.stderr,
        )
        return 2

    model_ids = _select_models(
        single=args.model,
        subset_csv=args.models,
        run_all=args.all,
    )
    ordered = _order_models(model_ids, policy=args.ordering)

    # Stream output to either stdout or `--out` file as we go, so users see
    # per-model progress in long cohort runs (rather than waiting for the
    # full 20-40 min cohort sweep to print at the end).
    out_stream: TextIO
    if args.out is not None:
        out_stream = Path(args.out).open("w", encoding="utf-8")
    else:
        out_stream = sys.stdout

    try:
        print("=" * 72, file=out_stream)
        print("HORUS cohort smoke — ADR-009 §Decision evidence", file=out_stream)
        print("=" * 72, file=out_stream)
        print(f"Image:          {image_path}", file=out_stream)
        print(f"Image size:     {image_path.stat().st_size:,} bytes", file=out_stream)
        print(f"Cohort size:    {len(ordered)} model(s)", file=out_stream)
        print(f"Ordering:       {args.ordering}", file=out_stream)
        if args.max_tokens is not None:
            print(f"max_tokens:     {args.max_tokens} (CLI override)", file=out_stream)
        print(file=out_stream)
        out_stream.flush()

        results: list[ExtractionResult] = []
        for idx, model_id in enumerate(ordered, start=1):
            print(
                f"[{idx}/{len(ordered)}] Running {model_id} ...",
                file=sys.stderr,
                flush=True,
            )
            result = _run_one(
                model_id=model_id,
                image_path=image_path,
                max_tokens_override=args.max_tokens,
            )
            results.append(result)
            category = COHORT_MANIFEST[model_id]["category"]
            print(_format_block(result, category=category), file=out_stream)
            print(file=out_stream)
            out_stream.flush()

        n_ok = sum(1 for r in results if r.is_ok)
        print("=" * 72, file=out_stream)
        print(
            f"SUMMARY: {n_ok}/{len(results)} cohort models ran to completion",
            file=out_stream,
        )
        if n_ok < len(results):
            failed = [r.model_id for r in results if not r.is_ok]
            print(f"Failed:  {failed}", file=out_stream)
        print("=" * 72, file=out_stream)
    finally:
        if args.out is not None:
            out_stream.close()

    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
