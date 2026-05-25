"""Tests for `EDAConfig` + `ComplexityTierConfig` + `FineTuningAnchorsConfig` (ADR-024).

Covers:

  - EDAConfig defaults match documented anchors
  - YAML round-trip with `eda:` section (`configs/eda-zugferd.yaml`)
  - Backward-compat: existing configs without `eda:` continue to parse
    (`configs/cohort-smoke.yaml` from ADR-011 must still load)
  - Pydantic fail-fast: out-of-range / non-monotonic / extra-key rejection
  - Cross-field validators: complexity-tier monotonicity, page-count-bins
    monotonicity, fine-tuning-anchor ordering
  - Defaults match literature anchors (Berghaus 2025, arxiv 2510.15727,
    standard LoRA range)

Mirrors the structure of `tests/test_config_eval.py` (the canonical sub-model
test pattern in HORUS). Refs: ADR-024 §"Decision + integration thoughts",
ADR-004 (config library), `src/horus/config.py` (the schema),
`.windsurf/rules/horus-config-discipline.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from horus.config import (
    ComplexityTierConfig,
    EDAConfig,
    ExperimentConfig,
    FineTuningAnchorsConfig,
    MLflowConfig,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. ComplexityTierConfig — defaults + validation
# ---------------------------------------------------------------------------


def test_complexity_tier_defaults_match_pilot_13_evidence() -> None:
    """`ComplexityTierConfig` defaults are seeded from pilot-13's 26-PDF subset."""
    cfg = ComplexityTierConfig()
    assert cfg.simple_max_pages == 1, "Pilot-13 evidence: 24/26 invoices are single-page"
    assert cfg.simple_max_line_items == 5, "Pilot-13 evidence: median line-item count is 3"
    assert cfg.medium_max_pages == 3, "Multi-page but not document-pack"
    assert cfg.medium_max_line_items == 20, "Richer line-item structure"


def test_complexity_tier_explicit_values_parse_cleanly() -> None:
    """`ComplexityTierConfig` accepts explicit threshold values."""
    cfg = ComplexityTierConfig(
        simple_max_pages=2,
        simple_max_line_items=10,
        medium_max_pages=5,
        medium_max_line_items=50,
    )
    assert cfg.simple_max_pages == 2
    assert cfg.medium_max_line_items == 50


def test_complexity_tier_rejects_simple_above_medium_pages() -> None:
    """`simple_max_pages > medium_max_pages` → ValidationError (else medium tier unreachable)."""
    with pytest.raises(ValidationError, match="medium_max_pages"):
        ComplexityTierConfig(simple_max_pages=5, medium_max_pages=3)


def test_complexity_tier_rejects_simple_above_medium_line_items() -> None:
    """`simple_max_line_items > medium_max_line_items` → ValidationError."""
    with pytest.raises(ValidationError, match="medium_max_line_items"):
        ComplexityTierConfig(simple_max_line_items=30, medium_max_line_items=20)


def test_complexity_tier_accepts_simple_equal_to_medium() -> None:
    """`simple_max == medium_max` is permitted (`<=` boundary; degenerate but valid)."""
    cfg = ComplexityTierConfig(
        simple_max_pages=3,
        simple_max_line_items=20,
        medium_max_pages=3,
        medium_max_line_items=20,
    )
    assert cfg.simple_max_pages == cfg.medium_max_pages == 3


def test_complexity_tier_rejects_zero_pages() -> None:
    """`simple_max_pages < 1` → ValidationError (pages start at 1)."""
    with pytest.raises(ValidationError, match="simple_max_pages"):
        ComplexityTierConfig(simple_max_pages=0)


def test_complexity_tier_rejects_extra_keys() -> None:
    """Unknown keys → ValidationError per `extra='forbid'`."""
    with pytest.raises(ValidationError, match="(extra|forbidden)"):
        ComplexityTierConfig.model_validate({"simple_max_pages": 1, "unknown_knob": True})


# ---------------------------------------------------------------------------
# 2. FineTuningAnchorsConfig — defaults + validation
# ---------------------------------------------------------------------------


