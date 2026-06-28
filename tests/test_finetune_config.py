"""Tests for the fine-tune config loader (issue #55)."""

from __future__ import annotations

from pathlib import Path

import pytest

from horus.finetune.config import FinetuneConfig, load_structuring_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_default_config_yaml_loads_and_validates() -> None:
    cfg = FinetuneConfig.from_yaml(REPO_ROOT / "configs" / "finetune-structurer.yaml")
    assert cfg.structurer_model == "google/gemma-4-E4B-it"
    assert cfg.lora.rank == 8
    assert cfg.lora.alpha == 16.0
    assert cfg.train.train_on_completions is True
    assert cfg.train.epochs >= 1
    assert cfg.train.batch_size >= 1


def test_extra_keys_rejected() -> None:
    with pytest.raises(ValueError):
        FinetuneConfig.model_validate({"structurer_model": "x", "bogus_key": 1})


def test_lora_rank_must_be_positive() -> None:
    with pytest.raises(ValueError):
        FinetuneConfig.model_validate({"lora": {"rank": 0}})


def test_structuring_prompt_loads_from_arm_b() -> None:
    prompt = load_structuring_prompt(REPO_ROOT / "configs" / "arm-b.yaml", "google/gemma-4-E4B-it")
    assert "meticulous accountant" in prompt
    # The field-glossary placeholder is filled later by build_structuring_input.
    assert "{field_glossary}" in prompt


def test_structuring_prompt_unknown_model_raises() -> None:
    with pytest.raises(ValueError, match="no entry for"):
        load_structuring_prompt(REPO_ROOT / "configs" / "arm-b.yaml", "no/such-model")


def test_config_structuring_prompt_method() -> None:
    cfg = FinetuneConfig.from_yaml(REPO_ROOT / "configs" / "finetune-structurer.yaml")
    assert "meticulous accountant" in cfg.structuring_prompt()
