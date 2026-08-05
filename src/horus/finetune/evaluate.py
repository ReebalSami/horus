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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from horus.config import EvalConfig
from horus.eval import structurer
from horus.eval.scorer import f1_from_counts, is_signal_bearing, score
from horus.finetune.dataset import InvoiceRecord, reader_text_from_transcript
from horus.vlm_extractor import MLXVLMExtractor, get_extractor

__all__ = [
    "EvalReport",
    "InvoiceEval",
    "evaluate_structurer",
    "score_saved_outputs",
]


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
    """Aggregate eval over a record list — the headline numbers + per-invoice detail.

    Three per-field surfaces, deliberately distinct (they answer different questions):

    - ``per_field_f1`` — **the diagnostic to use.** Pooled F1 from the TP/FP/FN counts.
      Fields that were never actually tested (all TN and/or EXCLUDED) are omitted
      rather than reported as 1.0.
    - ``per_field_mean`` — mean comparator score (ANLS\\* for STRING, 0/1 for typed)
      over signal-bearing outcomes only. Useful for "how close" on STRING fields;
      NOT an F1.
    - ``per_field_outcomes`` — raw ``{TP, FP, FN, TN, EXCLUDED}`` counts, so any
      derived number above can be audited without a re-run.

    Both aggregates gate on ``scorer.is_signal_bearing``: admitting TN (score 1.0)
    or EXCLUDED (score 0.0) makes a field's number a function of how often it is
    absent instead of how well it was read.

    Two more surfaces cover the REPEATING GROUPS, which the flat ones cannot see:

    - ``per_group_f1`` / ``per_group_outcomes`` — pooled over each group's cells
      (``vat_breakdown`` / ``skonto`` / ``line_items``).
    - ``per_group_cell_f1`` / ``per_group_cell_outcomes`` — keyed
      ``<group>.<sub_field>``, the cell-level equivalent of ``per_field_f1``.

    These exist because omitting them made a real regression unattributable: the
    headline ``mean_overall_micro_f1`` (flat + groups) fell 0.0458 while
    ``mean_micro_f1`` (flat only) ROSE, and nothing in the report could say why. The
    cause was 103 lost cells concentrated in two cells that went from perfect to
    zero, which is exactly what a per-cell surface surfaces at a glance (ADR-059).
    Same defect class as the per-field reporting bug in
    ``eval/per-field-reporting-audit.md``: a number was computed, then discarded
    before it reached the report.
    """

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
    per_field_f1: dict[str, float]
    per_field_outcomes: dict[str, dict[str, int]]
    per_group_f1: dict[str, float]
    per_group_outcomes: dict[str, dict[str, int]]
    per_group_cell_f1: dict[str, float]
    per_group_cell_outcomes: dict[str, dict[str, int]]
    per_invoice: list[InvoiceEval]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["per_invoice"] = [asdict(e) for e in self.per_invoice]
        return data


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _per_field_f1(counts: dict[str, dict[str, int]]) -> dict[str, float]:
    """Pooled per-field F1 from TP/FP/FN counts (fields with no signal are omitted).

    The trustworthy per-field diagnostic: unlike a mean over ``FieldResult.score``
    it cannot be moved by TN/EXCLUDED occurrences. A field absent from the result
    was never actually tested (all TN and/or EXCLUDED) — omitting it is the honest
    report, since a 1.0 there would mean "never asked", not "always right".
    """
    out: dict[str, float] = {}
    for key, c in sorted(counts.items()):
        if c["TP"] + c["FP"] + c["FN"] == 0:
            continue
        _, _, f1 = f1_from_counts(c["TP"], c["FP"], c["FN"])
        out[key] = f1
    return out


