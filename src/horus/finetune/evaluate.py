"""Shared structurer eval runner (issue #55): zero-shot AND LoRA through ONE code path.

Runs the Arm-B structuring pass — text-only Gemma over a cached reader transcript — over an
explicit list of `InvoiceRecord`s and scores each with the canonical scorer. Identical in
mechanics to `arm_b.run_arm_b`, but (a) over an arbitrary record list (the sealed val/train
split, not the 26 wired pairs) and (b) with an optional LoRA adapter applied to the structurer.

Using the SAME runner for the zero-shot baseline and the fine-tuned model is what makes the
comparison matched-precision: identical structuring prompt, identical reader text, identical
scorer, identical decode budget — the adapter is the only thing that changes.

Refs: ADR-038 (Arm-B), ADR-027/041/042 (metric surface + repeating groups), ADR-034 (no-HARKing).
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from horus.config import EvalConfig
from horus.eval import structurer
from horus.eval.scorer import score
from horus.finetune.dataset import InvoiceRecord, reader_text_from_transcript
from horus.vlm_extractor import MLXVLMExtractor, get_extractor

__all__ = ["EvalReport", "InvoiceEval", "evaluate_structurer"]


@dataclass(frozen=True)
class InvoiceEval:
    """Per-invoice eval outcome (a failed generation scores 0 with spurious=1.0)."""

    stem: str
    ok: bool
    micro_f1: float
    overall_micro_f1: float
    presence_conditional_f1: float
    spurious_emission_rate: float
    structure_seconds: float
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregate eval over a record list — the headline numbers + per-invoice detail."""

    label: str
    structurer_model: str
    adapter_dir: str | None
    n_total: int
    n_ok: int
    n_failed: int
    mean_micro_f1: float
    mean_overall_micro_f1: float
    mean_presence_conditional_f1: float
    mean_spurious_emission_rate: float
    per_field_mean: dict[str, float]
    per_invoice: list[InvoiceEval]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["per_invoice"] = [asdict(e) for e in self.per_invoice]
        return data


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _apply_adapter(extractor: MLXVLMExtractor, adapter_dir: Path) -> None:
    """Fuse a trained LoRA adapter onto the loaded structurer (in place)."""
    from mlx_vlm.trainer.utils import apply_lora_layers

    extractor._model = apply_lora_layers(extractor._model, str(adapter_dir))


def evaluate_structurer(
    records: list[InvoiceRecord],
    *,
    structurer_model: str,
    structuring_prompt: str,
    adapter_dir: Path | None = None,
    max_tokens: int = 2048,
    eval_cfg: EvalConfig | None = None,
    label: str = "zero-shot",
    progress: bool = True,
    save_outputs_dir: Path | None = None,
    reader_text_fn: Callable[[InvoiceRecord], str] | None = None,
) -> EvalReport:
    """Score the structurer (optionally LoRA-adapted) over every ready record in ``records``.

    ``save_outputs_dir`` persists each invoice's RAW structurer generation to
    ``<dir>/<stem>.txt`` so offline re-scoring (field-subset attribution, adapter
    A/B) never has to re-run the VLM (attribution audit, issue #55 follow-up).

    ``reader_text_fn`` overrides where the structurer input text comes from
    (default: the record's cached reader transcript). The oracle-transcript
    probe passes ``lambda r: render_oracle_transcript(r.gt)`` to measure the
    structurer ceiling independent of reading quality.
    """
    cfg = eval_cfg or EvalConfig()
    ready = [r for r in records if r.ready and r.gt is not None]
    if not ready:
        raise ValueError("evaluate_structurer received no ready records (need GT + transcript).")

    extractor = get_extractor(structurer_model)
    if not isinstance(extractor, MLXVLMExtractor):
        raise ValueError(
            f"structurer {structurer_model!r} must be an MLX model (text-only extract_text); "
            f"got {type(extractor).__name__}."
        )
    extractor.load()
    if adapter_dir is not None:
        _apply_adapter(extractor, adapter_dir)

    per_invoice: list[InvoiceEval] = []
    per_field_acc: dict[str, list[float]] = defaultdict(list)

    print(
        f"Eval [{label}]: structurer={structurer_model} "
        f"adapter={adapter_dir or '<none>'} invoices={len(ready)} max_tokens={max_tokens}",
        flush=True,
    )

    if save_outputs_dir is not None:
        save_outputs_dir.mkdir(parents=True, exist_ok=True)

    for i, rec in enumerate(ready, 1):
        assert rec.transcript_path is not None and rec.gt is not None  # (ready ⇒ both set)
        if reader_text_fn is not None:
            reader_text = reader_text_fn(rec)
        else:
            reader_text = reader_text_from_transcript(rec.transcript_path)
        full_prompt = structurer.build_structuring_input(structuring_prompt, reader_text)

        t0 = time.perf_counter()
        result = extractor.extract_text(full_prompt, max_tokens=max_tokens)
        secs = time.perf_counter() - t0

        if not result.is_ok:
            per_invoice.append(
                InvoiceEval(rec.stem, False, 0.0, 0.0, 0.0, 1.0, secs, error=result.error)
            )
            if progress:
                print(f"[{i}/{len(ready)}] {rec.stem}: FAILED ({result.error})", flush=True)
            continue

        if save_outputs_dir is not None:
            (save_outputs_dir / f"{rec.stem}.txt").write_text(result.text, encoding="utf-8")

        predicted = structurer.to_predicted_dict(result.text, structurer_model)
        predicted_groups = structurer.to_predicted_groups(result.text)
        scores = score(
            predicted,
            rec.gt,
            cfg=cfg,
            invoice_id=rec.stem,
            model_id=structurer_model,
            predicted_groups=predicted_groups,
        )
        per_invoice.append(
            InvoiceEval(
                stem=rec.stem,
                ok=True,
                micro_f1=scores.micro_f1,
                overall_micro_f1=scores.overall_micro_f1,
                presence_conditional_f1=scores.presence_conditional_f1,
                spurious_emission_rate=scores.spurious_emission_rate,
                structure_seconds=secs,
            )
        )
        for field_key, field_result in scores.per_field.items():
            per_field_acc[field_key].append(field_result.score)
        if progress:
            print(
                f"[{i}/{len(ready)}] {rec.stem}: overall={scores.overall_micro_f1:.3f} "
                f"micro={scores.micro_f1:.3f} presence={scores.presence_conditional_f1:.3f} "
                f"spurious={scores.spurious_emission_rate:.3f} ({secs:.1f}s)",
                flush=True,
            )

    ok = [e for e in per_invoice if e.ok]
    return EvalReport(
        label=label,
        structurer_model=structurer_model,
        adapter_dir=str(adapter_dir) if adapter_dir is not None else None,
        n_total=len(ready),
        n_ok=len(ok),
        n_failed=len(per_invoice) - len(ok),
        mean_micro_f1=_mean([e.micro_f1 for e in ok]),
        mean_overall_micro_f1=_mean([e.overall_micro_f1 for e in ok]),
        mean_presence_conditional_f1=_mean([e.presence_conditional_f1 for e in ok]),
        mean_spurious_emission_rate=_mean([e.spurious_emission_rate for e in ok]),
        per_field_mean={k: _mean(v) for k, v in sorted(per_field_acc.items())},
        per_invoice=per_invoice,
    )
