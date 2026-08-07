# Rented-GPU runbook — reader bake-off, transcript regeneration, held-out transcription (issues #55, #114)

Purpose: the M1 Pro 16 GB ceiling disqualified every full-precision reader candidate
locally (35 GiB Metal buffers, 4-bit German-text corruption, 49 min/page bf16 — see the
`feat(finetune): reader bake-off` commit). This runbook runs the bake-off at full
precision on a rented CUDA box, regenerates the 146 structurer-training transcripts with
the winning reader, and brings the artifacts home. **Training and final eval stay on the
M1** (the mlx_vlm LoRA trainer is Apple-only by design — matched train/serve precision).

Budget approved: ≲ $15 (< 6 GPU-hours on-demand). **Terminate the instance when done —
step 6 is not optional.**

> **Provider status (2026-08-01, supersedes 2026-07-31)**: the AWS quota appeal was
> **APPROVED** on case 178548148400462 ("Running On-Demand G and VT instances" raised to
> 4 vCPUs in eu-central-1 Frankfurt). **Plan of record is §1A (AWS g5.xlarge, A10G 24 GB)**
> again. §1B (RunPod) is retained as the fallback path in case AWS capacity/quota regresses.
> Prior note (2026-07-31, superseded): AWS had denied the increase twice under the
> fresh-account ramp policy, which made §1B the interim plan of record.

## 1A. Launch via AWS console (plan of record)

Target: `g5.xlarge` (A10G 24 GB), region `eu-central-1` (Frankfurt), on-demand ≈ $1.01/hr
(spot ≈ $0.30–0.45/hr also works — every pass is resumable — but on-demand is simpler).

### 1a. One-time pre-flight: vCPU quota for G instances

Fresh/lightly-used AWS accounts often have a **0-vCPU quota for G instances** — the launch
fails with `VcpuLimitExceeded` even though everything else is right. Check BEFORE launching:

1. Console → search **"Service Quotas"** → **AWS services** → **Amazon EC2**
2. Search the quota list for **"Running On-Demand G and VT instances"**
3. If **Applied account-level quota value < 4** → **Request increase at account level** → enter **4** → submit.
   Approval is usually quick for small values; you get an email.

### 1b. Launch wizard

1. Console → top-right region selector → **Europe (Frankfurt) eu-central-1**
2. **EC2** → **Instances** → **Launch instances** (orange button)
3. **Name**: `horus-bakeoff`
4. **Application and OS Images (AMI)** → search box: type
   **`Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)`** → **Quickstart AMIs** /
   **AWS Marketplace AMIs** tab → select it (publisher: Amazon Web Services, free AMI —
   NVIDIA driver + CUDA preinstalled; do NOT pick a "PyTorch" flavor, `setup.sh` installs deps)
5. **Instance type** → type `g5.xlarge` → select (4 vCPU / 16 GiB / 1×A10G 24 GB)
6. **Key pair** → **Create new key pair** → name `horus-gpu`, type **ED25519**, format **.pem**
   → **Create** (downloads `horus-gpu.pem`). Then on the Mac:
   `mv ~/Downloads/horus-gpu.pem ~/.ssh/ && chmod 400 ~/.ssh/horus-gpu.pem`
7. **Network settings** → keep default VPC/subnet; **Auto-assign public IP: Enable**;
   **Create security group** → check **Allow SSH traffic from** → dropdown: **My IP**
8. **Configure storage** → change to **200** GiB, type **gp3**
   (HF checkpoints: olmOCR-2-7B ≈16 GB, Qwen3-VL-4B ≈9 GB, MinerU ≈3 GB each)
9. (Optional, spot) **Advanced details** → **Purchasing option** → tick **Request Spot Instances**
10. Right panel **Summary** → **Number of instances: 1** → **Launch instance**
11. Click the instance id → wait for **Instance state: Running** + **Status checks: 2/2 passed**
    (~2 min) → copy the **Public IPv4 address** — that's `<instance-ip>` everywhere below
12. First connection test from the Mac:
    `ssh -i ~/.ssh/horus-gpu.pem ubuntu@<instance-ip>` → accept the host key → `nvidia-smi`
    must show **A10G**. Exit.

**Billing note**: the meter runs from launch until *terminate* (a *stopped* instance still
bills the 200 GB disk). Step 6 (terminate) is not optional.

All `ssh`/`rsync` commands below need `-i ~/.ssh/horus-gpu.pem` — or add once to `~/.ssh/config`:

