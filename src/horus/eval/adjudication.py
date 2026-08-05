"""Collapse N channel readings + printed evidence into per-cell decisions (ADR-062).

The held-out set has ~1,100 asserted cells across three independent readings (the text-layer
draft, the ADR-060 vision judge, the ADR-061 Azure channel). Reviewing all of them by hand is
not a plan; reviewing none of them is what produced the retracted 0.5692. This module decides
which cells carry a warrant strong enough to accept without eyes, and ranks the rest so the
author's attention goes to the most dangerous ones first.

**The gate is run per channel value, not once per cell.** The printed-evidence gate proves a
string is on the page. When two channels disagree, the question that resolves it is *which of
the two values is printed* — unanswerable from a single precomputed verdict against one
channel's GT. So each reading is checked independently, and "evidenced" becomes a property of
a reading rather than of a cell. That per-reading verdict is then used to *settle* the
disagreements it can: when exactly one competing value is printed and at least two channels
assign it to the field, the losing readings are refuted by the document itself and the cell
does not need an author. Where two competing values are both printed — one invoice's two
addresses — the gate discriminates nothing and the cell escalates regardless of majority.

**What the gate can and cannot settle** (inherited from `printed_evidence`): it proves
presence, never field ASSIGNMENT. A seller VAT id and a buyer VAT id are both printed, so
filing one as the other passes. Assignment is what a second independent channel buys, which
is why `proven` alone is not the top provenance class here.

**Specificity is not conflict either.** `NORDKAP` against `Nordkap (GmbH & Co KG)` is one
seller at two levels of detail; a marketplace trader against the marketplace operator is a
real question about which party EN16931 BT-27 names. Word-set containment tells them apart, and
the first kind gets its own lowest rank rather than sitting at the top of a worst-first sheet
next to two channels naming different companies. It is still escalated — BT-27 and BT-28 are
different fields — just recognised as one recurring question instead of 27 mysteries.

**Coverage is not conflict.** A cell one channel filled and another left null is a coverage
gain, not a disagreement — the silent channel made no competing claim. Conflating the two is
how "109 disagreements" turned out to be mostly the judge filling fields the draft never
attempted. Silence and inability are distinguished too: a channel that *cannot express* a
field (Azure has no BT-46) is excluded from the vote entirely rather than counted as a vote
for absence.

Provenance classes are the five in ADR-062, and they are deliberately unequal:
`text-layer-proven` rests on the document's own bytes; `two-channel-agreed` rests on two
systems that could in principle fail together. Both are accepted, but the difference survives
into the final report instead of being absorbed into one headline number.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Final, NamedTuple

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS
from horus.eval.normalizers import (
    _normalize_predicted_code,
    _normalize_predicted_date,
    _normalize_predicted_money,
    _normalize_predicted_rate,
    _normalize_predicted_string,
)
from horus.eval.printed_evidence import (
    EvidencePolicy,
    EvidenceStatus,
    TextLayer,
    check_value,
    fold_characters,
    policy_for_field,
    policy_for_group_cell,
)

__all__ = [
    "AUTO_ACCEPTED_CLASSES",
    "CellDecision",
    "ChannelReading",
    "EscalationRank",
    "ProvenanceClass",
    "adjudicate_cell",
    "adjudicate_document",
    "canonical_for_compare",
    "collapse_summary",
    "escalated",
    "policy_for_cell_key",
]


class ProvenanceClass(Enum):
    """Why a promoted cell is believed. The five classes of ADR-062."""

    TEXT_LAYER_PROVEN = "text-layer-proven"
    TWO_CHANNEL_AGREED = "two-channel-agreed"
    AUTHOR_ADJUDICATED = "author-adjudicated"
    EXEMPT_BY_POLICY = "exempt-by-policy"
    NULL_CLAIM = "null-claim"


#: Classes a cell may carry without an author ever looking at it.
#:
#: `TWO_CHANNEL_AGREED` is included deliberately. Excluding it would escalate every Tier B
#: cell (338 of them, where no deterministic warrant can ever exist) and make the second
#: channel pointless. It is accepted but recorded as the weaker class, so the final
#: breakdown shows exactly how much of the answer key rests on agreement rather than proof.
AUTO_ACCEPTED_CLASSES: Final[frozenset[ProvenanceClass]] = frozenset(
    {
        ProvenanceClass.TEXT_LAYER_PROVEN,
        ProvenanceClass.TWO_CHANNEL_AGREED,
        ProvenanceClass.NULL_CLAIM,
    }
)


class EscalationRank(Enum):
    """How alarming an unresolved cell is. Lower ordinal = review sooner.

    Ordered by the damage an unnoticed error would do, which is not the same as how hard
    the cell is to decide. An unevidenced assertion that nothing contradicts is the worst
    case precisely because it looks fine: it enters the answer key silently and every
    number computed against it inherits the error.

    This deviates from the parent plan's ordering in two places, on purpose.

    `CONFLICT_NONE_EVIDENCED` is ranked ABOVE `CONFLICT_ONE_EVIDENCED`: a disagreement where
    one side is printed on the page nearly resolves itself; a disagreement where neither is
    (every Tier B conflict) has no tiebreaker at all. A disagreement where *both* sides are
    printed lands in the same rank, for the same reason — two competing addresses are both
    on the page, so the gate discriminates nothing and the author is on their own.

    `NULL_DISPUTED` is ranked 4 rather than last. The plan put it near the bottom on the
    reading that a null claim is mild, but this rank is only ever reached when the asserted
    value is NOT printed — an evidenced value against a silent channel exits earlier as
    proven. So it means "one reader claims something no text layer backs, and another reader
    looked and found nothing", which is the handoff's headline danger, not a footnote.

    `NESTED_READINGS` is last because the channels agree on WHO or WHAT the value refers to
    and differ only on how much of it to write down. It is a real question — EN16931 keeps
    the seller's legal name (BT-27) and trading name (BT-28) apart, so a logo mark and the
    registered entity behind it are not interchangeable — but it is one question repeated
    across the corpus, not a per-document mystery, and it is nothing like two channels naming
    two different companies.
    """

    ASSERTED_UNEVIDENCED = 1
    CONFLICT_NONE_EVIDENCED = 2
    CONFLICT_ONE_EVIDENCED = 3
    NULL_DISPUTED = 4
    WEAK_MATCH = 5
    UNPARSEABLE = 6
    EXEMPT_VOCABULARY = 7
    SINGLE_CHANNEL_PROVEN = 8
    NESTED_READINGS = 9

    @property
    def label(self) -> str:
        return self.name.lower().replace("_", "-")


@dataclass(frozen=True)
class ChannelReading:
    """One channel's answer for one cell.

    `covered` is the three-valued distinction from ADR-061 collapsed to a boolean at this
    layer: False means the channel *cannot express* this field, so it is excluded from the
    vote. A channel that can express the field and returned nothing is `covered=True,
    value=None` — an actual claim of absence, which counts.
    """

    channel: str
    value: str | None
    covered: bool = True
    confidence: float | None = None

    @property
    def asserts(self) -> bool:
        return self.covered and self.value is not None


@dataclass(frozen=True)
class CellDecision:
    """The verdict for one cell, with everything needed to defend or review it."""

    key: str
    policy: EvidencePolicy
    readings: tuple[ChannelReading, ...]
    provenance: ProvenanceClass
    value: str | None
    rank: EscalationRank | None = None
    evidenced_channels: tuple[str, ...] = ()
    agreeing_channels: tuple[str, ...] = ()
    matched_text: str | None = None
    page: int | None = None
    note: str = ""
    group_rows: tuple[int, ...] = field(default=())

    @property
    def auto_accepted(self) -> bool:
        """Whether this cell can be promoted without an author looking at it."""
        return self.rank is None and self.provenance in AUTO_ACCEPTED_CLASSES

    @property
    def competing_values(self) -> tuple[str, ...]:
        """Distinct asserted values, in channel order — empty when there is no conflict."""
        seen: list[str] = []
        for reading in self.readings:
            if reading.asserts and reading.value is not None and reading.value not in seen:
                seen.append(reading.value)
        return tuple(seen)


_NORMALIZERS: Final[dict[EvidencePolicy, object]] = {
    EvidencePolicy.MONEY: _normalize_predicted_money,
    EvidencePolicy.DATE: _normalize_predicted_date,
    EvidencePolicy.RATE: _normalize_predicted_rate,
    EvidencePolicy.CODE: _normalize_predicted_code,
    EvidencePolicy.TEXT: _normalize_predicted_string,
}


#: Separators that differ between two renderings of the SAME printed text.
#:
#: A postal address is the motivating case: it wraps across lines on the page, so one reader
#: returns `"Hauptstr. 1\n20095 Hamburg"` while another joins it as `"Hauptstr. 1, 20095
#: Hamburg"`. Those are one reading in two renderings, and reporting them as a disagreement
#: sends the author to eyeball an address on nearly every document for no benefit — the same
#: coverage-vs-conflict error this module exists to avoid, wearing a different hat.
#:
#: Only whitespace and separator punctuation are folded. Digits, letters and currency stay
#: untouched, so `Hauptstr. 1` and `Hauptstr. 11`, or `ACME GmbH` and `ACME AG`, remain the
#: genuine conflicts they are.
_TEXT_SEPARATORS: Final[str] = " \t\r\n,.;:/\\|-–—_·•()[]"


#: Maps every separator to a space so free text can be split into comparable tokens.
_SEPARATORS_TO_SPACE: Final[dict[int, str]] = str.maketrans(dict.fromkeys(_TEXT_SEPARATORS, " "))


def _dense_text(value: str) -> str:
    """Rendering-insensitive form of a free-text value, for channel comparison only.

    Mirrors the densified haystack the printed-evidence gate already searches against, for
    the same reason: the page's line breaks are a layout artefact, not content.
    """
    folded = fold_characters(value)
    return "".join(char for char in folded if char not in _TEXT_SEPARATORS).casefold()


def _tokens(value: str) -> frozenset[str]:
    """Word tokens of a free-text value, folded the same way the gate folds the page."""
    return frozenset(fold_characters(value).casefold().translate(_SEPARATORS_TO_SPACE).split())


def canonical_for_compare(value: str | None, policy: EvidencePolicy) -> str | None:
    """Canonical form used to decide whether two channels said the same thing.

    Runs BOTH sides through the scorer's own normalizers, per ADR-058's symmetric-
    normalization rule — a one-sided fold has already inverted a correct answer once in this
    codebase. `1.234,56` from one channel and `1234.56` from another are the same reading
    and must not be reported as a conflict; equally, a genuine difference must survive.

    Falls back to a casefolded whitespace-collapsed form when a value will not parse, so an
    unparseable pair can still be compared for literal equality instead of being declared a
    conflict on a technicality.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if policy is EvidencePolicy.TEXT:
        dense = _dense_text(text)
        return dense or None
    normalizer = _NORMALIZERS.get(policy)
    if normalizer is not None:
        canonical = normalizer(text)  # type: ignore[operator]
        if canonical:
            return str(canonical).casefold()
    return " ".join(text.split()).casefold()


