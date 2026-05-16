"""Tests for horus.tracking — `Tracker` Protocol + `StdoutTracker` + `MLflowTracker`
+ `get_tracker` factory + `Run` dataclass (ADR-011).

Coverage:

1. `Run` dataclass — fields + frozen.
2. `StdoutTracker` — original 3-method Protocol shape (backward compat).
3. `StdoutTracker` — extended methods (`start_run`/`end_run`/`log_dict`/`set_tag`).
4. `StdoutTracker` — context-manager + procedural lifecycle forms.
5. `StdoutTracker` — nested-run indentation.
6. `StdoutTracker` — exception inside `with` block → status=FAILED + raise.
7. `MLflowTracker` — construction sets tracking_uri + experiment.
8. `MLflowTracker` — start_run merges cfg.run_tags with per-call tags.
9. `MLflowTracker` — full round-trip (params/metrics/tags/dict/artifact) verified
   via `mlflow.search_runs` against an ephemeral `tmp_path`-scoped tracking URI.
10. `MLflowTracker` — nested run creates correct parent/child `mlflow.parentRunId`.
11. `MLflowTracker` — exception inside `with` block → run status=FAILED + raise.
12. `get_tracker(None)` → `StdoutTracker`.
13. `get_tracker(cfg)` → `MLflowTracker` with cfg consumed.

All MLflow tests run against an isolated `tmp_path/mlruns.db` tracking URI so
they don't pollute any host MLflow state.

Run via: `uv run pytest tests/test_tracking.py`

Refs: ADR-011, horus-config-discipline.md, src/horus/tracking.py module docstring.
"""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Run dataclass
# ---------------------------------------------------------------------------


def test_run_dataclass_fields() -> None:
    """`Run` is a frozen dataclass with run_id + run_name (both `str | None`)."""
    from horus.tracking import Run

    r = Run(run_id="abc-123", run_name="my-run")
    assert r.run_id == "abc-123"
    assert r.run_name == "my-run"


def test_run_dataclass_frozen() -> None:
    """`Run` is frozen — mutation raises `dataclasses.FrozenInstanceError`."""
    from dataclasses import FrozenInstanceError

    from horus.tracking import Run

    r = Run(run_id="abc-123", run_name="my-run")
    with pytest.raises(FrozenInstanceError):
        r.run_id = "different"  # type: ignore[misc]


def test_run_dataclass_optional_fields() -> None:
    """Both `run_id` and `run_name` are `str | None` (StdoutTracker uses None)."""
    from horus.tracking import Run

    r = Run(run_id=None, run_name=None)
    assert r.run_id is None
    assert r.run_name is None


# ---------------------------------------------------------------------------
# StdoutTracker — original Protocol shape (backward compat)
# ---------------------------------------------------------------------------


