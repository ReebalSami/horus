"""Arm B runner — orchestrated read-then-structure structuring pass CLI (ADR-038).

Thin argparse wrapper around `horus.eval.arm_b.run_arm_b()`. Arm B is the
orchestrated extraction arm (image -> Granite reader -> text -> Gemma structurer
-> fields); this script drives its structuring pass over the cached reader
transcripts produced by a prior reader cohort run (e.g. the regex baseline's
Granite run). Pairs with `make arm-b`.

Usage:
    # Structuring pass over cached Granite transcripts (run the reader pass first):
    #   make pilot-13 CFG=configs/pilot-13.yaml,configs/baseline-regex.yaml
    uv run python scripts/run_arm_b.py \
        --cfg configs/pilot-13.yaml,configs/arm-b.yaml

Refs: ADR-038 (this script's enabling ADR — the two-pass Arm B mechanism),
      ADR-034 (the two arms), `horus.eval.arm_b.run_arm_b` (the runner this wraps).
"""

from __future__ import annotations

import argparse
import sys

from horus.cli.banner import print_banner
from horus.config import ExperimentConfig
from horus.eval.arm_b import run_arm_b
from horus.seeding import set_global_seed


def _csv(value: str) -> list[str]:
    """Argparse type converter for comma-separated lists (strips empty entries)."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_arm_b",
        description="HORUS Arm B (orchestrated) structuring-pass runner — ADR-038",
    )
    parser.add_argument(
        "--cfg",
        required=True,
        type=_csv,
        metavar="PATH[,OVERLAY,...]",
        help=(
            "Comma-separated YAML config path(s) to deep-merge (ADR-016). The "
            "cohort section MUST set `reader_model_id` + exactly one structurer "
            "in `working_models` + a `prompt_template_override` for it. Example: "
            "`configs/pilot-13.yaml,configs/arm-b.yaml`."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        metavar="N",
        help="Decode budget for each structuring generation (default 2048).",
    )
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv[1:])

    cfg = ExperimentConfig.from_yaml(args.cfg)
    cfg_display = ",".join(args.cfg)

    if cfg.cohort is None:
        print(
            f"ERROR: {cfg_display!r} is missing the cohort: section. "
            "See configs/arm-b.yaml for the canonical Arm B schema.",
            file=sys.stderr,
        )
        return 2
    if cfg.cohort.reader_model_id is None:
        print(
            f"ERROR: {cfg_display!r} cohort.reader_model_id is unset. Arm B "
            "requires the reader whose cached transcripts the structurer "
            "consumes (see configs/arm-b.yaml).",
            file=sys.stderr,
        )
        return 2

    set_global_seed(cfg.seed)

    print_banner()
    print(
        f"[arm-b] cfg={cfg_display} "
        f"experiment={cfg.mlflow.experiment_name!r} "
        f"reader={cfg.cohort.reader_model_id!r} "
        f"structurer={cfg.cohort.working_models!r}",
        flush=True,
    )

    result = run_arm_b(cfg, max_tokens=args.max_tokens)

    print()
    print("=" * 72, flush=True)
    print(f"[arm-b] parent_run_id={result.parent_run_id}", flush=True)
    print(
        f"[arm-b] invoices: {result.n_completed} completed, "
        f"{result.n_failed} failed out of {result.n_invoices_total} total",
        flush=True,
    )
    print(
        f"[arm-b] micro_F1: "
        f"pooled={result.cohort_micro_f1_pooled:.4f} "
        f"EN16931={result.cohort_micro_f1_en16931:.4f} "
        f"XRECHNUNG={result.cohort_micro_f1_xrechnung:.4f}",
        flush=True,
    )
    print("=" * 72, flush=True)

    return 0 if result.n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