```
Host horus-gpu
  HostName <instance-ip>
  User ubuntu
  IdentityFile ~/.ssh/horus-gpu.pem
```

then `ssh horus-gpu` / `rsync … horus-gpu:~/horus/` work without flags.

## 1B. Launch via RunPod (fallback — retained for reference)

Pods are Docker containers with the NVIDIA driver ready; you are `root` inside. Per-second
billing; ≈ $0.35–0.44/hr for an A40 48 GB → the full job costs < $5 of the ≤ $15 budget.

### Console steps (user)

1. <https://runpod.io> → sign up → **Billing** → load **$10** credit (card; minimum top-up)
2. **Settings → SSH Keys** → paste your public key (`cat ~/.ssh/id_ed25519.pub`; if none
   exists first run `ssh-keygen -t ed25519`). MUST happen **before** deploying the pod.
3. **Pods → Deploy**:
   - **GPU**: `A40` (48 GB) — fallback `RTX A6000` (48 GB) if A40 shows no availability
   - **Cloud type**: Secure Cloud (never preempted; community saves cents but can reclaim)
   - **Datacenter/region**: any **EU** location (e.g. EU-SE, EU-NL, EU-RO)
   - **Template**: any *RunPod PyTorch 2.x* template (base CUDA Ubuntu also fine —
     `setup.sh` installs everything via uv)
   - **Edit template**: Container disk **30 GB**; **Volume 250 GB** mounted at `/workspace`
     (checkpoints + corpus + transcripts live here; survives pod restarts)
   - Pricing: **On-Demand** → **Deploy**
4. Pod page → **Connect** → copy the **"SSH over exposed TCP"** command
   (`ssh root@<pod-ip> -p <port> -i ~/.ssh/id_ed25519`). If only the proxy command is
   shown, Edit Pod → **Expose TCP Ports** → add `22` → restart. The proxy (`ssh.runpod.io`)
   does NOT support rsync — the exposed-TCP endpoint is required.
5. Test: ssh in → `nvidia-smi` must show the A40. Exit. Give Cascade `<pod-ip>` + `<port>`.

### `~/.ssh/config` alias (so §2–§6 work verbatim)

```
Host horus-gpu
  HostName <pod-ip>
  Port <port>
  User root
  IdentityFile ~/.ssh/id_ed25519
```

### One-time pod prep (from the Mac, before §2)

```sh
ssh horus-gpu 'command -v rsync >/dev/null || (apt-get update -qq && apt-get install -y -qq rsync)'
ssh horus-gpu 'mkdir -p /workspace/horus && ln -sfn /workspace/horus /root/horus'
```

(The symlink keeps every `~/horus` path in §2–§6 valid while the bytes live on the
250 GB `/workspace` volume. `setup.sh` additionally redirects `HF_HOME` to
`/workspace/hf` when it detects a RunPod volume, so model checkpoints land there too.)

**Terminate** (RunPod flavor of §6): console → pod → **Terminate** (deletes container +
pod volume; billing stops). Verify the Pods list is empty afterwards.

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

> **macOS `rsync --relative` gotcha (hit 2026-08-04)**: the rsync shipped with macOS
> ignores the `./` pivot in `--relative` sources and reproduces the **full absolute
> path** on the remote, so the block above silently lands at
> `~/horus/Users/<you>/Projects/horus/data/…` rather than `~/horus/data/…` — while
> still reporting a successful byte count. It also lacks `--info=stats1` (use
> `--stats`). Either verify the destination after syncing, or drop `--relative` and
> give each source an explicit destination, as in §2b below.

### 2b. Held-out Belege set (issue #114) — replaces the corpus block above

The held-out run needs only `data/self-collected` (39 real invoices + hand-authored
GT). The synthetic corpus and the sealed split are irrelevant to it, so skip them —
`setup.sh`'s data check accepts EITHER dataset and fails only when neither arrived.

```sh
rsync -az ~/Projects/horus/data/self-collected/index.json horus-gpu:~/horus/data/self-collected/
rsync -az ~/Projects/horus/data/self-collected/gt/      horus-gpu:~/horus/data/self-collected/gt/
rsync -az ~/Projects/horus/data/self-collected/german/  horus-gpu:~/horus/data/self-collected/german/
rsync -az ~/Projects/horus/data/self-collected/english/ horus-gpu:~/horus/data/self-collected/english/
```

