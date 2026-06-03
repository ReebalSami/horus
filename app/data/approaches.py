"""The three extraction approaches the dashboard compares (ADR-034 / ADR-038).

Each approach is described once here, and its runtime facts (MLflow experiment
name, model, transcript directory, rasterizer settings, corpus root) are READ
from the very same `configs/*.yaml` the research pipeline uses — never hard-coded.
Composing `[pilot-13.yaml, <arm>.yaml]` through `ExperimentConfig` means the app
and the pipeline can never silently disagree about where an approach's data lives.

  - baseline — specialist reader (Granite) + hand-written regex parser.
  - arm_a    — one general model (Gemma) reads + structures in a single shot.
  - arm_b    — specialist reader (Granite) transcribes, then Gemma structures.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from horus.config import ExperimentConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = REPO_ROOT / "configs"

# Page images are rendered for on-screen display only; 150 DPI (~1240px on A4) is
# crisp enough and far lighter than the pipeline's 300 DPI. A dedicated cache dir
# keeps these previews from clobbering the harness's full-resolution renders.
_PREVIEW_DPI = 150
_PREVIEW_CACHE = REPO_ROOT / "data" / "raw" / "smoke" / "app-preview"


@dataclass(frozen=True)
class _Spec:
    """Static presentation metadata for one approach (the part not in the YAML)."""

    key: str
    short_name: str
    display_name: str
    tagline: str
    description: str
    accent_hex: str
    model_label: str
    config_names: tuple[str, ...]


@dataclass(frozen=True)
class Approach:
    """An extraction approach: presentation metadata + runtime facts from its config."""

    key: str
    short_name: str
    display_name: str
    tagline: str
    description: str
    accent_hex: str
    model_label: str
    experiment_name: str
    model_id: str
    reader_model_id: str | None
    transcript_dir: Path
    corpus_root: Path
    raster_dpi: int
    raster_cache_dir: Path
    # The working model's prompt override from the arm's config
    # (`cohort.prompt_template_override[model_id]`), or None when the arm relies
    # on the COHORT_MANIFEST default (the regex baseline). Used by the live demo
    # page (ADR-039) so it reads the prompt from config, never hard-coded.
    prompt: str | None


_SPECS: tuple[_Spec, ...] = (
    _Spec(
        key="baseline",
        short_name="Baseline",
        display_name="Regex baseline",
        tagline="Specialist reader + hand-written rules",
        description=(
            "A specialist document reader (Granite-Docling) transcribes the page, then a "
            "hand-written German-label regex parser pulls out the fields. Brittle by design "
            "and never invents a value — the auditable reference point the two model-driven "
            "methods are measured against."
        ),
        accent_hex="#6F8A92",  # muted slate-teal
        model_label="Granite-Docling 258M → regex",
        config_names=("pilot-13.yaml", "baseline-regex.yaml"),
    ),
    _Spec(
        key="arm_a",
        short_name="Method A",
        display_name="Single-shot",
        tagline="One general model reads + structures in one step",
        description=(
            "A single general vision-language model (Gemma) looks at the page image and emits "
            "the structured fields directly, in one shot — no specialist reader in front of it."
        ),
        accent_hex="#0E4D45",  # deep teal
        model_label="Gemma 4 E4B (single-shot)",
        config_names=("pilot-13.yaml", "arm-a.yaml"),
    ),
    _Spec(
        key="arm_b",
        short_name="Method B",
        display_name="Read-then-structure",
        tagline="Specialist reader feeds a general structurer",
        description=(
            "A specialist reader (Granite-Docling) transcribes the page first, then a general "
            "model (Gemma) turns that text into structured fields. Best accuracy on the dev set "
            "— and it invented nothing."
        ),
        accent_hex="#C9A227",  # antique gold — the winner
        model_label="Granite-Docling → Gemma 4 E4B",
        config_names=("pilot-13.yaml", "arm-b.yaml"),
    ),
)


def _resolve(path: Path) -> Path:
    """Resolve a possibly-relative config path against the repo root."""
    return path if path.is_absolute() else (REPO_ROOT / path)


@lru_cache(maxsize=1)
def load_approaches() -> tuple[Approach, ...]:
    """Compose each approach's config and return the resolved `Approach` records.

    Cached for the process: the underlying YAML is small and static, and the
    Streamlit app re-calls this on every rerun.
    """
    approaches: list[Approach] = []
    for spec in _SPECS:
        cfg_paths: list[str | Path] = [str(CONFIGS_DIR / name) for name in spec.config_names]
        cfg = ExperimentConfig.from_yaml(cfg_paths)
        cohort = cfg.cohort
        if cohort is None or not cohort.working_models:
            raise ValueError(f"approach {spec.key!r}: config is missing a cohort/working_models")
        model_id = cohort.working_models[0]
        overrides = cohort.prompt_template_override or {}
        approaches.append(
            Approach(
                key=spec.key,
                short_name=spec.short_name,
                display_name=spec.display_name,
                tagline=spec.tagline,
                description=spec.description,
                accent_hex=spec.accent_hex,
                model_label=spec.model_label,
                experiment_name=cfg.mlflow.experiment_name,
                model_id=model_id,
                reader_model_id=cohort.reader_model_id,
                transcript_dir=_resolve(cohort.transcript_archive_dir),
                corpus_root=_resolve(cohort.corpus_root),
                raster_dpi=_PREVIEW_DPI,
                raster_cache_dir=_PREVIEW_CACHE,
                prompt=overrides.get(model_id),
            )
        )
    return tuple(approaches)


def get_approach(key: str) -> Approach:
    """Return the approach with the given key (`baseline` / `arm_a` / `arm_b`)."""
    for approach in load_approaches():
        if approach.key == key:
            return approach
    raise KeyError(key)
