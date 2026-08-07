"""Text-only LoRA SFT of the Arm-B structurer via mlx_vlm (issue #55).

Reuses the SAME model the structurer uses at inference (`get_extractor` → the 4-bit gemma4
MLX checkpoint), applies LoRA to the language-model linears, and SFT-trains on the sealed
**train** split's (reader-transcript → JSON) pairs with the loss masked to the assistant
turn (the JSON answer) only. Saves a LoRA adapter dir that `evaluate_structurer` loads via
`apply_lora_layers` — so train-time and eval-time models are byte-identical but for the adapter.

Design facts (verified against mlx_vlm 0.5.0):
  - Items with no images → ``num_images=0`` → text-only chat formatting (the structurer path).
  - ``get_peft_model(model, find_all_linear_names(model.language_model), …)`` = LoRA on the
    language stack only; the base (incl. vision/audio towers) stays frozen.
  - Completion masking uses the FIRST ``<end_of_turn>`` id as the boundary (end of the user
    turn) — for Gemma's template this trains on the model turn + JSON answer only.

Per `horus-config-discipline`, every knob comes from `FinetuneConfig` (the YAML); this module
is logic only. Per `know-your-hardware`, peak memory is reported each step (16 GB ceiling).

Refs: ADR-038 (Arm-B structurer), ADR-034 (no-HARKing held-out split), issue #55.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from horus.config import EvalConfig
from horus.finetune.config import FinetuneConfig
from horus.finetune.dataset import build_dataset, build_records
from horus.finetune.split import carve_dev, load_split
from horus.vlm_extractor import MLXVLMExtractor, get_extractor

__all__ = [
    "FinetuneResult",
    "build_lr_schedule",
    "checkpoint_path",
    "materialize_checkpoint",
    "run_finetune",
]

_LOGGER = logging.getLogger(__name__)


def _noop_set_wired_limit(*_args: object, **_kwargs: object) -> None:
    """No-op stand-in for ``mx.set_wired_limit``.

    ``mlx_vlm.train()`` resets the wired limit to ``max_recommended`` on entry,
    which would undo the deliberate raise made before training starts. Patching
    the symbol with this no-op holds the raised limit for the whole run.
    """


# Fallback assistant-turn token id if <end_of_turn> can't be resolved (mlx_vlm's Qwen default).
_DEFAULT_ASSISTANT_ID = 77091


@dataclass
class FinetuneResult:
    """Outcome of one fine-tune run."""

    adapter_dir: Path
    n_train: int
    n_val: int
    iters: int
    max_seq_length: int
    train_on_completions: bool
    assistant_id: int
    flagged: list[tuple[str, float]]
    excluded: list[tuple[str, float, float]]
    dev_stems: list[str]
    checkpoint_iters: list[int]


def checkpoint_path(adapter_dir: Path | str, iteration: int) -> Path:
    """Path mlx_vlm writes an intermediate checkpoint to (``{it:07d}_adapters.safetensors``)."""
    return Path(adapter_dir) / f"{iteration:07d}_adapters.safetensors"


def materialize_checkpoint(adapter_dir: Path | str, iteration: int, dest: Path | str) -> Path:
    """Lay out one intermediate checkpoint as a directory ``apply_lora_layers`` can load.

    mlx_vlm saves every checkpoint as a SIBLING file (``0000117_adapters.safetensors``, …)
    next to a single shared ``adapter_config.json``, but ``apply_lora_layers`` only ever
    reads ``<dir>/adapters.safetensors``. So the per-epoch checkpoints exist yet cannot be
    evaluated as-is; without this the whole per-epoch selection design is decorative.

    Copies (never moves) the requested checkpoint to ``<dest>/adapters.safetensors`` and the
    shared config to ``<dest>/adapter_config.json``. Returns ``dest``.
    """
    import shutil

    src = checkpoint_path(adapter_dir, iteration)
    if not src.exists():
        available = sorted(p.name for p in Path(adapter_dir).glob("*_adapters.safetensors"))
        raise FileNotFoundError(
            f"no checkpoint at iteration {iteration} ({src}). Available: {available or 'none'}"
        )
    config = Path(adapter_dir) / "adapter_config.json"
    if not config.exists():
        raise FileNotFoundError(
            f"{config} is missing — apply_lora_layers needs it alongside the weights"
        )
    dest_dir = Path(dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / "adapters.safetensors")
    shutil.copy2(config, dest_dir / "adapter_config.json")
    return dest_dir


def build_lr_schedule(
    *,
    learning_rate: float,
    iters: int,
    schedule: str,
    warmup_ratio: float,
    min_ratio: float,
) -> Any:
    """Return an mlx learning-rate schedule (or the bare float for ``constant``).

    Warmup matters more than usual here: the LoRA B matrix starts at zero, so the first
    optimizer steps carry the least informative gradients of the whole run, and this run is
    short enough (~10^2 steps) that a bad first step is a meaningful fraction of it. The
    cosine tail keeps the final epoch from walking away from a good middle.
    """
    import mlx.optimizers as optim

    if schedule == "constant":
        return learning_rate

    warmup_steps = max(1, int(round(iters * warmup_ratio)))
    decay_steps = max(1, iters - warmup_steps)
    warmup = optim.linear_schedule(0.0, learning_rate, warmup_steps)
    decay = optim.cosine_decay(learning_rate, decay_steps, learning_rate * min_ratio)
    return optim.join_schedules([warmup, decay], [warmup_steps])


def _to_messages_item(example: dict[str, str]) -> dict[str, Any]:
    """A text-only SFT item: user = structuring input, assistant = target JSON (no images)."""
    return {
        "messages": [
            {"role": "user", "content": example["question"]},
            {"role": "assistant", "content": example["answer"]},
        ]
    }


def _resolve_turn_end_id(processor: Any) -> int | None:
    """Resolve the turn-END token id — the completion-mask boundary (first occurrence ends
    the user turn, so loss is trained on the assistant turn / JSON answer only).

    gemma-4 uses ``<turn|>`` (id 106); classic Gemma uses ``<end_of_turn>``. We try both and
    reject the ``<unk>`` id (``<end_of_turn>`` resolves to <unk>=3 on the gemma-4 tokenizer).
    """
    tokenizer = getattr(processor, "tokenizer", processor)
    convert = getattr(tokenizer, "convert_tokens_to_ids", None)
    if convert is None:
        return None
    unk = getattr(tokenizer, "unk_token_id", None)
    for token_name in ("<turn|>", "<end_of_turn>"):
        try:
            tid = convert(token_name)
        except Exception:  # noqa: BLE001 — tokenizer variance; try the next candidate
            continue
        if isinstance(tid, int) and tid >= 0 and tid != unk:
            return tid
    return None


def _enable_grad_checkpoint(model: Any) -> int:
    """Checkpoint every decoder layer under ``language_model`` (memory for compute).

    mlx_vlm's own ``train(grad_checkpoint=True)`` only inspects ``model.children()`` for a direct
    ``.layers`` attribute — but gemma-4 nests the decoder as ``language_model.model.layers``, so
    its check silently no-ops and the run OOMs at seq ~3k on 16 GB. ``grad_checkpoint`` patches
    ``type(layer).__call__``, so a single call on any one layer instance checkpoints them all.

    Returns the number of decoder layers found (0 = nothing checkpointed).
    """
    from mlx_vlm.trainer.utils import grad_checkpoint

    language_model = getattr(model, "language_model", None)
    for container in (language_model, getattr(language_model, "model", None)):
        layers = getattr(container, "layers", None) if container is not None else None
        if layers is not None and len(layers) > 0:
            grad_checkpoint(layers[0])  # patches type(layer).__call__ → all layers checkpointed
            return len(layers)
    return 0


def _free_unused_towers(model: Any) -> list[str]:
    """Release gemma-4's vision + audio towers (unused in a text-only SFT) to reclaim memory.

    The text-only forward (pixel_values=None, no audio) never invokes them: in
    ``gemma4.py::get_input_embeddings`` the vision ``_scatter`` returns early when
    ``pixel_values is None``, and the audio block is guarded by ``self.audio_tower is not None``.
    Setting the attributes to None drops their multi-GB un-quantized weights from the module
    tree (mlx parameter traversal skips non-Module/array attributes) while the ``is not None``
    guard then cleanly skips audio. This is what brings a 7.5B-4bit LoRA step under the 12.7 GB
    Metal working-set cap on a 16 GB M1 Pro (know-your-hardware).
    """
    import gc

    import mlx.core as mx

    freed = []
    for attr in ("vision_tower", "embed_vision", "audio_tower", "embed_audio"):
        if getattr(model, attr, None) is not None:
            setattr(model, attr, None)
            freed.append(attr)
    gc.collect()
    mx.clear_cache()
    return freed


def build_split_records(cfg: FinetuneConfig) -> tuple[list, list]:
    """Resolve the sealed train/val splits into `InvoiceRecord` lists (order = split order)."""
    records = build_records(
        Path(cfg.corpus_root),
        transcript_dir=Path(cfg.transcript_dir),
        reader_model=cfg.reader_model,
    )
    split = load_split(Path(cfg.split_path))
    by_stem = {r.stem: r for r in records}
    train_recs = [by_stem[s] for s in split.train if s in by_stem]
    val_recs = [by_stem[s] for s in split.val if s in by_stem]
    return train_recs, val_recs


def _auto_max_seq_length(dataset: Any, cap: int) -> tuple[int, int, int]:
    """Pick max_seq_length covering the longest example (rounded to mlx's pad grid, capped).

    Returns ``(max_seq_length, longest_example_tokens, n_truncated)``.
    """
    lengths = [
        int(np.array(dataset[i]["input_ids"]).reshape(-1).shape[0]) for i in range(len(dataset))
    ]
    longest = max(lengths)
    pad = 32
    rounded = ((longest + pad - 1) // pad) * pad + 1
    max_seq_length = min(rounded, cap)
    n_truncated = sum(1 for length in lengths if length > max_seq_length)
    return max_seq_length, longest, n_truncated


def run_finetune(
    cfg: FinetuneConfig,
    *,
    eval_cfg: EvalConfig | None = None,
    limit_train: int | None = None,
    override_iters: int | None = None,
    override_max_seq: int | None = None,
    skip_val: bool = False,
) -> FinetuneResult:
    """Run LoRA SFT over the sealed train split and save the adapter to ``cfg.adapter_dir``.

    ``limit_train`` / ``override_iters`` are debug knobs (a fast path-validation spike): cap the
    number of training pairs and/or force a small iteration count. Both default to the full run.
    """
    import mlx.core as mx
    import mlx.optimizers as optim
    from mlx_vlm.trainer.datasets import VisionDataset
    from mlx_vlm.trainer.sft_trainer import TrainingArgs, train
    from mlx_vlm.trainer.utils import find_all_linear_names, get_peft_model, save_adapter

    mx.random.seed(cfg.train.seed)
    np.random.seed(cfg.train.seed)

    prompt = cfg.structuring_prompt()
    train_recs, _sealed_val_recs = build_split_records(cfg)

    # The in-training validation signal comes from a dev slice carved out of TRAIN, never
    # from the sealed val. Before this, `val_dataset` was the sealed 29 with
    # `val_batches=-1`, so every run computed loss over the exact set the headline number
    # is reported on. That is a look at the answer sheet even when nothing is selected on
    # it, and it makes per-epoch checkpoint selection impossible to do honestly.
    # `_sealed_val_recs` is deliberately unused here; the sealed set is touched once, by
    # `finetune_evaluate.py`, after the epoch has already been chosen.
    dev_slice = carve_dev(train_recs, dev_fraction=cfg.dev_fraction, seed=cfg.dev_seed)
    dev_stems = set(dev_slice.dev)
    fit_recs = [r for r in train_recs if r.stem not in dev_stems]
    dev_recs = [r for r in train_recs if r.stem in dev_stems]
    print(
        f"Dev carve (from TRAIN, seed={cfg.dev_seed}, frac={cfg.dev_fraction}): "
        f"{len(fit_recs)} fit / {len(dev_recs)} dev; sealed val untouched",
        flush=True,
    )

    train_examples, flagged, excluded = build_dataset(
        fit_recs,
        structuring_prompt=prompt,
        eval_cfg=eval_cfg,
        min_self_overall=cfg.min_self_overall,
    )
    val_examples, _, _ = build_dataset(
        dev_recs,
        structuring_prompt=prompt,
        eval_cfg=eval_cfg,
        min_self_overall=cfg.min_self_overall,
    )
    if not train_examples:
        raise ValueError(
            "no training examples after self-consistency gating — check the split/transcripts"
        )
    if limit_train is not None and limit_train > 0:
        train_examples = train_examples[:limit_train]
        print(f"[spike] limiting to {len(train_examples)} train examples", flush=True)
    print(
        f"Fine-tune dataset: {len(train_examples)} train / {len(val_examples)} val "
        f"(flagged={len(flagged)} excluded={len(excluded)})",
        flush=True,
    )

    extractor = get_extractor(cfg.structurer_model)
    if not isinstance(extractor, MLXVLMExtractor):
        raise ValueError(f"structurer {cfg.structurer_model!r} must be an MLX model for training.")
    extractor.load()
    model, processor = extractor._model, extractor._processor
    config = model.config.__dict__

    train_ds = VisionDataset([_to_messages_item(e) for e in train_examples], config, processor)
    val_items = [] if skip_val else [_to_messages_item(e) for e in val_examples]
    val_ds = VisionDataset(val_items, config, processor) if val_items else None

    if override_max_seq is not None and override_max_seq > 0:
        max_seq_length = override_max_seq
        print(f"max_seq_length override={max_seq_length}", flush=True)
    elif cfg.train.max_seq_length > 0:
        max_seq_length = cfg.train.max_seq_length
    else:
        max_seq_length, longest, n_truncated = _auto_max_seq_length(
            train_ds, cfg.train.max_seq_length_cap
        )
        print(
            f"max_seq_length auto={max_seq_length} (longest example={longest} tokens, "
            f"cap={cfg.train.max_seq_length_cap}, truncated={n_truncated})",
            flush=True,
        )
        if n_truncated:
            _LOGGER.warning(
                "%d training example(s) exceed max_seq_length=%d and will be truncated; the "
                "JSON answer at the end may be lost. Raise max_seq_length_cap if memory allows.",
                n_truncated,
                max_seq_length,
            )

    modules = find_all_linear_names(model.language_model)
    print(f"LoRA targets (language_model linears): {sorted(modules)}", flush=True)
    model = get_peft_model(
        model,
        modules,
        rank=cfg.lora.rank,
        alpha=cfg.lora.alpha,
        dropout=cfg.lora.dropout,
        verbose=True,
    )

    if cfg.train.grad_checkpoint:
        n_ckpt = _enable_grad_checkpoint(model)
        if n_ckpt:
            print(f"grad-checkpointing ON for {n_ckpt} decoder layers", flush=True)
        else:
            _LOGGER.warning("grad_checkpoint requested but no decoder layers found to checkpoint")

    train_on_completions = cfg.train.train_on_completions
    assistant_id = _DEFAULT_ASSISTANT_ID
    if train_on_completions:
        turn_end = _resolve_turn_end_id(processor)
        if turn_end is None:
            _LOGGER.warning("could not resolve a turn-end token id — disabling completion masking")
            train_on_completions = False
        else:
            assistant_id = turn_end
            print(f"completion-masking ON; boundary=turn-end token id={assistant_id}", flush=True)

    iters_per_epoch = max(1, len(train_ds) // cfg.train.batch_size)
    iters = override_iters if override_iters else iters_per_epoch * cfg.train.epochs
    if cfg.train.steps_per_save:
        steps_per_save = cfg.train.steps_per_save
    elif cfg.train.checkpoint_every_epoch:
        steps_per_save = iters_per_epoch
    else:
        steps_per_save = iters + 1  # > iters ⇒ only the final save fires
    # mlx_vlm writes `<parent>/{it:07d}_adapters.safetensors` alongside the rolling
    # `adapters.safetensors` at every save, which is what makes per-epoch selection possible.
    checkpoint_iters = [it for it in range(1, iters + 1) if it % steps_per_save == 0]
    adapter_dir = Path(cfg.adapter_dir)
    adapter_file = adapter_dir / "adapters.safetensors"

    args = TrainingArgs(
        batch_size=cfg.train.batch_size,
        iters=iters,
        steps_per_report=cfg.train.steps_per_report,
        # Dev loss every epoch (not just at the endpoints) — with ~10^2 optimizer steps the
        # overfitting turn, if it comes, happens between epochs and is invisible at endpoints.
        steps_per_eval=max(1, min(iters_per_epoch, iters)),
        steps_per_save=steps_per_save,
        val_batches=-1,  # entire dev slice ⇒ a stable, low-variance dev-loss curve
        max_seq_length=max_seq_length,
        adapter_file=str(adapter_file),
        grad_checkpoint=False,  # applied manually above (mlx_vlm's misses gemma-4's nested layers)
        learning_rate=cfg.train.learning_rate,
        grad_clip=cfg.train.grad_clip,
        gradient_accumulation_steps=cfg.train.gradient_accumulation_steps,
    )
    lr_schedule = build_lr_schedule(
        learning_rate=cfg.train.learning_rate,
        iters=iters,
        schedule=cfg.train.lr_schedule,
        warmup_ratio=cfg.train.warmup_ratio,
        min_ratio=cfg.train.lr_min_ratio,
    )
    optimizer = optim.Adam(learning_rate=lr_schedule)

    if cfg.train.free_vision_audio:
        freed = _free_unused_towers(model)
        if freed:
            print(f"freed unused towers (text-only SFT): {', '.join(freed)}", flush=True)

    if mx.metal.is_available():
        info = mx.metal.device_info()
        rec = int(info.get("max_recommended_working_set_size", 0)) / 1e9
        mem = int(info.get("memory_size", 0)) / 1e9
        print(f"Metal: memory={mem:.1f} GB, max_recommended_working_set={rec:.1f} GB", flush=True)
        if cfg.train.wired_limit_gb > 0:
            target_gb = cfg.train.wired_limit_gb
            try:
                mx.set_wired_limit(int(target_gb * 1024**3))
                # Hold it: mlx_vlm's train() resets the limit to max_recommended on
                # entry. Patch through an Any-typed alias so this type-checks the
                # same way whether mlx is installed and typed (dev Mac) or absent
                # and therefore untyped (Linux CI) -- a `type: ignore` here would be
                # required on the Mac and flagged as unused on CI.
                mx_module: Any = mx
                mx_module.set_wired_limit = _noop_set_wired_limit
                print(f"raised wired limit -> {target_gb:.1f} GB (held through train)", flush=True)
            except Exception as exc:  # noqa: BLE001 — surface, don't crash
                _LOGGER.warning("could not raise wired limit to %.1f GB: %s", target_gb, exc)

    print(
        f"Training: iters={iters} ({iters_per_epoch}/epoch × {cfg.train.epochs}) "
        f"batch={cfg.train.batch_size} grad_accum={cfg.train.gradient_accumulation_steps} "
        f"lr={cfg.train.learning_rate} schedule={cfg.train.lr_schedule} "
        f"warmup={cfg.train.warmup_ratio} rank={cfg.lora.rank} alpha={cfg.lora.alpha} "
        f"-> {adapter_file}",
        flush=True,
    )
    if checkpoint_iters:
        print(f"Per-epoch checkpoints at iters: {checkpoint_iters}", flush=True)
    train(
        model=model,
        optimizer=optimizer,
        train_dataset=train_ds,
        val_dataset=val_ds,
        args=args,
        train_on_completions=train_on_completions,
        assistant_id=assistant_id,
    )
    save_adapter(model, str(adapter_file))
    print(
        f"Saved LoRA adapter -> {adapter_dir} (adapters.safetensors + adapter_config.json)",
        flush=True,
    )

    return FinetuneResult(
        adapter_dir=adapter_dir,
        n_train=len(train_ds),
        n_val=len(val_ds) if val_ds is not None else 0,
        iters=iters,
        max_seq_length=max_seq_length,
        train_on_completions=train_on_completions,
        assistant_id=assistant_id,
        flagged=flagged,
        excluded=excluded,
        dev_stems=sorted(dev_slice.dev),
        checkpoint_iters=checkpoint_iters,
    )
