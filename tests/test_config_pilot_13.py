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
    _deep_merge,
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


# ---------------------------------------------------------------------------
# 5. CohortConfig — invoice_subset + dev_only (ADR-016)
# ---------------------------------------------------------------------------


def test_cohort_config_invoice_subset_defaults_to_none() -> None:
    """`CohortConfig.invoice_subset` is None by default (= full corpus)."""
    cfg = CohortConfig(working_models=["m"])
    assert cfg.invoice_subset is None


def test_cohort_config_invoice_subset_accepts_list_of_stems() -> None:
    """`invoice_subset` accepts a list of PDF stems (without `.pdf`)."""
    cfg = CohortConfig(
        working_models=["m"],
        invoice_subset=["EN16931_Einfach", "XRECHNUNG_Einfach"],
    )
    assert cfg.invoice_subset == ["EN16931_Einfach", "XRECHNUNG_Einfach"]


def test_cohort_config_invoice_subset_rejects_non_string_entries() -> None:
    """`invoice_subset` entries must be strings (Pydantic type-validated)."""
    with pytest.raises(ValidationError, match="invoice_subset"):
        CohortConfig.model_validate(
            {"working_models": ["m"], "invoice_subset": [1, 2, 3]}
        )


def test_cohort_config_dev_only_defaults_to_false() -> None:
    """`CohortConfig.dev_only` is False by default (production-grade run)."""
    cfg = CohortConfig(working_models=["m"])
    assert cfg.dev_only is False


def test_cohort_config_dev_only_accepts_true() -> None:
    """`dev_only=true` is accepted; the harness applies the HARKing-prevention guard."""
    cfg = CohortConfig(working_models=["m"], dev_only=True)
    assert cfg.dev_only is True


# ---------------------------------------------------------------------------
# 6. _deep_merge helper — semantics per ADR-016
# ---------------------------------------------------------------------------


def test_deep_merge_empty_base_returns_override() -> None:
    """`_deep_merge({}, x) == x` for any dict x."""
    override = {"a": 1, "b": {"c": 2}}
    assert _deep_merge({}, override) == override


def test_deep_merge_empty_override_returns_base() -> None:
    """`_deep_merge(x, {}) == x` for any dict x."""
    base = {"a": 1, "b": {"c": 2}}
    assert _deep_merge(base, {}) == base


def test_deep_merge_disjoint_keys_unions_them() -> None:
    """Keys present in only one input survive in the result."""
    assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_deep_merge_scalar_override_wins() -> None:
    """Conflicting scalar value → override wins."""
    assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_deep_merge_nested_dicts_merge_recursively() -> None:
    """Nested dicts are merged recursively (NOT replaced)."""
    base = {"outer": {"a": 1, "b": 2}}
    override = {"outer": {"b": 20, "c": 3}}
    assert _deep_merge(base, override) == {"outer": {"a": 1, "b": 20, "c": 3}}


def test_deep_merge_lists_are_replaced_not_concatenated() -> None:
    """Lists are NOT element-wise merged; override list fully replaces base list.

    This is the canonical pydantic-settings deep-merge semantics + the user-
    intended behaviour for HORUS's dev-overlay use case (dev YAML replaces
    the 7-model cohort with `[MinerU]`, not appends to it).
    """
    base = {"models": ["A", "B", "C"]}
    override = {"models": ["X"]}
    assert _deep_merge(base, override) == {"models": ["X"]}


def test_deep_merge_none_override_replaces_base() -> None:
    """An explicit None in override replaces the base value (NOT preserves base)."""
    assert _deep_merge({"a": 1}, {"a": None}) == {"a": None}


def test_deep_merge_does_not_mutate_inputs() -> None:
    """`_deep_merge` returns a new dict; base + override are not mutated."""
    base = {"outer": {"a": 1}}
    override = {"outer": {"b": 2}}
    result = _deep_merge(base, override)
    assert base == {"outer": {"a": 1}}, "base mutated"
    assert override == {"outer": {"b": 2}}, "override mutated"
    assert result is not base
    assert result is not override


# ---------------------------------------------------------------------------
# 7. ExperimentConfig.from_yaml — multi-file composition (ADR-016)
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, content: str) -> Path:
    """Helper: write a YAML string to a temp path and return it."""
    path.write_text(content, encoding="utf-8")
    return path


def test_from_yaml_accepts_string_path_back_compat() -> None:
    """Single str path still works (existing API contract preserved)."""
    cfg = ExperimentConfig.from_yaml(str(REPO_ROOT / "configs" / "cohort-smoke.yaml"))
    assert cfg.seed == 42


def test_from_yaml_accepts_path_object_back_compat() -> None:
    """Single Path object still works (existing API contract preserved)."""
    cfg = ExperimentConfig.from_yaml(REPO_ROOT / "configs" / "cohort-smoke.yaml")
    assert cfg.seed == 42


def test_from_yaml_accepts_single_element_list() -> None:
    """A list with one path is equivalent to the single-path form."""
    cfg = ExperimentConfig.from_yaml([REPO_ROOT / "configs" / "cohort-smoke.yaml"])
    assert cfg.seed == 42


