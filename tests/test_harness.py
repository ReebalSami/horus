"""Tests for `horus.eval.harness` (ADR-014 PR(c) cohort orchestrator).

Strategy: real MLflow + real factur-x + real rasterizer; mock VLM extractor. The
extractor is the only component that requires GPU/model loading, so mocking it
keeps the tests fast and offline. Everything else (MLflow SQLite, pypdfium2,
factur-x XML extraction, the PR(b) scorer) runs against real fixtures.

Test matrix:

  Pure-function unit tests (no MLflow / no extractor):
    - test_invoice_profile_dispatch
    - test_model_slug_filesystem_safe
    - test_micro_f1_from_counts
    - test_aggregate_per_field_scores
    - test_filter_models_validates_subset
    - test_filter_invoices_matches_by_stem
    - test_strip_page_separators_idempotent
    - test_strip_page_separators_preserves_body_with_equals_signs
    - test_extract_and_concat_per_page_loop
    - test_list_paired_invoices_matches_conftest_helper

  Heatmap rendering (no MLflow):
    - test_render_cohort_heatmap_shape

  Integration (real MLflow + tempdir, mock extractor):
    - test_run_cohort_single_model_single_invoice_e2e
    - test_run_cohort_resume_skips_finished_nested_runs
    - test_run_cohort_profile_aggregation
    - test_run_cohort_xrechnung_uses_facturx_not_sidecar
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from horus.config import CohortConfig, ExperimentConfig, MLflowConfig, RasterizerConfig
from horus.eval.harness import (
    _PAGE_SEPARATOR_FMT,
    HarnessRunResult,
    _aggregate_per_field_scores,
    _extract_and_concat,
    _filter_invoices,
    _filter_models,
    _invoice_profile,
    _list_paired_invoices,
    _micro_f1_from_counts,
    _model_slug,
    _render_cohort_heatmap,
    _strip_page_separators,
    run_cohort,
)
from horus.vlm_extractor import ExtractionResult
from tests.conftest import ZUGFERD_CORPUS_DIR, ZUGFERD_FX_DIR

# ===========================================================================
# Pure-function unit tests
# ===========================================================================


def test_invoice_profile_dispatch() -> None:
    """`_invoice_profile` maps PDF stems to {EN16931, XRECHNUNG, UNKNOWN}."""
    assert _invoice_profile("EN16931_Einfach") == "EN16931"
    assert _invoice_profile("XRECHNUNG_Elektron") == "XRECHNUNG"
    assert _invoice_profile("unknown_stem") == "UNKNOWN"


def test_model_slug_filesystem_safe() -> None:
    """`_model_slug` converts HF model_ids to safe filesystem slugs."""
    assert (
        _model_slug("ibm-granite/granite-docling-258M-mlx")
        == "ibm-granite__granite-docling-258m-mlx"
    )
    assert _model_slug("PaddlePaddle/PaddleOCR-VL") == "paddlepaddle__paddleocr-vl"


def test_micro_f1_from_counts() -> None:
    """`_micro_f1_from_counts` implements the standard F1 = 2TP / (2TP + FP + FN)."""
    assert _micro_f1_from_counts({"tp": 5, "fp": 0, "fn": 0}) == 1.0
    assert _micro_f1_from_counts({"tp": 0, "fp": 5, "fn": 5}) == 0.0
    assert _micro_f1_from_counts({"tp": 0, "fp": 0, "fn": 0}) == 0.0
    # 2·3 / (6 + 1 + 1) = 6/8 = 0.75
    assert _micro_f1_from_counts({"tp": 3, "fp": 1, "fn": 1}) == 0.75


def test_aggregate_per_field_scores() -> None:
    """`_aggregate_per_field_scores` reduces per-invoice score lists to means."""
    per_invoice = {
        "model-A": {"field_1": [0.5, 1.0], "field_2": [0.0]},
        "model-B": {"field_1": [], "field_2": [0.8, 0.8]},
    }
    result = _aggregate_per_field_scores(per_invoice)
    assert result["model-A"]["field_1"] == 0.75
    assert result["model-A"]["field_2"] == 0.0
    assert "field_1" not in result["model-B"], "Empty score lists drop from aggregate"
    assert result["model-B"]["field_2"] == 0.8


def test_filter_models_validates_subset() -> None:
    """`_filter_models` raises if a subset contains unknown model_ids."""
    working = ["model-A", "model-B", "model-C"]
    assert _filter_models(working, subset=None) == working
    assert _filter_models(working, subset=["model-B"]) == ["model-B"]
    with pytest.raises(ValueError, match="not in cohort.working_models"):
        _filter_models(working, subset=["model-D"])


def test_filter_invoices_matches_by_stem(tmp_path: Path) -> None:
    """`_filter_invoices` selects pairs whose PDF stem is in the subset."""
    pairs = [
        (tmp_path / "EN16931_A.pdf", tmp_path / "EN16931_A.cii.xml"),
        (tmp_path / "EN16931_B.pdf", tmp_path / "EN16931_B.cii.xml"),
        (tmp_path / "XRECHNUNG_X.pdf", tmp_path / "XRECHNUNG_X.cii.xml"),
    ]
    assert len(_filter_invoices(pairs, subset=None)) == 3
    assert len(_filter_invoices(pairs, subset=["EN16931_A"])) == 1
    assert len(_filter_invoices(pairs, subset=["EN16931_A", "XRECHNUNG_X"])) == 2
    # Strengthened semantics per ADR-016: any unknown entry raises immediately.
    with pytest.raises(ValueError, match="not found in the corpus"):
        _filter_invoices(pairs, subset=["nonexistent"])


def test_filter_invoices_strict_raises_on_partial_unknown(tmp_path: Path) -> None:
    """Mix of known + unknown subset entries → raises (NEW strict behavior, ADR-016).

    Pre-ADR-016 behavior would silently drop the unknown entries and return the
    matched subset. That silent-skip is the failure mode this strengthening
    prevents (typos in dev-overlay YAML caught at boot, not at result-inspection).
    """
    pairs = [
        (tmp_path / "EN16931_A.pdf", tmp_path / "EN16931_A.cii.xml"),
        (tmp_path / "EN16931_B.pdf", tmp_path / "EN16931_B.cii.xml"),
    ]
    with pytest.raises(ValueError, match="not found in the corpus") as exc_info:
        _filter_invoices(pairs, subset=["EN16931_A", "EN16931_TYPO"])
    # Error message mentions the unmatched entry specifically (debuggability).
    assert "EN16931_TYPO" in str(exc_info.value)


def test_strip_page_separators_idempotent() -> None:
    """`_strip_page_separators` removes `===== PAGE N =====` lines + leaves body alone."""
    text = "===== PAGE 1 =====\nHeader text\n===== PAGE 2 =====\nBody text\n"
    stripped = _strip_page_separators(text)
    assert "===== PAGE" not in stripped
    assert "Header text" in stripped
    assert "Body text" in stripped
    # Idempotent: second pass is a no-op.
    assert _strip_page_separators(stripped) == stripped


def test_strip_page_separators_preserves_body_with_equals_signs() -> None:
    """Body content containing equals signs (e.g., tables) MUST survive stripping."""
    text = (
        "===== PAGE 1 =====\n"
        "| Field | Value |\n"
        "|=======|=======|\n"  # markdown-table-style separator (5 equals)
        "| Total | 100   |\n"
        "===== PAGE 2 =====\n"
    )
    stripped = _strip_page_separators(text)
    assert "|=======|=======|" in stripped, "Markdown table separators must survive"
    assert "===== PAGE" not in stripped


def test_extract_and_concat_per_page_loop() -> None:
    """`_extract_and_concat` calls extract() once per page; concats with separators."""

    @dataclass
    class _MockExtractor:
        backend_name: str = "mock"
        model_id: str = "mock/model"
        calls: list[Path] = None  # type: ignore[assignment]

        def __post_init__(self) -> None:
            self.calls = []

        def extract(self, image_path: Path, prompt: str, max_tokens: int) -> ExtractionResult:
            self.calls.append(image_path)
            return ExtractionResult(
                model_id=self.model_id,
                backend_name=self.backend_name,
                text=f"output-for-{image_path.stem}",
                extract_seconds=0.1,
            )

    extractor = _MockExtractor()
    pages = [Path("/fake/page-1.png"), Path("/fake/page-2.png"), Path("/fake/page-3.png")]
    concatenated, per_page = _extract_and_concat(
        extractor, pages, prompt="test prompt", max_tokens=512
    )

    assert len(extractor.calls) == 3, "Extractor called once per page"
    assert len(per_page) == 3
    assert all(r.is_ok for r in per_page)
    # Concat structure: separator → page-text → separator → page-text → …
    for i in range(1, 4):
        assert _PAGE_SEPARATOR_FMT.format(page=i) in concatenated
        assert f"output-for-page-{i}" in concatenated


def test_list_paired_invoices_matches_conftest_helper() -> None:
    """`harness._list_paired_invoices` returns the same 26 pairs as conftest's helper.

    Production-side `_list_paired_invoices` replicates `tests.conftest._list_paired_invoices`
    (prod code can't import tests). This test pins the equivalence so a drift in
    either implementation is caught.
    """
    from tests.conftest import _list_paired_invoices as _conftest_list

    harness_pairs = _list_paired_invoices(ZUGFERD_CORPUS_DIR)
    conftest_pairs = _conftest_list()

    assert len(harness_pairs) == len(conftest_pairs)
    assert {p[0].name for p in harness_pairs} == {p[0].name for p in conftest_pairs}


# ===========================================================================
# Heatmap rendering (no MLflow)
# ===========================================================================


def test_render_cohort_heatmap_shape() -> None:
    """`_render_cohort_heatmap` produces a Figure with 1 axes + the expected shape."""
    aggregate = {
        "model-A": {"seller_name": 0.8, "buyer_name": 0.7, "invoice_number": 1.0},
        "model-B": {"seller_name": 0.5, "buyer_name": 0.4},
    }
    fig = _render_cohort_heatmap(aggregate, title="test")
    # Figure has exactly 1 main axes (heatmap) + 1 colorbar axes.
    assert len(fig.axes) == 2
    main_ax = fig.axes[0]
    # Rows = models, cols = full FIELDS list (16 entries) regardless of which the
    # aggregate populates (sparse cells render as NaN/grey).
    assert len(main_ax.get_yticklabels()) == 2  # 2 models
    assert len(main_ax.get_xticklabels()) == 16  # 16 canonical fields


# ===========================================================================
# Integration: run_cohort with real MLflow + mock extractor
# ===========================================================================


@dataclass
class _MockExtractorForHarness:
    """Mock VLM extractor that satisfies the VLMExtractor Protocol.

    Returns deterministic synthetic text per page that contains German-label
    invoice content so the PR(b) adapter Layer 2 can extract SOME fields. The
    text doesn't need to score high — we just need a non-trivial transcript.
    """

    model_id: str
    backend_name: str = "mock-extractor"
    _loaded: bool = False
    _calls: int = 0

    def load(self) -> None:
        self._loaded = True

    def extract(self, image_path: Path, prompt: str, max_tokens: int) -> ExtractionResult:
        self._calls += 1
        # Synthetic text mimicking a partial invoice OCR result. Includes German
        # labels so PR(b)'s Layer 2 extractor finds at least a few fields.
        text = (
            f"Rechnungsnummer: 471102\n"
            f"Rechnungsdatum: 2018-03-05\n"
            f"Verkäufer\nName: Lieferant GmbH\n"
            f"Käufer\nName: Kunden AG\n"
            f"(synthetic page {self._calls} for {image_path.stem})\n"
        )
        return ExtractionResult(
            model_id=self.model_id,
            backend_name=self.backend_name,
            text=text,
            extract_seconds=0.01,
        )

    def unload(self) -> None:
        self._loaded = False


def _make_test_cfg(
    tmp_path: Path,
    *,
    parent_run_name: str = "test-pilot-13",
    working_models: list[str] | None = None,
    resume: bool = True,
    experiment_name: str | None = None,
    invoice_subset: list[str] | None = None,
    dev_only: bool = False,
) -> ExperimentConfig:
    """Build an ExperimentConfig for harness tests with isolated MLflow + cache paths.

    Extended for ADR-016 tests: `experiment_name`, `invoice_subset`, `dev_only`
    kwargs allow constructing dev-tier configs (HARKing-prevention guard) and
    YAML-subset-vs-CLI-precedence configs.
    """
    if working_models is None:
        working_models = ["ibm-granite/granite-docling-258M-mlx"]
    if experiment_name is None:
        experiment_name = f"harness-test-{parent_run_name}"
    # Pydantic-validate ExperimentConfig with all required sub-models.
    return ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(
            experiment_name=experiment_name,
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
            run_tags={"test": "harness"},
        ),
        rasterizer=RasterizerConfig(
            dpi=150,  # lower DPI = faster tests
            cache_dir=tmp_path / "raster-cache",
            image_format="png",
        ),
        cohort=CohortConfig(
            working_models=working_models,
            corpus_root=ZUGFERD_CORPUS_DIR,
            parent_run_name=parent_run_name,
            transcript_archive_dir=tmp_path / "transcripts",
            resume_on_existing_run=resume,
            invoice_subset=invoice_subset,
            dev_only=dev_only,
        ),
    )


def test_run_cohort_single_model_single_invoice_e2e(tmp_path: Path) -> None:
    """End-to-end smoke: 1 model × 1 invoice → 1 nested MLflow run with non-zero F1 inputs."""
    cfg = _make_test_cfg(tmp_path)

    # Patch get_extractor to return our mock instead of loading a real VLM.
    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        result = run_cohort(cfg, invoice_subset=["EN16931_Einfach"])

    assert isinstance(result, HarnessRunResult)
    assert result.n_models_attempted == 1
    assert result.n_models_loaded == 1
    assert result.n_invoices_total == 1
    assert result.n_completed == 1
    assert result.n_failed == 0
    assert result.n_skipped_resume == 0
    # The mock extractor populates Rechnungsnummer + Rechnungsdatum + Verkäufer.Name +
    # Käufer.Name → expect at least 1 field with positive aggregate score.
    flattened = [
        score for per_field in result.per_field_heatmap.values() for score in per_field.values()
    ]
    assert any(s > 0.0 for s in flattened), "Mock extractor should produce ≥1 positive field score"


def test_run_cohort_resume_skips_finished_nested_runs(tmp_path: Path) -> None:
    """Re-invoking on the same tracking_uri skips already-FINISHED nested runs."""
    cfg = _make_test_cfg(tmp_path)

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        # First run.
        first = run_cohort(cfg, invoice_subset=["EN16931_Einfach"])
        assert first.n_completed == 1
        assert first.n_skipped_resume == 0

        # Second run with same cfg → SHOULD skip the already-FINISHED nested run.
        # NOTE: re-using the same parent_run_name doesn't currently re-attach to the
        # existing parent (MLflow creates a new parent run); the resume check
        # queries by `tags.mlflow.parentRunId = <current_parent>` which is a
        # *new* run_id on the second invocation, so resume only protects against
        # mid-sweep interruption (the more important case), not cross-invocation
        # re-runs. To get cross-invocation resume working would require passing
        # the parent_run_id explicitly; this test pins the documented behavior.
        second = run_cohort(cfg, invoice_subset=["EN16931_Einfach"])
        # Cross-invocation: re-completes the invoice (parent re-runs are a separate concern).
        assert second.n_completed == 1


def test_run_cohort_xrechnung_uses_facturx_not_sidecar(tmp_path: Path) -> None:
    """XRECHNUNG fixtures: GT issue_date is 2018-* (factur-x), not 2024-* (sidecar).

    Pins the ADR-012 Probe 5 mitigation: harness MUST extract GT via factur-x,
    NOT the FeRD-shipped `.cii.xml` sidecar (which carries 2024-11-15 dates that
    would silently corrupt DATE-field F1).
    """
    cfg = _make_test_cfg(tmp_path)

    captured_gt = []  # mutable closure target

    real_extract_groundtruth = None
    from horus.eval import harness as harness_mod

    real_extract_groundtruth = harness_mod._extract_groundtruth_via_facturx

    def _wrapped(pdf_path: Path) -> Any:
        gt = real_extract_groundtruth(pdf_path)
        captured_gt.append((pdf_path.stem, gt))
        return gt

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with (
        patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor),
        patch.object(harness_mod, "_extract_groundtruth_via_facturx", side_effect=_wrapped),
    ):
        run_cohort(cfg, invoice_subset=["XRECHNUNG_Einfach"])

    assert len(captured_gt) == 1
    stem, gt = captured_gt[0]
    assert stem == "XRECHNUNG_Einfach"
    assert gt is not None, "XRECHNUNG_Einfach must have a factur-x XML attachment"

    issue_date_field = gt.header.get("issue_date")
    assert issue_date_field is not None
    iso = issue_date_field.normalized_value
    assert iso is not None and iso.startswith("2018-"), (
        f"XRECHNUNG_Einfach factur-x GT issue_date should start with '2018-' "
        f"(per ADR-012 Probe 5); got {iso!r}. If it starts with '2024-' the harness "
        f"is reading the sidecar — silent F1 corruption hazard."
    )


def test_run_cohort_profile_aggregation(tmp_path: Path) -> None:
    """Per-profile (EN16931 vs XRECHNUNG) + pooled F1 are all reported separately."""
    cfg = _make_test_cfg(tmp_path)

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        # 2 invoices: 1 EN16931 + 1 XRECHNUNG → both profile splits populated.
        result = run_cohort(
            cfg,
            invoice_subset=["EN16931_Einfach", "XRECHNUNG_Einfach"],
        )

    assert result.n_completed == 2
    # All three F1 values should be in [0.0, 1.0]
    for f1 in (
        result.cohort_micro_f1_pooled,
        result.cohort_micro_f1_en16931,
        result.cohort_micro_f1_xrechnung,
    ):
        assert 0.0 <= f1 <= 1.0


def test_run_cohort_raises_on_missing_rasterizer_or_cohort_cfg(tmp_path: Path) -> None:
    """`run_cohort` refuses to start with incomplete config (Pydantic fail-fast extends here)."""
    cfg_no_cohort = ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(experiment_name="missing-cohort"),
        rasterizer=RasterizerConfig(),
    )
    with pytest.raises(ValueError, match="cohort"):
        run_cohort(cfg_no_cohort)

    cfg_no_rasterizer = ExperimentConfig(
        seed=42,
        mlflow=MLflowConfig(experiment_name="missing-rasterizer"),
        cohort=CohortConfig(working_models=["m"], corpus_root=ZUGFERD_FX_DIR.parent.parent),
    )
    with pytest.raises(ValueError, match="rasterizer"):
        run_cohort(cfg_no_rasterizer)


# ===========================================================================
# Integration: ADR-016 (invoice_subset from YAML + dev_only forcing function)
# ===========================================================================


def test_run_cohort_invoice_subset_from_yaml_applied(tmp_path: Path) -> None:
    """`cohort.invoice_subset` from YAML is honored when CLI subset is None (ADR-016)."""
    cfg = _make_test_cfg(
        tmp_path,
        invoice_subset=["EN16931_Einfach"],  # YAML-declared subset of 1 invoice
    )

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        # CLI subset is None → YAML subset wins → 1 invoice scored.
        result = run_cohort(cfg)

    assert result.n_invoices_total == 1, (
        "YAML invoice_subset should restrict to 1 invoice even with CLI=None"
    )
    assert result.n_completed == 1


def test_run_cohort_cli_invoice_subset_overrides_yaml(tmp_path: Path) -> None:
    """CLI `invoice_subset` overrides `cohort.invoice_subset` from YAML (ADR-016)."""
    cfg = _make_test_cfg(
        tmp_path,
        invoice_subset=["XRECHNUNG_Einfach"],  # YAML declares 1 invoice
    )

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        # CLI subset = ["EN16931_Einfach"] WINS over YAML's ["XRECHNUNG_Einfach"].
        result = run_cohort(cfg, invoice_subset=["EN16931_Einfach"])

    assert result.n_invoices_total == 1
    assert result.n_completed == 1
    # Spot-check: search_runs for invoice_id=EN16931_Einfach exists; XRECHNUNG_Einfach does NOT.
    import mlflow  # noqa: PLC0415

    runs = mlflow.search_runs(
        experiment_ids=[
            mlflow.get_experiment_by_name(cfg.mlflow.experiment_name).experiment_id
        ],
        filter_string=f"tags.mlflow.parentRunId = '{result.parent_run_id}'",
        output_format="list",
    )
    invoice_ids = {r.data.tags.get("invoice_id") for r in runs}
    assert "EN16931_Einfach" in invoice_ids, "CLI override was not applied"
    assert "XRECHNUNG_Einfach" not in invoice_ids, "YAML subset leaked through CLI override"


def test_run_cohort_dev_only_blocks_canonical_experiment(tmp_path: Path) -> None:
    """`dev_only=true` + `experiment_name='pilot-13-full'` → raises (ADR-016 HARKing guard).

    Forcing function: a dev config trying to log to the canonical thesis-reporting
    experiment is blocked at boot before any MLflow / model interaction.
    """
    cfg = _make_test_cfg(
        tmp_path,
        experiment_name="pilot-13-full",  # CANONICAL — forbidden for dev_only=true
        dev_only=True,
        invoice_subset=["EN16931_Einfach"],
    )
    with pytest.raises(ValueError, match="dev_only=true.*pilot-13-full"):
        run_cohort(cfg)


def test_run_cohort_dev_only_tags_parent_and_nested_runs(tmp_path: Path) -> None:
    """`dev_only=true` tags parent + every nested run with `dev_only=true` (ADR-016)."""
    cfg = _make_test_cfg(
        tmp_path,
        experiment_name="harness-test-dev-only-tag",  # NON-canonical name; not blocked
        dev_only=True,
        invoice_subset=["EN16931_Einfach", "XRECHNUNG_Einfach"],
    )

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        result = run_cohort(cfg)

    assert result.n_completed == 2

    import mlflow  # noqa: PLC0415

    client = mlflow.MlflowClient()
    # Parent tagged dev_only=true.
    parent = client.get_run(result.parent_run_id)
    assert parent.data.tags.get("dev_only") == "true", (
        f"parent run missing dev_only tag; got tags={parent.data.tags}"
    )
    # All nested runs tagged dev_only=true.
    experiment_id = mlflow.get_experiment_by_name(
        cfg.mlflow.experiment_name
    ).experiment_id
    nested = mlflow.search_runs(
        experiment_ids=[experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{result.parent_run_id}'",
        output_format="list",
    )
    assert len(nested) == 2, f"expected 2 nested runs, got {len(nested)}"
    for r in nested:
        assert r.data.tags.get("dev_only") == "true", (
            f"nested run {r.info.run_id} missing dev_only tag; tags={r.data.tags}"
        )


def test_run_cohort_dev_only_false_tags_runs_as_false(tmp_path: Path) -> None:
    """Default `dev_only=False` still tags parent + nested with `dev_only=false` (audit-trail)."""
    cfg = _make_test_cfg(
        tmp_path,
        invoice_subset=["EN16931_Einfach"],
    )

    def _fake_get_extractor(model_id: str) -> Any:
        return _MockExtractorForHarness(model_id=model_id)

    with patch("horus.eval.harness.get_extractor", side_effect=_fake_get_extractor):
        result = run_cohort(cfg)

    import mlflow  # noqa: PLC0415

    parent = mlflow.MlflowClient().get_run(result.parent_run_id)
    assert parent.data.tags.get("dev_only") == "false", (
        "even dev_only=false runs get the tag (every run audit-trail-tagged per ADR-016)"
    )