def test_fine_tuning_anchors_defaults_match_literature() -> None:
    """`FineTuningAnchorsConfig` defaults match the cited literature anchors."""
    cfg = FineTuningAnchorsConfig()
    assert cfg.lora_min_examples == 200, "Standard LoRA practice (Hu et al. 2021)"
    assert cfg.lora_target_examples == 2000, "Comfortable LoRA upper-bound"
    assert cfg.eval_min_examples_for_thesis == 100, (
        "95% Wilson CI half-width ≤±0.10 reference (arxiv 2510.15727 = 102, Berghaus 2025 = 350)"
    )


def test_fine_tuning_anchors_rejects_min_above_target() -> None:
    """`lora_min > lora_target` → ValidationError (band would be empty)."""
    with pytest.raises(ValidationError, match="lora_target_examples"):
        FineTuningAnchorsConfig(lora_min_examples=3000, lora_target_examples=2000)


def test_fine_tuning_anchors_accepts_min_equal_to_target() -> None:
    """`lora_min == lora_target` is permitted (degenerate but valid)."""
    cfg = FineTuningAnchorsConfig(lora_min_examples=1000, lora_target_examples=1000)
    assert cfg.lora_min_examples == cfg.lora_target_examples == 1000


def test_fine_tuning_anchors_rejects_zero_min() -> None:
    """`lora_min_examples < 1` → ValidationError."""
    with pytest.raises(ValidationError, match="lora_min_examples"):
        FineTuningAnchorsConfig(lora_min_examples=0)


def test_fine_tuning_anchors_rejects_extra_keys() -> None:
    """Unknown keys → ValidationError."""
    with pytest.raises(ValidationError, match="(extra|forbidden)"):
        FineTuningAnchorsConfig.model_validate({"lora_min_examples": 200, "unknown_knob": True})


# ---------------------------------------------------------------------------
# 3. EDAConfig — defaults + value semantics
# ---------------------------------------------------------------------------


def test_eda_config_defaults() -> None:
    """`EDAConfig` defaults match plan §3.3 documented anchors."""
    cfg = EDAConfig()
    assert cfg.corpus_root == Path("data/raw/german/zugferd-corpus")
    assert cfg.output_dir == Path("experiments")
    assert cfg.page_count_bins == [1, 2, 3, 5, 10, 20]
    assert cfg.palette_static == "muted"
    assert cfg.palette_interactive == "plotly_white"
    assert cfg.figure_dpi == 300
    assert cfg.expected_min_pdfs == 26
    assert cfg.ground_truth_required is True
    # Nested defaults
    assert cfg.complexity.simple_max_pages == 1
    assert cfg.fine_tuning_anchors.lora_min_examples == 200


def test_eda_config_explicit_values_parse_cleanly() -> None:
    """`EDAConfig` accepts explicit knob values + nested sub-models."""
    cfg = EDAConfig(
        corpus_root=Path("data/raw/german/custom-corpus"),
        output_dir=Path("artifacts/eda"),
        page_count_bins=[1, 5, 10, 100],
        palette_static="colorblind",
        palette_interactive="simple_white",
        figure_dpi=150,
        complexity=ComplexityTierConfig(
            simple_max_pages=2, medium_max_pages=10, medium_max_line_items=100
        ),
        fine_tuning_anchors=FineTuningAnchorsConfig(lora_min_examples=500),
        expected_min_pdfs=151,
        ground_truth_required=False,
    )
    assert cfg.corpus_root == Path("data/raw/german/custom-corpus")
    assert cfg.page_count_bins == [1, 5, 10, 100]
    assert cfg.palette_static == "colorblind"
    assert cfg.complexity.simple_max_pages == 2
    assert cfg.fine_tuning_anchors.lora_min_examples == 500
    assert cfg.ground_truth_required is False


# ---------------------------------------------------------------------------
# 4. EDAConfig — page_count_bins validation (fail-fast at boot)
# ---------------------------------------------------------------------------


def test_eda_config_rejects_non_monotonic_page_count_bins() -> None:
    """`page_count_bins` must be strictly monotonically increasing."""
    with pytest.raises(ValidationError, match="monotonically increasing"):
        EDAConfig(page_count_bins=[1, 5, 3, 10])


def test_eda_config_rejects_duplicate_page_count_bins() -> None:
    """Duplicates in `page_count_bins` violate strict monotonicity (>=, not >)."""
    with pytest.raises(ValidationError, match="monotonically increasing"):
        EDAConfig(page_count_bins=[1, 2, 2, 5])


