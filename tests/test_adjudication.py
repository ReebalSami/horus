"""Adjudication of N channel readings into per-cell decisions (ADR-062).

Hermetic: text layers are built from literal strings via `prepare_text_layer`, so no PDF and
no credentials are needed.

The cases worth the most here are the ones where a plausible-looking shortcut would corrupt
the answer key: counting a silent channel as agreement, treating a locale difference as a
conflict, letting a structurally-blind channel vote on absence, or auto-accepting a value
that only one reader ever assigned to the field.
"""

from __future__ import annotations

from horus.eval.adjudication import (
    CellDecision,
    ChannelReading,
    EscalationRank,
    ProvenanceClass,
    adjudicate_cell,
    adjudicate_document,
    canonical_for_compare,
    collapse_summary,
    escalated,
    group_row_counts,
    policy_for_cell_key,
)
from horus.eval.ground_truth import FIELDS
from horus.eval.printed_evidence import EvidencePolicy, prepare_text_layer

EMPTY_LAYER = prepare_text_layer("")


def decide(key: str, *readings: ChannelReading, text: str = "") -> CellDecision:
    return adjudicate_cell(key, readings, prepare_text_layer(text))


# ---------------------------------------------------------------------------
# Auto-accept: the strongest warrant
# ---------------------------------------------------------------------------


def test_printed_and_two_channels_agree_is_the_top_class() -> None:
    decision = decide(
        "invoice_number",
        ChannelReading("judge", "RE-2022-0815"),
        ChannelReading("draft", "RE-2022-0815"),
        text="Rechnungsnummer RE-2022-0815",
    )
    assert decision.provenance is ProvenanceClass.TEXT_LAYER_PROVEN
    assert decision.auto_accepted
    assert decision.rank is None
    assert decision.value == "RE-2022-0815"
    assert set(decision.agreeing_channels) == {"judge", "draft"}
    assert "judge" in decision.evidenced_channels


def test_agreement_without_any_text_layer_is_the_weaker_class() -> None:
    """The Tier B case: no deterministic warrant can ever exist for these 338 cells.

    Accepted, but the class records that it rests on two systems that could in principle
    fail together — which is what keeps it out of the headline.
    """
    decision = decide(
        "seller_name",
        ChannelReading("judge", "ACME GmbH"),
        ChannelReading("azure", "ACME GmbH"),
    )
    assert decision.provenance is ProvenanceClass.TWO_CHANNEL_AGREED
    assert decision.auto_accepted
    assert decision.rank is None


def test_locale_differences_are_agreement_not_conflict() -> None:
    """ADR-058 symmetric normalization.

    A one-sided fold has already inverted a correct answer once in this codebase; reporting
    `1.234,56` against `1234.56` as a disagreement would send the author chasing a
    non-problem.
    """
    decision = decide(
        "grand_total_amount",
        ChannelReading("judge", "1.234,56"),
        ChannelReading("azure", "1234.56"),
        text="Gesamtbetrag 1.234,56 EUR",
    )
    assert decision.provenance is ProvenanceClass.TEXT_LAYER_PROVEN
    assert decision.competing_values == ("1.234,56", "1234.56")
    assert decision.auto_accepted


def test_date_locale_differences_also_agree() -> None:
    decision = decide(
        "issue_date",
        ChannelReading("judge", "28.09.2022"),
        ChannelReading("azure", "2022-09-28"),
        text="Rechnungsdatum 28.09.2022",
    )
    assert decision.auto_accepted


# ---------------------------------------------------------------------------
# Coverage is not conflict
# ---------------------------------------------------------------------------


def test_a_silent_channel_is_not_agreement() -> None:
    """One channel filling a field the other left null is coverage, not confirmation.

    Auto-accepting on this basis is how a single reader's opinion becomes ground truth.
    """
    decision = decide(
        "buyer_vat_id",
        ChannelReading("judge", "DE123456789"),
        ChannelReading("draft", None),
        text="USt-IdNr DE123456789",
    )
    assert decision.agreeing_channels == ("judge",)
    assert not decision.auto_accepted
    assert decision.rank is EscalationRank.SINGLE_CHANNEL_PROVEN


