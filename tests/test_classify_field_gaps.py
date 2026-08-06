"""Tests for the per-field cause classifier (`scripts/classify_field_gaps.py`).

The classifier decides, per field, whether a weak F1 is something the prompt could fix.
That decision gates real work in both directions: a wrong `prompt-candidate` sends the
next session editing a prompt whose additions ADR-048 and ADR-053 both measured as
net-NEGATIVE, while a wrong `reading-gap` hands a prompt-fixable gap to a LoRA, which
ADR-064 forbids. So the rules are pure functions and pinned here.

The rules under test, in evaluation order:

1. no gradable cells -> `untested` (an F1 of 0.000 over zero outcomes is undefined)
2. perfect text scoring BELOW reader text -> `label-mapping` (same model, same
   instruction; only the page wording differs, so the loss is label→key mapping)
3. below the adequacy bar with >= MIN_ORACLE_ERRORS errors -> `prompt-candidate`
4. below the adequacy bar with fewer -> `marginal` (recorded, not escalated)
5. at the adequacy bar but losing on reader text -> `reading-gap` (hands off)
6. at the bar on both arms -> `closed`

All fixtures are hand-written outcome counts; no corpus and no eval report are read, so
these run in CI.
"""

from __future__ import annotations

from scripts.classify_field_gaps import (
    MIN_ORACLE_ERRORS,
    ORACLE_ADEQUATE_F1,
    VERDICT_ORDER,
    classify_field,
)


def counts(tp: int = 0, fp: int = 0, fn: int = 0, tn: int = 0, excluded: int = 0) -> dict[str, int]:
    """Outcome counts in the shape `per_field_outcomes` uses."""
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "EXCLUDED": excluded}


def verdict_of(
    reader_f1: float | None,
    oracle_f1: float | None,
    reader_counts: dict[str, int],
    oracle_counts: dict[str, int],
) -> str:
    return classify_field(
        "some_field", "BT-999", reader_f1, oracle_f1, reader_counts, oracle_counts
    ).verdict


def test_a_field_with_no_gradable_cells_is_untested_not_failing() -> None:
    """`rounding_amount` is present on 1/146 invoices and absent from the val split.

    Reporting it as 0.000 would read as the worst field in the registry when in fact
    nothing was ever graded. ADR-058 called this out explicitly for this field.
    """
    assert verdict_of(None, None, counts(tn=29), counts(tn=29)) == "untested"


def test_no_ceiling_means_untested_even_when_the_reader_arm_has_outcomes() -> None:
    """Without gradable cells on perfect text there is no ceiling to compare against."""
    assert verdict_of(0.5, None, counts(tp=1, fn=1), counts(tn=29)) == "untested"


def test_perfect_text_scoring_below_reader_text_is_a_label_mapping_finding() -> None:
    """The `line_total_amount` shape: identical model, and the perfect page does worse.

    The only variable is the wording the oracle page prints, so the model is losing on
    label→key mapping rather than on reading. ADR-059 produced exactly this when the
    oracle label moved from schema jargon to the corpus's own wording.
    """
    assert (
        verdict_of(0.906, 0.863, counts(tp=24, fp=2, fn=3), counts(tp=22, fp=2, fn=5))
        == "label-mapping"
    )


def test_two_or_more_errors_on_perfect_text_is_a_prompt_candidate() -> None:
    """`seller_name`: 3 FN with the value in plain sight."""
    assert verdict_of(0.945, 0.945, counts(tp=26, fn=3), counts(tp=26, fn=3)) == "prompt-candidate"


def test_a_single_error_on_perfect_text_is_marginal_not_a_candidate() -> None:
    """`delivery_date`: one miss out of 20 gradable cells.

    The distinction is the whole point of counting errors instead of thresholding F1 —
    see the next test for why the F1 alone is misleading.
    """
    assert verdict_of(0.865, 0.974, counts(tp=16, fp=1, fn=4), counts(tp=19, fn=1)) == "marginal"


