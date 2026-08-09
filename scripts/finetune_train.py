"""Fine-tune the Arm-B structurer via text-only LoRA SFT (issue #55).

    uv run python scripts/finetune_train.py
    uv run python scripts/finetune_train.py --config configs/finetune-structurer.yaml

Reads every knob from the YAML (horus-config-discipline). Trains on the sealed TRAIN split
only, minus a deterministic dev slice carved out of it (ADR-067) which supplies the
in-training validation loss. The sealed VAL split is **not touched here at all** — it is
scored exactly once, by `scripts/finetune_evaluate.py --adapter <dir>`, after the epoch has
already been chosen on dev.

Saves a LoRA adapter to ``cfg.adapter_dir`` plus one checkpoint per epoch
(``{iter:07d}_adapters.safetensors``); `horus.finetune.train.materialize_checkpoint` lays a
chosen checkpoint out as a directory the evaluator can load.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.train import run_finetune  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="finetune_train")
    parser.add_argument("--config", default="configs/finetune-structurer.yaml")
    parser.add_argument("--limit-train", type=int, default=0, help="Spike: cap training pairs.")
    parser.add_argument("--iters", type=int, default=0, help="Spike: force iteration count.")
    parser.add_argument("--max-seq", type=int, default=0, help="Spike: override max_seq_length.")
    parser.add_argument("--no-val", action="store_true", help="Spike: skip val-loss endpoints.")
    args = parser.parse_args(argv[1:])

    cfg = FinetuneConfig.from_yaml(args.config)
    result = run_finetune(
        cfg,
        limit_train=args.limit_train or None,
        override_iters=args.iters or None,
        override_max_seq=args.max_seq or None,
        skip_val=args.no_val,
    )

    print()
    print("## Fine-tune complete")
    print(f"  adapter_dir          : {result.adapter_dir}")
    print(f"  train / val examples : {result.n_train} / {result.n_val}")
    print(f"  iters                : {result.iters}")
    print(f"  max_seq_length       : {result.max_seq_length}")
    mask = f"{result.train_on_completions} (id={result.assistant_id})"
    print(f"  completion-mask      : {mask}")
    if result.excluded:
        print(f"  excluded targets     : {len(result.excluded)} (self-score gate)")
    if result.flagged:
        print(f"  flagged targets      : {len(result.flagged)} (kept; scorer under-credits)")
    print()
    print(
        "Next: uv run python scripts/finetune_evaluate.py --split val "
        f"--adapter {result.adapter_dir} --label finetuned"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