def policy_for_cell_key(key: str) -> EvidencePolicy:
    """Resolve the evidence policy for a flat key or a `group[row].cell` key."""
    if "[" in key and "]." in key:
        group = key.split("[", 1)[0]
        cell = key.rsplit(".", 1)[1]
        return policy_for_group_cell(group, cell)
    return policy_for_field(key)


class _Group(NamedTuple):
    """What one agreeing set of readings contributes to a decision."""

    value: str | None
    primary_channel: str
    channels: tuple[str, ...]
    renderings: int


def _summarize(members: Sequence[ChannelReading], proven: frozenset[str]) -> _Group:
    """Collapse the readings that agree on one value into the fields a decision needs.

    Among channels that agree on CONTENT, prefers the rendering that is actually printed, and
    among those the fullest one. Free-text comparison is rendering-insensitive, so a group can
    hold two spellings of one address; storing the evidenced one keeps GT faithful to the
    page, and storing the fullest avoids silently promoting a truncation.
    """
    evidenced = [r for r in members if r.channel in proven]
    primary = max(evidenced or members, key=lambda r: len(r.value or ""))
    return _Group(
        value=primary.value,
        primary_channel=primary.channel,
        channels=tuple(r.channel for r in members),
        renderings=len({r.value for r in members if r.value is not None}),
    )


