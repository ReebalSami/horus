"""Hermetic tests for the CUDA LoRA path (ADR-067 2x2 design, ADR-068 venue).

No model is loaded and no GPU is required. What is pinned here is the wiring that decides
what the model would be trained ON — the part that is silently wrong rather than loudly
broken if it regresses:

* the reader/oracle arm resolves to genuinely different input text, with identical targets
  and identical invoice membership (otherwise the 2x2 attribution is not a controlled
  comparison, just two unrelated runs);
* prompt/completion records are shaped the way TRL's completion-only masking expects,
  since the alternative is silently computing loss over a ~3k-token prompt;
* the trainer refuses to run without CUDA rather than falling back to a device that
  ADR-068 records as non-viable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from horus.eval.ground_truth import FIELDS, GroundTruth, GroundTruthField
from horus.finetune.config import FinetuneConfig
from horus.finetune.dataset import InvoiceRecord, build_dataset, build_example
from horus.finetune.train_cuda import (
    build_prompt_completion_records,
    resolve_reader_text_fn,
)

_PROMPT = "Extract the invoice fields as JSON."


def _gt(present: dict[str, str]) -> GroundTruth:
    """Full-registry GroundTruth (same helper shape as `test_finetune_evaluate._gt`).

    `groundtruth_to_target` indexes every key in `FIELDS`, so a partial header raises
    `KeyError` rather than yielding a partial target.
    """
    header: dict[str, GroundTruthField] = {}
    for key, spec in FIELDS.items():
        value = present.get(key)
        header[key] = GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=value,
            normalized_value=value,
            xpath=spec.xpath,
            is_present=value is not None,
        )
    return GroundTruth(header=header)


def _rec(tmp_path: Path, stem: str = "inv-001") -> InvoiceRecord:
    """A ready record whose transcript says something an oracle page never would."""
    transcript = tmp_path / f"{stem}.txt"
    transcript.write_text(
        f"# Model: test\n# Invoice: {stem}\n\n--- Page 1 ---\nREADER-SIDE-MARKER\n",
        encoding="utf-8",
    )
    return InvoiceRecord(
        pdf_path=tmp_path / f"{stem}.pdf",
        stem=stem,
        subdir="ZUGFeRDv2",
        # A present value so the oracle page has something to render, making the two arms
        # differ by CONTENT rather than merely by one of them being empty.
        gt=_gt({"invoice_number": "R-2026-0001"}),
        gt_error=None,
        transcript_path=transcript,
    )


# ------------------------------------------------------------------- arm resolution


def test_reader_arm_uses_the_cached_transcript() -> None:
    assert resolve_reader_text_fn("reader") is None


def test_oracle_arm_returns_a_renderer() -> None:
    fn = resolve_reader_text_fn("oracle")
    assert callable(fn)


def test_unknown_arm_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown input_arm"):
        resolve_reader_text_fn("perfect")


def test_the_two_arms_feed_different_text_but_the_same_target(tmp_path: Path) -> None:
    """The 2x2 design is only valid if the arms differ in INPUT and agree on OUTPUT."""
    rec = _rec(tmp_path)

    reader_example = build_example(rec, structuring_prompt=_PROMPT)
    oracle_example = build_example(
        rec, structuring_prompt=_PROMPT, reader_text_fn=resolve_reader_text_fn("oracle")
    )

    assert "READER-SIDE-MARKER" in reader_example["question"]
    assert "READER-SIDE-MARKER" not in oracle_example["question"], (
        "oracle arm must not see reader text — that would defeat the whole comparison"
    )
    # The oracle page is rendered from the answer key, so the GT value appears in its input.
    assert "R-2026-0001" in oracle_example["question"]
    assert reader_example["question"] != oracle_example["question"]
    # Same supervision signal on both arms; only the input distribution changes.
    assert reader_example["answer"] == oracle_example["answer"]
    assert reader_example["stem"] == oracle_example["stem"]


def test_both_arms_keep_the_same_invoice_membership(tmp_path: Path) -> None:
    """Readiness defines sealed-split membership, so the arms must cover the same stems."""
    records = [_rec(tmp_path, f"inv-{i:03d}") for i in range(3)]

    reader_examples, _, _ = build_dataset(records, structuring_prompt=_PROMPT)
    oracle_examples, _, _ = build_dataset(
        records, structuring_prompt=_PROMPT, reader_text_fn=resolve_reader_text_fn("oracle")
    )

    assert [e["stem"] for e in reader_examples] == [e["stem"] for e in oracle_examples]


def test_reader_text_fn_is_actually_threaded_through_build_dataset(tmp_path: Path) -> None:
    """Guards against the override being accepted and then ignored."""
    calls: list[str] = []

    def _spy(rec: InvoiceRecord) -> str:
        calls.append(rec.stem)
        return "SPY-TEXT"

    examples, _, _ = build_dataset(
        [_rec(tmp_path)], structuring_prompt=_PROMPT, reader_text_fn=_spy
    )
    assert calls == ["inv-001"]
    assert "SPY-TEXT" in examples[0]["question"]


# ------------------------------------------------------------ TRL record shaping


def test_prompt_completion_records_match_the_conversational_schema() -> None:
    records = build_prompt_completion_records([{"question": "Q", "answer": '{"a":1}'}])

    assert len(records) == 1
    record = records[0]
    # TRL masks the prompt for exactly this shape; a `messages` list would not be masked
    # the same way and would depend on chat-template generation markers.
    assert set(record) == {"prompt", "completion"}
    assert record["prompt"] == [{"role": "user", "content": "Q"}]
    assert record["completion"] == [{"role": "assistant", "content": '{"a":1}'}]


def test_prompt_completion_preserves_order() -> None:
    examples = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(4)]
    records = build_prompt_completion_records(examples)
    assert [r["prompt"][0]["content"] for r in records] == ["Q0", "Q1", "Q2", "Q3"]


# --------------------------------------------------------------- LoRA target scoping


def _fake_gemma4_tree() -> Any:
    """A module tree mirroring gemma-4-E4B's real topology (verified on an A10G).

    Three properties matter and all three broke a naive implementation:
      * the text tower is at ``model.language_model`` \u2014 NOT a direct child;
      * the vision/audio towers contain identically-named projections, and PEFT matches
        `target_modules` by suffix, so bare names would adapt them too;
      * the text tower also holds gemma-4's per-layer-embedding projections, which are not
        a standard LoRA target.
    """
    import torch.nn as nn

    class Attn(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.q_proj = nn.Linear(4, 4)
            self.k_proj = nn.Linear(4, 4)
            self.v_proj = nn.Linear(4, 4)
            self.o_proj = nn.Linear(4, 4)

    class Layer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.self_attn = Attn()
            self.gate_proj = nn.Linear(4, 4)
            self.up_proj = nn.Linear(4, 4)
            self.down_proj = nn.Linear(4, 4)
            # gemma-4 specialty; must NOT be adapted.
            self.per_layer_input_gate = nn.Linear(4, 4)
            self.per_layer_projection = nn.Linear(4, 4)

    class LanguageModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.layers = nn.ModuleList([Layer(), Layer()])
            self.per_layer_model_projection = nn.Linear(4, 4)

    class VisionTower(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.q_proj = nn.Linear(4, 4)  # decoy: same suffix, different tower
            self.down_proj = nn.Linear(4, 4)

    class Inner(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.language_model = LanguageModel()
            self.vision_tower = VisionTower()

    class Outer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.model = Inner()
            self.lm_head = nn.Linear(4, 4)

    return Outer()


def test_lora_targets_are_found_one_level_deep() -> None:
    """The GPU smoke failed here: the text tower is not a direct child of the model."""
    from horus.finetune.train_cuda import language_model_linear_names

    names = language_model_linear_names(_fake_gemma4_tree())

    assert names, "must locate the nested language_model"
    assert all(n.startswith("model.language_model.") for n in names)


def test_lora_targets_exclude_other_towers_and_the_head() -> None:
    from horus.finetune.train_cuda import language_model_linear_names

    names = language_model_linear_names(_fake_gemma4_tree())

    assert not any("vision_tower" in n for n in names)
    assert not any(n.endswith("lm_head") for n in names)


def test_lora_targets_exclude_per_layer_embedding_projections() -> None:
    """gemma-4's PLE projections are an architectural specialty, not a LoRA target."""
    from horus.finetune.train_cuda import language_model_linear_names

    names = language_model_linear_names(_fake_gemma4_tree())

    assert not any("per_layer" in n for n in names)
    # 2 layers x (4 attention + 3 MLP)
    assert len(names) == 14


