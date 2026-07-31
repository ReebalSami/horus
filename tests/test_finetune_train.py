"""Tests for the fine-tune trainer's pure helpers (issue #55).

The training loop itself needs the model + Metal and is exercised by the live spike, not unit
tests. Here we cover the model-free logic: message-item shaping and config knob defaults.
"""

from __future__ import annotations

from horus.finetune.config import FinetuneConfig
from horus.finetune.train import _to_messages_item


def test_to_messages_item_shape() -> None:
    item = _to_messages_item({"stem": "x", "question": "Q-text", "answer": '{"a": 1}'})
    assert item == {
        "messages": [
            {"role": "user", "content": "Q-text"},
            {"role": "assistant", "content": '{"a": 1}'},
        ]
    }
    # No image key → the VisionDataset path computes num_images=0 → text-only formatting.
    assert "images" not in item


def test_memory_knob_defaults() -> None:
    cfg = FinetuneConfig()
    assert cfg.train.grad_checkpoint is False  # schema default; the YAML turns it on
    assert cfg.train.free_vision_audio is True
    assert cfg.train.wired_limit_gb == 0.0
    assert cfg.train.batch_size == 1


def test_yaml_enables_memory_levers() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    cfg = FinetuneConfig.from_yaml(repo_root / "configs" / "finetune-structurer.yaml")
    # The shipped config must enable the memory levers the M1 Pro run needs.
    assert cfg.train.grad_checkpoint is True
    assert cfg.train.free_vision_audio is True
