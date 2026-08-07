#!/usr/bin/env bash
# Unattended driver for the ADR-067 2x2 structurer LoRA study on a CUDA box (ADR-068).
#
# Runs, in the only order that is methodologically valid:
#   1. the MATCHED bf16 zero-shot baselines (reader + oracle input)   <- must precede everything
#   2. training of both arms (reader-input, oracle-input)
#   3. the four 2x2 evaluation cells
#
# Step 1 is not optional. The committed 0.8257 baseline is MLX 4-bit; this box is bf16, so a
# fine-tuned-vs-committed delta would conflate the adapter with a quantisation change
# (ADR-068). Every comparison must live inside one stack.
#
# Resume-safe: each step is skipped when its output already exists, so a dropped ssh session
# or a transient failure costs only the step that was in flight. Fails fast otherwise —
# continuing past a broken step would produce a partial grid that looks complete.
#
# Usage (on the instance):
#   nohup bash scripts/gpu/run_lora_2x2.sh > /tmp/lora-2x2.log 2>&1 &
#   tail -f /tmp/lora-2x2.log

set -uo pipefail

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/../.." || exit 1

FT_DIR="data/finetune"
READER_ADAPTER="$FT_DIR/adapter"
ORACLE_ADAPTER="$FT_DIR/adapter-oracle"

banner() {
    echo ""
    echo "==============================================================================="
    echo "== $* "
    echo "==  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "==============================================================================="
    echo ""
}

fail() {
    echo ""
    echo "!!! STEP FAILED: $*"
    echo "!!! Stopping. Nothing downstream is run, so the grid stays obviously incomplete"
    echo "!!! rather than silently partial."
    exit 1
}

# run_eval <out-json> <label> <extra-args...>
run_eval() {
    local out="$1"; shift
    local label="$1"; shift
    if [[ -s "$out" ]]; then
        echo "SKIP (exists): $out"
        return 0
    fi
    banner "EVAL: $label"
    uv run python scripts/finetune_evaluate.py \
        --backend cuda --split val --label "$label" --out "$out" "$@" \
        || fail "eval $label"
}

# run_train <adapter-dir> <config>
run_train() {
    local adapter="$1"; shift
    local config="$1"; shift
    if [[ -s "$adapter/adapter_config.json" ]]; then
        echo "SKIP (exists): $adapter"
        return 0
    fi
    banner "TRAIN: $config"
    uv run python scripts/finetune_train_cuda.py --config "$config" \
        || fail "train $config"
}

banner "GPU + environment"
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader
uv run python -c "import torch, trl, peft; print(f'torch {torch.__version__} / trl {trl.__version__} / peft {peft.__version__}')"

# --- 1. matched bf16 baselines (MANDATORY, before any adapter exists) ------------------
banner "PHASE 1/3 — matched bf16 baselines"
run_eval "$FT_DIR/eval-zeroshot-bf16-val.json" "zero-shot-bf16"
run_eval "$FT_DIR/eval-oracle-bf16-val.json"   "oracle-bf16" --oracle

# --- 2. train both arms ----------------------------------------------------------------
banner "PHASE 2/3 — train both arms"
run_train "$READER_ADAPTER" configs/finetune-structurer.yaml
run_train "$ORACLE_ADAPTER" configs/finetune-structurer-oracle.yaml

# --- 3. the 2x2 grid --------------------------------------------------------------------
banner "PHASE 3/3 — 2x2 evaluation"
run_eval "$FT_DIR/eval-ft-reader-on-reader-val.json" "ft-reader-on-reader" --adapter "$READER_ADAPTER"
run_eval "$FT_DIR/eval-ft-reader-on-oracle-val.json" "ft-reader-on-oracle" --adapter "$READER_ADAPTER" --oracle
run_eval "$FT_DIR/eval-ft-oracle-on-reader-val.json" "ft-oracle-on-reader" --adapter "$ORACLE_ADAPTER"
run_eval "$FT_DIR/eval-ft-oracle-on-oracle-val.json" "ft-oracle-on-oracle" --adapter "$ORACLE_ADAPTER" --oracle

banner "ALL STEPS COMPLETE"
echo "Artifacts to bring home before terminating:"
ls -la "$FT_DIR"/eval-*bf16*.json "$FT_DIR"/eval-ft-*.json 2>/dev/null
echo ""
echo "Adapters + selection provenance:"
ls -la "$READER_ADAPTER/horus_training_provenance.json" "$ORACLE_ADAPTER/horus_training_provenance.json" 2>/dev/null
