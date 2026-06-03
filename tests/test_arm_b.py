"""Tests for the Arm B (orchestrated) runner (`src/horus/eval/arm_b.py`, ADR-038).

Covers the boot-time validation branches (all of which raise BEFORE any corpus
walk or model load, so they need neither the ZUGFeRD corpus nor an MLX model) +
the pure prompt-assembly helper. The full structuring pipeline (reader transcript
-> Gemma text-only -> structurer -> score -> MLflow) is exercised by the dev run,
not unit-tested here (it requires a loaded model).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus.config import CohortConfig, ExperimentConfig, MLflowConfig
from horus.eval.arm_b import run_arm_b
from horus.eval.structurer import build_structuring_input

_GEMMA = "google/gemma-4-E4B-it"
_GRANITE = "ibm-granite/granite-docling-258M-mlx"


def _cfg(
    tmp_path: Path,
    *,
    experiment_name: str = "arm-b-test",
    **cohort_kwargs: object,
) -> ExperimentConfig:
    """Build a minimal ExperimentConfig for Arm B validation tests."""
    base: dict[str, object] = {
        "working_models": [_GEMMA],
        "corpus_root": tmp_path / "corpus",
        "transcript_archive_dir": tmp_path / "transcripts",
        "parent_run_name": "arm-b-test",
    }
    base.update(cohort_kwargs)
    return ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(
            experiment_name=experiment_name,
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
        ),
        cohort=CohortConfig(**base),  # type: ignore[arg-type]
    )


def test_build_structuring_input_embeds_prompt_and_reader_text() -> None:
    """The composed input carries the instruction + the reader text under a delimiter."""
    out = build_structuring_input("EXTRACT THE FIELDS", "Rechnung Nr. 471102")
    assert "EXTRACT THE FIELDS" in out
    assert "Rechnung Nr. 471102" in out
    assert "<<<" in out and ">>>" in out
    # Instruction precedes the reader text.
    assert out.index("EXTRACT THE FIELDS") < out.index("Rechnung Nr. 471102")


def test_run_arm_b_raises_when_cohort_missing(tmp_path: Path) -> None:
    """No cohort section -> ValueError (Arm B requires a CohortConfig)."""
    cfg = ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(experiment_name="arm-b-test"),
    )
    with pytest.raises(ValueError, match="cfg.cohort is None"):
        run_arm_b(cfg)


def test_run_arm_b_raises_without_reader_model_id(tmp_path: Path) -> None:
    """`reader_model_id` unset -> ValueError (Arm B needs the reader to consume)."""
    cfg = _cfg(tmp_path)  # reader_model_id defaults to None
    with pytest.raises(ValueError, match="requires cohort.reader_model_id"):
        run_arm_b(cfg)


def test_run_arm_b_raises_on_multiple_structurers(tmp_path: Path) -> None:
    """More than one structurer in working_models -> ValueError (held constant)."""
    cfg = _cfg(tmp_path, working_models=[_GEMMA, _GRANITE], reader_model_id=_GRANITE)
    with pytest.raises(ValueError, match="exactly ONE structurer"):
        run_arm_b(cfg)


def test_run_arm_b_raises_on_unknown_structurer(tmp_path: Path) -> None:
    """Structurer not in COHORT_MANIFEST -> ValueError."""
    cfg = _cfg(tmp_path, working_models=["nope/not-a-model"], reader_model_id=_GRANITE)
    with pytest.raises(ValueError, match="not in COHORT_MANIFEST"):
        run_arm_b(cfg)


def test_run_arm_b_raises_on_unknown_reader(tmp_path: Path) -> None:
    """Reader not in COHORT_MANIFEST -> ValueError."""
    cfg = _cfg(tmp_path, reader_model_id="nope/not-a-model")
    with pytest.raises(ValueError, match="not in COHORT_MANIFEST"):
        run_arm_b(cfg)


def test_run_arm_b_raises_without_structuring_prompt(tmp_path: Path) -> None:
    """No prompt_template_override for the structurer -> ValueError."""
    # adapter_mode defaults to 'regex' so the CohortConfig validator does not
    # itself require a prompt; run_arm_b's own check is what must fire.
    cfg = _cfg(tmp_path, reader_model_id=_GRANITE)
    with pytest.raises(ValueError, match="requires a structuring prompt"):
        run_arm_b(cfg)


def test_run_arm_b_raises_on_dev_only_canonical_experiment(tmp_path: Path) -> None:
    """A dev_only config targeting the canonical production experiment -> ValueError."""
    cfg = _cfg(
        tmp_path,
        experiment_name="pilot-13-full",  # canonical production experiment
        reader_model_id=_GRANITE,
        adapter_mode="structurer",
        prompt_template_override={_GEMMA: "STRUCTURE PROMPT"},
        dev_only=True,
    )
    with pytest.raises(ValueError, match="canonical production"):
        run_arm_b(cfg)