def test_a_structurally_blind_channel_does_not_vote_on_absence() -> None:
    """ADR-061's `not-covered`.

    Azure cannot express BT-46 at all. If that silence counted as a claim of absence, the
    cell would look disputed when only one channel ever had an opinion.
    """
    decision = decide(
        "buyer_reference",
        ChannelReading("judge", "Kostenstelle 4711"),
        ChannelReading("azure", None, covered=False),
    )
    assert decision.rank is not EscalationRank.NULL_DISPUTED
    assert decision.rank is EscalationRank.ASSERTED_UNEVIDENCED
    assert "azure" not in decision.agreeing_channels


def test_a_covered_channel_finding_nothing_is_a_disputed_null() -> None:
    decision = decide(
        "buyer_order_reference",
        ChannelReading("judge", "PO-99"),
        ChannelReading("azure", None, covered=True),
    )
    assert decision.rank is EscalationRank.NULL_DISPUTED
    assert "azure" in decision.note


def test_every_channel_reporting_absence_is_an_accepted_null_claim() -> None:
    decision = decide(
        "rounding_amount",
        ChannelReading("judge", None),
        ChannelReading("draft", None),
    )
    assert decision.provenance is ProvenanceClass.NULL_CLAIM
    assert decision.auto_accepted


def test_absence_nobody_could_check_is_not_a_warranted_null() -> None:
    """If no channel can express the field, "absent" is an assumption, not a finding."""
    decision = decide(
        "payment_means_code",
        ChannelReading("azure", None, covered=False),
    )
    assert decision.provenance is ProvenanceClass.NULL_CLAIM
    assert not decision.auto_accepted
    assert decision.rank is EscalationRank.ASSERTED_UNEVIDENCED


# ---------------------------------------------------------------------------
# Conflict
# ---------------------------------------------------------------------------


def test_conflict_with_one_side_printed_ranks_below_one_with_neither() -> None:
    """A printed side nearly resolves the cell; no printed side has no tiebreaker at all."""
    resolvable = decide(
        "seller_vat_id",
        ChannelReading("judge", "DE111111111"),
        ChannelReading("azure", "DE999999999"),
        text="USt-IdNr DE111111111",
    )
    unresolvable = decide(
        "seller_vat_id",
        ChannelReading("judge", "DE111111111"),
        ChannelReading("azure", "DE999999999"),
    )
    assert resolvable.rank is EscalationRank.CONFLICT_ONE_EVIDENCED
    assert unresolvable.rank is EscalationRank.CONFLICT_NONE_EVIDENCED
    assert unresolvable.rank.value < resolvable.rank.value


def test_a_conflict_proposes_no_value() -> None:
    """Picking a side automatically is exactly the decision the author must make."""
    decision = decide(
        "seller_name",
        ChannelReading("judge", "ACME GmbH"),
        ChannelReading("azure", "Zenith Handels AG"),
    )
    assert decision.value is None
    assert decision.provenance is ProvenanceClass.AUTHOR_ADJUDICATED
    assert decision.competing_values == ("ACME GmbH", "Zenith Handels AG")


def test_majority_without_evidence_is_reported_but_still_escalates() -> None:
    decision = decide(
        "seller_name",
        ChannelReading("judge", "ACME GmbH"),
        ChannelReading("draft", "ACME GmbH"),
        ChannelReading("azure", "Zenith Handels AG"),
    )
    assert set(decision.agreeing_channels) == {"judge", "draft"}
    assert not decision.auto_accepted


