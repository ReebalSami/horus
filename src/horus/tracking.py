"""Experiment tracking adapter (python-ml-uv brainstorm B4=C tracker-agnostic).

Defers the experiment-tracker choice to per-project decision at consumption
time. Ships a `Tracker` Protocol + `StdoutTracker` default; consumer swaps
for MLflow / W&B / TensorBoard / Aim / DVC / Neptune by implementing the
Protocol.

Example (default):
    from horus.tracking import DEFAULT_TRACKER as tracker

    tracker.log_metric("loss", 0.42, step=100)
    tracker.log_param("learning_rate", 1e-3)

Example (MLflow swap):
    import mlflow

    class MLflowTracker:
        def log_metric(self, key, value, step=None):
            mlflow.log_metric(key, value, step=step)
        def log_param(self, key, value):
            mlflow.log_param(key, value)
        def log_artifact(self, path):
            mlflow.log_artifact(path)

    tracker: Tracker = MLflowTracker()
"""

from __future__ import annotations

from typing import Protocol


class Tracker(Protocol):
    """Adapter Protocol for experiment trackers.

    Implement this Protocol to bind any tracker (MLflow / W&B / TensorBoard /
    Aim / DVC / Neptune / custom) without touching the rest of the codebase.
    """

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        """Log a single metric value at an optional step."""
        ...

    def log_param(self, key: str, value: object) -> None:
        """Log a single hyperparameter."""
        ...

    def log_artifact(self, path: str) -> None:
        """Log a file or directory artifact."""
        ...


class StdoutTracker:
    """Default tracker — prints to stdout. Zero-dep, zero-config."""

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        prefix = f"[step {step}] " if step is not None else ""
        print(f"{prefix}metric {key}={value}")

    def log_param(self, key: str, value: object) -> None:
        print(f"param {key}={value!r}")

    def log_artifact(self, path: str) -> None:
        print(f"artifact {path}")


# TODO: Replace with your project's chosen tracker (MLflow / W&B / TB / etc.).
# See module docstring for the swap pattern.
DEFAULT_TRACKER: Tracker = StdoutTracker()
