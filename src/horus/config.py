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
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two dicts; later (override) wins on conflict; nested dicts merge recursively.

    Implements the YAML composition pattern documented in pydantic-settings 2.x
    (`YamlConfigSettingsSource` with `deep_merge=True`). Used by
    `ExperimentConfig.from_yaml` to compose a small dev / ablation overlay
    (`configs/pilot-13-dev.yaml`) on top of a stable base (`configs/pilot-13.yaml`)
    without duplication. Per ADR-016 §"Decision + integration thoughts".

    Semantics (matching pydantic-settings):

      - Both values are dicts → recurse (nested merge).
      - Override value is a scalar / list / None → override replaces base entirely
        (lists are NOT element-wise merged — e.g.,
        base.cohort.working_models=[A, B] + override.cohort.working_models=[C]
        → [C], not [A, B, C]).
      - Keys present only in `override` are added; keys present only in `base`
        are preserved.

    The list-replacement semantics is the canonical pydantic-settings behaviour;
    it matches user intent for the HORUS dev-overlay use case (dev YAML wants to
    REPLACE the cohort.working_models list with `[MinerU]`, not append to the
    full 7-model list from the base).
    """
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


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
    invoice_subset: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of invoice PDF stems (without `.pdf` extension) to "
            "restrict the sweep to. None (default) = score the full corpus "
            "discovered under `corpus_root`. Per ADR-016: dev configs declare "
            "their subset here (e.g., `[EN16931_Einfach, XRECHNUNG_Einfach, "
            "EN16931_Reisekostenabrechnung]`); ad-hoc CLI subsetting via the "
            "`INVOICES=...` env var on `make pilot-13` overrides this field. "
            "Each entry must match a PDF stem in the paired-invoice discovery; "
            "unmatched entries raise at harness boot (no silent skips)."
        ),
    )
    dev_only: bool = Field(
        default=False,
        description=(
            "HARKing-prevention forcing function (per ADR-016 + NeurIPS Paper "
            "Checklist + brainstorm v2 §2 No-HARKing). When true, the config "
            "is a dev fixture set used for iterative tuning ONLY — NOT for "
            "final thesis-reported F1 numbers. The harness tags every nested "
            "run with `dev_only=true` and refuses to log to the canonical "
            "`pilot-13-full` MLflow experiment (the dev YAML must declare a "
            "distinct `mlflow.experiment_name` like `pilot-13-dev`). Final "
            "reported F1 numbers must come from a `dev_only: false` config "
            "scored against the held-out test split (issue #46 substrate)."
        ),
    )
    prompt_template_override: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional per-model prompt override map (ADR-018). When set, the "
            "harness uses `prompt_template_override[model_id]` as the prompt "
            "for that model instead of the per-model default in "
            "`horus.vlm_extractor.COHORT_MANIFEST[model_id]['prompt_template']`. "
            "Partial-coverage dicts are supported: models NOT present in the "
            "override fall through to their COHORT_MANIFEST default (so a "
            "single-model probe can override only that model). Keys MUST be a "
            "subset of `working_models` — typos raise `ValueError` at boot "
            "(per the cross-field validator below). Used by the structured-"
            "output probe's two arms (uniform JSON vs per-model native+JSON; "
            "see `configs/pilot-13-structured-probe-*.yaml`) AND by any future "
            "prompt-ablation experiment (#54 if probe ratifies). Defaults to "
            "None, so all existing pilot-13 configs continue to use the "
            "COHORT_MANIFEST defaults unchanged (back-compat preserved)."
        ),
    )
    adapter_mode: Literal["regex", "json"] = Field(
        default="regex",
        description=(
            "Layer-2 adapter dispatch mode (ADR-018). 'regex' (default) uses "
            "`src/horus/eval/adapters.py` — the canonical German-label-anchored "
            "regex extractor that consumes raw OCR / DocTags / markdown VLM "
            "output and produces the 16-field predicted dict (per ADR-013). "
            "'json' uses `src/horus/eval/adapters_json.py` — the sibling "
            "JSON parser that expects single-line JSON output from a model "
            "prompted via `prompt_template_override`. Binary dispatch (NOT a "
            "pluggable framework) — at exactly 2 variants this stays under "
            "ADR-016 supersession trigger #3 (which fires past 2 variants). "
            "Setting `adapter_mode='json'` requires `prompt_template_override` "
            "to be set (validated at boot — fail-fast per `horus-config-discipline`)."
        ),
    )

    @model_validator(mode="after")
    def _validate_prompt_override_invariants(self) -> CohortConfig:
        """Two cross-field invariants for ADR-018 (catches typos + misuse at boot).

        Invariant 1: if `adapter_mode == "json"`, `prompt_template_override` MUST
        be set. The JSON adapter expects JSON-formatted output; relying on
        per-model COHORT_MANIFEST defaults (which produce regular OCR / DocTags /
        markdown) would yield F1=0 across the board.

        Invariant 2: keys in `prompt_template_override` MUST be a subset of
        `working_models`. Catches YAML typos at boot (e.g.,
        `opendatalab/mineru2.5-pro-2604-1.2b` vs the canonical PascalCase
        `opendatalab/MinerU2.5-Pro-2604-1.2B`) BEFORE any model loads.

        Mirrors the strict-matching discipline from `_filter_invoices` (ADR-016)
        and the cohort.working_models cross-check pattern from
        `tests/test_config_pilot_13.py::test_pilot_13_working_models_match_canonical_evidence_base`.
        """
        if self.adapter_mode == "json" and self.prompt_template_override is None:
            raise ValueError(
                "cohort.adapter_mode='json' requires cohort.prompt_template_override "
                "to be set (per ADR-018 §Decision + integration thoughts). The JSON "
                "adapter expects single-line JSON output from the model; relying on "
                "the per-model COHORT_MANIFEST defaults (regular OCR / DocTags / "
                "markdown) would yield F1=0 across the board. Either set "
                "prompt_template_override or use adapter_mode='regex' (default)."
            )
        if self.prompt_template_override is not None:
            unknown = set(self.prompt_template_override) - set(self.working_models)
            if unknown:
                raise ValueError(
                    f"cohort.prompt_template_override contains "
                    f"{len(unknown)} model_id keys not in cohort.working_models: "
                    f"{sorted(unknown)}. Available working_models: "
                    f"{sorted(self.working_models)}. Per ADR-018: typos in YAML "
                    f"override dicts are caught at boot (no silent fall-through "
                    f"to COHORT_MANIFEST defaults that the user didn't intend)."
                )
        return self


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
    def from_yaml(
        cls,
        cfg_paths: str | Path | list[str | Path],
    ) -> ExperimentConfig:
        """Load + validate an experiment config from one or more YAML files.

        Accepts a single path (back-compat) or a list of paths. When a list is
        given, files are loaded in order and deep-merged with later-wins
        semantics — the canonical YAML composition pattern documented in
        pydantic-settings 2.x (`YamlConfigSettingsSource` with
        `deep_merge=True`). HORUS uses this for dev / ablation variants:
        `["configs/pilot-13.yaml", "configs/pilot-13-dev.yaml"]` composes a
        small ~15-line delta over the stable base without duplication. Per
        ADR-016.

        Reads each path via `yaml.safe_load`, deep-merges them in order,
        validates the merged dict against the Pydantic schema, layers `HORUS_*`
        env vars on top, and returns the instantiated config. Raises:

        - `FileNotFoundError` if any path does not exist.
        - `ValueError` if `cfg_paths` is an empty list.
        - `pydantic.ValidationError` if the merged data fails schema validation
          (missing required field, type mismatch, extra field, …).

        All failures happen BEFORE any model loads, dataset downloads, or
        compute is spent — the fail-fast contract from `horus-config-discipline`.

        Args:
            cfg_paths: A single path (str or Path) for back-compat, OR a list
                of paths to be deep-merged in order. Later files win on conflict.

        Examples:
            >>> # Back-compat single-path usage (still works).
            >>> cfg = ExperimentConfig.from_yaml("configs/pilot-13.yaml")

            >>> # Multi-file composition (the dev-overlay pattern per ADR-016).
            >>> cfg = ExperimentConfig.from_yaml([
            ...     "configs/pilot-13.yaml",        # base
            ...     "configs/pilot-13-dev.yaml",    # dev overlay (wins on conflict)
            ... ])
        """
        paths: list[Path]
        if isinstance(cfg_paths, (str, Path)):
            paths = [Path(cfg_paths)]
        else:
            paths = [Path(p) for p in cfg_paths]
        if not paths:
            raise ValueError("from_yaml requires at least one config path; got empty list")
        merged: dict[str, Any] = {}
        for p in paths:
            if not p.is_file():
                raise FileNotFoundError(f"Config file not found: {p}")
            with p.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError(
                    f"Config file {p} did not parse to a mapping (got {type(data).__name__})"
                )
            merged = _deep_merge(merged, data)
        return cls(**merged)