def test_the_gate_settles_a_conflict_it_can_discriminate() -> None:
    """The whole reason the gate runs per reading: refuting the loser.

    An OCR channel reads `24OBXDE-009312` as `240BXDE-009312`. Two channels agree on a value
    the document itself prints; the dissenter's value appears nowhere. That is the same warrant
    a unanimous `text-layer-proven` cell carries, plus a refuted competitor, so escalating it
    would spend author attention defending the page against a misread.
    """
    decision = decide(
        "invoice_number",
        ChannelReading("judge", "24OBXDE-009312"),
        ChannelReading("draft", "24OBXDE-009312"),
        ChannelReading("azure", "240BXDE-009312"),
        text="Rechnung 24OBXDE-009312 vom 04.03.2024",
    )
    assert decision.provenance is ProvenanceClass.TEXT_LAYER_PROVEN
    assert decision.auto_accepted
    assert decision.value == "24OBXDE-009312"
    assert set(decision.agreeing_channels) == {"judge", "draft"}
    assert "not printed" in decision.note


def test_a_lone_printed_reading_does_not_outvote_the_others() -> None:
    """Presence is not assignment: one channel filing a printed string is still one opinion.

    Also pins the evidence guard on the specificity rank. The words are nested (`ACME GmbH`
    inside `ACME Holding GmbH`), but the page prints the SHORTER one, so `Holding` came from
    somewhere other than the document. That is the gate refuting the fuller reading, not the
    harmless brand-versus-legal-name difference, and it must stay at conflict severity.
    """
    decision = decide(
        "seller_name",
        ChannelReading("judge", "ACME GmbH"),
        ChannelReading("draft", "ACME Holding GmbH"),
        ChannelReading("azure", "ACME Holding GmbH"),
        text="ACME GmbH",
    )
    assert not decision.auto_accepted
    assert decision.rank is EscalationRank.CONFLICT_ONE_EVIDENCED


def test_a_less_specific_reading_is_not_a_rival_claim() -> None:
    """Azure returns the logo, the other channels the legal entity. One seller, two lengths.

    Ranking this alongside two channels naming two different companies put 27 cells of
    brand-versus-legal-name at the top of a worst-first sheet. It still needs an author —
    BT-27 (legal name) and BT-28 (trading name) are different fields — but it is the last
    thing to look at, and the same question every time.
    """
    decision = decide(
        "seller_name",
        ChannelReading("judge", "Nordkap (GmbH & Co KG)"),
        ChannelReading("draft", "Nordkap (GmbH & Co KG)"),
        ChannelReading("azure", "NORDKAP"),
        text="NORDKAP Nordkap (GmbH & Co KG) Rechnung",
    )
    assert decision.rank is EscalationRank.NESTED_READINGS
    assert decision.rank.value > EscalationRank.CONFLICT_NONE_EVIDENCED.value
    assert not decision.auto_accepted
    # A default is offered because every reading names the same seller.
    assert decision.value == "Nordkap (GmbH & Co KG)"


def test_a_truncated_identifier_is_a_rival_claim() -> None:
    """Word containment, not substring containment.

    `KR004411` inside `KR004411982` drops characters that change which thing is referenced,
    so it must keep escalating at full severity rather than being called a shorter rendering.
    """
    decision = decide(
        "buyer_reference",
        ChannelReading("judge", "KR004411982"),
        ChannelReading("azure", "KR004411"),
    )
    assert decision.rank is EscalationRank.CONFLICT_NONE_EVIDENCED
    assert decision.value is None


def test_the_majority_reading_is_proposed_not_the_longest() -> None:
    """Verbosity must not outvote independent confirmation."""
    decision = decide(
        "seller_name",
        ChannelReading("judge", "ACME GmbH"),
        ChannelReading("draft", "ACME GmbH"),
        ChannelReading("azure", "ACME Holding GmbH"),
    )
    assert decision.rank is EscalationRank.NESTED_READINGS
    assert decision.value == "ACME GmbH"
    assert set(decision.agreeing_channels) == {"judge", "draft"}


def test_numeric_policies_never_treat_a_shorter_value_as_less_specific() -> None:
    """`1.234,56` against `234,56` is a wrong number, not a terser one."""
    decision = decide(
        "grand_total_amount",
        ChannelReading("judge", "1.234,56"),
        ChannelReading("azure", "234,56"),
    )
    assert decision.rank is EscalationRank.CONFLICT_NONE_EVIDENCED
    assert decision.value is None


