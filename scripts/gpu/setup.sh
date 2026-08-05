#!/usr/bin/env bash
# One-shot environment bootstrap for the rented CUDA box (issue #55 reader bake-off).
# Run ON the instance after the repo has been rsync'd to ~/horus (see README.md).
#
# Assumes: Ubuntu 22.04/24.04 with a working NVIDIA driver (nvidia-smi succeeds) —
# e.g. AWS Deep Learning Base AMI on g5.xlarge (A10G 24 GB).
set -euo pipefail

cd "$(dirname "$0")/../.."   # repo root

echo "== GPU check =="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

echo "== uv install =="
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv --version

echo "== HF cache placement (RunPod volume, if present) =="
if [ -d /workspace ]; then
    export HF_HOME=/workspace/hf
    grep -q 'HF_HOME=/workspace/hf' ~/.bashrc 2>/dev/null || echo 'export HF_HOME=/workspace/hf' >> ~/.bashrc
    echo "HF_HOME -> /workspace/hf (persistent volume; survives pod restart)"
else
    echo "no /workspace volume detected — default HF cache"
fi

echo "== Python + deps (mlx-vlm is platform-gated out on Linux) =="
uv python install 3.14
uv sync

echo "== CUDA visibility from torch =="
uv run python -c "import torch; assert torch.cuda.is_available(), 'torch cannot see CUDA'; print('CUDA OK:', torch.cuda.get_device_name(0))"

echo "== Data sanity (at least one dataset must have arrived) =="
# Two workloads run on this box and they need DIFFERENT data, so neither dataset can
# be a hard requirement: the reader bake-off / transcript regen needs the synthetic
# ZUGFeRD corpus + the sealed split, while the held-out Belege transcription needs
# only data/self-collected. Requiring both would force a pointless ~300 MB upload for
# a 39-invoice run. Requiring NEITHER would let a botched rsync look like success,
# which is the failure this check exists to catch — hence "at least one".
found_any=0

if [ -d data/raw/german/zugferd-corpus ]; then
    found_any=1
    echo "zugferd corpus PDFs: $(find data/raw/german/zugferd-corpus -name '*.pdf' | wc -l)"
    if [ -f data/finetune/split.json ]; then
        uv run python -c "import json, pathlib; s = json.loads(pathlib.Path('data/finetune/split.json').read_text()); print(f'sealed split: {len(s[\"train\"])} train / {len(s[\"val\"])} val')"
    else
        echo "WARN: corpus present but data/finetune/split.json is missing (needed to re-eval the sealed split)."
    fi
fi

if [ -f data/self-collected/index.json ]; then
    found_any=1
    echo "held-out Belege PDFs: $(find data/self-collected -name '*.pdf' | wc -l) (gt files: $(ls data/self-collected/gt 2>/dev/null | wc -l))"
fi

if [ "$found_any" -eq 0 ]; then
    echo "ERROR: no dataset found — expected data/raw/german/zugferd-corpus or data/self-collected/index.json." >&2
    echo "       Check the rsync step in scripts/gpu/README.md; note that macOS rsync ignores" >&2
    echo "       the './' --relative pivot, so paths can land under a nested Users/... tree." >&2
    exit 1
fi

echo "== Setup complete. Next: bake-off commands in scripts/gpu/README.md =="