def test_from_yaml_composes_base_plus_overlay(tmp_path: Path) -> None:
    """Two YAML files deep-merge with later-wins semantics."""
    base = _write_yaml(
        tmp_path / "base.yaml",
        "seed: 42\n"
        "mlflow:\n"
        "  experiment_name: base-exp\n"
        "  run_tags:\n"
        "    stage: pilot\n",
    )
    overlay = _write_yaml(
        tmp_path / "overlay.yaml",
        "mlflow:\n"
        "  experiment_name: overlay-exp\n"  # overrides base
        "  run_tags:\n"
        "    stage: dev\n"  # overrides base.mlflow.run_tags.stage
        "    cohort: dev-only\n",  # adds new key
    )
    cfg = ExperimentConfig.from_yaml([base, overlay])
    assert cfg.seed == 42, "base seed preserved (not in overlay)"
    assert cfg.mlflow.experiment_name == "overlay-exp", "overlay wins on conflict"
    assert cfg.mlflow.run_tags == {"stage": "dev", "cohort": "dev-only"}, (
        "nested dict merged: stage overridden, cohort added"
    )


def test_from_yaml_three_file_composition_last_wins(tmp_path: Path) -> None:
    """N-file composition: the last file's values win on conflict."""
    a = _write_yaml(
        tmp_path / "a.yaml", "seed: 1\nmlflow:\n  experiment_name: a\n"
    )
    b = _write_yaml(tmp_path / "b.yaml", "seed: 2\n")
    c = _write_yaml(tmp_path / "c.yaml", "seed: 3\n")
    cfg = ExperimentConfig.from_yaml([a, b, c])
    assert cfg.seed == 3, "last file wins"
    assert cfg.mlflow.experiment_name == "a", "earlier-only key survives"


def test_from_yaml_overlay_replaces_list_not_concatenates(tmp_path: Path) -> None:
    """Overlay list REPLACES base list (per `_deep_merge` semantics)."""
    base = _write_yaml(
        tmp_path / "base.yaml",
        "seed: 42\n"
        "mlflow:\n"
        "  experiment_name: pilot-13-full\n"
        "cohort:\n"
        "  working_models:\n"
        "    - A\n"
        "    - B\n"
        "    - C\n",
    )
    overlay = _write_yaml(
        tmp_path / "overlay.yaml",
        "cohort:\n"
        "  working_models:\n"
        "    - X\n",  # full replacement, not concatenation
    )
    cfg = ExperimentConfig.from_yaml([base, overlay])
    assert cfg.cohort is not None
    assert cfg.cohort.working_models == ["X"], (
        "overlay list replaces base list; this is the canonical dev-overlay use case"
    )


def test_from_yaml_dev_overlay_pattern_realistic(tmp_path: Path) -> None:
    """Realistic dev-overlay: small overlay + canonical base parses cleanly."""
    base = _write_yaml(
        tmp_path / "pilot-13.yaml",
        "seed: 42\n"
        "mlflow:\n"
        "  experiment_name: pilot-13-full\n"
        "cohort:\n"
        "  working_models:\n"
        "    - opendatalab/MinerU2.5-Pro-2604-1.2B\n"
        "    - allenai/olmOCR-2-7B-1025\n"
        "  parent_run_name: pilot-13-full\n",
    )
    overlay = _write_yaml(
        tmp_path / "pilot-13-dev.yaml",
        "mlflow:\n"
        "  experiment_name: pilot-13-dev\n"
        "cohort:\n"
        "  working_models:\n"
        "    - opendatalab/MinerU2.5-Pro-2604-1.2B\n"
        "  invoice_subset:\n"
        "    - EN16931_Einfach\n"
        "    - XRECHNUNG_Einfach\n"
        "    - EN16931_Reisekostenabrechnung\n"
        "  parent_run_name: pilot-13-dev\n"
        "  dev_only: true\n",
    )
    cfg = ExperimentConfig.from_yaml([base, overlay])
    assert cfg.cohort is not None
    assert cfg.cohort.working_models == ["opendatalab/MinerU2.5-Pro-2604-1.2B"]
    assert cfg.cohort.invoice_subset == [
        "EN16931_Einfach",
        "XRECHNUNG_Einfach",
        "EN16931_Reisekostenabrechnung",
    ]
    assert cfg.cohort.parent_run_name == "pilot-13-dev"
    assert cfg.cohort.dev_only is True
    assert cfg.mlflow.experiment_name == "pilot-13-dev"


def test_from_yaml_raises_filenotfound_on_missing_first_file(tmp_path: Path) -> None:
    """First missing file in list → FileNotFoundError mentions that path."""
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        ExperimentConfig.from_yaml([missing])


def test_from_yaml_raises_filenotfound_on_missing_overlay(tmp_path: Path) -> None:
    """Missing overlay file (with valid base) → FileNotFoundError mentions overlay."""
    base = _write_yaml(
        tmp_path / "base.yaml",
        "seed: 42\nmlflow:\n  experiment_name: x\n",
    )
    missing = tmp_path / "missing-overlay.yaml"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        ExperimentConfig.from_yaml([base, missing])