def test_stdout_tracker_log_metric(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_metric` prints `metric <key>=<value>` (+ `[step N] ` prefix when given)."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    t.log_metric("loss", 0.42)
    captured = capsys.readouterr().out
    assert "metric loss=0.42" in captured

    t.log_metric("acc", 0.85, step=100)
    captured = capsys.readouterr().out
    assert "[step 100] metric acc=0.85" in captured


def test_stdout_tracker_log_param(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_param` prints `param <key>=<repr(value)>`."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    t.log_param("learning_rate", 1e-3)
    captured = capsys.readouterr().out
    assert "param learning_rate=0.001" in captured


def test_stdout_tracker_log_artifact(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_artifact` prints `artifact <path>`."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    t.log_artifact("/tmp/dummy.txt")
    captured = capsys.readouterr().out
    assert "artifact /tmp/dummy.txt" in captured


# ---------------------------------------------------------------------------
# StdoutTracker — extended Protocol shape (ADR-011 additions)
# ---------------------------------------------------------------------------


def test_stdout_tracker_log_dict(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_dict` prints a JSON-formatted dict (sort_keys for determinism)."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    t.log_dict("heatmap", {"b_field": 0.9, "a_field": 0.7})
    captured = capsys.readouterr().out
    # sort_keys=True → "a_field" before "b_field"
    assert 'dict heatmap={"a_field": 0.7, "b_field": 0.9}' in captured


def test_stdout_tracker_set_tag(capsys: pytest.CaptureFixture[str]) -> None:
    """`set_tag` prints `tag <key>=<value>` (str, not repr)."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    t.set_tag("hardware", "Apple M1 Pro")
    captured = capsys.readouterr().out
    assert "tag hardware=Apple M1 Pro" in captured


def test_stdout_tracker_context_manager_form(capsys: pytest.CaptureFixture[str]) -> None:
    """`with tracker.start_run(...)` enters/exits cleanly + yields a `Run` handle."""
    from horus.tracking import Run, StdoutTracker

    t = StdoutTracker()
    with t.start_run(run_name="my-run", tags={"stage": "test"}) as run:
        assert isinstance(run, Run)
        assert run.run_id is None  # StdoutTracker has no run-identity
        assert run.run_name == "my-run"

    captured = capsys.readouterr().out
    assert "BEGIN RUN my-run" in captured
    assert "tag stage=test" in captured
    assert "END RUN [FINISHED]" in captured


def test_stdout_tracker_procedural_form(capsys: pytest.CaptureFixture[str]) -> None:
    """`start_run(...)` as context manager + procedural `end_run()` both work."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    # Use the contextmanager handle procedurally (`__enter__` then explicit
    # `end_run`). This is the "long-lived script" path documented in the
    # module docstring.
    cm = t.start_run(run_name="procedural-run")
    cm.__enter__()
    t.log_param("seed", 42)
    t.end_run(status="FINISHED")

    captured = capsys.readouterr().out
    assert "BEGIN RUN procedural-run" in captured
    assert "param seed=42" in captured
    assert "END RUN [FINISHED]" in captured


def test_stdout_tracker_nested_run_indents(capsys: pytest.CaptureFixture[str]) -> None:
    """Nested runs indent BEGIN/END brackets + per-call output by 2 spaces / level."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    with t.start_run(run_name="parent"):
        t.log_param("k1", "v1")
        with t.start_run(run_name="child", nested=True):
            t.log_param("k2", "v2")

    captured = capsys.readouterr().out
    lines = captured.split("\n")
    # Find the param lines and verify indentation increases at child level.
    k1_line = next(line for line in lines if "param k1=" in line)
    k2_line = next(line for line in lines if "param k2=" in line)
    # k1 should have 2-space indent (inside parent); k2 should have 4-space indent.
    assert k1_line.startswith("  param k1=")
    assert k2_line.startswith("    param k2=")
    # Nested label visible.
    assert "BEGIN RUN child (nested)" in captured


def test_stdout_tracker_exception_marks_failed(capsys: pytest.CaptureFixture[str]) -> None:
    """Exception inside `with` block exits the run with status=FAILED + re-raises."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    with pytest.raises(ValueError, match="boom"):
        with t.start_run(run_name="failing-run"):
            raise ValueError("boom")

    captured = capsys.readouterr().out
    assert "END RUN [FAILED]" in captured


def test_stdout_tracker_end_run_status_propagates(capsys: pytest.CaptureFixture[str]) -> None:
    """Explicit `end_run(status='KILLED')` prints the custom status."""
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    cm = t.start_run(run_name="killed-run")
    cm.__enter__()
    t.end_run(status="KILLED")

    captured = capsys.readouterr().out
    assert "END RUN [KILLED]" in captured


# ---------------------------------------------------------------------------
# Tracker Protocol — structural subtyping check
# ---------------------------------------------------------------------------


def test_stdout_tracker_satisfies_protocol() -> None:
    """`StdoutTracker` satisfies the `Tracker` Protocol shape structurally.

    Confirms every method declared in the Protocol is present + callable on
    `StdoutTracker`. Protocol is not `@runtime_checkable` by design (see
    src/horus/tracking.py module docstring), so we assert by feature-check
    rather than `isinstance`.
    """
    from horus.tracking import StdoutTracker

    t = StdoutTracker()
    assert callable(t.start_run)
    assert callable(t.end_run)
    assert callable(t.log_metric)
    assert callable(t.log_param)
    assert callable(t.log_dict)
    assert callable(t.set_tag)
    assert callable(t.log_artifact)

    # `start_run` is the @contextmanager-decorated form; calling it must
    # return an AbstractContextManager-shaped object.
    cm = t.start_run(run_name="probe")
    assert isinstance(cm, AbstractContextManager)
    cm.__enter__()
    cm.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# get_tracker factory
# ---------------------------------------------------------------------------


def test_get_tracker_returns_stdout_when_cfg_none() -> None:
    """`get_tracker(None)` → `StdoutTracker` (the zero-dep default path)."""
    from horus.tracking import StdoutTracker, get_tracker

    t = get_tracker(None)
    assert isinstance(t, StdoutTracker)


def test_get_tracker_returns_mlflow_when_cfg_given(tmp_path: Path) -> None:
    """`get_tracker(cfg)` → `MLflowTracker` when cfg is provided."""
    from horus.config import ExperimentConfig
    from horus.tracking import MLflowTracker, get_tracker

    cfg_path = tmp_path / "factory_smoke.yaml"
    tracking_uri = f"sqlite:///{tmp_path}/mlruns.db"
    cfg_path.write_text(
        f"seed: 1\nmlflow:\n  experiment_name: factory-smoke\n  tracking_uri: {tracking_uri}\n",
        encoding="utf-8",
    )
    cfg = ExperimentConfig.from_yaml(cfg_path)
    t = get_tracker(cfg)
    assert isinstance(t, MLflowTracker)


def test_default_tracker_constant_is_stdout() -> None:
    """`DEFAULT_TRACKER` module-level constant is a `StdoutTracker` instance.

    Backward-compatibility contract: `from horus.tracking import DEFAULT_TRACKER`
    must continue to work (used by tests + the `@run-experiment` skill's
    zero-dep import path).
    """
    from horus.tracking import DEFAULT_TRACKER, StdoutTracker

    assert isinstance(DEFAULT_TRACKER, StdoutTracker)


# ---------------------------------------------------------------------------
# MLflowTracker — integration tests against an ephemeral tmp_path SQLite URI
# ---------------------------------------------------------------------------


def _mk_cfg(
    tmp_path: Path,
    experiment_name: str = "test-experiment",
    run_tags: dict[str, str] | None = None,
) -> Any:
    """Build an ExperimentConfig pointing at an ephemeral tmp_path SQLite URI.

    Each test gets its own isolated `mlruns.db` + `mlruns/<exp>/<run>/artifacts/`
    tree so they don't interact + host MLflow state stays clean.
    """
    from horus.config import ExperimentConfig

    cfg_path = tmp_path / f"{experiment_name}.yaml"
    tracking_uri = f"sqlite:///{tmp_path}/mlruns.db"
    body = f"seed: 7\nmlflow:\n  experiment_name: {experiment_name}\n"
    if run_tags:
        body += "  run_tags:\n"
        for k, v in run_tags.items():
            # Quote values so YAML doesn't auto-coerce "16" → int 16
            # (would fail Pydantic's `run_tags: dict[str, str]` validation).
            body += f'    {k}: "{v}"\n'
    body += f"  tracking_uri: {tracking_uri}\n"
    cfg_path.write_text(body, encoding="utf-8")
    return ExperimentConfig.from_yaml(cfg_path)


def test_mlflow_tracker_construction_sets_uri_and_experiment(tmp_path: Path) -> None:
    """`MLflowTracker(cfg)` sets `mlflow.get_tracking_uri()` + creates the experiment."""
    import mlflow

    from horus.tracking import MLflowTracker

    cfg = _mk_cfg(tmp_path, experiment_name="ctor-test")
    _ = MLflowTracker(cfg.mlflow)

    assert mlflow.get_tracking_uri() == cfg.mlflow.tracking_uri
    exp = mlflow.get_experiment_by_name("ctor-test")
    assert exp is not None
    assert exp.name == "ctor-test"


def test_mlflow_tracker_full_round_trip(tmp_path: Path) -> None:
    """End-to-end: params/metrics/tags/dict/artifact land in MLflow + are readable back.

    Mirrors the cohort_smoke wire-up shape (without the model load): a parent
    run with tags + params + metrics + dict, a nested child run with its own
    params + metrics + an artifact.
    """
    import mlflow

    from horus.tracking import MLflowTracker

    cfg = _mk_cfg(
        tmp_path,
        experiment_name="round-trip",
        run_tags={"stage": "test", "issue": "16"},
    )
    tracker = MLflowTracker(cfg.mlflow)

    # Write an artifact-source file before the run starts (so we can clean up
    # without racing the MLflow log_artifact copy).
    artifact_src = tmp_path / "output.txt"
    artifact_src.write_text("hello mlflow", encoding="utf-8")

    with tracker.start_run(run_name="round-trip-parent", tags={"role": "parent"}) as parent:
        tracker.log_param("seed", cfg.seed)
        tracker.log_param("model_id", "test-model")
        tracker.log_metric("loss", 0.5)
        tracker.log_metric("loss", 0.4, step=1)
        tracker.set_tag("hardware", "M1 Pro")
        tracker.log_dict("heatmap", {"field_a": 0.85, "field_b": 0.92})

        with tracker.start_run(run_name="round-trip-child", nested=True) as child:
            tracker.log_param("child_param", "x")
            tracker.log_metric("child_metric", 1.5)
            tracker.log_artifact(str(artifact_src))
            child_run_id = child.run_id

        parent_run_id = parent.run_id

    # Both run_ids should be non-None (MLflowTracker returns the actual UUID).
    assert parent_run_id is not None
    assert child_run_id is not None
    assert parent_run_id != child_run_id

    # Read back via mlflow.search_runs. Use `*_record` suffix to avoid
    # mypy complaints about `parent` / `child` already bound to
    # `horus.tracking.Run` by the `with start_run(...) as parent:` line above.
    runs = mlflow.search_runs(experiment_names=["round-trip"], output_format="list")
    runs_by_id = {r.info.run_id: r for r in runs}
    parent_record = runs_by_id[parent_run_id]
    child_record = runs_by_id[child_run_id]

    # Parent: params + metrics + tags + dict artifact.
    assert parent_record.data.params["seed"] == "7"
    assert parent_record.data.params["model_id"] == "test-model"
    assert parent_record.data.metrics["loss"] == 0.4  # last logged value (step=1)
    assert parent_record.data.tags["hardware"] == "M1 Pro"
    assert parent_record.data.tags["role"] == "parent"
    # cfg.run_tags merged in at start_run time:
    assert parent_record.data.tags["stage"] == "test"
    assert parent_record.data.tags["issue"] == "16"

    # Parent dict artifact: log_dict writes "heatmap.json" (auto-appended).
    parent_artifact_dir = Path(parent_record.info.artifact_uri.replace("file://", ""))
    heatmap_file = parent_artifact_dir / "heatmap.json"
    assert heatmap_file.exists(), f"heatmap.json missing at {heatmap_file}"
    heatmap_data = json.loads(heatmap_file.read_text(encoding="utf-8"))
    assert heatmap_data == {"field_a": 0.85, "field_b": 0.92}

    # Child: param + metric + artifact + parentRunId link.
    assert child_record.data.params["child_param"] == "x"
    assert child_record.data.metrics["child_metric"] == 1.5
    assert child_record.data.tags["mlflow.parentRunId"] == parent_run_id

    child_artifact_dir = Path(child_record.info.artifact_uri.replace("file://", ""))
    assert (child_artifact_dir / "output.txt").exists()
    assert (child_artifact_dir / "output.txt").read_text(encoding="utf-8") == "hello mlflow"


def test_mlflow_tracker_exception_marks_run_failed(tmp_path: Path) -> None:
    """Exception inside `with start_run(...)` → MLflow run.status=FAILED + re-raise."""
    import mlflow

    from horus.tracking import MLflowTracker

    cfg = _mk_cfg(tmp_path, experiment_name="failure-test")
    tracker = MLflowTracker(cfg.mlflow)

    captured_run_id: str | None = None
    with pytest.raises(RuntimeError, match="intentional"):
        with tracker.start_run(run_name="will-fail") as r:
            captured_run_id = r.run_id
            tracker.log_param("seed", 1)
            raise RuntimeError("intentional")

    assert captured_run_id is not None
    run = mlflow.get_run(captured_run_id)
    assert run.info.status == "FAILED"


def test_mlflow_tracker_log_dict_appends_json_extension(tmp_path: Path) -> None:
    """`log_dict('foo', d)` writes `foo.json`; `log_dict('foo.json', d)` is idempotent."""
    import mlflow

    from horus.tracking import MLflowTracker

    cfg = _mk_cfg(tmp_path, experiment_name="dict-ext")
    tracker = MLflowTracker(cfg.mlflow)

    with tracker.start_run(run_name="dict-run") as r:
        tracker.log_dict("no_ext", {"a": 1})
        tracker.log_dict("with_ext.json", {"b": 2})
        run_id = r.run_id

    assert run_id is not None
    run = mlflow.get_run(run_id)
    artifact_dir = Path(run.info.artifact_uri.replace("file://", ""))
    assert (artifact_dir / "no_ext.json").exists()
    assert (artifact_dir / "with_ext.json").exists()
    # And NOT a double-extension file.
    assert not (artifact_dir / "with_ext.json.json").exists()


def test_mlflow_tracker_end_run_explicit_status(tmp_path: Path) -> None:
    """Procedural `tracker.end_run('KILLED')` writes the custom status to MLflow."""
    import mlflow

    from horus.tracking import MLflowTracker

    cfg = _mk_cfg(tmp_path, experiment_name="killed-status")
    tracker = MLflowTracker(cfg.mlflow)

    # Use procedural form (not `with`) so end_run() controls the status.
    cm = tracker.start_run(run_name="killed-run")
    r = cm.__enter__()
    run_id = r.run_id
    tracker.end_run(status="KILLED")
    # `__exit__` of an active-but-already-ended run is a no-op for MLflow
    # (mlflow.end_run is idempotent); ensure no double-end exception.
    cm.__exit__(None, None, None)

    assert run_id is not None
    run = mlflow.get_run(run_id)
    assert run.info.status == "KILLED"