def test_both_sides_printed_discriminates_nothing_and_ranks_worst() -> None:
    """An invoice prints the seller's address AND the buyer's; the gate proves both.

    Ranking this by evidenced CHANNELS would have called it `conflict-one-evidenced` on a
    2-1 majority and buried it below cells with an actual tiebreaker.
    """
    decision = decide(
        "seller_address",
        ChannelReading("judge", "Via Del Ponte 4, 6900 Lugano"),
        ChannelReading("draft", "Via Del Ponte 4, 6900 Lugano"),
        ChannelReading("azure", "Ringstrasse 7, 30159 Hannover"),
        text="Via Del Ponte 4, 6900 Lugano Ringstrasse 7, 30159 Hannover",
    )
    assert decision.rank is EscalationRank.CONFLICT_NONE_EVIDENCED
    assert decision.value is None


# ---------------------------------------------------------------------------
# Weak, unparseable, exempt
# ---------------------------------------------------------------------------


def test_a_short_incidental_match_is_not_evidence() -> None:
    decision = decide(
        "invoice_number",
        ChannelReading("judge", "42"),
        text="Position 42 von 99",
    )
    assert decision.rank is EscalationRank.WEAK_MATCH
    assert not decision.auto_accepted
    assert decision.provenance is not ProvenanceClass.TEXT_LAYER_PROVEN


def test_a_weak_match_never_makes_a_cell_worse_than_no_match() -> None:
    """Monotonicity. A weak match means "found, but too short to count" — neutral, not bad.

    Ranking it above channel agreement inverted the gate: three channels agreeing on `EUR`
    escalated on 32 documents, while the same three agreeing on a Tier B page with no text
    layer at all were auto-accepted. Nothing is credited to the short match — the class is
    the one this cell would carry with no text layer whatsoever.
    """
    with_weak_match = decide(
        "invoice_currency_code",
        ChannelReading("judge", "EUR"),
        ChannelReading("azure", "EUR"),
        text="Gesamtbetrag 1.234,56 EUR",
    )
    without_any_layer = decide(
        "invoice_currency_code",
        ChannelReading("judge", "EUR"),
        ChannelReading("azure", "EUR"),
    )
    assert with_weak_match.provenance is ProvenanceClass.TWO_CHANNEL_AGREED
    assert with_weak_match.auto_accepted
    assert with_weak_match.provenance is without_any_layer.provenance
    assert "too short" in with_weak_match.note


def test_a_contradicting_reader_outranks_a_short_match() -> None:
    decision = decide(
        "invoice_number",
        ChannelReading("judge", "42"),
        ChannelReading("azure", None, covered=True),
        text="Position 42 von 99",
    )
    assert decision.rank is EscalationRank.NULL_DISPUTED
    assert decision.rank.value < EscalationRank.WEAK_MATCH.value


def test_unparseable_values_escalate_with_the_policy_named() -> None:
    """The ~8 known bad `issue_date` values land here; #118 is deferred by author decision."""
    decision = decide(
        "issue_date",
        ChannelReading("judge", "not a date at all"),
        ChannelReading("draft", "not a date at all"),
        text="not a date at all",
    )
    assert decision.rank is EscalationRank.UNPARSEABLE
    assert "date" in decision.note


def test_exempt_vocabulary_from_one_channel_escalates() -> None:
    """`document_type` stores "invoice" while the page prints "Rechnung"."""
    decision = decide(
        "document_type",
        ChannelReading("judge", "invoice"),
        text="Rechnung Nr. 5",
    )
    assert decision.provenance is ProvenanceClass.EXEMPT_BY_POLICY
    assert decision.rank is EscalationRank.EXEMPT_VOCABULARY


