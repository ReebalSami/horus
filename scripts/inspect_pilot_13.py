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

from rich import box as rbox
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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

    console = Console(highlight=False)
    nested = mlflow.search_runs(
        experiment_ids=[experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{parent_run_id}'",
        order_by=["attributes.start_time ASC"],
        max_results=1000,
        output_format="list",
    )
    console.print(f"nested runs under parent {parent_run_id}: {len(nested)}")
    if not nested:
        return nested

    # Sort by (model_id, invoice_id) for a stable grid view.
    nested_sorted = sorted(
        nested,
        key=lambda r: (r.data.tags.get("model_id", ""), r.data.tags.get("invoice_id", "")),
    )

    table = Table(box=rbox.SIMPLE_HEAVY, show_lines=False, highlight=False)
    table.add_column("model", style="cyan", no_wrap=True)
    table.add_column("invoice", style="white")
    table.add_column("profile", style="dim")
    table.add_column("pages", justify="right")
    table.add_column("f1", justify="right")
    table.add_column("status")

    for r in nested_sorted:
        m = r.data.tags.get("model_id", "?")
        inv = r.data.tags.get("invoice_id", "?")
        profile = r.data.tags.get("profile", "?")
        pages = r.data.tags.get("pages", "-")
        f1 = float(r.data.metrics.get("micro_f1", 0.0))
        status = r.info.status
        f1_color = "green" if f1 >= 0.5 else ("yellow" if f1 >= 0.3 else "red")
        status_color = "green" if status == "FINISHED" else "red"
        table.add_row(
            m,
            inv,
            profile,
            pages,
            f"[{f1_color}]{f1:.3f}[/{f1_color}]",
            f"[{status_color}]{status}[/{status_color}]",
        )

    console.print(table)
    return nested


def _print_per_model_aggregate(nested: list) -> None:
    """Print mean micro_F1 per model across the inspected sweep."""
    from collections import defaultdict  # noqa: PLC0415

    console = Console(highlight=False)
    per_model: dict[str, list[float]] = defaultdict(list)
    for r in nested:
        m = r.data.tags.get("model_id", "?")
        if r.info.status != "FINISHED":
            continue
        f1 = float(r.data.metrics.get("micro_f1", 0.0))
        per_model[m].append(f1)

    console.print()
    console.print(
        Panel(
            Text(
                "per-model aggregate (mean micro_F1 across all FINISHED invoices)",
                justify="center",
            ),
            border_style="cyan",
        )
    )
    table = Table(box=rbox.SIMPLE_HEAVY, show_lines=False, highlight=False)
    table.add_column("model", style="cyan")
    table.add_column("n", justify="right")
    table.add_column("mean_f1", justify="right")

    ranked = sorted(per_model.items(), key=lambda kv: -sum(kv[1]) / max(len(kv[1]), 1))
    for m, scores in ranked:
        mean = sum(scores) / len(scores) if scores else 0.0
        f1_color = "green" if mean >= 0.5 else ("yellow" if mean >= 0.3 else "red")
        table.add_row(m, str(len(scores)), f"[{f1_color}]{mean:.3f}[/{f1_color}]")

    console.print(table)


def _print_perf_table(nested: list, *, parent_run_id: str) -> None:
    """Render per-model perf summary table — ADR-017 (issue #52).

    Sister to `_print_per_model_aggregate`. While that function ranks
    models by accuracy (mean micro_F1), this one surfaces the orthogonal
    timing / throughput / memory axis. Same source data (the list of
    MLflow nested Run objects already in memory); independent rendering.

    Columns (ADR-017 Amendment 1 — the TPS metric was split into two
    after AA-methodology research; see ADR-017 §"Amendment 1"):
      - `model`        : model_id (HF canonical name)
      - `n`            : count of FINISHED tuples with perf.* metrics
      - `wall_s`       : mean `extract_seconds_total` (entire scoring
                         wall-clock; includes rasterization + adapter + scorer)
      - `decode_tps`   : mean `perf.decode_tps_mean` — DECODE-ONLY tokens-per-second
                         (matches Artificial Analysis "Output Speed" definition
                         + MLX-VLM's `GenerationResult.generation_tps`). Available
                         only for MLX-routed extractors (the library reports
                         decode-only timing natively). Renders as `—` for
                         Transformers-MPS rows (decode-only unmeasurable via
                         public `transformers.generate(...)` API). Native
                         per-model tokenizer — NOT cross-model comparable in
                         absolute terms (re-tokenize with tiktoken o200k_base
                         for AA-strict cross-model comparison; deferred to H4).
      - `e2e_tps`      : mean `perf.inference_tps_mean` — END-TO-END
                         tokens-per-second (includes prompt encoding +
                         decode + post-processing). Always computable.
                         Use this for user-perceived latency claims;
                         use `decode_tps` for model-decode-speed claims.
      - `chars/s`      : mean `perf.chars_per_sec` (e2e, tokenizer-agnostic
                         sanity-check; pairs with `e2e_tps`)
      - `gen_tok`      : mean `perf.generation_tokens_total` per tuple
      - `peak_GB`      : mean `perf.peak_memory_gb` — for MLX models this is
                         the true peak via `mx.get_peak_memory()`; for MPS
                         models this is the post-extract snapshot via
                         `torch.mps.driver_allocated_memory()` (ADR-017 §D2.A;
                         documented limitation — snapshot, not transient peak)
      - `%_max`        : `max(peak_GB) / mps_ceiling_gb * 100` if the parent
                         logged `perf.mps_recommended_max_gb`; else `—`

    Sort: ascending by mean wall_s — fastest models top, slowest bottom.
    Eye-friendly for the H4 latency-efficiency story.

    Graceful degradation per ADR-017 §"Decision 3": pre-#52 parent runs
    (no perf.* metrics on any nested run) get a single-line note instead
    of a table. Mixed runs (some tuples have perf.*, some don't) report
    the perf table over the perf-equipped subset + a footer note with
    the un-equipped count. Pre-Amendment-1 runs that logged the legacy
    `perf.generation_tps_mean` are read back as `e2e_tps` (the legacy
    formula was end-to-end despite the misleading field name); their
    `decode_tps` renders as `—`.

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
    per_model_decode_tps: dict[str, list[float]] = defaultdict(list)
    per_model_e2e_tps: dict[str, list[float]] = defaultdict(list)
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
        # ADR-017 Amendment 1: prefer the new split metrics; fall back to
        # legacy `perf.generation_tps_mean` (which was end-to-end despite
        # the misleading name). Detection: a run is "perf-equipped" if
        # ANY of the three TPS metric keys is present.
        has_decode_tps = metrics.get("perf.decode_tps_mean") is not None
        has_inference_tps = metrics.get("perf.inference_tps_mean") is not None
        has_legacy_tps = metrics.get("perf.generation_tps_mean") is not None
        has_perf = has_decode_tps or has_inference_tps or has_legacy_tps

        if has_perf:
            n_with_perf += 1
            if wall_s is not None:
                per_model_wall[m].append(float(wall_s))
            # decode_tps: only from Amendment-1 metric (decode-only); legacy
            # runs had no decode-only metric. Skip the bucket when 0.0 —
            # MLflow logged 0.0 means decode_tps_available was false (MPS
            # backend); rendering as — is the right semantic, not "0.00".
            if has_decode_tps:
                decode_val = float(metrics["perf.decode_tps_mean"])
                if decode_val > 0.0:
                    per_model_decode_tps[m].append(decode_val)
            # e2e_tps: from Amendment-1 `inference_tps_mean` (preferred) or
            # legacy `generation_tps_mean` (which WAS end-to-end). Both map
            # to the same column.
            if has_inference_tps:
                per_model_e2e_tps[m].append(float(metrics["perf.inference_tps_mean"]))
            elif has_legacy_tps:
                per_model_e2e_tps[m].append(float(metrics["perf.generation_tps_mean"]))
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

    console = Console(highlight=False)
    console.print()
    console.print("per-model perf summary (mean across all FINISHED + perf-equipped tuples):")

    if n_with_perf == 0:
        console.print(
            "  no perf.* metrics found on any nested run — this parent run "
            "predates issue #52 instrumentation (run via post-#52 harness "
            "to populate per-tuple perf metrics)"
        )
        if mps_ceiling_gb is not None:
            console.print(f"  (MPS ceiling logged at parent: {mps_ceiling_gb:.2f} GB)")
        return

    if mps_ceiling_gb is not None:
        console.print(f"  MPS ceiling (host-constant): {mps_ceiling_gb:.2f} GB")
    else:
        console.print("  MPS ceiling: not logged at parent (host without MPS, or pre-#52 run)")

    def _mean_str(xs: list[float], *, fmt: str = "{:.2f}") -> str:
        if not xs:
            return "—"
        return fmt.format(sum(xs) / len(xs))

    # box=None preserves em-dash test assertions (row.rstrip().endswith("—")).
    table = Table(box=None, show_lines=False, show_edge=False, pad_edge=False, highlight=False)
    table.add_column("model", style="cyan", no_wrap=True)
    table.add_column("n", justify="right")
    table.add_column("wall_s", justify="right")
    table.add_column("decode_tps", justify="right")
    table.add_column("e2e_tps", justify="right")
    table.add_column("chars/s", justify="right")
    table.add_column("gen_tok", justify="right")
    table.add_column("peak_GB", justify="right")
    table.add_column("%_max", justify="right")

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
        n = len(per_model_e2e_tps[m])
        wall_s = _mean_str(per_model_wall[m])
        decode_tps = _mean_str(per_model_decode_tps[m])
        e2e_tps = _mean_str(per_model_e2e_tps[m])
        chars = _mean_str(per_model_chars[m])
        tokens = _mean_str(per_model_tokens[m], fmt="{:.0f}")
        peak = _mean_str(per_model_peak[m])
        if per_model_peak[m] and mps_ceiling_gb is not None and mps_ceiling_gb > 0:
            max_peak = max(per_model_peak[m])
            pct = f"{(max_peak / mps_ceiling_gb) * 100:.1f}%"
        else:
            pct = "—"
        table.add_row(m, str(n), wall_s, decode_tps, e2e_tps, chars, tokens, peak, pct)

    console.print(table)

    if n_without_perf > 0:
        console.print()
        console.print(
            f"  Note: {n_without_perf} tuples lack perf.* metrics (pre-#52 "
            f"logging) — excluded from the per-model means above"
        )


def _print_probe_1_money_tps(nested: list) -> None:
    """Probe 1: count MONEY-field TPs per model on EN16931_Einfach.

    PR(b) baseline = 0 MONEY TPs (page-1-only rasterization misses page-2 totals).
    Acceptance criterion = ≥3 MONEY TPs on at least 1 model.
    """
    import mlflow  # noqa: PLC0415

    console = Console(highlight=False)
    money_fields = MONEY_FIELDS
    console.print()
    console.print(
        Panel(
            Text(
                f"Probe 1 evidence — MONEY-field TPs on EN16931_Einfach "
                f"(acceptance: ≥3 / {len(money_fields)})",
                justify="center",
            ),
            border_style="yellow",
        )
    )

    client = mlflow.MlflowClient()
    rows: list[tuple[str, int, int]] = []
    for r in nested:
        if r.data.tags.get("invoice_id") != "EN16931_Einfach":
            continue
        if r.info.status != "FINISHED":
            continue
        m = r.data.tags.get("model_id", "?")
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

    table = Table(box=rbox.SIMPLE_HEAVY, highlight=False)
    table.add_column("model", style="cyan")
    table.add_column("money TPs", justify="right")
    table.add_column("/ MONEY fields", justify="right")

    rows.sort(key=lambda row: -row[1])
    best_tp = 0
    for m, money_tp, money_total in rows:
        display_val = "[red]ERR[/red]" if money_tp < 0 else str(money_tp)
        tp_color = "green" if money_tp >= 3 else ("yellow" if money_tp > 0 else "red")
        table.add_row(m, f"[{tp_color}]{display_val}[/{tp_color}]", f"{money_total} fields")
        if money_tp >= 0:
            best_tp = max(best_tp, money_tp)

    console.print(table)
    console.print()
    if best_tp >= 3:
        console.print(f"[bold green]Probe 1 PASS[/]: best-of-cohort MONEY TPs = {best_tp} (≥ 3)")
    else:
        console.print(f"[bold red]Probe 1 FAIL[/]: best-of-cohort MONEY TPs = {best_tp} (< 3)")


def _print_probe_2_xrechnung_dates(nested: list) -> None:
    """Probe 2: XRECHNUNG_Einfach DATE-field outcomes per model.

    PR(b) baseline = ~0 (sidecar carries 2024-* dates; models output 2018-* from
    the visual PDF → always mismatch). Acceptance = factur-x route lifts ≥1 model
    to TP on issue_date or due_date.
    """
    import mlflow  # noqa: PLC0415

    console = Console(highlight=False)
    date_fields = sorted(DATE_FIELDS)
    console.print()
    console.print(
        Panel(
            Text(
                "Probe 2 evidence — XRECHNUNG_Einfach DATE-field outcomes (factur-x route)",
                justify="center",
            ),
            border_style="yellow",
        )
    )

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

    table = Table(box=rbox.SIMPLE_HEAVY, highlight=False)
    table.add_column("model", style="cyan")
    for fk in date_fields:
        table.add_column(fk, justify="center")

    for m, outcomes in rows:
        colored_outcomes = []
        for o in outcomes:
            if o == "TP":
                colored_outcomes.append("[green]TP[/green]")
            elif o == "FN":
                colored_outcomes.append("[red]FN[/red]")
            elif o == "FP":
                colored_outcomes.append("[yellow]FP[/yellow]")
            else:
                colored_outcomes.append(o)
        table.add_row(m, *colored_outcomes)

    console.print(table)
    console.print()
    if any_tp:
        console.print(
            "[bold green]Probe 2 PASS[/]: ≥1 model has TP on a DATE field of "
            "XRECHNUNG_Einfach (factur-x route)."
        )
    else:
        console.print(
            "[bold red]Probe 2 FAIL[/]: 0 models scored TP on any DATE field of "
            "XRECHNUNG_Einfach. Inspect transcripts to determine whether the failure "
            "is route-level (sidecar drift) or model-level."
        )


def _print_extended_metrics(nested: list) -> None:
    """ADR-027: presence-conditional F1 + KIEval group-level F1 + spurious-
    emission rate (per-model + cohort) + per-canonical-label F1 (cohort).

    Re-aggregates the per-field outcomes already saved in each nested run's
    `per_field_scores.json` — no VLM, no re-run (ADR-020 offline rescore). Uses
    the SAME scorer metric functions as the per-invoice path (ADR-027 Fork 4).
    """
    import dataclasses  # noqa: PLC0415
    from collections import defaultdict  # noqa: PLC0415

    import mlflow  # noqa: PLC0415

    from horus.eval.scorer import (  # noqa: PLC0415
        FieldResult,
        f1_from_counts,
        group_level_counts,
        label_outcome_counts,
        presence_conditional_counts,
        spurious_emission_counts,
    )

    console = Console(highlight=False)
    console.print()
    console.print(
        Panel(
            Text(
                "ADR-027 extended metrics — presence-conditional F1 + group-level "
                "F1 (KIEval) + spurious-emission rate + per-label F1",
                justify="center",
            ),
            border_style="magenta",
        )
    )

    client = mlflow.MlflowClient()
    fr_field_names = [f.name for f in dataclasses.fields(FieldResult)]
    per_model: dict[str, list[list[FieldResult]]] = defaultdict(list)
    n_err = 0
    for r in nested:
        if r.info.status != "FINISHED":
            continue
        m = r.data.tags.get("model_id", "?")
        try:
            artifact_path = client.download_artifacts(r.info.run_id, "per_field_scores.json")
            with open(artifact_path, encoding="utf-8") as fh:
                data = json.load(fh)
            per_field = data.get("per_field", {})
            results = [
                FieldResult(**{k: rec[k] for k in fr_field_names}) for rec in per_field.values()
            ]
        except OSError, KeyError, TypeError, ValueError:  # noqa: BLE001 handled below
            n_err += 1
            continue
        per_model[m].append(results)

    if not per_model:
        console.print(
            "  no readable per_field_scores.json artifacts on the nested runs — "
            "cannot compute ADR-027 metrics"
        )
        return

    rows: list[tuple[str, int, float, float, float]] = []
    coh_pc = [0, 0, 0]
    coh_gl = [0, 0, 0]
    coh_fp = 0
    coh_abs = 0
    for m, invoices in per_model.items():
        pc_tp = pc_fp = pc_fn = 0
        gl_tp = gl_fp = gl_fn = 0
        sp_fp = sp_abs = 0
        for results in invoices:
            pt, pf, pn = presence_conditional_counts(results)
            pc_tp += pt
            pc_fp += pf
            pc_fn += pn
            gt, gf, gn = group_level_counts(results)
            gl_tp += gt
            gl_fp += gf
            gl_fn += gn
            xfp, xabs = spurious_emission_counts(results)
            sp_fp += xfp
            sp_abs += xabs
        coh_pc[0] += pc_tp
        coh_pc[1] += pc_fp
        coh_pc[2] += pc_fn
        coh_gl[0] += gl_tp
        coh_gl[1] += gl_fp
        coh_gl[2] += gl_fn
        coh_fp += sp_fp
        coh_abs += sp_abs
        rows.append(
            (
                m,
                len(invoices),
                f1_from_counts(pc_tp, pc_fp, pc_fn)[2],
                f1_from_counts(gl_tp, gl_fp, gl_fn)[2],
                sp_fp / sp_abs if sp_abs else 0.0,
            )
        )

    rows.sort(key=lambda x: -x[2])  # presence-conditional F1 desc

    table = Table(box=rbox.SIMPLE_HEAVY, highlight=False)
    table.add_column("model", style="cyan")
    table.add_column("n_inv", justify="right")
    table.add_column("presence_F1", justify="right")
    table.add_column("group_F1", justify="right")
    table.add_column("spurious", justify="right")
    for m, n_inv, pc_f1, gl_f1, sp_rate in rows:
        table.add_row(m, str(n_inv), f"{pc_f1:.3f}", f"{gl_f1:.3f}", f"{sp_rate:.3f}")
    table.add_section()
    table.add_row(
        "[bold]COHORT[/bold]",
        str(sum(n for _, n, _, _, _ in rows)),
        f"[bold]{f1_from_counts(coh_pc[0], coh_pc[1], coh_pc[2])[2]:.3f}[/bold]",
        f"[bold]{f1_from_counts(coh_gl[0], coh_gl[1], coh_gl[2])[2]:.3f}[/bold]",
        f"[bold]{(coh_fp / coh_abs if coh_abs else 0.0):.3f}[/bold]",
    )
    console.print(table)

    all_results = [r for invoices in per_model.values() for results in invoices for r in results]
    label_counts = label_outcome_counts(all_results)
    console.print()
    console.print("per-canonical-label F1 (cohort-pooled, hardest first):")
    ltable = Table(box=rbox.SIMPLE_HEAVY, highlight=False)
    ltable.add_column("field", style="cyan")
    ltable.add_column("tp", justify="right")
    ltable.add_column("fp", justify="right")
    ltable.add_column("fn", justify="right")
    ltable.add_column("f1", justify="right")
    label_rows = []
    for key, c in label_counts.items():
        label_rows.append((key, c[0], c[1], c[2], f1_from_counts(c[0], c[1], c[2])[2]))
    label_rows.sort(key=lambda x: x[4])
    for key, tp, fp, fn, f1 in label_rows:
        color = "green" if f1 >= 0.5 else ("yellow" if f1 >= 0.3 else "red")
        ltable.add_row(key, str(tp), str(fp), str(fn), f"[{color}]{f1:.3f}[/{color}]")
    console.print(ltable)

    if n_err:
        console.print()
        console.print(f"  Note: {n_err} nested runs lacked a readable per_field_scores.json")


def _csv(value: str) -> list[str]:
    """Argparse type converter for comma-separated config paths.

    Mirrors `scripts/run_pilot_13.py::_csv` so the inspector supports
    ADR-016 multi-file YAML composition (`--cfg base.yaml,overlay.yaml`).
    Without this, the dev-cohort smoke (which composes `pilot-13.yaml,
    pilot-13-dev.yaml`) cannot resolve to the `pilot-13-dev` experiment.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="inspect_pilot_13")
    parser.add_argument(
        "--cfg",
        default=[str(DEFAULT_CFG)],
        type=_csv,
        metavar="PATH[,OVERLAY,...]",
        help=(
            "Comma-separated YAML config path(s) to deep-merge (ADR-016 "
            f"multi-file composition; default: {DEFAULT_CFG}). Later files win "
            "on conflict. Pass `base.yaml,dev-overlay.yaml` to inspect a dev-cohort run."
        ),
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

    console = Console(highlight=False)
    exp = mlflow.get_experiment_by_name(cfg.mlflow.experiment_name)
    if exp is None:
        print(f"ERROR: experiment {cfg.mlflow.experiment_name!r} not found.", file=sys.stderr)
        return 1
    console.print(f"experiment: {cfg.mlflow.experiment_name!r} (id={exp.experiment_id})")

    parent = _resolve_parent_run_id(experiment_id=exp.experiment_id, override=args.parent_run_id)
    if parent is None:
        print("ERROR: no parent runs found.", file=sys.stderr)
        return 1
    console.print(f"inspecting parent run: {parent}")

    nested = _print_per_run_grid(exp.experiment_id, parent)
    if not nested:
        return 1

    _print_per_model_aggregate(nested)
    _print_perf_table(nested, parent_run_id=parent)
    _print_probe_1_money_tps(nested)
    _print_probe_2_xrechnung_dates(nested)
    _print_extended_metrics(nested)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
