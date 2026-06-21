"""Load + type the per-(model, invoice) scores the dashboard renders.

Reconstructs the per-field `FieldResult` records from each run's saved
`per_field_scores.json` (the same artifact `scripts/inspect_pilot_13.py` reads), so
every value the app shows comes from the pipeline's own scored output rather than a
re-implementation. `load_invoice_runs` resolves an approach's latest parent run and
returns one `InvoiceRun` per invoice; it returns an empty mapping (never raises) when
the experiment / parent / artifacts are absent.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

from app.data import mlflow_store
from app.data.approaches import Approach
from horus.eval.scorer import FieldResult

# Field names of the `FieldResult` dataclass — used to project each JSON record
# back into a typed `FieldResult` (mirrors inspect_pilot_13's reconstruction).
_FR_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(FieldResult))


@dataclass(frozen=True)
class InvoiceRun:
    """One (model, invoice) nested run: its tags, headline F1, and per-field results.

    `micro_f1` is the flat 34-field F1; `overall_micro_f1` additionally folds the
    repeating-group cells (VAT breakdown / Skonto / line items) so it covers the
    whole schema (ADR-042). `group_f1` maps each scored repeating group to its F1.
    Both fall back to the flat number / empty when an older run lacks them.
    """

    invoice_id: str
    model_id: str
    profile: str
    pages: int | None
    status: str
    micro_f1: float
    run_id: str
    field_results: list[FieldResult] = field(default_factory=list)
    overall_micro_f1: float = 0.0
    group_f1: dict[str, float] = field(default_factory=dict)

    @property
    def is_finished(self) -> bool:
        """True if the underlying MLflow run finished cleanly."""
        return self.status == "FINISHED"


def parse_field_results(per_field_scores: dict[str, Any]) -> list[FieldResult]:
    """Reconstruct typed `FieldResult`s from a `per_field_scores.json` payload.

    Tolerant: records missing an expected key (older artifact shape) are skipped
    rather than aborting the whole invoice.
    """
    per_field = per_field_scores.get("per_field", {})
    if not isinstance(per_field, dict):
        return []
    results: list[FieldResult] = []
    for record in per_field.values():
        try:
            results.append(FieldResult(**{key: record[key] for key in _FR_FIELDS}))
        except KeyError, TypeError:
            continue
    return results


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_invoice_runs(approach: Approach) -> dict[str, InvoiceRun]:
    """Return ``{invoice_id: InvoiceRun}`` for the approach's latest parent run.

    Empty mapping when the experiment / parent / runs are absent (fresh clone, CI,
    or a not-yet-run approach) — callers degrade gracefully on an empty result.
    """
    experiment_id = mlflow_store.get_experiment_id(approach.experiment_name)
    if experiment_id is None:
        return {}
    parent_run_id = mlflow_store.latest_parent_run_id(experiment_id)
    if parent_run_id is None:
        return {}

    runs: dict[str, InvoiceRun] = {}
    for run in mlflow_store.nested_runs(experiment_id, parent_run_id):
        tags = run.data.tags
        invoice_id = tags.get("invoice_id")
        if not invoice_id:
            continue
        payload = mlflow_store.load_artifact_json(run.info.run_id, "per_field_scores.json")
        results = parse_field_results(payload) if payload else []
        metrics = run.data.metrics
        flat_micro_f1 = float(metrics.get("micro_f1", 0.0))
        group_f1 = {
            key[len("group_") : -len("_f1")]: float(value)
            for key, value in metrics.items()
            if key.startswith("group_") and key.endswith("_f1")
        }
        runs[invoice_id] = InvoiceRun(
            invoice_id=invoice_id,
            model_id=tags.get("model_id", approach.model_id),
            profile=tags.get("profile", ""),
            pages=_int_or_none(tags.get("pages")),
            status=run.info.status,
            micro_f1=flat_micro_f1,
            run_id=str(run.info.run_id),
            field_results=results,
            # ADR-042: whole-schema headline (falls back to flat for older runs).
            overall_micro_f1=float(metrics.get("overall_micro_f1", flat_micro_f1)),
            group_f1=group_f1,
        )
    return runs
