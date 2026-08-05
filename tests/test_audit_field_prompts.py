"""Tests for the prompt-surface no-leakage guardrail (`scripts/audit_field_prompts.py`).

The guardrail's job is to stop a ground-truth answer reaching the model inside its own
prompt. It used to scan `FieldSpec.description` only, and only for fields that had one,
which left two holes:

- a value sitting in a `prompt_aliases` entry was never checked, even though aliases
  render into the prompt as "printed as: <alias>"; and
- a field with aliases but NO description got no leak check at all.

That is not a hypothetical gap. `payment_means_text`'s ground truth *is* a
payment-method phrase, so a plausible-looking German alias for that field is
indistinguishable from an answer — and ADR-058 records a description that leaked two
corpus values before the guardrail existed at all.

All fixtures are synthetic; no corpus is required, so these run in CI.
"""

from __future__ import annotations

import pytest

from scripts.audit_field_prompts import (
    MIN_LEAKED_VARIANT_CHARS,
    find_leaked_value,
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
