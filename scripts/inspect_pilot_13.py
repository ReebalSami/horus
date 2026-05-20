"""Inspect a pilot-13 parent MLflow run — grid of per-(model, invoice) F1 + Probe evidence.

Read-only inspection helper for ADR-014 PR(c). Surfaces:

  1. The latest pilot-13 parent run_id under the configured experiment.
  2. A grid `(model, invoice) → micro_F1` for all nested runs under that parent.
  3. Probe 1 evidence: MONEY field TP counts for the best-of-cohort model on
     EN16931_Einfach (ADR-014 §"acceptance criterion" — multi-page must lift
     MONEY-field TPs from PR(b)'s ~0 to ≥3 on at least one model).
  4. Probe 2 evidence: XRECHNUNG_Einfach DATE-field outcomes per model
     (ADR-014 + ADR-012 Probe 5 — confirms factur-x route delivers 2018-* dates
     that the models can actually match).

Usage:
    uv run python scripts/inspect_pilot_13.py
        # auto-picks latest parent under cfg.mlflow.experiment_name

    uv run python scripts/inspect_pilot_13.py --parent-run-id ac80183a746e458bb...
        # inspect a specific parent run by id

    uv run python scripts/inspect_pilot_13.py --cfg configs/pilot-13.yaml
        # override the experiment name via a different cfg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from horus.config import ExperimentConfig
from horus.eval.ground_truth import FIELDS

DEFAULT_CFG = Path("configs/pilot-13.yaml")

# Derive MONEY + DATE field sets dynamically from the canonical FIELDS registry.
# Hardcoded sets drift; FIELDS is the single source of truth (see ground_truth.py).
MONEY_FIELDS = frozenset(k for k, spec in FIELDS.items() if spec.field_type == "MONEY")
DATE_FIELDS = frozenset(k for k, spec in FIELDS.items() if spec.field_type == "DATE")


def _resolve_parent_run_id(*, experiment_id: str, override: str | None) -> str | None:
    """Return the parent run_id to inspect. CLI override > most-recent parent under exp."""
    import mlflow  # noqa: PLC0415 — defer heavy import

    if override is not None:
        return override
    # Most-recent (start_time DESC) run under the experiment with no parent run.
    candidates = mlflow.search_runs(
        experiment_ids=[experiment_id],
        filter_string="tags.mlflow.parentRunId IS NULL",
        order_by=["attributes.start_time DESC"],
        max_results=1,
        output_format="list",
    )
    if not candidates:
        return None
    return str(candidates[0].info.run_id)


def _print_per_run_grid(experiment_id: str, parent_run_id: str) -> list:
    """Print the (model, invoice) → micro_F1 grid; return the list of nested runs."""
    import mlflow  # noqa: PLC0415

    nested = mlflow.search_runs(
        experiment_ids=[experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{parent_run_id}'",
        order_by=["attributes.start_time ASC"],
        max_results=1000,
        output_format="list",
    )
    print(f"nested runs under parent {parent_run_id}: {len(nested)}")
    if not nested:
        return nested

    # Sort by (model_id, invoice_id) for a stable grid view.
    nested_sorted = sorted(
        nested,
        key=lambda r: (r.data.tags.get("model_id", ""), r.data.tags.get("invoice_id", "")),
    )
    print()
    print(f"{'model':<55} {'invoice':<48} {'profile':<10} {'pages':>5} {'f1':>8} status")
    print("-" * 130)
    for r in nested_sorted:
        m = r.data.tags.get("model_id", "?")
        inv = r.data.tags.get("invoice_id", "?")
        profile = r.data.tags.get("profile", "?")
        pages = r.data.tags.get("pages", "-")
        f1 = float(r.data.metrics.get("micro_f1", 0.0))
        status = r.info.status
        print(f"{m:<55} {inv:<48} {profile:<10} {pages:>5} {f1:>8.3f} {status}")

    return nested


def _print_per_model_aggregate(nested: list) -> None:
    """Print mean micro_F1 per model across the inspected sweep."""
    from collections import defaultdict  # noqa: PLC0415

    per_model: dict[str, list[float]] = defaultdict(list)
    for r in nested:
        m = r.data.tags.get("model_id", "?")
        if r.info.status != "FINISHED":
            continue
        f1 = float(r.data.metrics.get("micro_f1", 0.0))
        per_model[m].append(f1)

    print()
    print("per-model aggregate (mean micro_F1 across all FINISHED invoices in this sweep):")
    print(f"{'model':<55} {'n':>5} {'mean_f1':>10}")
    print("-" * 75)
    ranked = sorted(per_model.items(), key=lambda kv: -sum(kv[1]) / max(len(kv[1]), 1))
    for m, scores in ranked:
        mean = sum(scores) / len(scores) if scores else 0.0
        print(f"{m:<55} {len(scores):>5} {mean:>10.3f}")


def _print_perf_table(nested: list, *, parent_run_id: str) -> None:
    """Render per-model perf summary table — ADR-017 (issue #52).

    Sister to `_print_per_model_aggregate`. While that function ranks
    models by accuracy (mean micro_F1), this one surfaces the orthogonal
    timing / throughput / memory axis. Same source data (the list of
    MLflow nested Run objects already in memory); independent rendering.

    Columns:
      - `model`     : model_id (HF canonical name)
      - `n`         : count of FINISHED tuples with perf.* metrics
      - `wall_s`    : mean `extract_seconds_total` (the entire scoring
                      wall-clock; includes rasterization + adapter + scorer)
      - `tps`       : mean `perf.generation_tps_mean` (native per-model
                      tokenizer; NOT cross-model comparable — caveat per
                      ADR-017 §"Decision 5")
      - `chars/s`   : mean `perf.chars_per_sec` (tokenizer-agnostic
                      sanity-check; pairs with `tps`)
      - `gen_tok`   : mean `perf.generation_tokens_total` per tuple
      - `peak_GB`   : mean `perf.peak_memory_gb` — for MLX models this is
                      the true peak via `mx.get_peak_memory()`; for MPS
                      models this is the post-extract snapshot via
                      `torch.mps.driver_allocated_memory()` (ADR-017 §D2.A;
                      documented limitation — snapshot, not transient peak)
      - `%_max`     : `max(peak_GB) / mps_ceiling_gb * 100` if the parent
                      logged `perf.mps_recommended_max_gb`; else blank

    Sort: ascending by mean wall_s — fastest models top, slowest bottom.
    Eye-friendly for the H4 latency-efficiency story.

    Graceful degradation per ADR-017 §"Decision 3": pre-#52 parent runs
    (no perf.* metrics on any nested run) get a single-line note instead
    of a table. Mixed runs (some tuples have perf.*, some don't) report
    the perf table over the perf-equipped subset + a footer note with
    the un-equipped count.

    Args:
        nested: list of FINISHED nested Run objects (from MLflow). Same
            list `_print_per_model_aggregate` consumes.
        parent_run_id: parent run ID — used to fetch the host-constant
            `perf.mps_recommended_max_gb` ceiling for the %_max column.
    """
    from collections import defaultdict  # noqa: PLC0415

    import mlflow  # noqa: PLC0415 — defer heavy import

    # Fetch parent's MPS ceiling (constant per host; logged once at
    # run_cohort entry per ADR-017 Chunk 2). Silent fallback to None
    # when the parent predates #52 or when MPS is unavailable on the
    # logging host.
    client = mlflow.MlflowClient()
    mps_ceiling_gb: float | None = None
    try:
        parent_run = client.get_run(parent_run_id)
        ceiling = parent_run.data.metrics.get("perf.mps_recommended_max_gb")
        if ceiling is not None:
            mps_ceiling_gb = float(ceiling)
    except Exception:  # noqa: BLE001 — non-fatal; inspector continues without ceiling
        pass

    # Per-model accumulators (mean across all FINISHED + perf-equipped tuples).
    per_model_wall: dict[str, list[float]] = defaultdict(list)
    per_model_tps: dict[str, list[float]] = defaultdict(list)
    per_model_chars: dict[str, list[float]] = defaultdict(list)
    per_model_tokens: dict[str, list[float]] = defaultdict(list)
    per_model_peak: dict[str, list[float]] = defaultdict(list)

    n_with_perf = 0
    n_without_perf = 0

    for r in nested:
        if r.info.status != "FINISHED":
            continue
        m = r.data.tags.get("model_id", "?")
        metrics = r.data.metrics

        wall_s = metrics.get("extract_seconds_total")
        has_perf = metrics.get("perf.generation_tps_mean") is not None

        if has_perf:
            n_with_perf += 1
            if wall_s is not None:
                per_model_wall[m].append(float(wall_s))
            per_model_tps[m].append(float(metrics["perf.generation_tps_mean"]))
            if metrics.get("perf.chars_per_sec") is not None:
                per_model_chars[m].append(float(metrics["perf.chars_per_sec"]))
            if metrics.get("perf.generation_tokens_total") is not None:
                per_model_tokens[m].append(float(metrics["perf.generation_tokens_total"]))
            peak = metrics.get("perf.peak_memory_gb")
            if peak is not None and peak > 0.0:
                per_model_peak[m].append(float(peak))
        elif wall_s is not None:
            # FINISHED tuple but no perf.* — pre-#52 nested run.
            n_without_perf += 1

    print()
    print("per-model perf summary (mean across all FINISHED + perf-equipped tuples):")

    if n_with_perf == 0:
        print(
            "  no perf.* metrics found on any nested run — this parent run "
            "predates issue #52 instrumentation (run via post-#52 harness "
            "to populate per-tuple perf metrics)"
        )
        if mps_ceiling_gb is not None:
            print(f"  (MPS ceiling logged at parent: {mps_ceiling_gb:.2f} GB)")
        return

    if mps_ceiling_gb is not None:
        print(f"  MPS ceiling (host-constant): {mps_ceiling_gb:.2f} GB")
    else:
        print("  MPS ceiling: not logged at parent (host without MPS, or pre-#52 run)")

    header = (
        f"{'model':<55} {'n':>4} {'wall_s':>9} {'tps':>8} "
        f"{'chars/s':>9} {'gen_tok':>9} {'peak_GB':>9} {'%_max':>7}"
    )
    print(header)
    print("-" * len(header))

    def _mean_str(xs: list[float], *, fmt: str = "{:.2f}") -> str:
        if not xs:
            return "—"
        return fmt.format(sum(xs) / len(xs))

    # Sort by mean wall_s ascending (fastest models top).
    all_models = sorted(
        per_model_wall.keys(),
        key=lambda mm: (
            sum(per_model_wall[mm]) / max(len(per_model_wall[mm]), 1)
            if per_model_wall[mm]
            else float("inf")
        ),
    )
    for m in all_models:
        n = len(per_model_tps[m])
        wall_s = _mean_str(per_model_wall[m])
        tps = _mean_str(per_model_tps[m])
        chars = _mean_str(per_model_chars[m])
        tokens = _mean_str(per_model_tokens[m], fmt="{:.0f}")
        peak = _mean_str(per_model_peak[m])
        if per_model_peak[m] and mps_ceiling_gb is not None and mps_ceiling_gb > 0:
            max_peak = max(per_model_peak[m])
            pct = f"{(max_peak / mps_ceiling_gb) * 100:.1f}%"
        else:
            pct = "—"
        print(f"{m:<55} {n:>4} {wall_s:>9} {tps:>8} {chars:>9} {tokens:>9} {peak:>9} {pct:>7}")

    if n_without_perf > 0:
        print()
        print(
            f"  Note: {n_without_perf} tuples lack perf.* metrics (pre-#52 "
            f"logging) — excluded from the per-model means above"
        )


def _print_probe_1_money_tps(nested: list) -> None:
    """Probe 1: count MONEY-field TPs per model on EN16931_Einfach.

    PR(b) baseline = 0 MONEY TPs (page-1-only rasterization misses page-2 totals).
    Acceptance criterion = ≥3 MONEY TPs on at least 1 model.
    """
    import mlflow  # noqa: PLC0415

    money_fields = MONEY_FIELDS
    print()
    print(
        f"Probe 1 evidence — MONEY-field TPs on EN16931_Einfach "
        f"(acceptance: ≥3 / {len(money_fields)}):"
    )
    print(f"{'model':<55} {'money TPs':>10} {'/ MONEY fields':>20}")
    print("-" * 90)

    client = mlflow.MlflowClient()
    # tuple shape: (model_id, money_tp_or_minus_one_if_err, money_total). -1 sentinel for ERR.
    rows: list[tuple[str, int, int]] = []
    for r in nested:
        if r.data.tags.get("invoice_id") != "EN16931_Einfach":
            continue
        if r.info.status != "FINISHED":
            continue
        m = r.data.tags.get("model_id", "?")
        # Pull the per_field_scores.json artifact.
        try:
            artifact_path = client.download_artifacts(r.info.run_id, "per_field_scores.json")
            with open(artifact_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # noqa: BLE001
            rows.append((m, -1, len(money_fields)))
            continue
        per_field = data.get("per_field", {})
        money_tp = sum(1 for fk in money_fields if per_field.get(fk, {}).get("outcome") == "TP")
        money_total = sum(1 for fk in money_fields if fk in per_field)
        rows.append((m, money_tp, money_total))

    rows.sort(key=lambda row: -row[1])
    best_tp = 0
    for m, money_tp, money_total in rows:
        display = "ERR" if money_tp < 0 else str(money_tp)
        print(f"{m:<55} {display:>10} {f'/  {money_total} fields':>26}")
        if money_tp >= 0:
            best_tp = max(best_tp, money_tp)

    print()
    if best_tp >= 3:
        print(f"Probe 1 PASS: best-of-cohort MONEY TPs on EN16931_Einfach = {best_tp} (≥ 3)")
    else:
        print(f"Probe 1 FAIL: best-of-cohort MONEY TPs on EN16931_Einfach = {best_tp} (< 3)")


def _print_probe_2_xrechnung_dates(nested: list) -> None:
    """Probe 2: XRECHNUNG_Einfach DATE-field outcomes per model.

    PR(b) baseline = ~0 (sidecar carries 2024-* dates; models output 2018-* from
    the visual PDF → always mismatch). Acceptance = factur-x route lifts ≥1 model
    to TP on issue_date or due_date.
    """
    import mlflow  # noqa: PLC0415

    date_fields = sorted(DATE_FIELDS)
    print()
    print("Probe 2 evidence — XRECHNUNG_Einfach DATE-field outcomes (factur-x route):")
    header = f"{'model':<55}" + "".join(f"{fk:<16}" for fk in date_fields)
    print(header)
    print("-" * len(header))

    client = mlflow.MlflowClient()
    any_tp = False
    rows = []
    for r in nested:
        if r.data.tags.get("invoice_id") != "XRECHNUNG_Einfach":
            continue
        if r.info.status != "FINISHED":
            continue
        m = r.data.tags.get("model_id", "?")
        try:
            artifact_path = client.download_artifacts(r.info.run_id, "per_field_scores.json")
            with open(artifact_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # noqa: BLE001
            rows.append((m, ["ERR"] * len(date_fields)))
            continue
        per_field = data.get("per_field", {})
        outcomes = []
        for fk in date_fields:
            outcome = per_field.get(fk, {}).get("outcome", "?")
            outcomes.append(outcome)
            if outcome == "TP":
                any_tp = True
        rows.append((m, outcomes))

    for m, outcomes in rows:
        line = f"{m:<55}" + "".join(f"{o:<16}" for o in outcomes)
        print(line)

    print()
    if any_tp:
        print(
            "Probe 2 PASS: ≥1 model has TP on a DATE field of XRECHNUNG_Einfach (factur-x route)."
        )
    else:
        print(
            "Probe 2 FAIL: 0 models scored TP on any DATE field of XRECHNUNG_Einfach. "
            "Inspect transcripts to determine whether the failure is route-level "
            "(sidecar drift) or model-level (model cannot read the date)."
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="inspect_pilot_13")
    parser.add_argument(
        "--cfg",
        default=str(DEFAULT_CFG),
        help=f"Config YAML (default: {DEFAULT_CFG})",
    )
    parser.add_argument(
        "--parent-run-id",
        default=None,
        help="Inspect this parent run instead of latest",
    )
    args = parser.parse_args(argv[1:])

    import mlflow  # noqa: PLC0415

    cfg = ExperimentConfig.from_yaml(args.cfg)
    if cfg.mlflow.tracking_uri:
        mlflow.set_tracking_uri(cfg.mlflow.tracking_uri)

    exp = mlflow.get_experiment_by_name(cfg.mlflow.experiment_name)
    if exp is None:
        print(f"ERROR: experiment {cfg.mlflow.experiment_name!r} not found.", file=sys.stderr)
        return 1
    print(f"experiment: {cfg.mlflow.experiment_name!r} (id={exp.experiment_id})")

    parent = _resolve_parent_run_id(experiment_id=exp.experiment_id, override=args.parent_run_id)
    if parent is None:
        print("ERROR: no parent runs found.", file=sys.stderr)
        return 1
    print(f"inspecting parent run: {parent}")

    nested = _print_per_run_grid(exp.experiment_id, parent)
    if not nested:
        return 1

    _print_per_model_aggregate(nested)
    _print_perf_table(nested, parent_run_id=parent)
    _print_probe_1_money_tps(nested)
    _print_probe_2_xrechnung_dates(nested)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