Do NOT sync `_pagecache` / `_text` / `_drafts` — derived, and the box re-rasterizes.

This uploads REAL invoices to a rented box, which is acceptable only because the
instance is single-tenant, EU-region, has `DeleteOnTermination=true` on its root
volume, and is terminated at the end of the session (§6). Nothing private is
committed: `data/self-collected/` is git-ignored in full (ADR-040).

## 3. Bootstrap (on the instance)

```sh
ssh ubuntu@<instance-ip>
cd ~/horus && bash scripts/gpu/setup.sh
```

> **LD_LIBRARY_PATH gotcha (hit 2026-08-02, AWS DL Base AMI)**: the AMI exports
> `LD_LIBRARY_PATH=/usr/local/cuda/lib64:…` (system CUDA 13.2). Those libs SHADOW the
> pip-provided `nvidia-*` wheels torch links against (RUNPATH loses to
> LD_LIBRARY_PATH), producing `Invalid handle. Cannot load symbol cublasLtGetVersion`
> + SIGABRT at the first cuBLAS call — while `torch.cuda.is_available()` still passes
> (driver-only check). Fix: prefix every `uv run` with an empty override, e.g.
> `ssh horus-gpu 'cd ~/horus && LD_LIBRARY_PATH= PATH=$HOME/.local/bin:$PATH uv run python …'`
> (also note: `uv` lands in `~/.local/bin`, which non-interactive ssh shells don't have
> on PATH).

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
uv run python scripts/gpu/regen_transcripts.py --winner <model-id-from-step-4>
```

(Single-line — safe to drive over `ssh` from the Windsurf terminal, unlike the heredoc
this replaced. Resume-safe: re-running skips already-transcribed stems.)

## 5B. Held-out Belege transcription (issue #114) — alternative to §4/§5

Transcribes the 39 real invoices at bf16 native resolution with the canonical reader.
The local M1 path applies the manifest `max_pixels` cap (≈150 DPI effective on an A4
page), so a local run cannot produce comparable transcripts — that cap is the entire
reason this step belongs on CUDA rather than on the Mac.

```sh
LD_LIBRARY_PATH= PATH=$HOME/.local/bin:$PATH uv run python scripts/transcribe_heldout.py --force-transformers
```

Resume-safe (skips ids that already have a transcript); `--limit N` and `--stems <id>`
narrow the run; `--rasterize-only` renders page images without loading a model (the
LLM-judge pass consumes those). Output lands at
`data/self-collected/_transcripts/<reader-slug>__<id>.txt`, named by sanitized id only.

Observed 2026-08-04 (A10G 23 GB, `Qwen/Qwen3-VL-4B-Instruct` bf16): 39 invoices /
58 pages, **0 errors**, including a ~9 GB checkpoint fetch; ~16 min total instance
lifetime ≈ $0.45.

## 5C. Structurer LoRA fine-tune (issue #55, ADR-067 + ADR-068)

Why here and not on the Mac: a 4-example / 4-iteration path-validation smoke ran long
enough to be cancelled on the M1 Pro 16 GB, against a real budget of ~600 forward passes
(ADR-068). `mlx-vlm` is Apple-only, so this uses TRL + PEFT instead.

### Step 0 — smoke the path first (~2 min)

Never start a multi-hour run on never-executed code:

```sh
uv run python scripts/finetune_train_cuda.py --limit-train 4 --epochs 1 --max-length 4096
```

Expect: dev carve printed, LoRA target count printed, a dev-loss line, and an adapter at
`data/finetune/adapter/`. **The smoke's adapter is meaningless** — delete it before the
real run so it cannot be mistaken for a result.

### Step 1 — the matched bf16 baseline (MANDATORY before any adapter number)

The committed `0.8257` is MLX **4-bit** on Apple Silicon. This box runs **bf16**. A
`finetuned_bf16 − zeroshot_4bit` delta measures the adapter *plus* a quantisation change
(ADR-068). Re-measure first:

```sh
uv run python scripts/finetune_evaluate.py --backend cuda --split val --label zero-shot-bf16 --out data/finetune/eval-zeroshot-bf16-val.json
uv run python scripts/finetune_evaluate.py --backend cuda --split val --oracle --label oracle-bf16 --out data/finetune/eval-oracle-bf16-val.json
```

### Step 2 — train both arms (ADR-067's 2×2)

```sh
uv run python scripts/finetune_train_cuda.py --config configs/finetune-structurer.yaml
uv run python scripts/finetune_train_cuda.py --config configs/finetune-structurer-oracle.yaml
```

Each prints the per-epoch dev-loss curve and marks the selected epoch. Selection is on the
**dev slice carved from TRAIN**, never on the sealed 29. Provenance (chosen epoch, full
curve, dev stem list + hash) is written to
`<adapter_dir>/horus_training_provenance.json`.

The oracle-arm adapter is an **instrument, not a product** — it is trained on text no real
document produces and must never be reported as a deliverable.

### Step 3 — the 2×2 evaluation

Sealed val is scored **once per cell**. No re-picking an epoch after seeing these numbers.

```sh
# reader-trained adapter
uv run python scripts/finetune_evaluate.py --backend cuda --split val --adapter data/finetune/adapter --label ft-reader-on-reader --out data/finetune/eval-ft-reader-on-reader-val.json
uv run python scripts/finetune_evaluate.py --backend cuda --split val --adapter data/finetune/adapter --oracle --label ft-reader-on-oracle --out data/finetune/eval-ft-reader-on-oracle-val.json

