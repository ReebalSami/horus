"""Structured-output probe verdict matrix — ADR-019 W3.2 + ADR-021.

Computes the 2 × 2 verdict matrix that crosses (denominator) × (threshold)
for the structured-output probe (#53):

    | denominator           | pre-registered          | amended (F1≥0.1) |
    |-----------------------|-------------------------|------------------|
    | N of 7 (D2 = COUNT)   | cell A                  | cell B           |
    | N of 6 (D2 = FLAG)    | cell C                  | cell D           |

**Pre-registered threshold** (ADR-018 §"Pre-registered conditional verdict"):
``(json_validity=True, canonical_keys≥12)``. Per-arm conjunctive.

**Amended threshold** (ADR-019 §"Wave 3.2"; ratified by ADR-021): adds a value-
non-trivial gate ``(... ∧ micro_F1≥0.1)`` to defend against schema-mimicry —
GLM-OCR Arm A passes the pre-registered threshold with 16 placeholder
``<BT-N>`` keys (F1=0); the amended threshold catches this. Methodology-
discovery, NOT goalpost-move (ADR-019 §"Threshold-design gap (B4)").

**N-of-7 denominator** (D2 = COUNT): every working model in ADR-018's
working_models list contributes to ``n_total``. Honors the pre-registration
strictly.

**N-of-6 denominator** (D2 = FLAG): PaliGemma2 (a base VLM per HF model card,
emits explicit refusal in Arm A; pre-registration error per ADR-019 B8) is
excluded from BOTH ``n_passing`` AND ``n_total``. The flag is structural —
even if the model hypothetically passed, the N-of-6 cell excludes it.

**Per-model combined-max-per-arm rule** (pre-registered ADR-018): a model
passes if EITHER arm satisfies the threshold. ``arm_a is None and arm_b is
None`` → fails by construction.

**FILE / DEFER decision**: ``n_passing ≥ pass_count_threshold`` (default 3
per ADR-018) → FILE; else DEFER. The threshold count is NOT amended — only
the per-arm criterion is amended (which is what "amended threshold" means).

The matrix is purely additive over the existing pre-registered threshold;
there is no mutation of any existing threshold logic. Each cell is
independently reported so the reader sees which methodology lens flips
which verdicts.

Refs: ADR-019 (parent — bug catalog + Wave 3.2 architecture), ADR-018
(parent probe + pre-registered threshold), ADR-021 (forthcoming —
threshold + denominator dual-verdict ratification),
``tests/test_probe_verdict.py`` (per-cell coverage matrix).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Constants — pre-registered + amended threshold defaults
# ---------------------------------------------------------------------------

# Per ADR-018 §"Pre-registered conditional verdict": canonical_keys ≥ 12 of 16.
DEFAULT_CANONICAL_KEYS_MIN: int = 12

# Per ADR-018 §"Pre-registered conditional verdict": ≥ 3 of N models pass.
DEFAULT_PASS_COUNT_THRESHOLD: int = 3

# Per ADR-019 §"Threshold-design gap (B4)" + ADR-021 (forthcoming):
# value-non-trivial gate. F1=0.1 is permissive — even a single TP among
# 16 fields reaches micro_F1 ≈ 0.067; 2 TPs without FPs reach ~0.125.
# The gate excludes 0 TP cases (schema-mimicry: 16 placeholder keys, F1=0)
# without excluding partial-extraction cases.
DEFAULT_F1_MIN_AMENDED: float = 0.1

# Per ADR-019 §B8: PaliGemma2 is a base VLM (HF model card knowable at probe-
# design time per ADR-009 §smoke); inclusion in the threshold tally was a
# pre-registration error. The N-of-6 cell flags this model out structurally.
DEFAULT_PALIGEMMA_MODEL_ID: str = "google/paligemma2-3b-mix-448"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelArmScore:
    """Per-(model, arm) metrics consumed by the verdict matrix.

    Three fields cover the full threshold surface:

      - ``json_validity``: True iff ≥1 page of this (model, arm) tuple
        produced parseable JSON. Maps to ADR-018 §"Pre-registered conditional
        verdict" criterion #1.
      - ``canonical_keys``: count of FIELDS keys that the multipage adapter
        recovered (i.e., non-None values in the predicted_dict). Maps to
        ADR-018 criterion #2 (``canonical_keys ≥ 12``).
      - ``micro_f1``: micro F1 against the XML-grounded ground truth across
        the 16 fields. Used by the amended threshold (ADR-021 §"F1 gate").

    Constructed by the rescore script (Phase 4) from per-invoice score lists.
    Kept frozen so verdict-matrix construction is deterministic.
    """

    json_validity: bool
    canonical_keys: int
    micro_f1: float


@dataclass(frozen=True)
class ModelScore:
    """Per-model metrics across both probe arms.

    ``arm_a is None`` indicates the (model, arm A) tuple was not run / has no
    rescore data; same for ``arm_b``. A model with both arms None fails the
    threshold by construction (no evidence of compliance).

    Per the combined-max-per-arm rule (ADR-018): the model passes the
    threshold if EITHER arm satisfies it.
    """

    model_id: str
    arm_a: ModelArmScore | None  # uniform JSON arm
    arm_b: ModelArmScore | None  # native task prefix + JSON suffix arm


@dataclass(frozen=True)
class CellVerdict:
    """One cell of the 2×2 verdict matrix.

    Attributes:
        passing_models: tuple of model_ids that pass the cell's criteria
            (sorted alphabetically for determinism across Python dict
            iteration order).
        failing_models: tuple of model_ids that fail (also sorted).
        n_passing: ``len(passing_models)``.
        n_total: ``len(passing_models) + len(failing_models)``. For N-of-6
            cells, PaliGemma is excluded from BOTH lists, so ``n_total`` is
            reduced by 1 if PaliGemma was in the input.
        verdict: ``"FILE"`` if ``n_passing ≥ pass_count_threshold`` else
            ``"DEFER"``. The decision threshold is the same across all 4
            cells (only the per-arm criterion + denominator vary).
    """

    passing_models: tuple[str, ...]
    failing_models: tuple[str, ...]
    n_passing: int
    n_total: int
    verdict: Literal["FILE", "DEFER"]


@dataclass(frozen=True)
class VerdictMatrix:
    """The full 2×2 verdict matrix (denominator × threshold).

    Field naming: ``<threshold>_<denominator>``:

      - ``pre_registered_n_of_7``: pre-registered threshold, all models counted
      - ``pre_registered_n_of_6``: pre-registered threshold, PaliGemma flagged
      - ``amended_n_of_7``: amended threshold (F1≥0.1), all models counted
      - ``amended_n_of_6``: amended threshold, PaliGemma flagged

    Rendering as a markdown table for ADR-018 amendment / retro consumption is
    the caller's responsibility (this module is data-only).
    """

    pre_registered_n_of_7: CellVerdict
    pre_registered_n_of_6: CellVerdict
    amended_n_of_7: CellVerdict
    amended_n_of_6: CellVerdict


# ---------------------------------------------------------------------------
# Threshold-check primitives
# ---------------------------------------------------------------------------


def _arm_passes(
    arm: ModelArmScore | None,
    *,
    canonical_keys_min: int,
    f1_min: float | None,
) -> bool:
    """Return True iff ``arm`` satisfies the per-arm criterion.

    Args:
        arm: per-(model, arm) metrics, or None if the arm wasn't run.
        canonical_keys_min: minimum canonical_keys count (ADR-018 criterion).
        f1_min: minimum micro_F1 for the amended threshold; None for
            the pre-registered threshold (no F1 gate).

    Returns:
        True iff ``arm is not None`` AND all conjunctive criteria are met.
    """
    if arm is None:
        return False
    if not arm.json_validity:
        return False
    if arm.canonical_keys < canonical_keys_min:
        return False
    if f1_min is not None and arm.micro_f1 < f1_min:
        return False
    return True


def _model_passes(
    score: ModelScore,
    *,
    canonical_keys_min: int,
    f1_min: float | None,
) -> bool:
    """Return True iff EITHER arm of ``score`` satisfies the per-arm criterion.

    Combined-max-per-arm rule per ADR-018: a model passes the probe if at
    least one arm passes. A model with both arms None / failing fails.
    """
    return _arm_passes(
        score.arm_a, canonical_keys_min=canonical_keys_min, f1_min=f1_min
    ) or _arm_passes(
        score.arm_b, canonical_keys_min=canonical_keys_min, f1_min=f1_min
    )


# ---------------------------------------------------------------------------
# Cell + matrix construction
# ---------------------------------------------------------------------------


def _build_cell(
    per_model_scores: dict[str, ModelScore],
    *,
    canonical_keys_min: int,
    f1_min: float | None,
    pass_count_threshold: int,
    excluded_model_ids: frozenset[str],
) -> CellVerdict:
    """Build one cell of the verdict matrix.

    Args:
        per_model_scores: input dict mapping model_id → ModelScore.
        canonical_keys_min: ADR-018 criterion #2.
        f1_min: amended-threshold F1 gate; None for pre-registered.
        pass_count_threshold: minimum ``n_passing`` for FILE verdict.
        excluded_model_ids: model_ids to exclude from BOTH ``n_passing``
            and ``n_total`` (the N-of-6 PaliGemma flag mechanism).

    Returns:
        Frozen ``CellVerdict`` with sorted passing/failing lists.
    """
    passing: list[str] = []
    failing: list[str] = []
    for model_id, score in per_model_scores.items():
        if model_id in excluded_model_ids:
            continue
        if _model_passes(score, canonical_keys_min=canonical_keys_min, f1_min=f1_min):
            passing.append(model_id)
        else:
            failing.append(model_id)
    passing.sort()
    failing.sort()
    n_passing = len(passing)
    n_total = n_passing + len(failing)
    verdict: Literal["FILE", "DEFER"] = (
        "FILE" if n_passing >= pass_count_threshold else "DEFER"
    )
    return CellVerdict(
        passing_models=tuple(passing),
        failing_models=tuple(failing),
        n_passing=n_passing,
        n_total=n_total,
        verdict=verdict,
    )


def compute_verdict_matrix(
    per_model_scores: dict[str, ModelScore],
    *,
    paligemma_model_id: str = DEFAULT_PALIGEMMA_MODEL_ID,
    canonical_keys_min: int = DEFAULT_CANONICAL_KEYS_MIN,
    pass_count_threshold: int = DEFAULT_PASS_COUNT_THRESHOLD,
    f1_min_amended: float = DEFAULT_F1_MIN_AMENDED,
) -> VerdictMatrix:
    """Compute the 2 × 2 verdict matrix from per-model scores.

    The four cells cross (denominator) × (threshold). All cells share the same
    ``pass_count_threshold`` decision rule — only the per-arm criterion + the
    denominator vary, per the ADR-019 W3.2 architecture. There is NO mutation
    of any existing threshold logic; the amended threshold and N-of-6
    denominator are purely additive reporting.

    Args:
        per_model_scores: dict mapping model_id → ModelScore. Order does not
            matter (cells iterate sorted output).
        paligemma_model_id: model_id flagged out of the N-of-6 cells per
            ADR-019 §B8 (HF model card: base VLM). Defaults to
            ``"google/paligemma2-3b-mix-448"``.
        canonical_keys_min: pre-registered + amended criterion #2 (default 12
            per ADR-018).
        pass_count_threshold: minimum cell.n_passing for FILE verdict
            (default 3 per ADR-018).
        f1_min_amended: amended-threshold F1 gate (default 0.1 per ADR-019
            §"Threshold-design gap (B4)").

    Returns:
        Frozen ``VerdictMatrix`` with 4 cells. Caller renders as a markdown
        table for ADR-018 amendment / retro consumption.

    Examples:
        >>> from horus.eval.probe_verdict import (
        ...     ModelArmScore, ModelScore, compute_verdict_matrix,
        ... )
        >>> scores = {
        ...     "gemma-4": ModelScore(
        ...         model_id="gemma-4",
        ...         arm_a=ModelArmScore(json_validity=True, canonical_keys=14, micro_f1=0.5),
        ...         arm_b=None,
        ...     ),
        ... }
        >>> matrix = compute_verdict_matrix(scores)
        >>> matrix.pre_registered_n_of_7.passing_models
        ('gemma-4',)
        >>> matrix.pre_registered_n_of_7.verdict  # 1 of 1 < 3 → DEFER
        'DEFER'
    """
    n_of_7_excluded: frozenset[str] = frozenset()
    n_of_6_excluded: frozenset[str] = frozenset({paligemma_model_id})

    return VerdictMatrix(
        pre_registered_n_of_7=_build_cell(
            per_model_scores,
            canonical_keys_min=canonical_keys_min,
            f1_min=None,
            pass_count_threshold=pass_count_threshold,
            excluded_model_ids=n_of_7_excluded,
        ),
        pre_registered_n_of_6=_build_cell(
            per_model_scores,
            canonical_keys_min=canonical_keys_min,
            f1_min=None,
            pass_count_threshold=pass_count_threshold,
            excluded_model_ids=n_of_6_excluded,
        ),
        amended_n_of_7=_build_cell(
            per_model_scores,
            canonical_keys_min=canonical_keys_min,
            f1_min=f1_min_amended,
            pass_count_threshold=pass_count_threshold,
            excluded_model_ids=n_of_7_excluded,
        ),
        amended_n_of_6=_build_cell(
            per_model_scores,
            canonical_keys_min=canonical_keys_min,
            f1_min=f1_min_amended,
            pass_count_threshold=pass_count_threshold,
            excluded_model_ids=n_of_6_excluded,
        ),
    )


__all__ = [
    "DEFAULT_CANONICAL_KEYS_MIN",
    "DEFAULT_F1_MIN_AMENDED",
    "DEFAULT_PALIGEMMA_MODEL_ID",
    "DEFAULT_PASS_COUNT_THRESHOLD",
    "CellVerdict",
    "ModelArmScore",
    "ModelScore",
    "VerdictMatrix",
    "compute_verdict_matrix",
]
