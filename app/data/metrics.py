"""Live recomputation of the headline comparison metrics from per-field scores.

The four metrics on the comparison page are pooled HERE from the per-invoice
`FieldResult` lists using the project's own scorer helpers — never read from
possibly-stale saved aggregates (the drift-proof, scientifically honest path).
Cohort pooling follows the scorer convention: sum the per-invoice counts, then
take one F1 (identical to `scripts/inspect_pilot_13.py`).

The four headline metrics:
  - overall field accuracy  — micro-F1 pooled over every field of every invoice
  - presence accuracy       — F1 over GT-present fields only (did it get the
                              fields that ARE on the invoice)
  - grouping accuracy       — KIEval all-or-nothing group F1 (seller/buyer/totals)
  - invention rate          — spurious-emission rate: how often a value is emitted
                              for a field that is genuinely absent (lower = better)
"""

from __future__ import annotations

from dataclasses import dataclass

from horus.eval.scorer import (
    FieldResult,
    f1_from_counts,
    group_level_counts,
    label_outcome_counts,
    presence_conditional_counts,
    spurious_emission_counts,
)

_OUTCOME_IDX: dict[str, int] = {"TP": 0, "FP": 1, "FN": 2}


@dataclass(frozen=True)
class ApproachMetrics:
    """Pooled metrics for one approach across a set of invoices."""

    n_invoices: int
    overall_f1: float
    overall_precision: float
    overall_recall: float
    presence_f1: float
    group_f1: float
    spurious_rate: float
    per_label_f1: dict[str, float]
    per_label_counts: dict[str, tuple[int, int, int]]
    per_type_f1: dict[str, float]


def pool_metrics(per_invoice: list[list[FieldResult]]) -> ApproachMetrics:
    """Pool the four headline metrics (+ per-label, per-type F1) across invoices."""
    micro = [0, 0, 0]
    presence = [0, 0, 0]
    group = [0, 0, 0]
    spur_fp = 0
    spur_absent = 0
    all_results: list[FieldResult] = []
    by_type: dict[str, list[int]] = {}

    for results in per_invoice:
        for r in results:
            all_results.append(r)
            idx = _OUTCOME_IDX.get(r.outcome)
            if idx is not None:
                micro[idx] += 1
                by_type.setdefault(r.field_type, [0, 0, 0])[idx] += 1
        ptp, pfp, pfn = presence_conditional_counts(results)
        presence[0] += ptp
        presence[1] += pfp
        presence[2] += pfn
        gtp, gfp, gfn = group_level_counts(results)
        group[0] += gtp
        group[1] += gfp
        group[2] += gfn
        fp, absent = spurious_emission_counts(results)
        spur_fp += fp
        spur_absent += absent

    overall_p, overall_r, overall_f1 = f1_from_counts(micro[0], micro[1], micro[2])
    label_counts = label_outcome_counts(all_results)

    return ApproachMetrics(
        n_invoices=len(per_invoice),
        overall_f1=overall_f1,
        overall_precision=overall_p,
        overall_recall=overall_r,
        presence_f1=f1_from_counts(presence[0], presence[1], presence[2])[2],
        group_f1=f1_from_counts(group[0], group[1], group[2])[2],
        spurious_rate=(spur_fp / spur_absent if spur_absent else 0.0),
        per_label_f1={
            key: f1_from_counts(counts[0], counts[1], counts[2])[2]
            for key, counts in label_counts.items()
        },
        per_label_counts=label_counts,
        per_type_f1={
            field_type: f1_from_counts(counts[0], counts[1], counts[2])[2]
            for field_type, counts in by_type.items()
        },
    )
