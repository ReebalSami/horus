"""Tests for `src/horus/eval/probe_verdict.py` — the 2×2 verdict matrix (ADR-019 W3.2).

Per ADR-019 §"Wave 3.2 architecture": the verdict matrix crosses
(2 denominators) × (2 thresholds) for the structured-output probe (#53):

    | denominator           | pre-registered          | amended (F1≥0.1) |
    |-----------------------|-------------------------|------------------|
    | N of 7 (D2 = COUNT)   | cell A                  | cell B           |
    | N of 6 (D2 = FLAG)    | cell C                  | cell D           |

Pre-registered threshold: `(json_validity=1, canonical_keys≥12)`. Amended
threshold adds `(... ∧ micro_F1≥0.1)` to defend against schema-mimicry
(GLM-OCR Arm A: 16 placeholder keys, F1=0). N-of-6 flags PaliGemma2 as
structurally-non-participating (base VLM per HF model card; pre-registration
error per ADR-019 B8).

Per-model combined-max-per-arm rule: pass if EITHER arm satisfies the criteria.

Tests organized:

    1. Per-arm threshold check (`_arm_passes` / via the public surface)
    2. Per-model combined-max-per-arm rule
    3. Cell aggregation (per-cell pass/fail counts; FILE/DEFER decision)
    4. Full 2×2 matrix construction
    5. Edge cases (empty input; PaliGemma absent; arm None)

Refs: ADR-019 (parent), ADR-018 (probe).
"""

from __future__ import annotations

from horus.eval.probe_verdict import (
    ModelArmScore,
    ModelScore,
    VerdictMatrix,
    compute_verdict_matrix,
)

# ---------------------------------------------------------------------------
# Fixtures (synthetic — exercise each cell of the matrix independently)
# ---------------------------------------------------------------------------


def _arm(json_ok: bool, keys: int, f1: float) -> ModelArmScore:
    """Compact ModelArmScore constructor for test fixtures."""
    return ModelArmScore(json_validity=json_ok, canonical_keys=keys, micro_f1=f1)


def _passing_arm() -> ModelArmScore:
    """Arm score that passes BOTH pre-registered AND amended thresholds."""
    return _arm(True, 16, 0.5)


def _schema_mimicry_arm() -> ModelArmScore:
    """Arm score that passes pre-registered but FAILS amended (F1<0.1).

    Models the GLM-OCR Arm A pattern: 16 placeholder keys, F1=0. This is the
    core motivation for the amended threshold.
    """
    return _arm(True, 16, 0.0)


def _failing_arm() -> ModelArmScore:
    """Arm score that fails BOTH thresholds (no JSON, 0 keys, 0 F1)."""
    return _arm(False, 0, 0.0)


def _low_keys_arm() -> ModelArmScore:
    """Arm score that fails canonical_keys threshold (<12) but has high F1.

    Synthetic edge case: the threshold is conjunctive — passing F1 alone
    doesn't qualify.
    """
    return _arm(True, 5, 0.7)


# ---------------------------------------------------------------------------
# 1. Per-arm threshold check (via the public surface)
# ---------------------------------------------------------------------------


