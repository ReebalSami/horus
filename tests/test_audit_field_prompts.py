"""Tests for the prompt-surface guardrail + advisory channel (`scripts/audit_field_prompts.py`).

Two concerns, both about what reaches the model:

**The no-leakage gate (check E).** Its job is to stop a ground-truth answer reaching the
model inside its own prompt. It used to scan `FieldSpec.description` only, and only for
fields that had one, which left two holes:

- a value sitting in a `prompt_aliases` entry was never checked, even though aliases
  render into the prompt as "printed as: <alias>"; and
- a field with aliases but NO description got no leak check at all.

That is not a hypothetical gap. `payment_means_text`'s ground truth *is* a
payment-method phrase, so a plausible-looking German alias for that field is
indistinguishable from an answer — and ADR-058 records a description that leaked two
corpus values before the guardrail existed at all.

**The missing-alias advisory (check C).** Its job is to propose labels worth adding. It
is only useful if its proposals are safe to paste, and originally they were not: the
channel was dominated by the corpus's own answers, by a `(no label)` sentinel, and by
labels that were *already listed* but could not match because only one side of the
comparison had its framing punctuation trimmed. The tests below pin all three fixes.

All fixtures are synthetic; no corpus is required, so these run in CI.
"""

from __future__ import annotations

import pytest

from scripts.audit_field_prompts import (
    _DOCTAG_RE,
    _LABELLIKE_RE,
    MIN_LEAKED_VARIANT_CHARS,
    NO_LABEL,
    _fold,
    _label_form,
    _leading_label,
    find_leaked_value,
    is_answer_shaped,
    order_needles,
)

# One invoice's answer for a payment-method field, in the printed form a page shows.
_ANSWER = "überweisung auf unser konto"
_VARIANTS: list[tuple[str, list[str]]] = [("invoice-001", [_ANSWER, "2018-06-01"])]


def test_leak_in_an_alias_is_caught() -> None:
    """The hole this test exists for: an answer carried by an alias.

    Before the guardrail was widened this returned nothing, so a proposed alias could
    have handed the model the answer for every invoice printing that phrase.
    """
    leak = find_leaked_value([("alias", "Überweisung auf unser Konto")], _VARIANTS)
    assert leak is not None, "an answer inside an alias must be caught"
    assert leak.surface_kind == "alias"
    assert leak.invoice == "invoice-001"


def test_leak_is_caught_when_the_field_has_no_description() -> None:
    """Second hole: the check must not depend on the field being glossed."""
    assert find_leaked_value([("alias", "Überweisung auf unser Konto")], _VARIANTS) is not None


def test_leak_in_a_description_is_still_caught() -> None:
    """The original behaviour must survive the widening."""
    leak = find_leaked_value(
        [("description", "How payment is made, e.g. Überweisung auf unser Konto")], _VARIANTS
    )
    assert leak is not None
    assert leak.surface_kind == "description"


def test_casing_cannot_hide_a_leak() -> None:
    """Upper-casing a leaked value must not smuggle it past the guardrail.

    The load-bearing case for German, where every noun is capitalized: before both
    sides of the comparison were folded, a capitalized value could never match.
    """
    assert find_leaked_value([("alias", "ÜBERWEISUNG AUF UNSER KONTO")], _VARIANTS) is not None


def test_umlaut_transliteration_cannot_hide_a_leak() -> None:
    """`ü` and `ue` are the same word to the fold, so spelling it out is not a bypass."""
    assert find_leaked_value([("alias", "Ueberweisung auf unser Konto")], _VARIANTS) is not None


def test_deleting_an_umlaut_is_a_different_string_and_is_not_folded() -> None:
    """Pins a real limitation: `Uberweisung` (umlaut DROPPED) is not `Überweisung`.

    The fold transliterates (`ü` -> `ue`) and normalizes NFC/NFD; it does not strip
    diacritics. So an ASCII-mangled spelling reads as a different string and is not
    reported. Recorded as a test rather than left as folklore — the distinction cost
    a wrong assumption while writing these tests.
    """
    assert find_leaked_value([("alias", "Uberweisung auf unser Konto")], _VARIANTS) is None


def test_a_genuine_label_is_not_flagged() -> None:
    """A real printed label that is not an answer must pass, or the gate is useless."""
    assert find_leaked_value([("alias", "Zahlungsart")], _VARIANTS) is None


