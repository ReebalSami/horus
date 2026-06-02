"""Thin read-only wrapper over the local MLflow run store.

Points MLflow at the repo-root SQLite store (`mlflow.db` + `mlruns/` artifacts —
the same store `make mlflow-ui` browses) using an ABSOLUTE URI so resolution does
not depend on the current working directory. Mirrors the run-resolution pattern in
`scripts/inspect_pilot_13.py`: experiment-by-name → latest parent run → its nested
per-(model, invoice) runs → the `per_field_scores.json` artifact each one carries.

`mlflow` is imported lazily inside each function (it is a heavy import) so the
module can be imported cheaply by tests that only exercise the pure helpers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MLFLOW_DB = REPO_ROOT / "mlflow.db"
TRACKING_URI = f"sqlite:///{MLFLOW_DB}"


def store_exists() -> bool:
    """True if the local MLflow SQLite store is present at the repo root."""
    return MLFLOW_DB.is_file()


@lru_cache(maxsize=1)
def _configure() -> None:
    """Point MLflow at the local SQLite store once per process."""
    import mlflow

    mlflow.set_tracking_uri(TRACKING_URI)


def get_experiment_id(name: str) -> str | None:
    """Return the experiment id for `name`, or None if it does not exist."""
    import mlflow

    _configure()
    experiment = mlflow.get_experiment_by_name(name)
    return None if experiment is None else str(experiment.experiment_id)


def _search_runs(**kwargs: Any) -> list[Any]:
    """`mlflow.search_runs(output_format="list", ...)` returned as a plain list.

    Wrapping in `list(...)` and annotating `list[Any]` keeps callers clear of
    MLflow's `list | DataFrame` return-type union (we always pass the list form).
    """
    import mlflow

    _configure()
    return list(mlflow.search_runs(output_format="list", **kwargs))


def latest_parent_run_id(experiment_id: str) -> str | None:
    """Most-recent (start_time DESC) top-level run under the experiment."""
    runs = _search_runs(
        experiment_ids=[experiment_id],
        filter_string="tags.mlflow.parentRunId IS NULL",
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if not runs:
        return None
    return str(runs[0].info.run_id)


def nested_runs(experiment_id: str, parent_run_id: str) -> list[Any]:
    """All nested runs under the given parent, in start-time order."""
    return _search_runs(
        experiment_ids=[experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{parent_run_id}'",
        order_by=["attributes.start_time ASC"],
        max_results=1000,
    )


def load_artifact_json(run_id: str, artifact_path: str) -> dict[str, Any] | None:
    """Download + parse a JSON artifact from a run; None if missing/unreadable."""
    import mlflow

    _configure()
    client = mlflow.MlflowClient()
    try:
        local_path = client.download_artifacts(run_id, artifact_path)
        with open(local_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001 — any MLflow / IO / JSON failure → treat as absent
        return None
    return data if isinstance(data, dict) else None
