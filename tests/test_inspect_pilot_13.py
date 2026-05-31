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
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ADR-022: `scripts/` is a Python package; `from scripts import inspect_pilot_13`
# resolves natively via pytest's `pythonpath = ["."]` ini config (no per-file
# sys.path manipulation needed).
from scripts import inspect_pilot_13


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

    Pins the Amendment-1 rendering contract:
      - header line contains all 9 columns (decode_tps + e2e_tps split per AA)
      - MLX-backed model row shows numeric decode_tps; MPS-backed shows —
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
                    "perf.decode_tps_mean": 75.0,  # MLX backend: decode-only TPS
                    "perf.inference_tps_mean": 50.0,  # E2E always lower (prompt encoding overhead)
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
                    "perf.decode_tps_mean": 0.0,  # MPS backend: decode-only unmeasurable
                    "perf.inference_tps_mean": 18.3,
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
    # Header columns present (Amendment 1: tps split into decode_tps + e2e_tps).
    for col in ("wall_s", "decode_tps", "e2e_tps", "chars/s", "gen_tok", "peak_GB", "%_max"):
        assert col in out, f"column header {col!r} missing from output"
    # One row per model.
    assert "model-A" in out
    assert "model-B" in out
    # %_max column populated for both (3.0 / 21.33 ≈ 14.1%; 7.5 / 21.33 ≈ 35.2%).
    assert "14.1%" in out, f"model-A %_max should be 14.1%, output:\n{out}"
    assert "35.2%" in out, f"model-B %_max should be 35.2%, output:\n{out}"
    # MLX backend (model-A) row shows numeric decode_tps; MPS backend
    # (model-B) row shows — (decode_tps unmeasurable per ADR-017 Amendment 1).
    model_a_line = next(line for line in out.splitlines() if "model-A" in line)
    model_b_line = next(line for line in out.splitlines() if "model-B" in line)
    assert "75.00" in model_a_line, (
        f"model-A is MLX-backed (decode_tps=75.0); decode_tps column should render "
        f"as '75.00'. Row: {model_a_line!r}"
    )
    # MPS row: decode_tps column should render as — (NOT 0.00 — 0.0 is the
    # sentinel for unmeasurable per harness logic; inspector filters those out).
    # The line will contain at least one — (decode_tps); peak/%_max may also.
    assert "—" in model_b_line, (
        f"model-B is MPS-backed (decode_tps=0.0 sentinel); inspector should render "
        f"— not numeric. Row: {model_b_line!r}"
    )


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
    assert "decode_tps" not in out  # Amendment-1 column also absent on graceful path


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
                    "perf.decode_tps_mean": 50.0,
                    "perf.inference_tps_mean": 33.3,
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


def test_print_perf_table_reads_legacy_generation_tps_mean_as_e2e_tps(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pre-Amendment-1 runs that logged `perf.generation_tps_mean` render as e2e_tps.

    ADR-017 Amendment 1 split the misleading single TPS metric into two
    (decode_tps_mean + inference_tps_mean). The old `generation_tps_mean`
    formula was actually end-to-end despite the misleading name. The
    inspector preserves backward-compat: legacy runs are read and rendered
    in the `e2e_tps` column (which is what they actually were); their
    `decode_tps` shows — (no decode-only metric was ever logged).

    Pins the backward-compat contract so existing parent runs in the
    `pilot-13-full` experiment remain inspectable without re-running.
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    parent_id, nested = _make_synthetic_parent_with_nested(
        tracking_uri=tracking_uri,
        experiment_name="inspector-perf-test-legacy",
        parent_metrics={"perf.mps_recommended_max_gb": 21.33},
        nested_specs=[
            {
                "model_id": "legacy-model",
                "metrics": {
                    "extract_seconds_total": 100.0,
                    "perf.generation_tokens_total": 500,
                    # Legacy metric only (pre-Amendment-1 run).
                    "perf.generation_tps_mean": 5.0,
                    "perf.chars_per_sec": 50.0,
                    "perf.peak_memory_gb": 4.2,
                    "perf.output_len_chars_total": 5000,
                    "perf.pages_extracted_ok": 2,
                    # NOTE: perf.decode_tps_mean + perf.inference_tps_mean
                    # deliberately ABSENT (legacy run).
                },
            },
        ],
    )

    inspect_pilot_13._print_perf_table(nested, parent_run_id=parent_id)
    out = capsys.readouterr().out

    # Section + header rendered — legacy run IS perf-equipped.
    assert "per-model perf summary" in out
    assert "decode_tps" in out  # Header always present when ANY tps metric exists
    assert "e2e_tps" in out
    # Find the legacy-model row.
    row_lines = [line for line in out.splitlines() if "legacy-model" in line]
    assert len(row_lines) == 1, f"expected 1 legacy-model row, got {row_lines}"
    row = row_lines[0]
    # e2e_tps shows the legacy value (5.00) — the pre-Amendment-1 metric was
    # actually end-to-end despite the misleading `generation_tps_mean` name.
    assert "5.00" in row, (
        f"legacy perf.generation_tps_mean=5.0 should render as e2e_tps=5.00; row was: {row!r}"
    )
    # decode_tps shows — (no decode-only metric in legacy logging).
    assert "—" in row, (
        f"legacy run has no perf.decode_tps_mean → decode_tps column must be —; row was: {row!r}"
    )


def test_csv_type_converter_splits_multifile_cfg() -> None:
    """`_csv` accepts comma-separated config paths (ADR-016 multi-file composition).

    Regression guard: the inspector previously treated `--cfg` as a single
    path, breaking the documented `make inspect-pilot-13
    CFG=base.yaml,overlay.yaml` invocation. Mirrors the
    `run_pilot_13.py::_csv` precedent.
    """
    assert inspect_pilot_13._csv("a.yaml") == ["a.yaml"]
    assert inspect_pilot_13._csv("a.yaml,b.yaml") == ["a.yaml", "b.yaml"]
    assert inspect_pilot_13._csv(" a.yaml , b.yaml ") == ["a.yaml", "b.yaml"]
    # Empty entries from trailing commas are stripped.
    assert inspect_pilot_13._csv("a.yaml,,b.yaml,") == ["a.yaml", "b.yaml"]
    assert inspect_pilot_13._csv("") == []


def test_print_perf_table_sorts_by_wall_s_ascending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Models sort by mean wall_s ascending — fastest first.

    Pins the Chunk 4 sort order. H8 latency-efficiency story reads top-down;
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
                    "perf.decode_tps_mean": 10.0,
                    "perf.inference_tps_mean": 6.7,
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
                    "perf.decode_tps_mean": 150.0,
                    "perf.inference_tps_mean": 100.0,
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
                    "perf.decode_tps_mean": 37.5,
                    "perf.inference_tps_mean": 25.0,
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
