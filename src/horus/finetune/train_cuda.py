"""CUDA LoRA SFT for the Arm-B structurer via TRL + PEFT (issue #55, ADR-067/ADR-068).

Why this exists alongside `train.py`
------------------------------------
`train.py` trains through `mlx_vlm`, which is Apple-Silicon-only and, measured on an
M1 Pro 16 GB, could not complete even a 4-example / 4-iteration smoke in acceptable time
(`know-your-hardware`: 7.99 B params 4-bit + grad checkpointing + seq ~3 k saturates the
12.7 GB Metal working set). The full budget is ~600 forward passes, so local training is
not viable and it monopolises the only machine the author works on. Venue moves to the
same rented A10G class already proven for the reader bake-off (ADR-057).

What this file does NOT re-decide
---------------------------------
The data is byte-identical to the MLX path: same sealed split (`split.json`, fingerprints
verified), same dev carve (`carve_dev`), same structuring prompt (loaded from
`configs/arm-b.yaml`, so all arms share one instruction string per ADR-034/038), same
target construction and self-consistency gate (`build_dataset`). Only the executor changes.

Checkpoint selection (ADR-067)
------------------------------
The discipline is delegated to TRL/HF rather than hand-rolled, because
`load_best_model_at_end` + `metric_for_best_model="eval_loss"` + per-epoch eval on the DEV
slice is exactly the pre-registered rule, implemented by a well-tested library. The sealed
validation set is **never** passed to the trainer; it is scored once, afterwards, by
`scripts/finetune_evaluate.py`.

Loss masking
------------
Examples are emitted in TRL's *conversational prompt-completion* form
(``{"prompt": [user…], "completion": [assistant…]}``), for which TRL masks the prompt and
computes loss on the completion only (`completion_only_loss` defaults to True for that
format). This is preferred over `assistant_only_loss`, which additionally depends on
``{% generation %}`` markers being present in the model's chat template.

Refs: ADR-067 (recipe + selection), ADR-068 (venue + matched-stack baseline), issue #55.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from horus.config import EvalConfig
from horus.finetune.config import FinetuneConfig
from horus.finetune.dataset import InvoiceRecord, build_dataset, render_oracle_transcript
from horus.finetune.split import carve_dev
from horus.finetune.train import build_split_records

__all__ = [
    "CudaFinetuneResult",
    "build_prompt_completion_records",
    "language_model_linear_names",
    "resolve_reader_text_fn",
    "run_finetune_cuda",
]

_LOGGER = logging.getLogger(__name__)


@dataclass
class CudaFinetuneResult:
    """Outcome of a CUDA LoRA run (mirrors `FinetuneResult`, plus selection provenance)."""

    adapter_dir: Path
    input_arm: str
    n_train: int
    n_dev: int
    epochs: float
    max_length: int
    target_modules: list[str]
    dev_stems: list[str]
    flagged: list[tuple[str, float]]
    excluded: list[tuple[str, float, float]]
    best_checkpoint: str | None
    log_history: list[dict[str, Any]] = field(default_factory=list)

    def eval_loss_by_epoch(self) -> list[tuple[float, float]]:
        """``(epoch, eval_loss)`` pairs — the curve the checkpoint was selected on."""
        return [
            (float(rec["epoch"]), float(rec["eval_loss"]))
            for rec in self.log_history
            if "eval_loss" in rec and "epoch" in rec
        ]


def resolve_reader_text_fn(input_arm: str) -> Callable[[InvoiceRecord], str] | None:
    """Map ``cfg.input_arm`` to a `build_dataset` text source.

    ``None`` means "use the record's cached reader transcript" (the default path). The
    oracle arm returns the SAME renderer the oracle eval arm uses, so the training and
    evaluation instruments cannot drift apart.
    """
    if input_arm == "reader":
        return None
    if input_arm == "oracle":

        def _oracle(rec: InvoiceRecord) -> str:
            if rec.gt is None:  # unreachable for ready records; guards the type
                raise ValueError(f"{rec.stem} has no ground truth to render an oracle page")
            return render_oracle_transcript(rec.gt)

        return _oracle
    raise ValueError(f"unknown input_arm {input_arm!r} (expected 'reader' or 'oracle')")


def build_prompt_completion_records(examples: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert `build_dataset` output into TRL conversational prompt-completion records.

    `build_dataset` yields ``{"question": <structuring input>, "answer": <target JSON>}``.
    Emitting ``prompt``/``completion`` (rather than a single ``messages`` list) is what makes
    the prompt masking deterministic and independent of chat-template internals.
    """
    return [
        {
            "prompt": [{"role": "user", "content": ex["question"]}],
            "completion": [{"role": "assistant", "content": ex["answer"]}],
        }
        for ex in examples
    ]