def _readings_are_nested(
    groups: Mapping[str, list[ChannelReading]], proven: frozenset[str]
) -> bool:
    """Whether the readings are one value written at different levels of detail.

    This is what separates `NORDKAP` against `Nordkap (GmbH & Co KG)` — one seller written at
    two levels of detail — from a marketplace trader against the marketplace operator, which
    is a genuine question about which party BT-27 names. Both look identical to a
    string-equality comparison, and lumping them together put 27 brand-versus-legal-name
    cells at the top of a worst-first sheet.

    Deliberately word-set containment, not substring containment: `KR004411` inside
    `KR004411982` is a truncated REFERENCE, where the missing characters change which thing
    is being referred to. Word containment cannot fire there, so identifiers keep escalating
    at full severity.

    Containment alone is not enough. If the page prints `ACME GmbH` and two channels return
    `ACME Holding GmbH`, the extra word came from somewhere other than the document — the
    gate is refuting the fuller reading, not merely failing to reach it. So the widest
    reading has to be one the gate proved, unless it proved nothing at all (Tier B, where
    detail differences genuinely cannot be arbitrated either way).
    """
    words = {canonical: _tokens(members[0].value or "") for canonical, members in groups.items()}
    host = max(words, key=lambda canonical: len(words[canonical]))
    if any(not candidate <= words[host] for candidate in words.values()):
        return False
    evidenced = {
        canonical
        for canonical, members in groups.items()
        if any(r.channel in proven for r in members)
    }
    return not evidenced or host in evidenced


