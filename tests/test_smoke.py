"""Smoke test for the bootstrapped python-ml-uv project (HORUS).

Validates that:
- The package imports cleanly.
- The seeding primitive produces deterministic stdlib `random` output without
  requiring optional ML deps (numpy / torch).
- The tracking adapter's StdoutTracker default is wired up.
- The `ExperimentConfig` schema loads + validates YAML files with the
  fail-fast contract per `horus-config-discipline` / ADR-004.

Run via: `uv run pytest tests/test_smoke.py`
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_package_imports() -> None:
    """Package and its core utility modules import cleanly."""
    import horus  # noqa: F401
    from horus import config, seeding, tracking  # noqa: F401

    assert horus.__version__ == "0.1.0"


def test_set_global_seed_stdlib_only() -> None:
    """Seeding via stdlib `random` is deterministic across calls."""
    from horus.seeding import set_global_seed

    set_global_seed(42)
    a = [random.random() for _ in range(8)]
    set_global_seed(42)
    b = [random.random() for _ in range(8)]
    assert a == b, "stdlib random seeding must be deterministic"


def test_default_tracker_protocol() -> None:
    """DEFAULT_TRACKER satisfies the Tracker Protocol shape."""
    from horus.tracking import DEFAULT_TRACKER

    # Each Protocol method should be callable without raising.
    DEFAULT_TRACKER.log_metric("loss", 0.42, step=1)
    DEFAULT_TRACKER.log_param("learning_rate", 1e-3)
    DEFAULT_TRACKER.log_artifact("/tmp/dummy")


def test_experiment_config_from_yaml_loads_and_validates(tmp_path: Path) -> None:
    """Valid YAML loads cleanly into a typed `ExperimentConfig`."""
    from horus.config import ExperimentConfig

    cfg_path = tmp_path / "smoke.yaml"
    cfg_path.write_text(
        "seed: 42\nmlflow:\n  experiment_name: smoke-test\n  run_tags:\n    stage: smoke\n",
        encoding="utf-8",
    )
    cfg = ExperimentConfig.from_yaml(cfg_path)

    assert cfg.seed == 42
    assert cfg.mlflow.experiment_name == "smoke-test"
    assert cfg.mlflow.run_tags == {"stage": "smoke"}
    assert cfg.mlflow.tracking_uri is None  # default


def test_experiment_config_missing_file_raises(tmp_path: Path) -> None:
    """Missing config file raises FileNotFoundError before any Pydantic call."""
    from horus.config import ExperimentConfig

    with pytest.raises(FileNotFoundError):
        ExperimentConfig.from_yaml(tmp_path / "does-not-exist.yaml")


def test_experiment_config_missing_required_field_raises(tmp_path: Path) -> None:
    """Missing required field (`mlflow.experiment_name`) raises ValidationError."""
    from horus.config import ExperimentConfig

    cfg_path = tmp_path / "smoke.yaml"
    cfg_path.write_text(
        "seed: 42\nmlflow:\n  run_tags: {}\n",  # missing experiment_name
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        ExperimentConfig.from_yaml(cfg_path)


def test_experiment_config_extra_field_forbidden(tmp_path: Path) -> None:
    """Extra (unknown) field at the top level raises ValidationError per `extra='forbid'`."""
    from horus.config import ExperimentConfig

    cfg_path = tmp_path / "smoke.yaml"
    cfg_path.write_text(
        "seed: 42\nmlflow:\n  experiment_name: smoke-test\nunknown_knob: not-allowed\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        ExperimentConfig.from_yaml(cfg_path)


def test_experiment_config_extra_field_in_submodel_forbidden(tmp_path: Path) -> None:
    """Extra field inside a nested sub-model (`mlflow.unknown`) also raises."""
    from horus.config import ExperimentConfig

    cfg_path = tmp_path / "smoke.yaml"
    cfg_path.write_text(
        "seed: 42\nmlflow:\n  experiment_name: smoke-test\n  unknown_subknob: not-allowed\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        ExperimentConfig.from_yaml(cfg_path)
