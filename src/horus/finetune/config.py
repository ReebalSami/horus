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
    seed: int = 42
    steps_per_report: int = Field(default=10, ge=1)
    # 0 → save only the final adapter (no intermediate checkpoints).
    steps_per_save: int = Field(default=0, ge=0)


class FinetuneConfig(BaseModel):
    """Top-level fine-tune experiment config (Pydantic-validated at boot)."""

    model_config = {"extra": "forbid"}

    structurer_model: str = "google/gemma-4-E4B-it"
    structuring_prompt_config: str = "configs/arm-b.yaml"
    corpus_root: str = "data/raw/german/zugferd-corpus"
    transcript_dir: str = "docs/sources/transcripts-multipage"
    reader_model: str = "ibm-granite/granite-docling-258M-mlx"
    split_path: str = "data/finetune/split.json"
    adapter_dir: str = "data/finetune/adapter"
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