def test_a_small_denominator_cannot_manufacture_a_prompt_candidate() -> None:
    """`billing_period_start` is present on 3 val invoices, so one miss reads as 0.800.

    Thresholding on F1 alone flagged this as a prompt gap; it is one data point. This is
    the regression that motivated `MIN_ORACLE_ERRORS`.
    """
    assert 0.800 < ORACLE_ADEQUATE_F1, "the fixture must sit below the adequacy bar"
    assert verdict_of(0.333, 0.800, counts(tp=2, fp=7, fn=1), counts(tp=2, fn=1)) == "marginal"


def test_ceiling_on_perfect_text_with_a_reader_loss_is_a_reading_gap() -> None:
    """`payment_means_text`: 1.000 on perfect text, 0.133 on reader text.

    A severe reader-arm loss is still hands-off when the prompt is proven adequate —
    adding glossary text here spends prompt budget for nothing.
    """
    assert verdict_of(0.133, 1.000, counts(tp=1, fp=9, fn=4), counts(tp=5)) == "reading-gap"


def test_ceiling_on_both_arms_is_closed() -> None:
    """Nothing to repair, and saying so explicitly keeps the field out of the work list."""
    assert verdict_of(1.000, 1.000, counts(tp=5), counts(tp=5)) == "closed"


def test_equal_scores_below_ceiling_do_not_count_as_a_reading_gap() -> None:
    """A field losing the same amount on both arms is not the reader's fault.

    `seller_name` scores 0.945 on both; the cause turned out to be ground truth carrying
    embedded newlines. Calling that a reading gap would have hidden it.
    """
    assert verdict_of(0.945, 0.945, counts(tp=26, fn=3), counts(tp=26, fn=3)) != "reading-gap"


def test_excluded_and_tn_outcomes_do_not_count_as_signal() -> None:
    """Only TP/FP/FN are gradable; TN and EXCLUDED must not create a false ceiling.

    This is the per-field reporting defect ADR-058 fixed — contaminating per-field F1
    with non-signal outcomes is what hid three fields scoring 0.000.
    """
    assert verdict_of(None, None, counts(tn=10, excluded=19), counts(tn=10, excluded=19)) == (
        "untested"
    )


def test_the_gap_is_the_headroom_against_the_field_s_own_ceiling() -> None:
    """`gap` drives escalation ordering, so its sign convention is load-bearing."""
    worse_on_reader = classify_field("f", "BT-1", 0.800, 1.000, counts(tp=4, fn=1), counts(tp=5))
    assert worse_on_reader.gap > 0

    worse_on_oracle = classify_field(
        "f", "BT-1", 0.906, 0.863, counts(tp=24, fp=2, fn=3), counts(tp=22, fp=2, fn=5)
    )
    assert worse_on_oracle.gap < 0


def test_a_missing_ceiling_yields_a_zero_gap_rather_than_raising() -> None:
    """Sorting must not blow up on a field the oracle arm never graded."""
    assert classify_field("f", "BT-1", 0.5, None, counts(tp=1, fn=1), counts(tn=29)).gap == 0.0


def test_every_verdict_the_classifier_emits_is_orderable() -> None:
    """`VERDICT_ORDER` drives the sort; an unlisted verdict would raise at render time."""
    emitted = {
        verdict_of(None, None, counts(tn=29), counts(tn=29)),
        verdict_of(0.5, None, counts(tp=1, fn=1), counts(tn=29)),
        verdict_of(0.906, 0.863, counts(tp=24, fp=2, fn=3), counts(tp=22, fp=2, fn=5)),
        verdict_of(0.945, 0.945, counts(tp=26, fn=3), counts(tp=26, fn=3)),
        verdict_of(0.865, 0.974, counts(tp=16, fp=1, fn=4), counts(tp=19, fn=1)),
        verdict_of(0.133, 1.000, counts(tp=1, fp=9, fn=4), counts(tp=5)),
        verdict_of(1.000, 1.000, counts(tp=5), counts(tp=5)),
    }
    assert emitted <= set(VERDICT_ORDER)
    assert MIN_ORACLE_ERRORS == 2, "fixtures above are written against a two-error bar"