def test_arm_passing_both_thresholds() -> None:
    """Arm with json_validity=True, keys=16, F1=0.5 passes BOTH thresholds."""
    scores = {
        "model": ModelScore(model_id="model", arm_a=_passing_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ("model",)
    assert matrix.amended_n_of_7.passing_models == ("model",)


def test_arm_passing_pre_registered_failing_amended_schema_mimicry() -> None:
    """Schema-mimicry: 16 placeholder keys + F1=0 → passes pre-registered, fails amended."""
    scores = {
        "model": ModelScore(model_id="model", arm_a=_schema_mimicry_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ("model",)
    assert matrix.amended_n_of_7.passing_models == ()


def test_arm_failing_canonical_keys_threshold() -> None:
    """High F1 but only 5 keys → fails BOTH thresholds (canonical_keys≥12 is conjunctive)."""
    scores = {
        "model": ModelScore(model_id="model", arm_a=_low_keys_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ()
    assert matrix.amended_n_of_7.passing_models == ()


def test_arm_failing_json_validity() -> None:
    """json_validity=False → fails BOTH thresholds regardless of keys/F1."""
    arm = _arm(json_ok=False, keys=16, f1=0.9)
    scores = {"model": ModelScore(model_id="model", arm_a=arm, arm_b=None)}
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ()
    assert matrix.amended_n_of_7.passing_models == ()


# ---------------------------------------------------------------------------
# 2. Per-model combined-max-per-arm rule
# ---------------------------------------------------------------------------


def test_model_passes_if_any_arm_passes() -> None:
    """Model passes if EITHER arm satisfies the threshold (pre-registered ADR-018)."""
    scores = {
        "model_a_only": ModelScore(
            model_id="model_a_only", arm_a=_passing_arm(), arm_b=_failing_arm()
        ),
        "model_b_only": ModelScore(
            model_id="model_b_only", arm_a=_failing_arm(), arm_b=_passing_arm()
        ),
        "model_neither": ModelScore(
            model_id="model_neither", arm_a=_failing_arm(), arm_b=_failing_arm()
        ),
    }
    matrix = compute_verdict_matrix(scores)
    assert set(matrix.pre_registered_n_of_7.passing_models) == {
        "model_a_only",
        "model_b_only",
    }
    assert matrix.pre_registered_n_of_7.failing_models == ("model_neither",)


def test_model_with_only_arm_a_recorded() -> None:
    """Model with arm_b=None counts arm_a only (no penalty for missing arm)."""
    scores = {
        "model_a_only": ModelScore(model_id="model_a_only", arm_a=_passing_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ("model_a_only",)


def test_model_with_no_arm_data_fails() -> None:
    """Model with arm_a=None and arm_b=None fails by construction."""
    scores = {
        "model_no_data": ModelScore(model_id="model_no_data", arm_a=None, arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ()
    assert matrix.pre_registered_n_of_7.failing_models == ("model_no_data",)


# ---------------------------------------------------------------------------
# 3. Cell aggregation — verdict (FILE / DEFER) from pass-count
# ---------------------------------------------------------------------------


def test_verdict_file_when_3_of_7_pass_pre_registered() -> None:
    """3 of 7 models pass pre-registered threshold → FILE."""
    scores = {
        f"m{i}": ModelScore(
            model_id=f"m{i}",
            arm_a=_passing_arm() if i < 3 else _failing_arm(),
            arm_b=None,
        )
        for i in range(7)
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.n_passing == 3
    assert matrix.pre_registered_n_of_7.verdict == "FILE"


def test_verdict_defer_when_2_of_7_pass_pre_registered() -> None:
    """2 of 7 models pass pre-registered threshold → DEFER (need ≥3)."""
    scores = {
        f"m{i}": ModelScore(
            model_id=f"m{i}",
            arm_a=_passing_arm() if i < 2 else _failing_arm(),
            arm_b=None,
        )
        for i in range(7)
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.n_passing == 2
    assert matrix.pre_registered_n_of_7.verdict == "DEFER"


def test_verdict_defer_when_zero_pass() -> None:
    """0 of 7 models pass → DEFER."""
    scores = {
        f"m{i}": ModelScore(model_id=f"m{i}", arm_a=_failing_arm(), arm_b=None)
        for i in range(7)
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.n_passing == 0
    assert matrix.pre_registered_n_of_7.verdict == "DEFER"


def test_verdict_file_when_all_pass() -> None:
    """7 of 7 models pass → FILE."""
    scores = {
        f"m{i}": ModelScore(model_id=f"m{i}", arm_a=_passing_arm(), arm_b=None)
        for i in range(7)
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.n_passing == 7
    assert matrix.pre_registered_n_of_7.verdict == "FILE"


# ---------------------------------------------------------------------------
# 4. PaliGemma denominator dimension (N-of-7 vs. N-of-6 per D2)
# ---------------------------------------------------------------------------


def test_paligemma_counted_in_n_of_7_denominator() -> None:
    """PaliGemma2 fails (refusal); N-of-7 denominator counts it as 1 of 7 in `n_total`."""
    scores = {
        "google/paligemma2-3b-mix-448": ModelScore(
            model_id="google/paligemma2-3b-mix-448",
            arm_a=_failing_arm(),
            arm_b=_failing_arm(),
        ),
        "model_passing": ModelScore(
            model_id="model_passing", arm_a=_passing_arm(), arm_b=None
        ),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.n_total == 2
    assert matrix.pre_registered_n_of_7.n_passing == 1
    assert "google/paligemma2-3b-mix-448" in matrix.pre_registered_n_of_7.failing_models


def test_paligemma_flagged_in_n_of_6_denominator() -> None:
    """PaliGemma2 flagged out of N-of-6 denominator (n_total reduced by 1)."""
    scores = {
        "google/paligemma2-3b-mix-448": ModelScore(
            model_id="google/paligemma2-3b-mix-448",
            arm_a=_failing_arm(),
            arm_b=_failing_arm(),
        ),
        "model_passing": ModelScore(
            model_id="model_passing", arm_a=_passing_arm(), arm_b=None
        ),
    }
    matrix = compute_verdict_matrix(scores)
    # PaliGemma is excluded from BOTH passing and failing in the N-of-6 cell.
    assert matrix.pre_registered_n_of_6.n_total == 1
    assert "google/paligemma2-3b-mix-448" not in matrix.pre_registered_n_of_6.passing_models
    assert "google/paligemma2-3b-mix-448" not in matrix.pre_registered_n_of_6.failing_models
    assert matrix.pre_registered_n_of_6.passing_models == ("model_passing",)


def test_paligemma_passing_still_excluded_from_n_of_6() -> None:
    """Even if PaliGemma2 hypothetically passed, the N-of-6 cell excludes it (D2 spec).

    The flag is structural (base VLM is structurally non-participating per
    HF card) — the N-of-6 cell ALWAYS excludes PaliGemma regardless of its
    individual score. This pins that behavior.
    """
    scores = {
        "google/paligemma2-3b-mix-448": ModelScore(
            model_id="google/paligemma2-3b-mix-448",
            arm_a=_passing_arm(),  # hypothetical
            arm_b=None,
        ),
        "model_other": ModelScore(model_id="model_other", arm_a=_failing_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert "google/paligemma2-3b-mix-448" not in matrix.pre_registered_n_of_6.passing_models
    assert matrix.pre_registered_n_of_6.n_total == 1


def test_paligemma_absent_from_input_n_of_6_unchanged() -> None:
    """No PaliGemma in input → N-of-7 and N-of-6 cells have identical n_total."""
    scores = {
        f"m{i}": ModelScore(model_id=f"m{i}", arm_a=_passing_arm(), arm_b=None)
        for i in range(5)
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.n_total == 5
    assert matrix.pre_registered_n_of_6.n_total == 5


# ---------------------------------------------------------------------------
# 5. Full 2×2 matrix construction
# ---------------------------------------------------------------------------


def test_full_2x2_matrix_all_cells_populated() -> None:
    """compute_verdict_matrix returns a VerdictMatrix with all 4 cells populated."""
    scores = {
        "m1": ModelScore(model_id="m1", arm_a=_passing_arm(), arm_b=None),
        "m2": ModelScore(model_id="m2", arm_a=_schema_mimicry_arm(), arm_b=None),
        "m3": ModelScore(model_id="m3", arm_a=_failing_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert isinstance(matrix, VerdictMatrix)
    # Pre-registered N-of-7: m1 + m2 pass (both have keys≥12, json_validity=True)
    assert matrix.pre_registered_n_of_7.n_passing == 2
    # Amended N-of-7: only m1 passes (m2 fails F1≥0.1 gate)
    assert matrix.amended_n_of_7.n_passing == 1
    # No PaliGemma in input → N-of-6 == N-of-7 here
    assert matrix.pre_registered_n_of_6.n_passing == matrix.pre_registered_n_of_7.n_passing
    assert matrix.amended_n_of_6.n_passing == matrix.amended_n_of_7.n_passing


def test_matrix_cell_independence_paligemma_schema_mimicry() -> None:
    """Realistic shape: PaliGemma fails + schema-mimicry model passes pre-registered only.

    Reproduces the locked locked-in concern from ADR-019: GLM-OCR Arm A passes
    the pre-registered threshold with placeholder values (F1=0), but only
    PaliGemma reduces the denominator. All 4 cells should produce different
    pass-counts to demonstrate the matrix's diagnostic value.
    """
    scores = {
        "google/paligemma2-3b-mix-448": ModelScore(
            model_id="google/paligemma2-3b-mix-448",
            arm_a=_failing_arm(),
            arm_b=_failing_arm(),
        ),
        "schema_mimicry_model": ModelScore(
            model_id="schema_mimicry_model",
            arm_a=_schema_mimicry_arm(),
            arm_b=None,
        ),
        "real_passing_model": ModelScore(
            model_id="real_passing_model", arm_a=_passing_arm(), arm_b=None
        ),
    }
    matrix = compute_verdict_matrix(scores)

    # Pre-registered N-of-7: schema-mimicry + real pass = 2 of 3
    assert matrix.pre_registered_n_of_7.n_passing == 2
    assert matrix.pre_registered_n_of_7.n_total == 3

    # Pre-registered N-of-6: schema-mimicry + real pass = 2 of 2 (PaliGemma flagged)
    assert matrix.pre_registered_n_of_6.n_passing == 2
    assert matrix.pre_registered_n_of_6.n_total == 2

    # Amended N-of-7: only real passes = 1 of 3
    assert matrix.amended_n_of_7.n_passing == 1
    assert matrix.amended_n_of_7.n_total == 3

    # Amended N-of-6: only real passes = 1 of 2
    assert matrix.amended_n_of_6.n_passing == 1
    assert matrix.amended_n_of_6.n_total == 2


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------


def test_empty_input_yields_all_defer() -> None:
    """Empty per_model_scores dict → all 4 cells DEFER, 0 passing of 0 total."""
    matrix = compute_verdict_matrix({})
    for cell in (
        matrix.pre_registered_n_of_7,
        matrix.pre_registered_n_of_6,
        matrix.amended_n_of_7,
        matrix.amended_n_of_6,
    ):
        assert cell.n_passing == 0
        assert cell.n_total == 0
        assert cell.verdict == "DEFER"
        assert cell.passing_models == ()


def test_pass_threshold_default_is_3() -> None:
    """The pre-registered pass threshold is `n_passing ≥ 3` (per ADR-018)."""
    # 3 passing → FILE; 2 passing → DEFER (boundary already covered above; pin default)
    scores_3 = {
        f"m{i}": ModelScore(
            model_id=f"m{i}", arm_a=_passing_arm() if i < 3 else _failing_arm(), arm_b=None
        )
        for i in range(7)
    }
    matrix_3 = compute_verdict_matrix(scores_3)
    assert matrix_3.pre_registered_n_of_7.verdict == "FILE"


def test_custom_pass_threshold_via_kwarg() -> None:
    """`pass_count_threshold` kwarg overrides the default (testing-only convenience)."""
    scores = {
        "m1": ModelScore(model_id="m1", arm_a=_passing_arm(), arm_b=None),
        "m2": ModelScore(model_id="m2", arm_a=_passing_arm(), arm_b=None),
    }
    # Threshold = 2: 2 passing of 2 total → FILE
    matrix_low = compute_verdict_matrix(scores, pass_count_threshold=2)
    assert matrix_low.pre_registered_n_of_7.verdict == "FILE"

    # Threshold = 3: 2 passing of 2 total → DEFER (not enough)
    matrix_high = compute_verdict_matrix(scores, pass_count_threshold=3)
    assert matrix_high.pre_registered_n_of_7.verdict == "DEFER"


def test_custom_f1_min_via_kwarg() -> None:
    """`f1_min_amended` kwarg overrides the default (testing-only convenience)."""
    arm = _arm(json_ok=True, keys=16, f1=0.05)
    scores = {"model": ModelScore(model_id="model", arm_a=arm, arm_b=None)}

    # f1_min_amended = 0.0 → amended threshold trivially satisfied; passes
    matrix_lax = compute_verdict_matrix(scores, f1_min_amended=0.0)
    assert "model" in matrix_lax.amended_n_of_7.passing_models

    # f1_min_amended = 0.1 (default) → 0.05 < 0.1 → fails
    matrix_default = compute_verdict_matrix(scores)
    assert "model" not in matrix_default.amended_n_of_7.passing_models


def test_passing_models_sorted_alphabetically_for_determinism() -> None:
    """Passing-models tuple is sorted (deterministic across Python dict-iteration order)."""
    scores = {
        "z_model": ModelScore(model_id="z_model", arm_a=_passing_arm(), arm_b=None),
        "a_model": ModelScore(model_id="a_model", arm_a=_passing_arm(), arm_b=None),
        "m_model": ModelScore(model_id="m_model", arm_a=_passing_arm(), arm_b=None),
    }
    matrix = compute_verdict_matrix(scores)
    assert matrix.pre_registered_n_of_7.passing_models == ("a_model", "m_model", "z_model")
