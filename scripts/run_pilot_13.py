"""Pilot #13 runner — full cohort × ZUGFeRD-corpus evaluation harness CLI (ADR-014).

Thin argparse wrapper around `horus.eval.harness.run_cohort()`. The harness is the
substrate; this script is the user-facing entry-point for `make pilot-13` and ad-hoc
shell invocation.

Usage:
    # Full sweep (7 working models × 26 invoices)
    uv run python scripts/run_pilot_13.py --cfg configs/pilot-13.yaml

    # Multi-file YAML composition (ADR-016): base + dev overlay
    uv run python scripts/run_pilot_13.py \
        --cfg configs/pilot-13.yaml,configs/pilot-13-dev.yaml

    # Subset on invoices (3 fixtures) — Step 5 validation per ADR-014 plan
    uv run python scripts/run_pilot_13.py --cfg configs/pilot-13.yaml \
        --invoices EN16931_Einfach,EN16931_Einfach_negativePaymentDue,XRECHNUNG_Einfach

    # Subset on models (smallest possible smoke)
    uv run python scripts/run_pilot_13.py --cfg configs/pilot-13.yaml \
        --invoices EN16931_Einfach \
        --models ibm-granite/granite-docling-258M-mlx

    # Disable resume (re-run all (model, invoice) tuples even if already FINISHED)
    uv run python scripts/run_pilot_13.py --cfg configs/pilot-13.yaml --no-resume

Refs: ADR-014 §"Decision + integration thoughts" (this script's enabling ADR —
      forthcoming). Pairs with `make pilot-13` (Makefile target wired in step 4).
      `horus.eval.harness.run_cohort` (the orchestrator this script wraps).
"""

from __future__ import annotations

import argparse
import sys

from horus.cli.banner import print_banner
from horus.cli.dashboard import get_display_adapter
from horus.config import ExperimentConfig
from horus.eval.harness import HarnessRunResult, run_cohort
from horus.seeding import set_global_seed


def _csv(value: str) -> list[str]:
    """Argparse type converter for comma-separated lists (strips empty entries)."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_pilot_13",
        description="HORUS pilot #13 cohort harness runner — ADR-014",
    )
    parser.add_argument(
        "--cfg",
        required=True,
        type=_csv,
        metavar="PATH[,OVERLAY,...]",
        help=(
            "Comma-separated YAML config path(s) to deep-merge (ADR-016 multi-file "
            "composition). Single path or `base.yaml,overlay.yaml` (later wins). "
            "Examples: `configs/pilot-13.yaml` (full sweep); "
            "`configs/pilot-13.yaml,configs/pilot-13-dev.yaml` (dev overlay)."
        ),
    )
    parser.add_argument(
        "--invoices",
        type=_csv,
        default=None,
        metavar="STEM,STEM,…",
        help=(
            "Comma-separated PDF stems to restrict the sweep to "
            "(e.g., EN16931_Einfach,XRECHNUNG_Einfach). Omit for full corpus."
        ),
    )
    parser.add_argument(
        "--models",
        type=_csv,
        default=None,
        metavar="ID,ID,…",
        help=(
            "Comma-separated model IDs to restrict the sweep to "
            "(must all be in cohort.working_models). Omit for full cohort."
        ),
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help=(
            "Disable MLflow search_runs resume safety. Re-runs every (model, invoice) "
            "tuple even if a FINISHED nested run already exists under the parent."
        ),
    )
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv[1:])

    # args.cfg is list[str] (per _csv type converter). from_yaml accepts list.
    cfg = ExperimentConfig.from_yaml(args.cfg)
    cfg_display = ",".join(args.cfg)

    # Pydantic-validate at boot: cohort + rasterizer MUST be present for pilot-13.
    # run_cohort raises ValueError if either is None; surface that nicely here.
    if cfg.cohort is None:
        print(
            f"ERROR: {cfg_display!r} is missing the cohort: section. "
            "See configs/pilot-13.yaml for the canonical pilot-13 schema.",
            file=sys.stderr,
        )
        return 2
    if cfg.rasterizer is None:
        print(
            f"ERROR: {cfg_display!r} is missing the rasterizer: section. "
            "See configs/pilot-13.yaml for the canonical pilot-13 schema.",
            file=sys.stderr,
        )
        return 2

    # Honor --no-resume CLI override of the YAML default.
    if args.no_resume:
        cfg.cohort.resume_on_existing_run = False

    set_global_seed(cfg.seed)

    print_banner()
    print(
        f"[pilot-13] cfg={cfg_display} "
        f"experiment={cfg.mlflow.experiment_name!r} "
        f"parent_run_name={cfg.cohort.parent_run_name!r}",
        flush=True,
    )
    if args.invoices is not None:
        print(f"[pilot-13] --invoices subset: {args.invoices}", flush=True)
    if args.models is not None:
        print(f"[pilot-13] --models subset: {args.models}", flush=True)
    if not cfg.cohort.resume_on_existing_run:
        print("[pilot-13] resume DISABLED (--no-resume)", flush=True)

    display = get_display_adapter()
    _result_box: list[HarnessRunResult] = []

    def _harness() -> None:
        _result_box.append(
            run_cohort(
                cfg,
                invoice_subset=args.invoices,
                model_subset=args.models,
                display=display,
            )
        )

    display.run_with_harness(_harness)
    result = _result_box[0]

    # Summary footer.
    print()
    print("=" * 72, flush=True)
    print(f"[pilot-13] parent_run_id={result.parent_run_id}", flush=True)
    print(
        f"[pilot-13] models: {result.n_models_loaded}/{result.n_models_attempted} loaded",
        flush=True,
    )
    print(
        f"[pilot-13] (model, invoice) tuples: "
        f"{result.n_completed} completed, "
        f"{result.n_failed} failed, "
        f"{result.n_skipped_resume} skipped (resume) "
        f"out of {result.n_models_attempted * result.n_invoices_total} total",
        flush=True,
    )
    print(
        f"[pilot-13] cohort micro_F1: "
        f"pooled={result.cohort_micro_f1_pooled:.4f} "
        f"EN16931={result.cohort_micro_f1_en16931:.4f} "
        f"XRECHNUNG={result.cohort_micro_f1_xrechnung:.4f}",
        flush=True,
    )
    print("=" * 72, flush=True)

    return 0 if result.n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