def test_exempt_vocabulary_two_channels_agreeing_is_settled() -> None:
    """No amount of searching will ever help here, so agreement is the only warrant."""
    decision = decide(
        "document_type",
        ChannelReading("judge", "invoice"),
        ChannelReading("draft", "invoice"),
        text="Rechnung Nr. 5",
    )
    assert decision.provenance is ProvenanceClass.TWO_CHANNEL_AGREED
    assert decision.auto_accepted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_blank_readings_are_not_treated_as_competing_values() -> None:
    decision = decide(
        "seller_name",
        ChannelReading("judge", "ACME GmbH"),
        ChannelReading("azure", "   "),
        text="ACME GmbH",
    )
    assert decision.rank is EscalationRank.SINGLE_CHANNEL_PROVEN
    assert decision.value == "ACME GmbH"


def test_canonical_for_compare_folds_money_and_falls_back_for_junk() -> None:
    assert canonical_for_compare("1.234,56", EvidencePolicy.MONEY) == "1234.56"
    assert canonical_for_compare("1234.56", EvidencePolicy.MONEY) == "1234.56"
    assert canonical_for_compare("  ", EvidencePolicy.MONEY) is None
    # Unparseable still compares literally rather than being called a conflict.
    assert canonical_for_compare("n/a", EvidencePolicy.MONEY) == canonical_for_compare(
        "N/A", EvidencePolicy.MONEY
    )


def test_policy_resolves_for_flat_and_group_cell_keys() -> None:
    assert policy_for_cell_key("grand_total_amount") is EvidencePolicy.MONEY
    assert policy_for_cell_key("line_items[0].name") is EvidencePolicy.TEXT
    assert policy_for_cell_key("vat_breakdown[2].category_code") is EvidencePolicy.EXEMPT


def test_adjudicate_document_answers_every_registry_field() -> None:
    decisions = adjudicate_document(
        {"judge": {"invoice_number": "R-1"}, "azure": {"invoice_number": "R-1"}},
        prepare_text_layer("R-1"),
    )
    assert [d.key for d in decisions] == list(FIELDS)


def test_adjudicate_document_honours_per_channel_coverage() -> None:
    decisions = adjudicate_document(
        {"judge": {"buyer_reference": "X-1"}, "azure": {}},
        EMPTY_LAYER,
        coverage={"azure": {"buyer_reference": False}},
    )
    by_key = {d.key: d for d in decisions}
    assert by_key["buyer_reference"].rank is EscalationRank.ASSERTED_UNEVIDENCED
    assert by_key["buyer_reference"].rank is not EscalationRank.NULL_DISPUTED


def test_escalated_orders_worst_first_then_by_key() -> None:
    decisions = [
        decide("seller_name", ChannelReading("judge", "A"), text="A"),
        decide(
            "seller_vat_id",
            ChannelReading("judge", "DE1"),
            ChannelReading("azure", "DE2"),
        ),
    ]
    ordered = escalated(decisions)
    assert [d.rank for d in ordered] == [
        EscalationRank.CONFLICT_NONE_EVIDENCED,
        EscalationRank.SINGLE_CHANNEL_PROVEN,
    ]


def test_collapse_summary_partitions_every_decision() -> None:
    decisions = adjudicate_document(
        {"judge": {"invoice_number": "R-1"}, "draft": {"invoice_number": "R-1"}},
        prepare_text_layer("R-1"),
    )
    summary = collapse_summary(decisions)
    assert summary["total"] == len(FIELDS)
    assert summary["auto_accepted"] + summary["escalated"] == summary["total"]
    assert sum(summary[p.value] for p in ProvenanceClass) == summary["total"]


def test_group_row_counts_surface_segmentation_disagreement() -> None:
    """Row-count mismatch is the group signal; positional cell diffs would be noise."""
    counts = group_row_counts(
        {
            "judge": {"line_items": [{"name": "a"}, {"name": "b"}]},
            "azure": {"line_items": [{"name": "ab"}]},
            "draft": {},
        },
        "line_items",
    )
    assert counts == {"judge": 2, "azure": 1, "draft": 0}