def test_printed_date_form_is_caught_against_an_iso_ground_truth() -> None:
    """A description naming `01.06.2018` leaks a GT stored as `2018-06-01`.

    Matching printed variants rather than only the canonical form is the reason this
    works; an ISO-only comparison waved exactly this case through.
    """
    variants = [("invoice-002", ["2018-06-01", "01.06.2018"])]
    leak = find_leaked_value([("description", "the invoice date, e.g. 01.06.2018")], variants)
    assert leak is not None
    assert leak.variant == "01.06.2018"


@pytest.mark.parametrize("short_value", ["EUR", "19", "S"])
def test_short_values_are_vocabulary_not_answers(short_value: str) -> None:
    """Currency codes, VAT rates and category letters must not trip the gate.

    They are the field's vocabulary; flagging them would make the guardrail
    unusable on exactly the fields that need a label most.
    """
    variants = [("invoice-003", [short_value])]
    assert len(short_value) < MIN_LEAKED_VARIANT_CHARS
    assert find_leaked_value([("alias", f"Betrag in {short_value}")], variants) is None


def test_description_is_reported_before_aliases() -> None:
    """Reporting order follows the surface order the caller passes.

    Keeps the audit output stable when a field leaks through more than one surface.
    """
    leak = find_leaked_value(
        [("description", _ANSWER), ("alias", _ANSWER)],
        _VARIANTS,
    )
    assert leak is not None
    assert leak.surface_kind == "description"


def test_reported_variant_is_deterministic_across_runs() -> None:
    """`value_variants` returns a set, so the gate sorts before matching.

    Without that, WHICH of several leaked variants gets reported would follow hash
    order and a gate failure would not reproduce identically.
    """
    variants = [("invoice-004", {"aaaa-leaked", "bbbb-leaked", "cccc-leaked"})]
    surfaces = [("description", "aaaa-leaked bbbb-leaked cccc-leaked")]
    reported = {find_leaked_value(surfaces, variants) for _ in range(8)}
    assert len(reported) == 1
    only = reported.pop()
    assert only is not None
    assert only.variant == "aaaa-leaked"


def test_no_surfaces_means_no_leak() -> None:
    """A field contributing no prompt text cannot leak."""
    assert find_leaked_value([], _VARIANTS) is None


def test_no_present_ground_truth_means_no_leak() -> None:
    """With no answers to leak, any prompt text is safe."""
    assert find_leaked_value([("alias", "Überweisung auf unser Konto")], []) is None


# --- check C: label-form symmetry -------------------------------------------------


def test_an_alias_written_with_a_trailing_period_matches_its_printed_form() -> None:
    """The asymmetry that made check C report aliases it had itself been given.

    Observed labels come from `_leading_label`, which trims framing punctuation; the
    known-set used to be built from raw registry text. So `'Rechnungssumme ohne USt.'`
    never equalled the `'Rechnungssumme ohne USt'` the page prints, and the audit
    advised adding a label that was already there — 82 invoices' worth on
    `tax_basis_total_amount`, plus `Steuernr.` and `Kunden-Nr.`.
    """
    alias = "Rechnungssumme ohne USt."
    clean = _DOCTAG_RE.sub("|", "<fcel>Rechnungssumme ohne USt.<fcel>1.234,56")
    observed = _leading_label(clean, "1.234,56")

    assert observed == "Rechnungssumme ohne USt"
    assert _fold(_label_form(alias)) == _fold(observed), "both sides must fold alike"
    # The negative control: without `_label_form` on the registry side these differ,
    # which is precisely how the false findings arose.
    assert _fold(alias) != _fold(observed)


def test_label_form_is_idempotent() -> None:
    """Applying the fold twice must not change the result.

    Load-bearing because observed labels are already `_label_form`-ed when check C
    re-folds them for comparison; a non-idempotent fold would reintroduce the
    asymmetry from the other direction.
    """
    for raw in ("Rechnungssumme ohne USt.", "  Fälligkeit  ", "|Steuernr.|", "Leistungsdatum"):
        once = _label_form(raw)
        assert _label_form(once) == once


def test_leading_label_returns_the_sentinel_when_only_markup_precedes_the_value() -> None:
    """An unlabelled table cell yields the sentinel, not an empty string."""
    assert _leading_label("|  |1.234,56", "1.234,56") == NO_LABEL


def test_the_no_label_sentinel_passes_the_label_like_screen() -> None:
    """Why the sentinel needs dropping BY NAME rather than by the generic screen.

    `_LABELLIKE_RE` only asks for three consecutive letters, and "label" satisfies it.
    So the sentinel was counted as an observed label and reached ×122 on
    `grand_total_amount`, crowding out the real findings.
    """
    assert _LABELLIKE_RE.search(NO_LABEL) is not None