def test_lora_target_scoping_refuses_a_model_with_no_text_tower() -> None:
    import torch.nn as nn

    from horus.finetune.train_cuda import language_model_linear_names

    class NoTextTower(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.q_proj = nn.Linear(4, 4)

    with pytest.raises(ValueError, match="no `language_model` submodule"):
        language_model_linear_names(NoTextTower())


# ------------------------------------------------------------------- config wiring


def test_reader_arm_is_the_default() -> None:
    assert FinetuneConfig().input_arm == "reader"


def test_input_arm_rejects_an_unknown_value() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FinetuneConfig(input_arm="perfect")  # type: ignore[arg-type]


def test_shipped_configs_declare_distinct_arms_and_adapter_dirs() -> None:
    """Two arms writing to one adapter_dir would have the second silently clobber the first."""
    reader = FinetuneConfig.from_yaml("configs/finetune-structurer.yaml")
    oracle = FinetuneConfig.from_yaml("configs/finetune-structurer-oracle.yaml")

    assert reader.input_arm == "reader"
    assert oracle.input_arm == "oracle"
    assert reader.adapter_dir != oracle.adapter_dir

    # Everything that must be held constant for the comparison to be controlled.
    assert reader.structurer_model == oracle.structurer_model
    assert reader.structuring_prompt_config == oracle.structuring_prompt_config
    assert reader.split_path == oracle.split_path
    assert (reader.dev_fraction, reader.dev_seed) == (oracle.dev_fraction, oracle.dev_seed)
    assert reader.min_self_overall == oracle.min_self_overall
    assert reader.lora.model_dump() == oracle.lora.model_dump()
    assert reader.train.model_dump() == oracle.train.model_dump()


# ------------------------------------------------------------------- CUDA guard


def test_trainer_refuses_without_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-068: the MLX path could not finish a 4-example smoke; no silent local fallback."""
    import torch

    from horus.finetune import train_cuda

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    cfg: Any = FinetuneConfig()
    with pytest.raises(RuntimeError, match="no CUDA device"):
        train_cuda.run_finetune_cuda(cfg)