#: The conventional LoRA surface for a decoder LLM: attention projections + MLP projections.
#: Deliberately EXCLUDES gemma-4's per-layer-embedding projections (`per_layer_input_gate`,
#: `per_layer_model_projection`, `per_layer_projection`), which are an architectural
#: specialty of this family rather than a standard adaptation target — adapting them would
#: be an unstudied choice smuggled in under "all linears".
STANDARD_LORA_SUFFIXES: frozenset[str] = frozenset(
    {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
)


def language_model_linear_names(model: Any) -> list[str]:
    """Fully-qualified names of the standard LoRA projections inside the text tower.

    PEFT matches `target_modules` as name *suffixes*, so bare names like ``q_proj`` would
    also adapt identically-named projections in the vision and audio towers — gemma-4 has
    `q_proj`-style linears in both. Fully-qualified paths are therefore collected and passed
    verbatim, mirroring the MLX path's restriction of LoRA to the language model.

    The text tower is located by *searching* the module tree rather than assuming it is a
    direct child: on gemma-4 the real path is ``model.language_model``, one level deeper than
    the outer `AutoModelForCausalLM` wrapper.
    """
    import torch.nn as nn

    lm_name, language_model = None, None
    for name, module in model.named_modules():
        if name.endswith("language_model"):
            lm_name, language_model = name, module
            break
    if language_model is None:
        raise ValueError(
            "no `language_model` submodule found anywhere in the module tree — cannot scope "
            "LoRA to the text tower; refusing to adapt the whole model, which would pull in "
            "the vision and audio towers and not be comparable to the MLX run"
        )

    names = [
        f"{lm_name}.{name}"
        for name, module in language_model.named_modules()
        if isinstance(module, nn.Linear) and name.rsplit(".", 1)[-1] in STANDARD_LORA_SUFFIXES
    ]
    if not names:
        raise ValueError(
            f"found no standard LoRA projections under {lm_name!r} "
            f"(looked for {sorted(STANDARD_LORA_SUFFIXES)})"
        )
    return sorted(names)


def run_finetune_cuda(
    cfg: FinetuneConfig,
    *,
    eval_cfg: EvalConfig | None = None,
    limit_train: int | None = None,
    override_epochs: float | None = None,
    override_max_length: int | None = None,
    model_id: str | None = None,
) -> CudaFinetuneResult:
    """Run LoRA SFT on CUDA and save the best-by-dev-loss adapter to ``cfg.adapter_dir``.

    ``model_id`` overrides the HF repo to load. It exists because `cfg.structurer_model`
    (``google/gemma-4-E4B-it``) is mapped to an MLX 4-bit mirror by `COHORT_MANIFEST`, which
    is meaningless here; on CUDA the canonical bf16 repo is loaded directly.
    """
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoProcessor
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise RuntimeError(
            "no CUDA device visible — this trainer is for the rented GPU box. "
            "On Apple Silicon use scripts/finetune_train.py (mlx), though see ADR-068 "
            "for why that path is not viable at full scale."
        )

    prompt = cfg.structuring_prompt()
    train_recs, _sealed_val_recs = build_split_records(cfg)

    # Identical carve to the MLX path (same fn, same seed, same fraction) so the two runs
    # would train on the same invoices. `_sealed_val_recs` is intentionally unused: the
    # sealed set is scored once, later, by scripts/finetune_evaluate.py.
    dev_slice = carve_dev(train_recs, dev_fraction=cfg.dev_fraction, seed=cfg.dev_seed)
    dev_stems = set(dev_slice.dev)
    fit_recs = [r for r in train_recs if r.stem not in dev_stems]
    dev_recs = [r for r in train_recs if r.stem in dev_stems]

    reader_text_fn = resolve_reader_text_fn(cfg.input_arm)
    train_examples, flagged, excluded = build_dataset(
        fit_recs,
        structuring_prompt=prompt,
        eval_cfg=eval_cfg,
        min_self_overall=cfg.min_self_overall,
        reader_text_fn=reader_text_fn,
    )
    dev_examples, _, _ = build_dataset(
        dev_recs,
        structuring_prompt=prompt,
        eval_cfg=eval_cfg,
        min_self_overall=cfg.min_self_overall,
        reader_text_fn=reader_text_fn,
    )
    if not train_examples:
        raise ValueError(
            "no training examples after self-consistency gating — check the split/transcripts"
        )
    if not dev_examples:
        raise ValueError(
            "dev slice is empty after self-consistency gating — nothing to select a "
            "checkpoint on, which would silently reduce this to 'take the last epoch'"
        )
    if limit_train is not None and limit_train > 0:
        train_examples = train_examples[:limit_train]
        print(f"[spike] limiting to {len(train_examples)} train examples", flush=True)

    print(
        f"Input arm: {cfg.input_arm} "
        f"({'cached reader transcripts' if reader_text_fn is None else 'GT-rendered oracle text'})",
        flush=True,
    )
    print(
        f"Dev carve (from TRAIN, seed={cfg.dev_seed}, frac={cfg.dev_fraction}): "
        f"{len(train_examples)} fit / {len(dev_examples)} dev; sealed val untouched",
        flush=True,
    )
    print(f"gating: flagged={len(flagged)} excluded={len(excluded)}", flush=True)

    train_pc = build_prompt_completion_records(train_examples)
    train_ds = Dataset.from_list(train_pc)
    dev_ds = Dataset.from_list(build_prompt_completion_records(dev_examples))

    resolved_model_id = model_id or cfg.structurer_model
    print(f"Loading {resolved_model_id} (bf16) …", flush=True)
    processor = AutoProcessor.from_pretrained(resolved_model_id)
    model = AutoModelForCausalLM.from_pretrained(
        resolved_model_id,
        dtype=torch.bfloat16,
        device_map="auto",
    )
    model.config.use_cache = False  # incompatible with gradient checkpointing

    # Apply Liger explicitly. Passing `use_liger_kernel=True` to SFTConfig alone silently
    # no-opped here (zero log output, memory profile unchanged, still OOM) because the model
    # is instantiated before the trainer sees it. Patching by hand and asserting the result
    # means the config knob cannot quietly mean nothing.
    if cfg.train.use_liger_kernel:
        from liger_kernel.transformers import _apply_liger_kernel_to_instance

        before = type(model).__name__
        _apply_liger_kernel_to_instance(model=model)
        model_type = getattr(model.config, "model_type", "<unknown>")
        patched = any(
            "liger" in type(module).__module__.lower() for _, module in model.named_modules()
        )
        print(
            f"Liger: requested=True model_type={model_type} wrapper={before} "
            f"patched_modules={'YES' if patched else 'NO'}",
            flush=True,
        )
        if not patched:
            raise RuntimeError(
                f"use_liger_kernel=True but no Liger module was installed for model_type "
                f"{model_type!r}. Refusing to continue: the run would silently use the "
                f"unfused loss and OOM at long sequence length. Either set "
                f"use_liger_kernel: false and use a larger GPU (ADR-068's documented "
                f"fallback), or add support for this architecture."
            )

    target_modules = language_model_linear_names(model)
    print(f"LoRA targets: {len(target_modules)} language-model linears", flush=True)

    # `LoraParams.alpha` is a float because the MLX API took one; PEFT types `lora_alpha`
    # as int. Truncating silently would change the alpha/r scaling factor that defines the
    # adapter's effective strength (16.5/8 = 2.0625 vs 16/8 = 2.0), so a fractional alpha
    # is refused rather than quietly rounded.
    if not float(cfg.lora.alpha).is_integer():
        raise ValueError(
            f"lora.alpha={cfg.lora.alpha} is fractional; PEFT takes an integer lora_alpha "
            "and rounding would change the alpha/rank scaling. Use a whole number."
        )
    peft_config = LoraConfig(
        r=cfg.lora.rank,
        lora_alpha=int(cfg.lora.alpha),
        lora_dropout=cfg.lora.dropout,
        target_modules=target_modules,
        bias="none",
        task_type="CAUSAL_LM",
    )

    # Honour the config's documented `max_seq_length: 0 = auto` semantics, mirroring
    # `train._auto_max_seq_length`. Previously this always used the CAP, which both wasted
    # compute and hid how close the real data sits to the ceiling.
    if override_max_length:
        max_length = override_max_length
    elif cfg.train.max_seq_length > 0:
        max_length = cfg.train.max_seq_length
    else:
        tokenizer = processor.tokenizer if hasattr(processor, "tokenizer") else processor
        token_lengths = [
            len(
                tokenizer(
                    tokenizer.apply_chat_template(
                        rec["prompt"] + rec["completion"],
                        tokenize=False,
                        add_generation_prompt=False,
                    )
                )["input_ids"]
            )
            for rec in train_pc
        ]
        longest = max(token_lengths)
        rounded = ((longest + 255) // 256) * 256
        max_length = min(rounded, cfg.train.max_seq_length_cap)
        n_truncated = sum(1 for length in token_lengths if length > max_length)
        print(
            f"auto max_length={max_length} (longest example {longest} tokens, "
            f"cap {cfg.train.max_seq_length_cap})",
            flush=True,
        )
        if n_truncated:
            # Loud, because truncation silently removes the tail of a reader transcript —
            # the model would be trained to produce a full answer from partial input.
            print(
                f"WARNING: {n_truncated}/{len(token_lengths)} examples exceed max_length "
                f"and WILL BE TRUNCATED — their targets no longer match their inputs.",
                flush=True,
            )
    epochs = override_epochs if override_epochs is not None else float(cfg.train.epochs)
    adapter_dir = Path(cfg.adapter_dir)

    args = SFTConfig(
        output_dir=str(adapter_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=cfg.train.batch_size,
        gradient_accumulation_steps=cfg.train.gradient_accumulation_steps,
        learning_rate=cfg.train.learning_rate,
        lr_scheduler_type=cfg.train.lr_schedule,
        warmup_ratio=cfg.train.warmup_ratio,
        max_grad_norm=cfg.train.grad_clip,
        gradient_checkpointing=cfg.train.grad_checkpoint,
        use_liger_kernel=cfg.train.use_liger_kernel,
        activation_offloading=cfg.train.activation_offloading,
        bf16=True,
        max_length=max_length,
        # Asserted, not inferred. The default is None ("auto: True for prompt-completion
        # datasets"), and this one flag decides whether loss is taken over the ~3k-token
        # prompt as well as the answer. Setting it explicitly means a future change to the
        # dataset shape fails loudly instead of silently training on the input.
        completion_only_loss=True,
        seed=cfg.train.seed,
        data_seed=cfg.train.seed,
        logging_steps=cfg.train.steps_per_report,
        # --- ADR-067 checkpoint selection, delegated to HF ---
        eval_strategy="epoch",
        save_strategy="epoch",
        per_device_eval_batch_size=cfg.train.batch_size,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        save_total_limit=None,  # keep every epoch so the curve stays auditable
        report_to=[],
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        processing_class=processor,
        peft_config=peft_config,
    )

    print(
        f"Training: epochs={epochs} batch={cfg.train.batch_size} "
        f"grad_accum={cfg.train.gradient_accumulation_steps} lr={cfg.train.learning_rate} "
        f"schedule={cfg.train.lr_schedule} warmup={cfg.train.warmup_ratio} "
        f"rank={cfg.lora.rank} alpha={cfg.lora.alpha} max_length={max_length}",
        flush=True,
    )
    trainer.train()

    best = getattr(trainer.state, "best_model_checkpoint", None)
    log_history = list(getattr(trainer.state, "log_history", []))

    # `load_best_model_at_end` has already restored the best-by-dev-loss weights, so what
    # gets saved here IS the selected checkpoint — not merely the last epoch.
    trainer.save_model(str(adapter_dir))
    processor.save_pretrained(str(adapter_dir))

    result = CudaFinetuneResult(
        adapter_dir=adapter_dir,
        input_arm=cfg.input_arm,
        n_train=len(train_ds),
        n_dev=len(dev_ds),
        epochs=epochs,
        max_length=max_length,
        target_modules=target_modules,
        dev_stems=sorted(dev_slice.dev),
        flagged=flagged,
        excluded=excluded,
        best_checkpoint=best,
        log_history=log_history,
    )

    # Persist the selection evidence next to the adapter: which epoch won, on what curve,
    # and over which dev stems. Without this the choice is unreproducible after the fact.
    provenance = {
        "adapter_dir": str(adapter_dir),
        "model_id": resolved_model_id,
        "input_arm": cfg.input_arm,
        "selection": {
            "rule": "min eval_loss on the dev slice carved from TRAIN (ADR-067)",
            "best_checkpoint": best,
            "eval_loss_by_epoch": result.eval_loss_by_epoch(),
        },
        "dev_slice": {
            "seed": cfg.dev_seed,
            "fraction": cfg.dev_fraction,
            "n_dev": len(dev_ds),
            "sha256_dev": dev_slice.sha256_dev,
            "stems": sorted(dev_slice.dev),
        },
        "hyperparameters": {
            "epochs": epochs,
            "batch_size": cfg.train.batch_size,
            "gradient_accumulation_steps": cfg.train.gradient_accumulation_steps,
            "learning_rate": cfg.train.learning_rate,
            "lr_schedule": cfg.train.lr_schedule,
            "warmup_ratio": cfg.train.warmup_ratio,
            "lora_rank": cfg.lora.rank,
            "lora_alpha": cfg.lora.alpha,
            "lora_dropout": cfg.lora.dropout,
            "max_length": max_length,
            "seed": cfg.train.seed,
        },
        "n_train": len(train_ds),
        "n_target_modules": len(target_modules),
        "log_history": log_history,
    }
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "horus_training_provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result