# --- check C: the answer-shaped filter -------------------------------------------


def test_a_candidate_that_is_exactly_the_answer_is_dropped_at_any_length() -> None:
    """`EUR` is `invoice_currency_code`'s ground truth, and it is only three chars.

    Check E deliberately ignores values this short — inside prose they are vocabulary.
    A standalone candidate is not prose, so equality has to bite regardless of length,
    or the audit proposes the answer for 97 invoices as a label.
    """
    assert len("EUR") < MIN_LEAKED_VARIANT_CHARS
    assert is_answer_shaped("EUR", [("invoice-001", ["EUR", "€"])])


def test_an_answer_embedded_in_a_longer_candidate_is_dropped() -> None:
    """The `seller_iban` case: the heuristic returned `'IBAN <the actual IBAN>'`."""
    variants = [("invoice-002", ["DE88200800000970375700"])]
    assert is_answer_shaped("IBAN DE88200800000970375700", variants)


def test_a_doctype_word_inside_pdf_boilerplate_is_dropped() -> None:
    """`document_type`'s answer is a printed WORD, so page furniture matches it.

    The raw channel proposed `'Stylesheet zur Lesbarmachung der XML-Daten von ZUGFeRD
    2.0-Rechnungen'` ×25 — a PDF footer, not a label.
    """
    variants = [("invoice-003", ["rechnung", "invoice", "facture"])]
    assert is_answer_shaped(
        "Stylesheet zur Lesbarmachung der XML-Daten von ZUGFeRD 2.0-Rechnungen", variants
    )


def test_a_genuine_printed_label_survives_the_filter() -> None:
    """The filter must not eat real findings, or check C stops being useful."""
    variants = [("invoice-004", ["1234.56", "1.234,56"])]
    assert not is_answer_shaped("Rechnungssumme ohne USt", variants)


def test_a_short_coincidental_substring_does_not_drop_a_label() -> None:
    """A sub-threshold value occurring inside a label is coincidence, not leakage.

    `€` sits inside `'Betrag in €'`, but that phrase is a label, not an answer. Only
    exact equality bites below `MIN_LEAKED_VARIANT_CHARS`.
    """
    assert not is_answer_shaped("Betrag in €", [("invoice-005", ["€"])])


def test_no_ground_truth_means_nothing_is_answer_shaped() -> None:
    """With no answers on record, every candidate is proposable."""
    assert not is_answer_shaped("Leistungsdatum", [])


def test_an_empty_candidate_is_not_answer_shaped() -> None:
    """Guards the fold returning empty for an all-punctuation candidate."""
    assert not is_answer_shaped("", [("invoice-006", ["EUR"])])


# --- check C: deterministic anchor selection --------------------------------------


def test_needle_order_does_not_depend_on_set_iteration_order() -> None:
    """The reproducibility bug: hash order used to decide which label got reported.

    `value_variants` returns a set. Check C cuts the line at the first variant it finds,
    so an unordered collection let CPython's string hashing choose the cut — and the
    audit reported `'Liefer- und Leistungsdatum'` ×38 on one run and ×40 on the next
    over an unchanged corpus.
    """
    variants = {"05.03.2018", "2018-03-05", "5.3.2018", "05/03/2018"}
    first = order_needles(variants)
    # Same members, different insertion order: the result must be identical.
    assert order_needles(set(reversed(sorted(variants)))) == first
    assert order_needles(list(variants) + list(variants)) == first


def test_needles_are_ordered_longest_first() -> None:
    """A longer variant pins the printed value more tightly, so it anchors first."""
    ordered = order_needles({"5.3.2018", "05.03.2018", "2018-03-05"})
    assert [len(v) for v in ordered] == sorted((10, 10, 8), reverse=True)
    assert ordered[-1] == "5.3.2018"


def test_needle_order_is_total_so_equal_lengths_do_not_tie() -> None:
    """Same-length variants sort lexicographically, or the order is still arbitrary."""
    assert order_needles({"05/03/2018", "05.03.2018", "2018-03-05"}) == [
        "05.03.2018",
        "05/03/2018",
        "2018-03-05",
    ]


def test_short_variants_cannot_anchor_a_label() -> None:
    """1-2 char fragments occur all over a page; the cut they imply is meaningless."""
    assert order_needles({"€", "19", "EUR", "1.234,56"}) == ["1.234,56", "EUR"]


def test_ordering_an_empty_variant_set_is_empty() -> None:
    """A field with no printed variants contributes no observations."""
    assert order_needles(set()) == []