def test_from_yaml_raises_valueerror_on_empty_list() -> None:
    """Empty path list → ValueError (per `from_yaml` precondition)."""
    with pytest.raises(ValueError, match="empty list"):
        ExperimentConfig.from_yaml([])


def test_from_yaml_raises_on_non_mapping_yaml(tmp_path: Path) -> None:
    """A YAML file containing a list (not a mapping) at top-level → ValueError."""
    bad = _write_yaml(tmp_path / "bad.yaml", "- a\n- b\n- c\n")
    with pytest.raises(ValueError, match="did not parse to a mapping"):
        ExperimentConfig.from_yaml(bad)


def test_from_yaml_handles_empty_yaml_file_as_empty_dict(tmp_path: Path) -> None:
    """An empty YAML file is treated as `{}` (so it can be a no-op overlay)."""
    base = _write_yaml(
        tmp_path / "base.yaml",
        "seed: 42\nmlflow:\n  experiment_name: x\n",
    )
    empty = _write_yaml(tmp_path / "empty.yaml", "")
    cfg = ExperimentConfig.from_yaml([base, empty])
    assert cfg.seed == 42
    assert cfg.mlflow.experiment_name == "x"


def test_from_yaml_extra_keys_still_rejected_after_merge(tmp_path: Path) -> None:
    """`extra='forbid'` enforcement survives multi-file merge (defense in depth)."""
    base = _write_yaml(
        tmp_path / "base.yaml",
        "seed: 42\nmlflow:\n  experiment_name: x\n",
    )
    overlay = _write_yaml(
        tmp_path / "overlay.yaml", "unknown_top_level_key: surprise\n"
    )
    with pytest.raises(ValidationError, match="(extra|forbidden)"):
        ExperimentConfig.from_yaml([base, overlay])


def test_loads_real_pilot_13_dev_composition() -> None:
    """`configs/pilot-13.yaml` + `configs/pilot-13-dev.yaml` compose cleanly (ADR-016).

    The realistic dev-overlay regression test: the actual files shipped in
    `configs/` produce a valid `ExperimentConfig` when composed. If `pilot-13.yaml`
    changes in a way the overlay doesn't anticipate (e.g., a new required field
    added to a sub-model), this test fails first — protecting the dev loop.
    """
    base = REPO_ROOT / "configs" / "pilot-13.yaml"
    overlay = REPO_ROOT / "configs" / "pilot-13-dev.yaml"
    assert base.is_file(), f"missing base config: {base}"
    assert overlay.is_file(), f"missing dev overlay: {overlay}"

    cfg = ExperimentConfig.from_yaml([base, overlay])

    # ----- mlflow: overlay wins on experiment_name + most tags; base tags merged -----
    assert cfg.mlflow.experiment_name == "pilot-13-dev", "overlay experiment_name wins"
    assert cfg.mlflow.run_tags["stage"] == "pilot-13-dev", "overlay tag overrides base"
    assert cfg.mlflow.run_tags["issue"] == "51", "overlay tag overrides base"
    assert cfg.mlflow.run_tags["adr"] == "ADR-016", "overlay tag overrides base"
    # Inherited tags from base (not in overlay) survive.
    assert cfg.mlflow.run_tags["corpus"] == "zugferd-full"
    assert cfg.mlflow.run_tags["rasterizer"] == "pypdfium2"
    assert cfg.mlflow.run_tags["dpi"] == "300"
    assert cfg.mlflow.run_tags["xml_route"] == "facturx"

    # ----- eval: untouched by overlay; base values pass through -----
    assert cfg.eval is not None
    assert cfg.eval.anls_threshold == 0.5
    assert cfg.eval.string_normalize_nfc is True

    # ----- rasterizer: untouched by overlay; base values pass through -----
    assert cfg.rasterizer is not None
    assert cfg.rasterizer.dpi == 300

    # ----- cohort: overlay REPLACES working_models + adds invoice_subset + dev_only -----
    assert cfg.cohort is not None
    assert cfg.cohort.working_models == ["opendatalab/MinerU2.5-Pro-2604-1.2B"], (
        "1-model dev cohort fully replaces base's 7-model list (list-replacement semantics)"
    )
    assert cfg.cohort.invoice_subset == [
        "EN16931_Einfach",
        "XRECHNUNG_Einfach",
        "EN16931_Reisekostenabrechnung",
    ]
    assert cfg.cohort.dev_only is True, "HARKing-prevention forcing function active"
    assert cfg.cohort.parent_run_name == "pilot-13-dev"
    assert str(cfg.cohort.transcript_archive_dir) == "docs/sources/transcripts-multipage-dev", (
        "separate transcript dir so dev runs never pollute the 182-tuple canonical archive"
    )
    # Inherited from base.
    assert str(cfg.cohort.corpus_root) == "data/raw/german/zugferd-corpus"
    assert cfg.cohort.resume_on_existing_run is True

    # ----- seed: inherited from base; no override -----
    assert cfg.seed == 42
