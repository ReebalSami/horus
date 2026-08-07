"""Pydantic config for the structurer LoRA fine-tune (issue #55, `horus-config-discipline`).

ALL fine-tune knobs (LoRA rank/alpha/dropout, learning rate, batch/accumulation, epochs,
sequence length, completion-masking, seed) live in a YAML (`configs/finetune-structurer.yaml`)
validated by `FinetuneConfig` at boot — fails fast before any model loads.

The *structuring prompt* — the controlled variable that must be byte-identical across the
zero-shot baseline, the training targets, and the fine-tuned eval — is NOT duplicated here. It
is loaded from its canonical home (`configs/arm-b.yaml`'s `cohort.prompt_template_override`) via
`load_structuring_prompt`, so all three passes provably share one string ("matched-precision").

Refs: ADR-038 (Arm-B structurer prompt), `horus-config-discipline`; plan
``~/.windsurf/plans/horus-finetune-structurer-55a1c3.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

__all__ = ["FinetuneConfig", "LoraParams", "TrainParams", "load_structuring_prompt"]


class LoraParams(BaseModel):
    """LoRA adapter hyperparameters (applied to the language-model linears only)."""

    model_config = {"extra": "forbid"}

    rank: int = Field(default=8, ge=1)
    alpha: float = Field(default=16.0, gt=0)
    dropout: float = Field(default=0.05, ge=0.0, le=1.0)


class TrainParams(BaseModel):
    """SFT loop hyperparameters consumed by the mlx_vlm trainer."""

    model_config = {"extra": "forbid"}

    learning_rate: float = Field(default=1e-4, gt=0)
    batch_size: int = Field(default=1, ge=1)
    gradient_accumulation_steps: int = Field(default=8, ge=1)
    epochs: int = Field(default=4, ge=1)
    # 0 → auto-pick from the longest example (rounded up, capped at max_seq_length_cap).
    max_seq_length: int = Field(default=0, ge=0)
    max_seq_length_cap: int = Field(default=8192, ge=256)
    train_on_completions: bool = True
    grad_clip: float = Field(default=1.0, gt=0)
    grad_checkpoint: bool = False  # trade compute for memory (M1 Pro 16 GB safety valve)
    # Release gemma-4's vision + audio towers before a TEXT-ONLY SFT. They are never
    # invoked when pixel_values=None (verified in gemma4.py get_input_embeddings), so
    # dropping their multi-GB un-quantized weights reclaims the headroom a 7.5B-4bit
    # LoRA step needs under the 12.7 GB Metal cap. Disable only if training multimodally.
    free_vision_audio: bool = True
    # Raise the Metal wired-memory limit above mlx's conservative max_recommended
    # (~2/3 RAM). 0 = leave mlx's default. On a 16 GB M1 Pro, ~13–14 is the headroom
    # that lets a 7.5B-4bit LoRA step fit; too high starves the OS (know-your-hardware).
    wired_limit_gb: float = Field(default=0.0, ge=0.0)
    seed: int = 42
    steps_per_report: int = Field(default=10, ge=1)
    # 0 → save only the final adapter (no intermediate checkpoints).
    steps_per_save: int = Field(default=0, ge=0)
    # Constant LR is what mlx_vlm's example uses, but every current small-data LoRA
    # recommendation pairs a cosine decay with a short warmup: the first few steps of a
    # freshly-initialised adapter are the least trustworthy gradients in the run, and
    # decaying the tail is what stops the last epoch from undoing the good middle.
    lr_schedule: Literal["constant", "cosine"] = "cosine"
    # Fraction of total iters spent warming up from 0 to `learning_rate`.
    warmup_ratio: float = Field(default=0.03, ge=0.0, lt=0.5)
    # Floor for the cosine decay, as a fraction of `learning_rate`.
    lr_min_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    # Save a checkpoint every epoch so a non-overfit one can be CHOSEN rather than
    # assumed. With 117 training invoices the epoch count dominates the outcome, and
    # keeping only the final adapter makes that choice unavailable after the fact.
    checkpoint_every_epoch: bool = True


class FinetuneConfig(BaseModel):
    """Top-level fine-tune experiment config (Pydantic-validated at boot)."""

    model_config = {"extra": "forbid"}

    structurer_model: str = "google/gemma-4-E4B-it"
    structuring_prompt_config: str = "configs/arm-b.yaml"
    corpus_root: str = "data/raw/german/zugferd-corpus"
    transcript_dir: str = "docs/sources/transcripts-multipage"
    # ADR-057's canonical reader. This default was left at the superseded
    # granite-258M long after the lineage switched, so a bare `FinetuneConfig()`
    # silently selected the wrong transcripts — it mis-measured one prompt-audit run
    # before the YAML was loaded explicitly (ADR-058 finding 4). Every current call
    # site passes YAML, so aligning the default changes no behaviour today; it just
    # stops being a trap. Keep in step with configs/finetune-structurer.yaml.
    reader_model: str = "Qwen/Qwen3-VL-4B-Instruct"
    split_path: str = "data/finetune/split.json"
    adapter_dir: str = "data/finetune/adapter"
    # Which text the structurer is trained ON (ADR-067 2x2 attribution design):
    #   "reader" - cached Qwen3-VL-4B transcripts; the deployable adapter.
    #   "oracle" - GT-rendered perfect transcripts (`render_oracle_transcript`); an
    #              instrument, not a product. Separates "learned the output schema" from
    #              "learned to survive reader noise", because Gemma already scores 0.9719
    #              on perfect text, so a reader-arm gain could otherwise be either one.
    # The invoice SET is identical for both arms (readiness still gates membership), so
    # the two adapters differ only in the input distribution they saw.
    input_arm: Literal["reader", "oracle"] = "reader"
    # Dev slice carved out of the sealed TRAIN side (never out of val) so the epoch can be
    # selected without spending a look at the sealed validation set. See
    # `horus.finetune.split.carve_dev`; `split.json` itself is never rewritten.
    dev_fraction: float = Field(default=0.15, gt=0.0, lt=1.0)
    dev_seed: int = 4242
    eval_max_tokens: int = Field(default=2048, ge=64)
    min_self_overall: float = Field(default=0.95, ge=0.0, le=1.0)
    lora: LoraParams = Field(default_factory=LoraParams)
    train: TrainParams = Field(default_factory=TrainParams)

    @classmethod
    def from_yaml(cls, path: str | Path) -> FinetuneConfig:
        """Load + validate a fine-tune config from a YAML file."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    def structuring_prompt(self) -> str:
        """The structurer instruction, loaded from its canonical config (DRY + matched)."""
        return load_structuring_prompt(self.structuring_prompt_config, self.structurer_model)


def load_structuring_prompt(config_path: str | Path, model_id: str) -> str:
    """Pull a structurer instruction from a config's ``cohort.prompt_template_override``.

    Parses the YAML directly (not as a full `ExperimentConfig`) so a partial/layered config
    such as ``arm-b.yaml`` can be read standalone without tripping required-field validation.
    """
    data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    try:
        overrides = data["cohort"]["prompt_template_override"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{config_path} has no cohort.prompt_template_override (needed for the "
            f"structuring prompt)."
        ) from exc
    if model_id not in overrides:
        raise ValueError(
            f"{config_path} cohort.prompt_template_override has no entry for {model_id!r}. "
            f"Known: {sorted(overrides)}"
        )
    return overrides[model_id]
