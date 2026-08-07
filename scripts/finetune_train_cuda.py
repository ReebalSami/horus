"""Fine-tune the Arm-B structurer via TRL + PEFT LoRA on a CUDA box (issue #55, ADR-068).

    uv run python scripts/finetune_train_cuda.py                                  # reader arm
    uv run python scripts/finetune_train_cuda.py --config configs/finetune-structurer-oracle.yaml

Runs ON the rented GPU instance (see `scripts/gpu/README.md`). Refuses to run without a
visible CUDA device — the Apple-Silicon path is `scripts/finetune_train.py`, which ADR-068
records as non-viable at full scale on an M1 Pro 16 GB.

Reads every knob from the YAML (`horus-config-discipline`). Trains on the sealed TRAIN split
minus a deterministic dev slice carved out of it; the dev slice supplies the per-epoch
validation loss that selects the checkpoint (ADR-067). The sealed VAL split is **never**
touched here — it is scored once, afterwards, by `scripts/finetune_evaluate.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.train_cuda import run_finetune_cuda  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="finetune_train_cuda")
    parser.add_argument("--config", default="configs/finetune-structurer.yaml")
    parser.add_argument(
        "--model-id",
        default=None,
        help=(
            "HF repo to load. Defaults to cfg.structurer_model. Override when the config's "
            "id maps to an MLX mirror that is meaningless on CUDA."
        ),
    )
    parser.add_argument("--limit-train", type=int, default=0, help="Spike: cap training pairs.")
    parser.add_argument("--epochs", type=float, default=0.0, help="Spike: override epoch count.")
    parser.add_argument("--max-length", type=int, default=0, help="Spike: override max_length.")
    args = parser.parse_args(argv[1:])

    cfg = FinetuneConfig.from_yaml(args.config)
    result = run_finetune_cuda(
        cfg,
        limit_train=args.limit_train or None,
        override_epochs=args.epochs or None,
        override_max_length=args.max_length or None,
        model_id=args.model_id,
    )

    print()
    print("## Fine-tune complete")
    print(f"  adapter_dir          : {result.adapter_dir}")
    print(f"  input arm            : {result.input_arm}")
    print(f"  train / dev examples : {result.n_train} / {result.n_dev}")
    print(f"  epochs (budget)      : {result.epochs}")
    print(f"  max_length           : {result.max_length}")
    print(f"  LoRA target modules  : {len(result.target_modules)}")
    if result.excluded:
        print(f"  excluded targets     : {len(result.excluded)} (self-score gate)")
    if result.flagged:
        print(f"  flagged targets      : {len(result.flagged)} (kept; scorer under-credits)")

    curve = result.eval_loss_by_epoch()
    if curve:
        print()
        print("  dev loss by epoch (the selection curve):")
        best_epoch, best_loss = min(curve, key=lambda pair: pair[1])
        for epoch, loss in curve:
            marker = "  <- selected" if (epoch, loss) == (best_epoch, best_loss) else ""
            print(f"    epoch {epoch:>5.2f}  eval_loss {loss:.4f}{marker}")
    else:
        print()
        print("  WARNING: no dev-loss history recorded — the checkpoint was NOT selected on dev.")

    print(f"  best checkpoint      : {result.best_checkpoint}")
    print(f"  provenance           : {result.adapter_dir}/horus_training_provenance.json")
    print()
    print(
        "Next: uv run python scripts/finetune_evaluate.py --split val "
        f"--adapter {result.adapter_dir} --label finetuned-{result.input_arm}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
