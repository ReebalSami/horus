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

echo "== Corpus + split sanity =="
uv run python -c "
from pathlib import Path
import json
corpus = Path('data/raw/german/zugferd-corpus')
split = json.loads(Path('data/finetune/split.json').read_text())
pdfs = list(corpus.rglob('*.pdf'))
print(f'corpus PDFs: {len(pdfs)}; split: {len(split[\"train\"])} train / {len(split[\"val\"])} val')
assert pdfs, 'corpus missing — check the rsync include list in scripts/gpu/README.md'
"

echo "== Setup complete. Next: bake-off commands in scripts/gpu/README.md =="