def _plurality(groups: Mapping[str, list[ChannelReading]]) -> list[ChannelReading]:
    """The group with the most channels behind it; the fullest reading breaks a tie.

    Majority first, on purpose. Preferring the longest string outright would let one
    channel's `ACME Holding GmbH` displace two channels agreeing on `ACME GmbH` — trading
    independent confirmation for verbosity.
    """
    return max(groups.values(), key=lambda m: (len(m), len(_tokens(m[0].value or ""))))


def _rank_for_conflict(evidenced_groups: int) -> EscalationRank:
    """Rank on how many DISTINCT VALUES the gate found, not how many channels it proved.

    Counting channels conflates two opposite situations: three channels proving one value
    against a lone dissenter (nearly resolved) and three channels proving three different
    values (hopeless). Only the number of evidenced value groups says whether the gate
    discriminates, and discrimination is the whole reason the gate is run per reading.
    """
    if evidenced_groups == 1:
        return EscalationRank.CONFLICT_ONE_EVIDENCED
    return EscalationRank.CONFLICT_NONE_EVIDENCED


def adjudicate_cell(
    key: str,
    readings: Sequence[ChannelReading],
    layer: TextLayer,
    *,
    policy: EvidencePolicy | None = None,
) -> CellDecision:
    """Decide one cell from its channel readings and the document's text layer.

    The gate runs once PER ASSERTED READING, so a disagreement can be settled by asking
    which value is actually printed rather than by trusting whichever channel was checked.
    """
    resolved_policy = policy if policy is not None else policy_for_cell_key(key)
    readings = tuple(readings)
    # A reading whose value canonicalizes to nothing (whitespace, an empty token) is not an
    # assertion. Filtering here rather than later keeps the value-grouping below guaranteed
    # non-empty, so there is no path where a blank string becomes a competing "value".
    asserting = [
        r
        for r in readings
        if r.asserts and canonical_for_compare(r.value, resolved_policy) is not None
    ]

    # --- nobody claims a value -------------------------------------------------------
    if not asserting:
        # A channel that CAN express the field and returned nothing is claiming absence.
        # A channel that cannot is saying nothing at all. If nobody could even look, that
        # is not a null claim we can stand behind.
        claimants = [r.channel for r in readings if r.covered]
        if not claimants:
            return CellDecision(
                key=key,
                policy=resolved_policy,
                readings=readings,
                provenance=ProvenanceClass.NULL_CLAIM,
                value=None,
                rank=EscalationRank.ASSERTED_UNEVIDENCED,
                note="no channel can express this field — absence is unwarranted, not proven",
            )
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.NULL_CLAIM,
            value=None,
            agreeing_channels=tuple(claimants),
            note="every channel that could answer reported absence",
        )

    # --- gate each asserted reading independently -------------------------------------
    gated = {
        reading.channel: check_value(key, reading.value, resolved_policy, layer)
        for reading in asserting
    }
    evidenced = tuple(channel for channel, result in gated.items() if result.is_proven)
    weak = tuple(
        channel
        for channel, result in gated.items()
        if result.status is EvidenceStatus.FOUND and result.weak
    )
    unparseable = tuple(
        channel for channel, result in gated.items() if result.status is EvidenceStatus.UNPARSEABLE
    )

    groups: dict[str, list[ChannelReading]] = {}
    for reading in asserting:
        canonical = canonical_for_compare(reading.value, resolved_policy)
        if canonical is None:
            continue
        groups.setdefault(canonical, []).append(reading)

    # Silent channels that COULD have answered but did not, while others did: a disputed
    # null. Reported, but the mildest kind of dispute — an absence claim is unfalsifiable
    # by search, so a channel finding nothing is weak evidence against one that found
    # something.
    dissenting_nulls = tuple(r.channel for r in readings if r.covered and r.value is None)

    proven_channels = frozenset(channel for channel, result in gated.items() if result.is_proven)
    exempt = resolved_policy is EvidencePolicy.EXEMPT

    # --- conflict --------------------------------------------------------------------
    if len(groups) > 1:
        evidenced_groups = [
            members
            for members in groups.values()
            if any(r.channel in proven_channels for r in members)
        ]
        widest = max(len(members) for members in groups.values())
        # The gate is run per reading precisely so a disagreement can be settled by asking
        # which value is printed. When exactly one competing value is on the page AND at
        # least two independent channels assign it to this field, that is the same warrant
        # `text-layer-proven` already accepts unanimously — plus a refuted competitor,
        # which makes it strictly stronger, not weaker. Escalating it would send the author
        # to confirm a value the document itself backs against one it does not.
        if len(evidenced_groups) == 1 and len(evidenced_groups[0]) >= 2:
            members = evidenced_groups[0]
            if len(members) >= widest:
                won = _summarize(members, proven_channels)
                refuted = len(groups) - 1
                return CellDecision(
                    key=key,
                    policy=resolved_policy,
                    readings=readings,
                    provenance=ProvenanceClass.TEXT_LAYER_PROVEN,
                    value=won.value,
                    evidenced_channels=evidenced,
                    agreeing_channels=won.channels,
                    matched_text=gated[won.primary_channel].matched,
                    note=(
                        f"printed on the page and independently assigned by "
                        f"{len(won.channels)} channels; {refuted} competing reading(s) are "
                        "not printed at all"
                        + (
                            "; renderings differ, kept the printed one"
                            if won.renderings > 1
                            else ""
                        )
                    ),
                )
        plurality = _summarize(_plurality(groups), proven_channels)
        if resolved_policy is EvidencePolicy.TEXT and _readings_are_nested(groups, proven_channels):
            return CellDecision(
                key=key,
                policy=resolved_policy,
                readings=readings,
                provenance=ProvenanceClass.AUTHOR_ADJUDICATED,
                # Proposed, not accepted: `rank` keeps it off the auto-accept path. A value
                # is offered here — unlike a genuine conflict, where offering one would be
                # making the author's decision for them — because every reading names the
                # same thing, so the only open question is how much of it to keep.
                value=plurality.value,
                rank=EscalationRank.NESTED_READINGS,
                evidenced_channels=evidenced,
                agreeing_channels=plurality.channels,
                matched_text=gated[plurality.primary_channel].matched,
                note=(f"{len(groups)} readings of the same value at different levels of detail"),
            )
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.AUTHOR_ADJUDICATED,
            value=None,
            rank=_rank_for_conflict(len(evidenced_groups)),
            evidenced_channels=evidenced,
            agreeing_channels=plurality.channels,
            matched_text=gated[plurality.primary_channel].matched,
            note=f"{len(groups)} distinct values across {len(asserting)} channel(s)",
        )

    unanimous = _summarize(next(iter(groups.values())), proven_channels)
    winning_value = unanimous.value
    primary_channel = unanimous.primary_channel
    agreeing = unanimous.channels
    rendering_count = unanimous.renderings
    matched = gated[primary_channel].matched

    # --- unanimous among the channels that answered -----------------------------------
    if exempt:
        # Controlled vocabulary: the page prints "Rechnung" while GT stores "invoice", so
        # the gate structurally cannot apply. Two agreeing channels still settle it; one
        # does not, and no amount of searching will.
        if len(agreeing) >= 2:
            return CellDecision(
                key=key,
                policy=resolved_policy,
                readings=readings,
                provenance=ProvenanceClass.TWO_CHANNEL_AGREED,
                value=winning_value,
                agreeing_channels=agreeing,
                note="controlled vocabulary; settled by channel agreement, not by search",
            )
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.EXEMPT_BY_POLICY,
            value=winning_value,
            rank=EscalationRank.EXEMPT_VOCABULARY,
            agreeing_channels=agreeing,
            note="controlled vocabulary asserted by one channel; gate cannot apply",
        )

    if unparseable:
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.AUTHOR_ADJUDICATED,
            value=winning_value,
            rank=EscalationRank.UNPARSEABLE,
            evidenced_channels=evidenced,
            agreeing_channels=agreeing,
            note=f"value did not parse as {resolved_policy.value} for {', '.join(unparseable)}",
        )

    if evidenced and len(agreeing) >= 2:
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.TEXT_LAYER_PROVEN,
            value=winning_value,
            evidenced_channels=evidenced,
            agreeing_channels=agreeing,
            matched_text=matched,
            note=(
                f"printed on the page and independently assigned by {len(agreeing)} channels"
                + ("; renderings differ, kept the printed one" if rendering_count > 1 else "")
                + (f"; {', '.join(dissenting_nulls)} found nothing" if dissenting_nulls else "")
            ),
        )

    if evidenced:
        # Printed, but only one channel says it belongs to THIS field. The gate cannot
        # settle assignment, so this is escalated — at the lowest rank, because the value
        # is at least demonstrably on the page and nothing contradicts it.
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.TEXT_LAYER_PROVEN,
            value=winning_value,
            rank=EscalationRank.SINGLE_CHANNEL_PROVEN,
            evidenced_channels=evidenced,
            agreeing_channels=agreeing,
            matched_text=matched,
            note="printed on the page, but only one channel assigns it to this field",
        )

    if len(agreeing) >= 2:
        # Nothing deterministic backs this (the Tier B case), but two independent readers
        # produced the same string. Accepted, and permanently marked as the weaker warrant.
        #
        # Checked BEFORE `weak` on purpose. A weak match means "found, but too short to
        # count as evidence" — neutral, not negative. Ranking it above agreement made the
        # gate non-monotonic: three channels agreeing on `EUR` escalated, while the same
        # three agreeing on a Tier B page with no text layer at all were accepted. The
        # class recorded here is the one this cell would carry with no match whatsoever,
        # so nothing is credited to the short match.
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.TWO_CHANNEL_AGREED,
            value=winning_value,
            agreeing_channels=agreeing,
            matched_text=gated[weak[0]].matched if weak else None,
            note=(
                f"no text-layer warrant; {len(agreeing)} independent channels agree"
                + ("; renderings differ" if rendering_count > 1 else "")
                + ("; text-layer match too short to count" if weak else "")
                + (f"; {', '.join(dissenting_nulls)} found nothing" if dissenting_nulls else "")
            ),
        )

    if dissenting_nulls:
        # Ranked above `weak` (4 vs 5): a contradicting reader is a stronger reason to look
        # than a short match is a reason to relax.
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.AUTHOR_ADJUDICATED,
            value=winning_value,
            rank=EscalationRank.NULL_DISPUTED,
            agreeing_channels=agreeing,
            matched_text=gated[weak[0]].matched if weak else None,
            note=f"asserted by {', '.join(agreeing)}; {', '.join(dissenting_nulls)} found nothing",
        )

    if weak:
        return CellDecision(
            key=key,
            policy=resolved_policy,
            readings=readings,
            provenance=ProvenanceClass.AUTHOR_ADJUDICATED,
            value=winning_value,
            rank=EscalationRank.WEAK_MATCH,
            agreeing_channels=agreeing,
            matched_text=gated[weak[0]].matched,
            note="match too short to be evidence — a 2-3 character string occurs incidentally",
        )

    # One channel, no evidence, nobody contradicting. The most dangerous cell there is:
    # it looks exactly like a good one.
    return CellDecision(
        key=key,
        policy=resolved_policy,
        readings=readings,
        provenance=ProvenanceClass.AUTHOR_ADJUDICATED,
        value=winning_value,
        rank=EscalationRank.ASSERTED_UNEVIDENCED,
        agreeing_channels=agreeing,
        note=(f"asserted only by {primary_channel}, with no printed evidence and no confirmation"),
    )


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def adjudicate_document(
    channels: Mapping[str, Mapping[str, object]],
    layer: TextLayer,
    *,
    coverage: Mapping[str, Mapping[str, bool]] | None = None,
) -> list[CellDecision]:
    """Adjudicate every flat field of one invoice across all channels.

    Args:
        channels: `{channel_name: {field_key: value}}`.
        layer: the document's extracted text layer (empty for Tier B).
        coverage: optional `{channel_name: {field_key: can_express}}`; a field absent from
            a channel's map defaults to covered. This is how ADR-061's `not-covered` state
            reaches the vote, and getting it wrong would let Azure's structural silence
            count as a claim that the field is absent.

    Returns:
        One decision per registered flat field, in registry order.

    Repeating groups are deliberately not adjudicated cell-by-cell here: rows do not align
    across channels (one reader may split a line the other merges), so a positional cell
    comparison would manufacture conflicts out of a difference in row segmentation. Group
    review is a row-level task and is handled separately.
    """
    coverage = coverage or {}
    decisions: list[CellDecision] = []
    for key in FIELDS:
        readings = [
            ChannelReading(
                channel=name,
                value=_as_text(values.get(key)),
                covered=coverage.get(name, {}).get(key, True),
            )
            for name, values in channels.items()
        ]
        decisions.append(adjudicate_cell(key, readings, layer))
    return decisions