@dataclass
class _Accumulator:
    """The single per-invoice scoring + aggregation site shared by every eval path.

    Deliberately ONE implementation: the TN/EXCLUDED contamination defect
    (`eval/per-field-reporting-audit.md`) happened precisely because three call
    sites each aggregated `FieldResult.score` on their own. The live runner
    (`evaluate_structurer`) and the offline re-scorer (`score_saved_outputs`)
    both feed this, so a future reporting change lands once.
    """

    cfg: EvalConfig
    structurer_model: str
    # When False, repeating groups are not scored at all and `overall_micro_f1`
    # collapses to the flat `micro_f1`. Set by a caller whose GROUND TRUTH for the
    # groups is unreviewed: scoring against an unverified answer key produces a
    # number that looks like a measurement and is not one (ADR-063).
    score_groups: bool = True
    per_invoice: list[InvoiceEval] = field(default_factory=list)
    _score_acc: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _counts: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "EXCLUDED": 0}
        )
    )
    # Repeating-group cell outcomes, pooled per group and per <group>.<sub_field>.
    _group_counts: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "EXCLUDED": 0}
        )
    )
    _group_cell_counts: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "EXCLUDED": 0}
        )
    )

    def add_failure(self, stem: str, secs: float, error: str | None) -> None:
        """Record a generation that never produced text (scores 0, spurious 1.0)."""
        self.per_invoice.append(InvoiceEval(stem, False, 0.0, 0.0, 0.0, 1.0, secs, error=error))

    def add_generation(self, rec: InvoiceRecord, raw_text: str, secs: float) -> Any:
        """Parse + score one raw structurer generation; accumulate and return the scores."""
        assert rec.gt is not None  # callers filter on `ready`
        predicted = structurer.to_predicted_dict(raw_text, self.structurer_model)
        # `score` treats groups as opt-in via this argument, so passing None is a true
        # exclusion — the group cells never enter `overall_*`, rather than being scored
        # against an empty GT and counted as spurious emissions.
        predicted_groups = structurer.to_predicted_groups(raw_text) if self.score_groups else None
        scores = score(
            predicted,
            rec.gt,
            cfg=self.cfg,
            invoice_id=rec.stem,
            model_id=self.structurer_model,
            predicted_groups=predicted_groups,
        )
        self.per_invoice.append(
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
            self._counts[field_key][field_result.outcome] += 1
            # Only TP/FP/FN carry signal. Letting TN (score 1.0) or EXCLUDED
            # (score 0.0) into the mean makes a field's number a function of how
            # often it is absent, not of how well it was read. See
            # `scorer.SIGNAL_OUTCOMES`.
            if is_signal_bearing(field_result.outcome):
                self._score_acc[field_key].append(field_result.score)
        # `scores.repeating` is populated only when `predicted_groups` is passed, so
        # this loop is empty on a groups-excluded run. Each cell's english_key is
        # "<group>[<pair>].<sub>", so the sub-field name is the trailing dot-segment.
        for group_key, group_result in scores.repeating.items():
            for cell in group_result.cell_results:
                self._group_counts[group_key][cell.outcome] += 1
                sub_key = cell.english_key.rsplit(".", 1)[-1]
                self._group_cell_counts[f"{group_key}.{sub_key}"][cell.outcome] += 1
        return scores

    def report(self, *, label: str, adapter_dir: Path | None, n_total: int) -> EvalReport:
        ok = [e for e in self.per_invoice if e.ok]
        return EvalReport(
            label=label,
            structurer_model=self.structurer_model,
            adapter_dir=str(adapter_dir) if adapter_dir is not None else None,
            n_total=n_total,
            n_ok=len(ok),
            n_failed=len(self.per_invoice) - len(ok),
            mean_micro_f1=_mean([e.micro_f1 for e in ok]),
            mean_overall_micro_f1=_mean([e.overall_micro_f1 for e in ok]),
            mean_presence_conditional_f1=_mean([e.presence_conditional_f1 for e in ok]),
            mean_spurious_emission_rate=_mean([e.spurious_emission_rate for e in ok]),
            per_field_mean={k: _mean(v) for k, v in sorted(self._score_acc.items())},
            per_field_f1=_per_field_f1(self._counts),
            per_field_outcomes={k: dict(v) for k, v in sorted(self._counts.items())},
            per_group_f1=_per_field_f1(self._group_counts),
            per_group_outcomes={k: dict(v) for k, v in sorted(self._group_counts.items())},
            per_group_cell_f1=_per_field_f1(self._group_cell_counts),
            per_group_cell_outcomes={
                k: dict(v) for k, v in sorted(self._group_cell_counts.items())
            },
            per_invoice=self.per_invoice,
        )


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
    score_groups: bool = True,
) -> EvalReport:
    """Score the structurer (optionally LoRA-adapted) over every ready record in ``records``.

    ``save_outputs_dir`` persists each invoice's RAW structurer generation to
    ``<dir>/<stem>.txt`` so offline re-scoring (field-subset attribution, adapter
    A/B) never has to re-run the VLM (attribution audit, issue #55 follow-up).

    ``reader_text_fn`` overrides where the structurer input text comes from
    (default: the record's cached reader transcript). The oracle-transcript
    probe passes ``lambda r: render_oracle_transcript(r.gt)`` to measure the
    structurer ceiling independent of reading quality.

    ``score_groups=False`` excludes the repeating groups; use it when the corpus's
    group rows are not part of the verified answer key (ADR-063).
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

    acc = _Accumulator(cfg=cfg, structurer_model=structurer_model, score_groups=score_groups)

    print(
        f"Eval [{label}]: structurer={structurer_model} "
        f"adapter={adapter_dir or '<none>'} invoices={len(ready)} max_tokens={max_tokens} "
        f"groups={'scored' if score_groups else 'EXCLUDED'}",
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
            acc.add_failure(rec.stem, secs, result.error)
            if progress:
                print(f"[{i}/{len(ready)}] {rec.stem}: FAILED ({result.error})", flush=True)
            continue

        if save_outputs_dir is not None:
            (save_outputs_dir / f"{rec.stem}.txt").write_text(result.text, encoding="utf-8")

        scores = acc.add_generation(rec, result.text, secs)
        if progress:
            print(
                f"[{i}/{len(ready)}] {rec.stem}: overall={scores.overall_micro_f1:.3f} "
                f"micro={scores.micro_f1:.3f} presence={scores.presence_conditional_f1:.3f} "
                f"spurious={scores.spurious_emission_rate:.3f} ({secs:.1f}s)",
                flush=True,
            )

    return acc.report(label=label, adapter_dir=adapter_dir, n_total=len(ready))


def score_saved_outputs(
    records: list[InvoiceRecord],
    outputs_dir: Path,
    *,
    structurer_model: str,
    eval_cfg: EvalConfig | None = None,
    label: str = "score-only",
    adapter_dir: Path | None = None,
    progress: bool = True,
    score_groups: bool = True,
) -> EvalReport:
    """Re-score generations saved by ``--save-outputs`` — no model load, no inference.

    Reads ``<outputs_dir>/<stem>.txt`` for every ready record and pushes it through
    the SAME `_Accumulator` the live runner uses, so a scorer / normalizer / parser
    change can be measured against a frozen set of generations in seconds instead of
    re-running the VLM. This is the path `evaluate_structurer`'s docstring promised
    but no CLI exposed; it is also how an adapter A/B is scored after a LoRA run.

    Records with no saved output are reported as failures (never silently dropped),
    so ``n_failed`` surfaces an incomplete generation set.
    """
    cfg = eval_cfg or EvalConfig()
    ready = [r for r in records if r.ready and r.gt is not None]
    if not ready:
        raise ValueError("score_saved_outputs received no ready records (need GT + transcript).")
    if not outputs_dir.is_dir():
        raise FileNotFoundError(f"Saved-outputs dir not found: {outputs_dir}")

    acc = _Accumulator(cfg=cfg, structurer_model=structurer_model, score_groups=score_groups)
    print(
        f"Re-score [{label}]: outputs={outputs_dir} structurer={structurer_model} "
        f"invoices={len(ready)} groups={'scored' if score_groups else 'EXCLUDED'} "
        "(no inference)",
        flush=True,
    )

    for i, rec in enumerate(ready, 1):
        path = outputs_dir / f"{rec.stem}.txt"
        if not path.is_file():
            acc.add_failure(rec.stem, 0.0, f"no saved output at {path}")
            if progress:
                print(f"[{i}/{len(ready)}] {rec.stem}: MISSING saved output", flush=True)
            continue
        scores = acc.add_generation(rec, path.read_text(encoding="utf-8"), 0.0)
        if progress:
            print(
                f"[{i}/{len(ready)}] {rec.stem}: overall={scores.overall_micro_f1:.3f} "
                f"micro={scores.micro_f1:.3f} presence={scores.presence_conditional_f1:.3f} "
                f"spurious={scores.spurious_emission_rate:.3f}",
                flush=True,
            )

    return acc.report(label=label, adapter_dir=adapter_dir, n_total=len(ready))