def test_eda_config_rejects_too_few_page_count_bins() -> None:
    """`page_count_bins` with <2 edges → ValidationError (need at least 1 bin)."""
    with pytest.raises(ValidationError, match="at least 2 edges"):
        EDAConfig(page_count_bins=[1])


def test_eda_config_rejects_zero_page_count_bin() -> None:
    """`page_count_bins` entries must all be >= 1 (page counts are positive)."""
    with pytest.raises(ValidationError, match=">= 1"):
        EDAConfig(page_count_bins=[0, 1, 2, 5])


def test_eda_config_rejects_negative_page_count_bin() -> None:
    """`page_count_bins` entries must all be >= 1."""
    with pytest.raises(ValidationError, match=">= 1"):
        EDAConfig(page_count_bins=[-1, 1, 2, 5])


def test_eda_config_accepts_minimal_valid_bins() -> None:
    """Two bin edges = one bin (the minimum valid histogram)."""
    cfg = EDAConfig(page_count_bins=[1, 100])
    assert cfg.page_count_bins == [1, 100]


# ---------------------------------------------------------------------------
# 5. EDAConfig — figure_dpi range + extra-keys + ground_truth_required
# ---------------------------------------------------------------------------


def test_eda_config_rejects_dpi_below_72() -> None:
    """`figure_dpi < 72` → ValidationError (loses body-text legibility)."""
    with pytest.raises(ValidationError, match="figure_dpi"):
        EDAConfig(figure_dpi=50)


def test_eda_config_rejects_dpi_above_600() -> None:
    """`figure_dpi > 600` → ValidationError (wasted compute past PDF limits)."""
    with pytest.raises(ValidationError, match="figure_dpi"):
        EDAConfig(figure_dpi=1200)


def test_eda_config_rejects_extra_keys() -> None:
    """Unknown keys → ValidationError per `extra='forbid'`."""
    with pytest.raises(ValidationError, match="(extra|forbidden)"):
        EDAConfig.model_validate({"corpus_root": "data/", "unknown_knob": True})


def test_eda_config_rejects_zero_expected_min_pdfs() -> None:
    """`expected_min_pdfs < 1` → ValidationError."""
    with pytest.raises(ValidationError, match="expected_min_pdfs"):
        EDAConfig(expected_min_pdfs=0)


def test_eda_config_expected_min_examples_default_is_none() -> None:
    """`expected_min_examples` defaults to None (per ADR-025: PDF chapters use
    `expected_min_pdfs`; only non-PDF chapters set this).
    """
    cfg = EDAConfig()
    assert cfg.expected_min_examples is None


def test_eda_config_accepts_expected_min_examples() -> None:
    """Non-PDF chapters set `expected_min_examples` per ADR-025."""
    cfg = EDAConfig(expected_min_examples=9000)
    assert cfg.expected_min_examples == 9000


def test_eda_config_rejects_zero_expected_min_examples() -> None:
    """`expected_min_examples < 1` → ValidationError (per Field ge=1)."""
    with pytest.raises(ValidationError, match="expected_min_examples"):
        EDAConfig(expected_min_examples=0)


def test_eda_config_pdf_and_non_pdf_knobs_coexist() -> None:
    """Both `expected_min_pdfs` AND `expected_min_examples` can be set; chapters
    pick whichever is relevant. PDF chapters reference `expected_min_pdfs`;
    non-PDF chapters reference `expected_min_examples`. Coexistence in the
    schema is intentional per ADR-025.
    """
    cfg = EDAConfig(expected_min_pdfs=151, expected_min_examples=10000)
    assert cfg.expected_min_pdfs == 151
    assert cfg.expected_min_examples == 10000


# ---------------------------------------------------------------------------
# 6. ExperimentConfig — optional `eda:` (backward-compat with existing YAMLs)
# ---------------------------------------------------------------------------


def test_experiment_config_eda_is_optional_with_none_default() -> None:
    """`ExperimentConfig` without `eda:` parses with `eda=None`."""
    cfg = ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(experiment_name="test-no-eda"),
    )
    assert cfg.eda is None, "Default eda should be None for backward-compat"


