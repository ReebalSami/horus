"""Unit tests for `scripts/inspect_pilot_13.py` perf-table rendering.

ADR-017 (issue #52) extension: the inspector script gained `_print_perf_table`,
which surfaces the per-tuple `perf.*` MLflow metrics logged by the cohort
harness as a per-model performance summary. These tests pin the rendering
contract — column shape, sort order, graceful degradation when perf metrics
are missing — without invoking the full pilot-13 cohort sweep.

Strategy: real MLflow + sqlite tracking (matches `test_harness.py` style); no
real VLM extractor. Synthetic parent + nested runs are written directly via
`mlflow.start_run` / `log_metric`. This isolates the inspector logic from the
upstream harness write path.

`scripts/` is not a package — `inspect_pilot_13` loads via `sys.path` manipulation
(matches the `tests/test_rescore.py` precedent).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ is not a package — load inspect_pilot_13 via sys.path manipulation.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import inspect_pilot_13  # noqa: E402


def _make_synthetic_parent_with_nested(
    *,
    tracking_uri: str,
    experiment_name: str,
    nested_specs: list[dict],
    parent_metrics: dict | None = None,
) -> tuple[str, list]:
    """Helper: write a parent run + N nested runs to MLflow; return (parent_id, nested_runs).

    Args:
        tracking_uri: sqlite:/// URI pointing at a tmp_path-isolated DB.
        experiment_name: experiment name (created if missing).
        nested_specs: list of dicts with keys: `model_id`, `metrics` (dict),
            `tags` (dict, optional). Each spec becomes one FINISHED nested run.
        parent_metrics: optional dict of metrics to log on the parent run
            (typically `{"perf.mps_recommended_max_gb": 21.33}` to exercise
            the %_max column).

    Returns:
        (parent_run_id, list of nested Run objects in MLflow's `search_runs`
        order).
    """
    import mlflow  # noqa: PLC0415

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name="parent-test") as parent_run:
        parent_id = parent_run.info.run_id
        if parent_metrics:
            for k, v in parent_metrics.items():
                mlflow.log_metric(k, float(v))

        for spec in nested_specs:
            with mlflow.start_run(run_name=f"nested-{spec['model_id']}", nested=True):
                mlflow.set_tag("model_id", spec["model_id"])
                for k, v in spec.get("tags", {}).items():
                    mlflow.set_tag(k, v)
                for k, v in spec.get("metrics", {}).items():
                    mlflow.log_metric(k, float(v))

    experiment = mlflow.get_experiment_by_name(experiment_name)
    assert experiment is not None
    nested = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{parent_id}'",
        output_format="list",
    )
    return parent_id, nested


def test_print_perf_table_renders_full_table_when_metrics_present(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Renders the perf table with model rows + all column headers when nested runs have perf.*.

    Pins the Chunk 4 rendering contract:
      - header line contains all 8 columns
      - one row per model with mean values
      - MPS ceiling line shown when parent logs `perf.mps_recommended_max_gb`
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    parent_id, nested = _make_synthetic_parent_with_nested(
        tracking_uri=tracking_uri,
        experiment_name="inspector-perf-test-full",
        parent_metrics={"perf.mps_recommended_max_gb": 21.33},
        nested_specs=[
            {
                "model_id": "model-A",
                "metrics": {
                    "extract_seconds_total": 4.0,
                    "perf.generation_tokens_total": 200,
                    "perf.generation_tps_mean": 50.0,
                    "perf.chars_per_sec": 600.0,
                    "perf.peak_memory_gb": 3.0,
                    "perf.output_len_chars_total": 2400,
                    "perf.pages_extracted_ok": 2,
                },
            },
            {
                "model_id": "model-B",
                "metrics": {
                    "extract_seconds_total": 12.0,
                    "perf.generation_tokens_total": 220,
                    "perf.generation_tps_mean": 18.3,
                    "perf.chars_per_sec": 200.0,
                    "perf.peak_memory_gb": 7.5,
                    "perf.output_len_chars_total": 2400,
                    "perf.pages_extracted_ok": 2,
                },
            },
        ],
    )

    inspect_pilot_13._print_perf_table(nested, parent_run_id=parent_id)
    out = capsys.readouterr().out

    # Section header present.
    assert "per-model perf summary" in out
    # MPS ceiling line surfaces.
    assert "MPS ceiling" in out
    assert "21.33" in out
    # Header columns present.
    for col in ("wall_s", "tps", "chars/s", "gen_tok", "peak_GB", "%_max"):
        assert col in out, f"column header {col!r} missing from output"
    # One row per model.
    assert "model-A" in out
    assert "model-B" in out
    # %_max column populated for both (3.0 / 21.33 ≈ 14.1%; 7.5 / 21.33 ≈ 35.2%).
    assert "14.1%" in out, f"model-A %_max should be 14.1%, output:\n{out}"
    assert "35.2%" in out, f"model-B %_max should be 35.2%, output:\n{out}"


def test_print_perf_table_falls_back_when_no_perf_metrics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pre-#52 nested runs (no perf.*) → single-line note instead of empty table.

    Graceful degradation per ADR-017 §"Decision 3": parent runs from before
    issue #52's harness instrumentation predate `perf.*` logging. The inspector
    must surface that explicitly rather than render a blank table or zeros.
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    parent_id, nested = _make_synthetic_parent_with_nested(
        tracking_uri=tracking_uri,
        experiment_name="inspector-perf-test-pre52",
        parent_metrics=None,  # pre-#52 parents had no MPS ceiling either
        nested_specs=[
            {
                "model_id": "old-model",
                "metrics": {
                    # Only the pre-#52 metric — no perf.*
                    "extract_seconds_total": 5.0,
                    "extract_seconds_mean": 2.5,
                },
            },
        ],
    )

    inspect_pilot_13._print_perf_table(nested, parent_run_id=parent_id)
    out = capsys.readouterr().out

    assert "no perf.* metrics found" in out
    # Header line for the table NOT printed (graceful path).
    assert "wall_s" not in out
    assert "%_max" not in out


def test_print_perf_table_shows_dash_when_no_mps_ceiling(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When parent run lacks `perf.mps_recommended_max_gb`, %_max column shows "—".

    Covers two operational cases:
      - Non-MPS hosts (e.g., CI with no Apple Silicon) — torch.mps unavailable
        at parent-run time → harness skips the ceiling log → inspector reads
        no ceiling → "—".
      - Pre-#52 parent runs that have nested perf metrics from a partial backfill
        (unlikely but logically possible).

    The `_mean_str` formatter still prints peak_GB for the row; only the
    ratio column degrades.
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    parent_id, nested = _make_synthetic_parent_with_nested(
        tracking_uri=tracking_uri,
        experiment_name="inspector-perf-test-no-ceiling",
        parent_metrics=None,  # CRUCIAL — no MPS ceiling on parent
        nested_specs=[
            {
                "model_id": "model-X",
                "metrics": {
                    "extract_seconds_total": 3.0,
                    "perf.generation_tokens_total": 100,
                    "perf.generation_tps_mean": 33.3,
                    "perf.chars_per_sec": 500.0,
                    "perf.peak_memory_gb": 2.0,
                    "perf.output_len_chars_total": 1500,
                    "perf.pages_extracted_ok": 1,
                },
            },
        ],
    )

    inspect_pilot_13._print_perf_table(nested, parent_run_id=parent_id)
    out = capsys.readouterr().out

    assert "model-X" in out
    # The ceiling-not-logged hint surfaces.
    assert "not logged at parent" in out
    # %_max column of model-X shows "—" (not a percentage).
    # Find the model-X row and check the trailing token.
    model_x_lines = [line for line in out.splitlines() if "model-X" in line]
    assert len(model_x_lines) == 1, f"expected 1 model-X row, got: {model_x_lines}"
    row = model_x_lines[0]
    # Last column is %_max; should end with the em-dash sentinel, not a %.
    assert row.rstrip().endswith("—"), (
        f"%_max should show — when no MPS ceiling logged; row was:\n{row!r}"
    )


def test_print_perf_table_sorts_by_wall_s_ascending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Models sort by mean wall_s ascending — fastest first.

    Pins the Chunk 4 sort order. H4 latency-efficiency story reads top-down;
    putting the slowest model on top would invert the inspector's intent.
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    parent_id, nested = _make_synthetic_parent_with_nested(
        tracking_uri=tracking_uri,
        experiment_name="inspector-perf-test-sort",
        parent_metrics={"perf.mps_recommended_max_gb": 21.33},
        nested_specs=[
            {
                "model_id": "slow-model",
                "metrics": {
                    "extract_seconds_total": 30.0,  # SLOW
                    "perf.generation_tokens_total": 200,
                    "perf.generation_tps_mean": 6.7,
                    "perf.chars_per_sec": 80.0,
                    "perf.peak_memory_gb": 6.0,
                    "perf.output_len_chars_total": 2400,
                    "perf.pages_extracted_ok": 2,
                },
            },
            {
                "model_id": "fast-model",
                "metrics": {
                    "extract_seconds_total": 2.0,  # FAST
                    "perf.generation_tokens_total": 200,
                    "perf.generation_tps_mean": 100.0,
                    "perf.chars_per_sec": 1200.0,
                    "perf.peak_memory_gb": 1.5,
                    "perf.output_len_chars_total": 2400,
                    "perf.pages_extracted_ok": 2,
                },
            },
            {
                "model_id": "medium-model",
                "metrics": {
                    "extract_seconds_total": 8.0,  # MEDIUM
                    "perf.generation_tokens_total": 200,
                    "perf.generation_tps_mean": 25.0,
                    "perf.chars_per_sec": 300.0,
                    "perf.peak_memory_gb": 3.0,
                    "perf.output_len_chars_total": 2400,
                    "perf.pages_extracted_ok": 2,
                },
            },
        ],
    )

    inspect_pilot_13._print_perf_table(nested, parent_run_id=parent_id)
    out = capsys.readouterr().out

    # Get index of each model row in the output.
    fast_idx = out.find("fast-model")
    medium_idx = out.find("medium-model")
    slow_idx = out.find("slow-model")

    assert fast_idx > 0, "fast-model row missing from output"
    assert medium_idx > 0, "medium-model row missing from output"
    assert slow_idx > 0, "slow-model row missing from output"
    # Sort: fast < medium < slow
    assert fast_idx < medium_idx < slow_idx, (
        f"models not sorted by wall_s ascending: "
        f"fast={fast_idx}, medium={medium_idx}, slow={slow_idx}"
    )