# oracle-trained adapter (instrument)
uv run python scripts/finetune_evaluate.py --backend cuda --split val --adapter data/finetune/adapter-oracle --label ft-oracle-on-reader --out data/finetune/eval-ft-oracle-on-reader-val.json
uv run python scripts/finetune_evaluate.py --backend cuda --split val --adapter data/finetune/adapter-oracle --oracle --label ft-oracle-on-oracle --out data/finetune/eval-ft-oracle-on-oracle-val.json
```

Reading the grid (ADR-067): `ft-reader-on-reader` is the only deployable number;
`ft-oracle-on-reader` tests whether schema-learning transfers to noisy text;
`ft-reader-on-oracle` tests whether noise-training cost clean accuracy;
`ft-oracle-on-oracle` measures headroom above the 0.9719 clean ceiling.

## 6. Bring artifacts home + TERMINATE

```sh
# from the Mac
rsync -avz ubuntu@<instance-ip>:~/horus/data/finetune/bakeoff/ ~/Projects/horus/data/finetune/bakeoff/
rsync -avz ubuntu@<instance-ip>:~/horus/data/finetune/gpu-transcripts/ ~/Projects/horus/data/finetune/gpu-transcripts/

# held-out Belege transcripts (§5B) — private, stays in the git-ignored tree
rsync -az horus-gpu:~/horus/data/self-collected/_transcripts/ ~/Projects/horus/data/self-collected/_transcripts/

# fine-tune (§5C): both adapters + their selection provenance + the 6 eval reports.
# The provenance JSONs are what make the chosen epoch auditable after the box is gone,
# so bring them home BEFORE terminating.
rsync -avz ubuntu@<instance-ip>:~/horus/data/finetune/adapter/ ~/Projects/horus/data/finetune/adapter/
rsync -avz ubuntu@<instance-ip>:~/horus/data/finetune/adapter-oracle/ ~/Projects/horus/data/finetune/adapter-oracle/
rsync -avz --include='eval-*bf16*.json' --include='eval-ft-*.json' --exclude='*' ubuntu@<instance-ip>:~/horus/data/finetune/ ~/Projects/horus/data/finetune/
```

**Verify the artifacts are home BEFORE terminating** — the root volume is destroyed
with the instance.

(With the ssh alias from §1A/§1B, replace `ubuntu@<instance-ip>` with `horus-gpu`.)

- **AWS** (plan of record): console → instance → **Terminate instance** (NOT stop — a
  stopped instance still bills the 200 GB disk), or from the Mac:

```sh
aws ec2 terminate-instances --instance-ids <id> --region eu-central-1
aws ec2 describe-instances --instance-ids <id> --region eu-central-1 \
  --query 'Reservations[].Instances[].State.Name'   # expect "shutting-down"/"terminated"
```

- **RunPod** (only if §1B was used): console → pod → **Terminate**; verify the Pods list
  is empty (billing stops).

## 7. Back on the Mac

1. Score the GPU transcripts: `scripts/finetune_reader_bakeoff.py --reader <winner> --score-only`
2. Reader-selection ADR (per `horus-decision-discipline`) citing both bake-off tables
3. Rebuild the SFT dataset on the winner's transcripts → local LoRA fine-tune → val eval
