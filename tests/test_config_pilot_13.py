"""Tests for `RasterizerConfig` + `CohortConfig` + optional fields on `ExperimentConfig`.

Covers per `horus-config-discipline` + ADR-014:

  - YAML round-trip with `rasterizer:` + `cohort:` sections (`configs/pilot-13.yaml`)
  - Backward-compat: existing configs without these sections continue to parse
    (`configs/cohort-smoke.yaml` from ADR-011 + `configs/pilot-13-eval.yaml` from ADR-013)
  - Pydantic fail-fast: DPI out-of-range, empty working_models, extra-key rejection
  - Defaults match the ADR-014 §Decision rationale

Refs: ADR-014 §"Decision + integration thoughts" (forthcoming), ADR-013 (parent),
      ADR-004 (config library), `src/horus/config.py` (the schema),
      `.windsurf/rules/horus-config-discipline.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from horus.config import (
    CohortConfig,
    ExperimentConfig,
    MLflowConfig,
    RasterizerConfig,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. RasterizerConfig — defaults + value semantics
# ---------------------------------------------------------------------------


def test_rasterizer_config_defaults_match_adr_014_rationale() -> None:
    """All `RasterizerConfig` defaults match the ADR-014 §Decision rationale."""
    cfg = RasterizerConfig()
    assert cfg.dpi == 300, "Default 300 DPI matches A4 → 2480px (legacy sips baseline)"
    assert cfg.cache_dir == Path("data/raw/smoke/multipage"), (
        "Default cache_dir matches gitignored ADR-014 convention"
    )
    assert cfg.image_format == "png", "Default PNG (lossless; matches smoke artifact convention)"


def test_rasterizer_config_explicit_values_parse_cleanly() -> None:
    """`RasterizerConfig` accepts explicit knob values."""
    cfg = RasterizerConfig(dpi=200, cache_dir=Path("/tmp/raster"), image_format="jpeg")
    assert cfg.dpi == 200
    assert cfg.cache_dir == Path("/tmp/raster")
    assert cfg.image_format == "jpeg"


# ---------------------------------------------------------------------------
# 2. RasterizerConfig — validation (fail-fast at boot)
# ---------------------------------------------------------------------------


def test_rasterizer_config_rejects_dpi_below_72() -> None:
    """`dpi < 72` → ValidationError (below body-text legibility)."""
    with pytest.raises(ValidationError, match="dpi"):
        RasterizerConfig(dpi=50)


def test_rasterizer_config_rejects_dpi_above_600() -> None:
    """`dpi > 600` → ValidationError (wastes compute past cohort longest_edge=2048)."""
    with pytest.raises(ValidationError, match="dpi"):
        RasterizerConfig(dpi=1200)


def test_rasterizer_config_rejects_invalid_image_format() -> None:
    """`image_format` outside the {png, jpeg} Literal → ValidationError."""
    with pytest.raises(ValidationError, match="image_format"):
        RasterizerConfig(image_format="webp")  # type: ignore[arg-type]


def test_rasterizer_config_rejects_extra_keys() -> None:
    """Unknown keys in YAML → ValidationError (per `extra='forbid'` discipline)."""
    with pytest.raises(ValidationError, match="(extra|forbidden)"):
        RasterizerConfig.model_validate({"dpi": 300, "unknown_knob": True})


def test_rasterizer_config_accepts_dpi_at_boundaries() -> None:
    """`dpi` of exactly 72 or 600 is permitted (closed interval)."""
    cfg_lo = RasterizerConfig(dpi=72)
    cfg_hi = RasterizerConfig(dpi=600)
    assert cfg_lo.dpi == 72
    assert cfg_hi.dpi == 600


# ---------------------------------------------------------------------------
# 3. CohortConfig — defaults + value semantics
# ---------------------------------------------------------------------------


def test_cohort_config_defaults_match_adr_014_rationale() -> None:
    """`CohortConfig` defaults match the ADR-014 §Decision rationale (working_models required)."""
    cfg = CohortConfig(working_models=["test-model"])
    assert cfg.working_models == ["test-model"]
    assert cfg.corpus_root == Path("data/raw/german/zugferd-corpus")
    assert cfg.parent_run_name == "pilot-13-full"
    assert cfg.transcript_archive_dir == Path("docs/sources/transcripts-multipage")
    assert cfg.resume_on_existing_run is True, "Default resume-safety enabled"


def test_cohort_config_rejects_empty_working_models() -> None:
    """`working_models = []` → ValidationError (min_length=1 enforced)."""
    with pytest.raises(ValidationError, match="working_models"):
        CohortConfig(working_models=[])


def test_cohort_config_rejects_missing_working_models() -> None:
    """`working_models` is required (no default)."""
    with pytest.raises(ValidationError, match="working_models"):
        CohortConfig()  # type: ignore[call-arg]


def test_cohort_config_rejects_extra_keys() -> None:
    """Unknown keys → ValidationError (per `extra='forbid'`)."""
    with pytest.raises(ValidationError, match="(extra|forbidden)"):
        CohortConfig.model_validate({"working_models": ["m"], "unknown_knob": True})


# ---------------------------------------------------------------------------
# 4. ExperimentConfig — optional `rasterizer:` + `cohort:` (backward-compat)
# ---------------------------------------------------------------------------


def test_experiment_config_rasterizer_and_cohort_are_optional() -> None:
    """`ExperimentConfig` without `rasterizer:` or `cohort:` parses with both None."""
    cfg = ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(experiment_name="test-no-pilot-13"),
    )
    assert cfg.rasterizer is None
    assert cfg.cohort is None


def test_experiment_config_loads_cohort_smoke_yaml_unchanged() -> None:
    """`configs/cohort-smoke.yaml` (no `rasterizer:` / `cohort:`) loads unchanged after ADR-014."""
    cfg_path = REPO_ROOT / "configs" / "cohort-smoke.yaml"
    assert cfg_path.is_file(), f"Missing pre-existing config: {cfg_path}"
    cfg = ExperimentConfig.from_yaml(cfg_path)
    assert cfg.seed == 42
    assert cfg.rasterizer is None, "cohort-smoke.yaml has no rasterizer: section"
    assert cfg.cohort is None, "cohort-smoke.yaml has no cohort: section"


def test_experiment_config_loads_pilot_13_eval_yaml_unchanged() -> None:
    """`configs/pilot-13-eval.yaml` (no `rasterizer:` / `cohort:`) loads unchanged after ADR-014."""
    cfg_path = REPO_ROOT / "configs" / "pilot-13-eval.yaml"
    assert cfg_path.is_file(), f"Missing PR(b) config: {cfg_path}"
    cfg = ExperimentConfig.from_yaml(cfg_path)
    assert cfg.seed == 42
    assert cfg.eval is not None, "pilot-13-eval.yaml has an eval: section"
    assert cfg.rasterizer is None, "pilot-13-eval.yaml has no rasterizer: section"
    assert cfg.cohort is None, "pilot-13-eval.yaml has no cohort: section"


def test_experiment_config_loads_pilot_13_yaml() -> None:
    """`configs/pilot-13.yaml` loads cleanly with all 3 sections (eval + rasterizer + cohort)."""
    cfg_path = REPO_ROOT / "configs" / "pilot-13.yaml"
    assert cfg_path.is_file(), f"Missing PR(c) config: {cfg_path}"
    cfg = ExperimentConfig.from_yaml(cfg_path)

    assert cfg.seed == 42
    assert cfg.mlflow.experiment_name == "pilot-13-full"
    assert cfg.mlflow.run_tags.get("adr") == "ADR-014"
    assert cfg.mlflow.run_tags.get("pr") == "prc-cohort-harness"

    assert cfg.eval is not None
    assert cfg.eval.anls_threshold == 0.5

    assert cfg.rasterizer is not None
    assert cfg.rasterizer.dpi == 300
    assert cfg.rasterizer.cache_dir == Path("data/raw/smoke/multipage")
    assert cfg.rasterizer.image_format == "png"

    assert cfg.cohort is not None
    assert len(cfg.cohort.working_models) == 7, (
        "ADR-009 Amendment 1: 7 working / 10 cohort models (3 errored excluded)"
    )
    assert cfg.cohort.parent_run_name == "pilot-13-full"
    assert cfg.cohort.resume_on_existing_run is True


def test_pilot_13_working_models_match_canonical_evidence_base() -> None:
    """`configs/pilot-13.yaml::cohort.working_models` matches the 7 entries in
    `tests/test_scorer_integration.WORKING_TRANSCRIPTS` (the canonical evidence base
    per ADR-013 §"Decision + integration thoughts" + ADR-009 Amendment 1)."""
    cfg_path = REPO_ROOT / "configs" / "pilot-13.yaml"
    cfg = ExperimentConfig.from_yaml(cfg_path)
    assert cfg.cohort is not None

    # Mapping: WORKING_TRANSCRIPTS filename → canonical model_id in COHORT_MANIFEST.
    # If COHORT_MANIFEST is amended (e.g., to add a model), this mapping AND the
    # pilot-13.yaml working_models list must be updated together.
    expected_model_ids = {
        "ibm-granite/granite-docling-258M-mlx",  # granite-docling-258m.txt
        "opendatalab/MinerU2.5-Pro-2604-1.2B",  # mineru-2-5-pro-vlm.txt
        "allenai/olmOCR-2-7B-1025",  # olmocr-2-7b.txt
        "google/gemma-4-E4B-it",  # gemma-4-e4b-it.txt
        "zai-org/GLM-OCR",  # glm-ocr.txt
        "PaddlePaddle/PaddleOCR-VL",  # paddleocr-vl.txt
        "google/paligemma2-3b-mix-448",  # paligemma2-3b-mix-448.txt
    }
    assert set(cfg.cohort.working_models) == expected_model_ids, (
        "pilot-13.yaml working_models drifted from WORKING_TRANSCRIPTS — update both files together"
    )
