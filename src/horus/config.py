"""HORUS experiment configuration schema.

Single source of truth for an experiment's knobs. Loaded via
`ExperimentConfig.from_yaml(cfg_path)` from `configs/<slug>.yaml`. Pydantic
validates at boot — any malformed YAML, missing required field, type mismatch,
or extra (unrecognised) field raises `pydantic.ValidationError` BEFORE any
model loads, dataset downloads, or compute is spent. This is the architectural
forcing function described by `.windsurf/rules/horus-config-discipline.md`
and ratified by `docs/decisions/ADR-004-config-library.md`.

`HORUS_*` env vars layer on top of the YAML data (per pydantic-settings source
ordering) for secrets-style overrides — e.g., `HORUS_MLFLOW__TRACKING_URI`
overrides `mlflow.tracking_uri` when set in the shell environment. The double
underscore (`__`) is the nested-delimiter convention from `pydantic-settings`.

The schema is intentionally minimal at Bundle 2 close. It grows per experiment:
when M2D.5 step 6 authors the first Granite-Docling pilot, that experiment's
ADR extends this schema with `model: ModelConfig`, `dataset: DatasetConfig`,
`eval: EvalConfig`, etc. — each addition is a code change reviewable in PR.

Example (the canonical experiment-boot pattern):
    from horus.config import ExperimentConfig
    from horus.seeding import set_global_seed

    cfg = ExperimentConfig.from_yaml("configs/granite-pilot.yaml")
    set_global_seed(cfg.seed)
    # ... cfg.mlflow.experiment_name, cfg.mlflow.run_tags ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLflowConfig(BaseModel):
    """MLflow tracking metadata (sub-model of `ExperimentConfig`)."""

    model_config = ConfigDict(extra="forbid")

    experiment_name: str = Field(
        description="MLflow experiment name (e.g., 'granite-pilot').",
    )
    run_tags: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Tags applied to the MLflow run (e.g., {'stage': 'pilot', 'cohort': 'granite'})."
        ),
    )
    tracking_uri: str | None = Field(
        default=None,
        description=(
            "MLflow tracking URI; None = local file:./mlruns. "
            "Override at run-time via the `HORUS_MLFLOW__TRACKING_URI` env var."
        ),
    )


class EvalConfig(BaseModel):
    """Per-field F1 scoring knobs (sub-model of `ExperimentConfig`).

    Tunes PR(b)'s scorer (`src/horus/eval/scorer.py`) per ADR-013. Every knob
    has a literature-default — pilots that don't override these inherit the
    Biten+ ICCV'19 + DocILE-aligned behavior. Override via YAML
    (`configs/pilot-13-eval.yaml`) or `HORUS_EVAL__*` env vars.

    Refs:
      - `docs/decisions/ADR-013-vlm-prediction-scorer.md` (this sub-model's
        ratifying ADR).
      - `docs/sources/papers/biten-2019-anls-iccv.md` (ANLS threshold rationale).
      - `docs/sources/tools/docile-rossumai.md` (tolerance-windows precedent).
      - `.windsurf/rules/horus-config-discipline.md` (this is the architectural
        forcing function — knobs live HERE, not in `.py` constants).
    """

    model_config = ConfigDict(extra="forbid")

    anls_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "ANLS* threshold (Biten+ ICCV'19): NLS scores below this collapse "
            "to 0.0; scores at or above pass through unchanged. Applied by the "
            "STRING-type comparator (seller_name, buyer_name). 0.5 is the "
            "literature default; the pilot may tune this per `horus-config-discipline`."
        ),
    )
    money_tolerance_cents: int = Field(
        default=0,
        ge=0,
        description=(
            "Allowed |predicted - gt| in integer cents for the MONEY comparator. "
            "0 = strict (exact 2-decimal Decimal match). Reserved for a future "
            "amendment if the pilot finds models systematically off-by-rounding; "
            "default keeps Vorsteuerabzug strict."
        ),
    )
    date_tolerance_days: int = Field(
        default=0,
        ge=0,
        description=(
            "Allowed |predicted - gt| in days for the DATE comparator. 0 = strict "
            "(exact ISO-8601 match). Reserved for a future amendment if VLMs "
            "systematically misread DD/MM."
        ),
    )
    string_normalize_nfc: bool = Field(
        default=True,
        description=(
            "If true, apply Unicode NFC to predicted strings before STRING/CODE "
            "comparison (matches PR(a)'s GT-side normalizer; ensures 'München' "
            "in composed vs decomposed form compares equal)."
        ),
    )
    log_excluded_to_dict: bool = Field(
        default=True,
        description=(
            "If true, include EXCLUDED (normalizer-rejected GT) FieldResult "
            "entries in the per_field dict logged to MLflow. Useful for "
            "diagnostics; doesn't affect F1 numerators or denominators "
            "(EXCLUDED already drops from both per ADR-013 §Truth table)."
        ),
    )


class RasterizerConfig(BaseModel):
    """Multi-page PDF rasterization knobs (sub-model of `ExperimentConfig`).

    Tunes PR(c)'s rasterizer (`src/horus/eval/rasterize.py`) per ADR-014. Every
    knob has a default chosen to match the legacy `sips --resampleWidth 2480`
    page-1 baseline (`Makefile:89-91` pre-PR(c) `make cohort-smoke`) — meaning
    per-cohort-model `longest_edge=2048` internal resize (ADR-007) is unchanged.

    Refs:
      - `docs/decisions/ADR-014-cohort-harness-multipage.md` (this sub-model's
        ratifying ADR — forthcoming).
      - `docs/sources/tools/pypdfium2.md` (rasterizer source archival).
      - `.windsurf/rules/horus-config-discipline.md` (architectural forcing
        function — knobs live HERE, not in `.py` constants).
    """

    model_config = ConfigDict(extra="forbid")

    dpi: int = Field(
        default=300,
        ge=72,
        le=600,
        description=(
            "Rasterization DPI. Default 300 (A4 width 2480 px, matching the "
            "legacy `sips --resampleWidth 2480` baseline + ADR-007's per-model "
            "`longest_edge=2048` internal resize ceiling). Range [72, 600] is "
            "sensible; below 72 loses body-text legibility, above 600 wastes "
            "compute past the cohort internal resize."
        ),
    )
    cache_dir: Path = Field(
        default=Path("data/raw/smoke/multipage"),
        description=(
            "Directory under which per-PDF rasterized PNGs are cached. Outputs "
            "land at `<cache_dir>/<pdf_stem>/page-<N>.<ext>`. mtime-based "
            "invalidation (PDF newer than PNG → re-render) makes the cache "
            "load-bearing for harness resume-safety. Gitignored at "
            "`data/raw/smoke/multipage/`."
        ),
    )
    image_format: Literal["png", "jpeg"] = Field(
        default="png",
        description=(
            "Output image format. 'png' (default; lossless, matches existing "
            "per-model smoke artifact convention) or 'jpeg' (lossy, smaller "
            "files — useful only if disk pressure becomes a constraint on "
            "the 26 × 7 cohort sweep)."
        ),
    )


class CohortConfig(BaseModel):
    """Pilot-13 cohort orchestration knobs (sub-model of `ExperimentConfig`).

    Tunes PR(c)'s harness (`src/horus/eval/harness.py`) per ADR-014. Defines
    which cohort models participate in the sweep, where the ZUGFeRD corpus
    lives, where transcripts are archived, and whether to resume from
    already-finished MLflow nested runs on re-invocation.

    `working_models` is intentionally required (no default) so each pilot
    config explicitly declares its cohort — preventing silent drift when
    ADR-009 adds or removes members. The 3 ADR-009 errored models (DeepSeek-
    OCR-2, Qwen3-VL-4B-Instruct, Molmo-7B-D) are simply absent from the
    `working_models` list — they aren't hard-excluded by code.

    Refs:
      - `docs/decisions/ADR-014-cohort-harness-multipage.md` (this sub-model's
        ratifying ADR — forthcoming).
      - `docs/decisions/ADR-009-pilot-vlm-cohort.md` + Amendment 1 (cohort
        manifest substrate — the 10-model 3-Cat foundation).
      - `tests/test_scorer_integration.WORKING_TRANSCRIPTS` (7 working model
        transcripts; this list is the canonical evidence base for the
        `working_models` field's expected contents).
    """

    model_config = ConfigDict(extra="forbid")

    working_models: list[str] = Field(
        description=(
            "Cohort model IDs to run in the sweep (HuggingFace canonical IDs "
            "matching `horus.vlm_extractor.COHORT_MANIFEST` keys). The 7 "
            "working models from ADR-009 are the expected default at PR(c) "
            "landing; the 3 errored models are not included here. Adding a "
            "model that isn't in COHORT_MANIFEST raises at harness boot."
        ),
        min_length=1,
    )
    corpus_root: Path = Field(
        default=Path("data/raw/german/zugferd-corpus"),
        description=(
            "Root of the ZUGFeRD test corpus. Paired-invoice discovery walks "
            "`<corpus_root>/XML-Rechnung/FX/*.pdf` × "
            "`<corpus_root>/XML-Rechnung/CII/*.cii.xml`. Currently the only "
            "supported corpus; non-ZUGFeRD corpora are ADR-014 supersession "
            "trigger (b)."
        ),
    )
    parent_run_name: str = Field(
        default="pilot-13-full",
        description=(
            "MLflow parent run name. Per-(model, invoice) nested runs hang "
            "under this parent. Re-using the same name on a resume run "
            "re-attaches to the existing parent via search_runs lookup. "
            "Change for ablation runs (e.g., `pilot-13-tau-03` for the "
            "τ=0.3 threshold-sensitivity branch)."
        ),
    )
    transcript_archive_dir: Path = Field(
        default=Path("docs/sources/transcripts-multipage"),
        description=(
            "Directory under which concatenated per-(model, invoice) "
            "transcripts are saved as `.txt` artifacts. Paths land at "
            "`<dir>/<model_slug>__<invoice_stem>.txt`. Committed to the repo "
            "as ADR-014 §Decision smoke evidence."
        ),
    )
    resume_on_existing_run: bool = Field(
        default=True,
        description=(
            "If true (default), skip per-(model, invoice) nested runs whose "
            "tags already match a FINISHED MLflow run under the parent. "
            "Makes the cohort sweep interruptible: ctrl-c → re-invoke → "
            "harness picks up where left off. Set false for fresh runs "
            "(e.g., after deleting `mlflow.db` for a clean re-baseline)."
        ),
    )


class ExperimentConfig(BaseSettings):
    """Single source of truth for an experiment's knobs.

    Loaded via `ExperimentConfig.from_yaml(cfg_path)` from
    `configs/<slug>.yaml`. `HORUS_*` env vars layer on top via
    `pydantic-settings` source ordering.

    Extend per experiment as needed: add new sub-models (`ModelConfig`,
    `DatasetConfig`, `EvalConfig`, etc.) as required fields here, with
    sensible Pydantic types + descriptions. Every knob lives in YAML;
    nothing is hardcoded in `.py` files outside this module
    (per `horus-config-discipline`).
    """

    model_config = SettingsConfigDict(
        env_prefix="HORUS_",
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=False,
    )

    seed: int = Field(
        description=(
            "Global RNG seed (Python, NumPy, PyTorch via `horus.seeding.set_global_seed`)."
        ),
    )
    mlflow: MLflowConfig
    eval: EvalConfig | None = Field(
        default=None,
        description=(
            "Optional per-field F1 scoring knobs (ADR-013). Required only for "
            "experiments that invoke the PR(b) scorer "
            "(e.g., `configs/pilot-13-eval.yaml`); existing experiments without "
            "an `eval:` YAML section continue to work unchanged."
        ),
    )
    rasterizer: RasterizerConfig | None = Field(
        default=None,
        description=(
            "Optional multi-page rasterization knobs (ADR-014). Required only "
            "for experiments that invoke the PR(c) harness "
            "(e.g., `configs/pilot-13.yaml`); existing experiments without a "
            "`rasterizer:` YAML section continue to work unchanged."
        ),
    )
    cohort: CohortConfig | None = Field(
        default=None,
        description=(
            "Optional cohort orchestration knobs (ADR-014). Required only for "
            "experiments that invoke the PR(c) harness; existing experiments "
            "without a `cohort:` YAML section continue to work unchanged."
        ),
    )

    @classmethod
    def from_yaml(cls, cfg_path: str | Path) -> ExperimentConfig:
        """Load + validate an experiment config from a YAML file.

        Reads `cfg_path` via `yaml.safe_load`, validates the result against the
        Pydantic schema, layers `HORUS_*` env vars on top, and returns the
        instantiated config. Raises:

        - `FileNotFoundError` if `cfg_path` does not exist.
        - `pydantic.ValidationError` if the YAML data fails schema validation
          (missing required field, type mismatch, extra field, …).

        Both classes of failure happen BEFORE any model loads, dataset
        downloads, or compute is spent — the fail-fast contract from
        `horus-config-discipline`.
        """
        path = Path(cfg_path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
