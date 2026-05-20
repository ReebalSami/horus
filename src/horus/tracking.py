"""Experiment tracking adapter (HORUS — ADR-011 extended Protocol).

Defines the `Tracker` Protocol + two concrete implementations:

  - `StdoutTracker` — zero-dep printer for tests + bare scripts (DEFAULT_TRACKER)
  - `MLflowTracker` — MLflow-backed tracker (ratified by ADR-011)

Extended for ADR-011 with `start_run` / `end_run` / `log_dict` / `set_tag` to
support pilot #13's per-field heatmap (`log_dict`), hardware-fingerprint
tagging (`set_tag`), and the parent/nested run shape needed by
`scripts/cohort_smoke.py` (`start_run` / `end_run`).

Recommended usage = `get_tracker(cfg)` factory + context-manager form:

    from horus.config import ExperimentConfig
    from horus.tracking import get_tracker

    cfg = ExperimentConfig.from_yaml("configs/cohort-smoke.yaml")
    tracker = get_tracker(cfg)  # MLflowTracker(cfg.mlflow); StdoutTracker if cfg is None

    with tracker.start_run(run_name="cohort-sweep", tags={"stage": "smoke"}) as parent:
        for model_id in cohort:
            with tracker.start_run(run_name=model_id, nested=True) as child:
                tracker.log_param("model_id", model_id)
                tracker.log_metric("extract_seconds", t)
                tracker.set_tag("hardware_fingerprint", "Apple M1 Pro / 16 GB")

Procedural form (no `with`; pair `start_run` with explicit `end_run`):

    tracker.start_run(run_name="single-run")
    tracker.log_param("seed", 42)
    tracker.end_run()

The Protocol is intentionally small + non-leaky: every method maps 1:1 onto
the MLflow native API. Swapping to W&B / Aim / TensorBoard is a matter of
implementing the same 7 methods (see ADR-011 §"Decision + integration thoughts").
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from horus.config import ExperimentConfig, MLflowConfig


@dataclass(frozen=True)
class Run:
    """A handle to an active tracker run.

    `run_id` is the tracker's identity for this run (MLflow's UUID string, or
    `None` for `StdoutTracker` which has no run-identity concept). `run_name`
    is the human-readable label set at `start_run` time (may be `None` if the
    caller didn't provide one).
    """

    run_id: str | None
    run_name: str | None


class Tracker(Protocol):
    """Adapter Protocol for experiment trackers.

    Implement this Protocol to bind any tracker (MLflow / W&B / TensorBoard /
    Aim / DVC / Neptune / custom) without touching consumer code. See the
    module docstring for the canonical usage patterns.

    Extended for ADR-011 (was 3 methods; now 7). The two new run-lifecycle
    methods (`start_run` + `end_run`) support nested runs for cohort sweeps;
    `log_dict` + `set_tag` round out the structured-data + tagging surface
    that pilot #13's eval harness needs.
    """

    def start_run(
        self,
        run_name: str | None = None,
        nested: bool = False,
        tags: dict[str, str] | None = None,
    ) -> AbstractContextManager[Run]:
        """Open a new run + return a context manager yielding the `Run` handle.

        The run is opened as a side effect of this call. Callers may either:

        - Use `with` (recommended; auto-ends on exit, exception-safe):
              `with tracker.start_run(...) as run: ...`
        - Pair with an explicit `end_run()` call (procedural form):
              `tracker.start_run(...); ...; tracker.end_run()`

        `nested=True` opens this run as a child of an already-active run
        (matches `mlflow.start_run(nested=True)` semantics). `tags` are
        applied at run-creation time (atomic; no race window).
        """
        ...

    def end_run(self, status: str = "FINISHED") -> None:
        """End the currently-active run.

        `status` is one of `"FINISHED"`, `"FAILED"`, `"KILLED"` (MLflow's
        run-status vocabulary). The context-manager form of `start_run` calls
        this automatically on `__exit__` (with `"FAILED"` if an exception
        propagates).
        """
        ...

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        """Log a single metric value at an optional step."""
        ...

    def log_param(self, key: str, value: object) -> None:
        """Log a single hyperparameter."""
        ...

    def log_dict(self, key: str, data: dict[str, Any]) -> None:
        """Log a structured dict as a JSON artifact on the active run.

        Used for per-field heatmaps, classification reports, confusion
        matrices, and any non-scalar structured run output that doesn't fit
        the metric / param shape. `key` is the artifact filename; `.json` is
        appended if missing.
        """
        ...

    def set_tag(self, key: str, value: str) -> None:
        """Set / overwrite a tag on the active run.

        Tags are categorical run metadata that appear as filterable columns
        in the MLflow UI (e.g., `hardware_fingerprint`, `commit_sha`,
        `cohort_label`). Distinct from params, which are immutable and used
        for run-comparison axes.
        """
        ...

    def log_artifact(self, path: str) -> None:
        """Log a file or directory artifact on the active run."""
        ...


class StdoutTracker:
    """Default tracker — prints to stdout. Zero-dep, zero-config.

    Implements the full extended Tracker Protocol per ADR-011. Nested runs
    are indicated by indenting BEGIN/END RUN brackets. Used by tests + bare
    scripts that don't have an MLflow config. Maintains per-instance run
    depth so nested-run indentation is correct under sequential / cohort use.
    """

    def __init__(self) -> None:
        self._depth = 0  # current nesting level (drives indent)

    @contextmanager
    def start_run(
        self,
        run_name: str | None = None,
        nested: bool = False,
        tags: dict[str, str] | None = None,
    ) -> Iterator[Run]:
        indent = "  " * self._depth
        label = run_name or "<unnamed>"
        nested_marker = " (nested)" if nested else ""
        print(f"{indent}BEGIN RUN {label}{nested_marker}")
        if tags:
            for k, v in sorted(tags.items()):
                print(f"{indent}  tag {k}={v}")
        self._depth += 1
        try:
            yield Run(run_id=None, run_name=run_name)
            self._end_run_internal("FINISHED")
        except BaseException:
            self._end_run_internal("FAILED")
            raise

    def end_run(self, status: str = "FINISHED") -> None:
        self._end_run_internal(status)

    def _end_run_internal(self, status: str) -> None:
        if self._depth > 0:
            self._depth -= 1
        indent = "  " * self._depth
        print(f"{indent}END RUN [{status}]")

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        indent = "  " * self._depth
        prefix = f"[step {step}] " if step is not None else ""
        print(f"{indent}{prefix}metric {key}={value}")

    def log_param(self, key: str, value: object) -> None:
        indent = "  " * self._depth
        print(f"{indent}param {key}={value!r}")

    def log_dict(self, key: str, data: dict[str, Any]) -> None:
        indent = "  " * self._depth
        print(f"{indent}dict {key}={json.dumps(data, sort_keys=True)}")

    def set_tag(self, key: str, value: str) -> None:
        indent = "  " * self._depth
        print(f"{indent}tag {key}={value}")

    def log_artifact(self, path: str) -> None:
        indent = "  " * self._depth
        print(f"{indent}artifact {path}")


class MLflowTracker:
    """MLflow-backed tracker (ratified by ADR-011).

    Delegates every Protocol method 1:1 to MLflow's native `mlflow.*` API.
    Construction sets the tracking URI (when provided in cfg) + experiment
    name; run lifecycle is per `start_run` / `end_run` pair (or `with` form).

    Per ADR-011 §Decision: MLflow 3.7+ defaults to `sqlite:///mlflow.db` for
    metadata + `mlruns/<exp>/<run>/artifacts/` for filesystem artifacts when
    `tracking_uri=None` (the Python-client write path; see ADR-015 for the
    server-side `./mlartifacts/` proxy distinction). Both `mlruns/` and
    `mlflow.db` are gitignored in HORUS (`.gitignore`).

    `cfg.run_tags` are applied as default tags on every run started via this
    tracker; per-call `tags` passed to `start_run` override on key collision.
    """

    def __init__(self, cfg: MLflowConfig) -> None:
        import mlflow  # noqa: PLC0415 — top-level import would couple StdoutTracker users to mlflow availability

        self._cfg = cfg
        if cfg.tracking_uri is not None:
            mlflow.set_tracking_uri(cfg.tracking_uri)
        mlflow.set_experiment(cfg.experiment_name)

    @contextmanager
    def start_run(
        self,
        run_name: str | None = None,
        nested: bool = False,
        tags: dict[str, str] | None = None,
    ) -> Iterator[Run]:
        import mlflow  # noqa: PLC0415

        # Merge cfg-level default tags with per-call tags; per-call wins.
        merged_tags = dict(self._cfg.run_tags)
        if tags:
            merged_tags.update(tags)

        active = mlflow.start_run(
            run_name=run_name,
            nested=nested,
            tags=merged_tags or None,
        )
        run_id: str = active.info.run_id
        try:
            yield Run(run_id=run_id, run_name=run_name)
            mlflow.end_run(status="FINISHED")
        except BaseException:
            mlflow.end_run(status="FAILED")
            raise

    def end_run(self, status: str = "FINISHED") -> None:
        import mlflow  # noqa: PLC0415

        mlflow.end_run(status=status)

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        import mlflow  # noqa: PLC0415

        mlflow.log_metric(key, value, step=step)

    def log_param(self, key: str, value: object) -> None:
        import mlflow  # noqa: PLC0415

        mlflow.log_param(key, value)

    def log_dict(self, key: str, data: dict[str, Any]) -> None:
        import mlflow  # noqa: PLC0415

        # MLflow infers format from extension; auto-append .json if missing.
        artifact_file = key if key.endswith((".json", ".yaml", ".yml")) else f"{key}.json"
        mlflow.log_dict(data, artifact_file=artifact_file)

    def set_tag(self, key: str, value: str) -> None:
        import mlflow  # noqa: PLC0415

        mlflow.set_tag(key, value)

    def log_artifact(self, path: str) -> None:
        import mlflow  # noqa: PLC0415

        mlflow.log_artifact(path)


def get_tracker(cfg: ExperimentConfig | None = None) -> Tracker:
    """Factory: dispatch to the right tracker based on config.

    - `cfg is None` → `StdoutTracker()` (zero-dep; tests + bare scripts).
    - `cfg` provided → `MLflowTracker(cfg.mlflow)` (the production path,
      per ADR-011).

    Used by `scripts/cohort_smoke.py` (when `--cfg PATH` is provided) and
    pilot #13's eval harness. Removes the duplicate `if/else` dispatch that
    would otherwise repeat at every consumer call site.
    """
    if cfg is None:
        return StdoutTracker()
    return MLflowTracker(cfg.mlflow)


# Module-level default — preserved for tests + the `@run-experiment` skill's
# zero-dep import path. New consumers should prefer `get_tracker(cfg)`.
DEFAULT_TRACKER: Tracker = StdoutTracker()