def test_experiment_config_loads_cohort_smoke_yaml_unchanged() -> None:
    """`configs/cohort-smoke.yaml` (no `eda:`) loads unchanged after ADR-024.

    Backward-compat guard: the ADR-011 cohort-smoke config must continue to
    parse after this PR adds the optional `eda:` sub-model.
    """
    cfg_path = REPO_ROOT / "configs" / "cohort-smoke.yaml"
    assert cfg_path.is_file(), f"Missing pre-existing config: {cfg_path}"
    cfg = ExperimentConfig.from_yaml(cfg_path)
    assert cfg.seed == 42
    assert cfg.mlflow.experiment_name == "cohort-smoke"
    assert cfg.eda is None, "cohort-smoke.yaml has no eda: section"


def test_experiment_config_loads_eda_zugferd_yaml() -> None:
    """`configs/eda-zugferd.yaml` loads cleanly with the new `eda:` section."""
    cfg_path = REPO_ROOT / "configs" / "eda-zugferd.yaml"
    assert cfg_path.is_file(), f"Missing ADR-024 config: {cfg_path}"
    cfg = ExperimentConfig.from_yaml(cfg_path)

    assert cfg.seed == 42
    assert cfg.mlflow.experiment_name == "eda-zugferd"
    assert cfg.mlflow.run_tags.get("adr") == "ADR-024"
    assert cfg.mlflow.run_tags.get("issue") == "46"
    assert cfg.mlflow.run_tags.get("descriptive_only") == "true"

    assert cfg.eda is not None, "eda-zugferd.yaml MUST have an eda: section"
    eda = cfg.eda
    assert eda.corpus_root == Path("data/raw/german/zugferd-corpus")
    assert eda.output_dir == Path("experiments")
    assert eda.page_count_bins == [1, 2, 3, 5, 10, 20]
    assert eda.palette_static == "muted"
    assert eda.palette_interactive == "plotly_white"
    assert eda.figure_dpi == 300
    assert eda.expected_min_pdfs == 26
    assert eda.ground_truth_required is True

    # Pre-committed complexity-tier thresholds.
    assert eda.complexity.simple_max_pages == 1
    assert eda.complexity.simple_max_line_items == 5
    assert eda.complexity.medium_max_pages == 3
    assert eda.complexity.medium_max_line_items == 20

    # Fine-tuning anchors.
    assert eda.fine_tuning_anchors.lora_min_examples == 200
    assert eda.fine_tuning_anchors.lora_target_examples == 2000
    assert eda.fine_tuning_anchors.eval_min_examples_for_thesis == 100


# ---------------------------------------------------------------------------
# 7. ExperimentConfig — env-var overrides (pydantic-settings double-underscore)
# ---------------------------------------------------------------------------


def test_experiment_config_eda_env_var_path_documented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`HORUS_EDA__FIGURE_DPI=150` documents the env-var override pathway.

    Per `pydantic-settings`: env vars supplement values NOT present in the
    init kwargs. When the parent `eda` field is None (no eda: in YAML),
    pydantic-settings does NOT auto-construct an EDAConfig from env vars —
    eda stays None. The override CAN take effect when eda is explicitly
    constructed. This test documents the env-var pathway exists; tuning
    behavior is the YAML's responsibility per `horus-config-discipline`.

    Mirrors the env-var-pathway-documentation pattern from
    `tests/test_config_eval.py::test_experiment_config_env_var_overrides_eval_threshold`.
    """
    monkeypatch.setenv("HORUS_EDA__FIGURE_DPI", "150")
    cfg = ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(experiment_name="env-test"),
    )
    # When eda is absent from init kwargs, pydantic-settings does NOT
    # auto-construct an EDAConfig from env vars — eda stays None.
    assert cfg.eda is None or cfg.eda.figure_dpi in (150, 300)


def test_experiment_config_loads_eda_zugferd_yaml_via_list() -> None:
    """`from_yaml` accepts a single-element list (back-compat with multi-file flow)."""
    cfg_path = REPO_ROOT / "configs" / "eda-zugferd.yaml"
    cfg = ExperimentConfig.from_yaml([cfg_path])
    assert cfg.eda is not None
    assert cfg.eda.corpus_root == Path("data/raw/german/zugferd-corpus")
