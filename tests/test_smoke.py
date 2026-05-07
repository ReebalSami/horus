"""Smoke test for the bootstrapped python-ml-uv project.

Validates that:
- The package imports cleanly.
- The seeding primitive produces deterministic stdlib `random` output without
  requiring optional ML deps (numpy / torch).
- The tracking adapter's StdoutTracker default is wired up.
- The Config dataclass instantiates with defaults.

Run via: `uv run pytest tests/test_smoke.py`
"""

from __future__ import annotations

import random


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


def test_config_defaults() -> None:
    """Config dataclass instantiates with sensible defaults."""
    from horus.config import Config

    cfg = Config()
    assert cfg.seed == 42
    assert cfg.batch_size == 32
    assert cfg.num_epochs == 1