def escalated(decisions: Sequence[CellDecision]) -> list[CellDecision]:
    """Cells needing an author, worst first then by key for a stable sheet order."""
    pending = [d for d in decisions if not d.auto_accepted and d.rank is not None]
    return sorted(pending, key=lambda d: (d.rank.value if d.rank else 99, d.key))


def collapse_summary(decisions: Sequence[CellDecision]) -> dict[str, int]:
    """Counts for the collapse ratio — the deliverable of the adjudication pass.

    Safe to print: counts only, no values.
    """
    accepted = [d for d in decisions if d.auto_accepted]
    # A cell nobody claimed a value for is a null claim. Counting those as "collapsed"
    # inflates the ratio with cells that never needed work — roughly half an invoice's
    # schema is legitimately absent, so the asserted-only figure is the honest one and both
    # are reported rather than letting a reader pick the flattering denominator.
    asserted = [d for d in decisions if d.provenance is not ProvenanceClass.NULL_CLAIM]
    summary: dict[str, int] = {
        "total": len(decisions),
        "auto_accepted": len(accepted),
        "escalated": len(decisions) - len(accepted),
        "asserted_total": len(asserted),
        "asserted_auto_accepted": sum(1 for d in asserted if d.auto_accepted),
        "asserted_escalated": sum(1 for d in asserted if not d.auto_accepted),
        "null_claims": len(decisions) - len(asserted),
    }
    for provenance in ProvenanceClass:
        matching = [d for d in decisions if d.provenance is provenance]
        summary[provenance.value] = len(matching)
        # A cell can carry the strongest provenance and STILL be escalated — a printed value
        # only one channel assigned to the field is `text-layer-proven` but unconfirmed on
        # assignment. Reporting the class alone would overstate what has actually been
        # settled, so the accepted share is broken out.
        summary[f"{provenance.value}/accepted"] = sum(1 for d in matching if d.auto_accepted)
    for rank in EscalationRank:
        summary[rank.label] = sum(1 for d in decisions if d.rank is rank)
    return summary


def group_row_counts(channels: Mapping[str, Mapping[str, object]], group: str) -> dict[str, int]:
    """Row count per channel for one repeating group.

    A disagreement in row COUNT is the signal worth surfacing for groups: it means the
    readers segmented the table differently, which no cell-level comparison can express.
    """
    if group not in REPEATING_GROUPS:
        raise KeyError(f"{group!r} is not a registered repeating group")
    counts: dict[str, int] = {}
    for name, values in channels.items():
        rows = values.get(group)
        counts[name] = len(rows) if isinstance(rows, Sequence) and not isinstance(rows, str) else 0
    return counts
