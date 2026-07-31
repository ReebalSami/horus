# Rented-GPU runbook — reader bake-off + transcript regeneration (issue #55)

Purpose: the M1 Pro 16 GB ceiling disqualified every full-precision reader candidate
locally (35 GiB Metal buffers, 4-bit German-text corruption, 49 min/page bf16 — see the
`feat(finetune): reader bake-off` commit). This runbook runs the bake-off at full
precision on a rented CUDA box, regenerates the 146 structurer-training transcripts with
the winning reader, and brings the artifacts home. **Training and final eval stay on the
M1** (the mlx_vlm LoRA trainer is Apple-only by design — matched train/serve precision).

Budget approved: ≲ $15 (< 6 GPU-hours on-demand). **Terminate the instance when done —
step 6 is not optional.**

## 1. Launch (once)

- **Instance**: `g5.xlarge` (A10G 24 GB), region `eu-central-1` (Frankfurt)
- **AMI**: *Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)* — driver preinstalled
- **Disk**: 200 GB gp3 (HF checkpoints: olmOCR-2-7B ≈16 GB, Qwen3-VL-4B ≈9 GB, MinerU ≈3 GB)
- **Security group**: SSH (22) from your IP only
- On-demand ≈ $1.01/hr; spot ≈ $0.30–0.45/hr (spot is fine — every pass here is resumable)

## 2. Sync repo + data (from the Mac)

```sh
rsync -avz --delete \
  --exclude '.git' --exclude '.venv' --exclude 'mlruns' --exclude 'mlflow.db' \
  --exclude 'data/' --exclude 'tools/' --exclude '__pycache__' \
  ~/Projects/horus/ ubuntu@<instance-ip>:~/horus/

rsync -avz --relative \
  ~/Projects/horus/./data/raw/german/zugferd-corpus \
  ~/Projects/horus/./data/finetune/split.json \
  ~/Projects/horus/./docs/sources/transcripts-multipage \
  ubuntu@<instance-ip>:~/horus/
```

(`docs/sources/transcripts-multipage` ships with the repo sync already; the explicit
line is belt-and-braces in case of exclude-pattern drift. Raster cache is NOT synced —
`pypdfium2` re-rasterizes on the box at the same 300 DPI / PNG settings.)

## 3. Bootstrap (on the instance)

```sh
ssh ubuntu@<instance-ip>
cd ~/horus && bash scripts/gpu/setup.sh
```

## 4. Reader bake-off — full precision, 29 sealed val invoices

Candidates ran at their canonical HF repos via `--force-transformers` (bf16, native
resolution — the `max_pixels` cap is MPS-only). Prompt / max_tokens / repetition_penalty
still come from `COHORT_MANIFEST`, so runs are comparable with the local 4-bit results.

```sh
# OCR-specialist 7B — the local 4-bit run corrupted German text; bf16 is the real test
uv run python scripts/finetune_reader_bakeoff.py \
  --reader allenai/olmOCR-2-7B-1025 --force-transformers

# Generalist 4B at native resolution — locally infeasible (35 GiB Metal buffer)
uv run python scripts/finetune_reader_bakeoff.py \
  --reader Qwen/Qwen3-VL-4B-Instruct --force-transformers

# Control: local leader (~0.72 answerability on M1) re-run on CUDA
uv run python scripts/finetune_reader_bakeoff.py \
  --reader opendatalab/MinerU2.5-Pro-2604-1.2B --force-transformers

# LEAD candidate (ADR-054): MinerU 3.3-release checkpoint — fixes 2604 stability
# issues + native multilingual OCR (German); same arch/wiring as 2604
uv run python scripts/finetune_reader_bakeoff.py \
  --reader opendatalab/MinerU2.5-Pro-2605-1.2B --force-transformers
```

Each prints the per-invoice answerability table vs the canonical Granite baseline
(mean 0.658). **Decision rule**: highest mean answerability wins, with no subdir
collapsing below the Granite baseline; ties break toward the smaller model
(local-deployability, H8 efficiency).

## 5. Regenerate all 146 transcripts with the winner

```sh
uv run python - <<'PY'
from pathlib import Path
from horus.finetune.dataset import build_records
from horus.finetune.reader_pass import ReaderPassConfig, run_reader_pass

WINNER = "<model-id-from-step-4>"
run_reader_pass(
    build_records(Path("data/raw/german/zugferd-corpus")),
    config=ReaderPassConfig(
        reader_model=WINNER,
        transcript_dir=Path("data/finetune/gpu-transcripts"),
        force_transformers=True,
    ),
)
PY
```

(Heredoc is fine here — this runs in a plain SSH shell on Linux, not the Windsurf
macOS terminal; the `no-terminal-oneline-scripts` crash hazard does not apply.)

## 6. Bring artifacts home + TERMINATE

```sh
# from the Mac
rsync -avz ubuntu@<instance-ip>:~/horus/data/finetune/bakeoff/ ~/Projects/horus/data/finetune/bakeoff/
rsync -avz ubuntu@<instance-ip>:~/horus/data/finetune/gpu-transcripts/ ~/Projects/horus/data/finetune/gpu-transcripts/

aws ec2 terminate-instances --instance-ids <id> --region eu-central-1
aws ec2 describe-instances --instance-ids <id> --region eu-central-1 \
  --query 'Reservations[].Instances[].State.Name'   # expect "shutting-down"/"terminated"
```

## 7. Back on the Mac

1. Score the GPU transcripts: `scripts/finetune_reader_bakeoff.py --reader <winner> --score-only`
2. Reader-selection ADR (per `horus-decision-discipline`) citing both bake-off tables
3. Rebuild the SFT dataset on the winner's transcripts → local LoRA fine-tune → val eval
