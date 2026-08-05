"""Printed-evidence gate — is a ground-truth value actually ON the page it claims?

Motivation, stated bluntly because it is a correction rather than a feature: the
superseded held-out ground truth was drafted by a model reading each PDF's text layer,
and 12 of the 39 documents have **no text layer at all**. For those, the drafter had no
input and the values it produced were invented — yet they looked exactly like the real
ones, and scoring against them produced a plausible 0.5692 that had to be retracted.

This module removes the class of error rather than the instance. A value may enter ground
truth only if the document's own text layer contains it. The text layer is the strongest
evidence available here: for a born-digital PDF those are the literal character codes the
issuer embedded when generating the file — not a reading, not an interpretation, and not
a model's opinion.

**What this gate proves, and what it does not.** It proves a string is present on the
page, which makes fabrication structurally impossible. It does **not** prove the string
belongs to the field it was filed under: a seller VAT id and a buyer VAT id are both
printed, so filing one as the other passes the gate. Field ASSIGNMENT must be settled by
an independent channel (the ADR-060 vision judge), and the two disciplines are
deliberately separated — conflating them is how a gate becomes a false sense of rigour.

It also cannot prove a NEGATIVE. "This field is absent" is unfalsifiable by search, and
roughly half the schema is legitimately absent on a typical invoice, so nulls carry a
weaker warrant by construction and must be reported as such rather than counted as
verified.

**Why per-field policies instead of one substring test.** A naive ``value in text`` check
fails three different ways on real invoices, each silently:

- IBANs and card numbers print grouped (``DE89 3704 0044 …``) while GT stores them bare,
  so a correct value is reported missing.
- Addresses wrap across lines, so the stored one-line form never matches the extracted
  two-line form.
- Money, dates and rates are stored canonically (``1234.56``, ``2026-03-17``) and printed
  in locale form (``1.234,56``, ``17.03.2026``), so a correct value never matches
  literally in either direction.

So numeric values are canonicalized through the SCORER's own normalizers and then
searched for as every plausible PRINTED rendering. Both disciplines are inherited from
ADR-058: compare as printed, and normalize symmetrically on both sides.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS
from horus.eval.normalizers import (
    _normalize_predicted_date,
    _normalize_predicted_money,
    _normalize_predicted_rate,
)

# --------------------------------------------------------------------------------------
# Text-layer extraction
# --------------------------------------------------------------------------------------

#: Characters that differ typographically but not semantically for presence testing.
#: PDFs freely mix these with their ASCII counterparts, and a stored value will have been
#: keyed with whichever the author's editor produced.
_CHAR_FOLDING: Final[dict[str, str]] = {
    "\u00a0": " ",  # no-break space
    "\u202f": " ",  # narrow no-break space
    "\u2007": " ",  # figure space
    "\u2009": " ",  # thin space
    "\u200b": "",  # zero-width space
    "\u00ad": "",  # soft hyphen
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",  # minus sign
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
}


def fold_characters(text: str) -> str:
    """NFKC-normalize and fold typographic variants to their ASCII counterparts.

    NFKC handles ligatures and most exotic spaces; the explicit table covers dashes and
    quotes, which NFKC deliberately leaves alone but which are interchangeable for
    deciding whether a value appears on a page.
    """
    folded = unicodedata.normalize("NFKC", text)
    return "".join(_CHAR_FOLDING.get(char, char) for char in folded)


@dataclass(frozen=True)
class TextLayer:
    """A PDF's extracted text, in the two shapes the gate searches.

    Both haystacks are pre-computed once per document because a full GT check runs ~48
    lookups against them.
    """

    raw: str
    collapsed: str
    dense: str
    word_count: int

    @property
    def exists(self) -> bool:
        """Whether this PDF has a usable text layer at all.

        False is the Tier B signal: no deterministic evidence is available for this
        document and every value must come from the independent channels instead.
        """
        return self.word_count > 0


def prepare_text_layer(raw: str) -> TextLayer:
    """Build the searchable forms of an extracted text layer.

    ``collapsed`` reduces every whitespace run to one space, which is what makes a
    wrapped address findable. ``dense`` removes whitespace entirely, which is what makes
    a grouped IBAN and a spaced-out date findable. Both are casefolded, because letter
    case is a rendering choice (a header may shout a seller name that GT stores in title
    case) and the gate is asking about presence, not typography.
    """
    folded = fold_characters(raw)
    collapsed = " ".join(folded.split()).casefold()
    dense = "".join(folded.split()).casefold()
    return TextLayer(raw=raw, collapsed=collapsed, dense=dense, word_count=len(folded.split()))


def extract_text_layer(pdf_path: Path) -> TextLayer:
    """Extract and prepare the embedded text layer of a PDF.

    Uses ``pypdfium2``, already a direct dependency per ADR-014 — so no new dependency
    and no Poppler system binary, consistent with ADR-014 having rejected
    Poppler-via-subprocess for the rasterizer. ``get_text_bounded`` is chosen over
    ``get_text_range`` because the latter is limited to UCS-2 while invoices carry
    ``€``, ``ä``, ``ß`` and similar.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        pages: list[str] = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                pages.append(textpage.get_text_bounded())
            finally:
                textpage.close()
                page.close()
    finally:
        pdf.close()
    # PDFium emits CRLF; normalize so downstream line handling is platform-neutral.
    return prepare_text_layer("\n".join(pages).replace("\r\n", "\n"))


# --------------------------------------------------------------------------------------
# Printed-variant generation
# --------------------------------------------------------------------------------------


def _group_thousands(digits: str, separator: str) -> str:
    """Insert a thousands separator every three digits from the right."""
    if len(digits) <= 3:
        return digits
    head = len(digits) % 3 or 3
    parts = [digits[:head]] + [digits[i : i + 3] for i in range(head, len(digits), 3)]
    return separator.join(parts)


def money_printed_variants(canonical: str) -> set[str]:
    """Every plausible printed rendering of a canonical ``1234.56`` amount.

    Covers German (``1.234,56``) and Anglo (``1,234.56``) grouping, ungrouped forms,
    space grouping, and the German whole-amount shorthand ``50,-``. Signed and unsigned
    forms are both emitted: a deduction may print as ``-14,73`` while GT stores the
    magnitude, or the reverse, and the gate is asking about presence, not sign
    convention — sign correctness is the scorer's business, not this module's.
    """
    negative = canonical.startswith("-")
    body = canonical.lstrip("-")
    integer_part, _, fraction = body.partition(".")
    fraction = fraction or "00"

    magnitudes: set[str] = set()
    for separator, decimal_mark in ((".", ","), (",", "."), (" ", ","), ("", ",")):
        grouped = _group_thousands(integer_part, separator) if separator else integer_part
        magnitudes.add(f"{grouped}{decimal_mark}{fraction}")
    magnitudes.add(f"{integer_part}.{fraction}")

    if fraction == "00":
        for separator in (".", ",", " ", ""):
            grouped = _group_thousands(integer_part, separator) if separator else integer_part
            magnitudes.add(grouped)
            magnitudes.add(f"{grouped},-")
            magnitudes.add(f"{grouped}.-")

    variants = set(magnitudes)
    if negative:
        variants |= {f"-{m}" for m in magnitudes}
        variants |= {f"({m})" for m in magnitudes}
    return variants


#: Month names as German and English invoices actually print them, indexed 1-12.
_MONTH_NAMES: Final[dict[int, tuple[str, ...]]] = {
    1: ("Januar", "Jan", "January"),
    2: ("Februar", "Feb", "February"),
    3: ("März", "Maerz", "Mrz", "Mär", "March", "Mar"),
    4: ("April", "Apr"),
    5: ("Mai", "May"),
    6: ("Juni", "Jun", "June"),
    7: ("Juli", "Jul", "July"),
    8: ("August", "Aug"),
    9: ("September", "Sep", "Sept"),
    10: ("Oktober", "Okt", "October", "Oct"),
    11: ("November", "Nov"),
    12: ("Dezember", "Dez", "December", "Dec"),
}


def date_printed_variants(iso: str) -> set[str]:
    """Every plausible printed rendering of an ISO ``YYYY-MM-DD`` date.

    Includes German dotted, Anglo slashed in BOTH field orders, ISO, and long forms with
    German and English month names. Both ``DD/MM`` and ``MM/DD`` are emitted because the
    held-out set spans German and English documents and a slashed date is genuinely
    ambiguous — resolving it is the judge's job; the gate only asks whether SOME
    rendering of this date is printed.
    """
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso)
    if not match:
        return set()
    year, month, day = match.group(1), match.group(2), match.group(3)
    d_int, m_int = str(int(day)), str(int(month))

    variants: set[str] = {iso}
    for separator in (".", "/", "-"):
        variants.add(f"{day}{separator}{month}{separator}{year}")
        variants.add(f"{d_int}{separator}{m_int}{separator}{year}")
        variants.add(f"{month}{separator}{day}{separator}{year}")
        variants.add(f"{m_int}{separator}{d_int}{separator}{year}")
        variants.add(f"{day}{separator}{month}{separator}{year[2:]}")
    variants.add(f"{day}.{month}.")  # German short form, year implied by context

    for name in _MONTH_NAMES[int(month)]:
        variants.add(f"{day}. {name} {year}")
        variants.add(f"{d_int}. {name} {year}")
        variants.add(f"{d_int} {name} {year}")
        variants.add(f"{name} {d_int}, {year}")
        variants.add(f"{name} {day}, {year}")
        variants.add(f"{name} {d_int} {year}")
    return variants


def rate_printed_variants(canonical: str) -> set[str]:
    """Every plausible printed rendering of a VAT rate such as ``19`` or ``7.5``.

    Percent-suffixed forms are emitted alongside bare numbers so the caller can prefer a
    match carrying percent context. A bare ``19`` matches inside an unrelated ``19.03.``
    date, which is why :func:`check_value` marks short numeric matches weak instead of
    treating them as proof.
    """
    try:
        number = float(canonical)
    except ValueError:
        return set()

    bases: set[str] = set()
    for decimals in (0, 1, 2):
        text = f"{number:.{decimals}f}"
        if decimals and text.rstrip("0").endswith("."):
            pass  # keep trailing-zero forms: invoices print "19,00" verbatim
        bases.add(text)
        bases.add(text.replace(".", ","))
    variants = set(bases)
    for base in bases:
        variants.add(f"{base}%")
        variants.add(f"{base} %")
    return variants


# --------------------------------------------------------------------------------------
# Policies
# --------------------------------------------------------------------------------------


class EvidencePolicy(Enum):
    """How a field's value must be looked for in the text layer."""

    TEXT = "text"
    CODE = "code"
    MONEY = "money"
    DATE = "date"
    RATE = "rate"
    EXEMPT = "exempt"


class EvidenceStatus(Enum):
    """The verdict for one ground-truth cell."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    EXEMPT = "exempt"
    NULL_CLAIM = "null_claim"
    NO_TEXT_LAYER = "no_text_layer"
    UNPARSEABLE = "unparseable"


#: Fields whose GT value is a controlled-vocabulary token that is NEVER printed as
#: stored, so the gate cannot apply and must say so rather than report a false miss.
#: ``document_type`` stores "invoice" while the page prints "Rechnung"; BT-81 stores the
#: UNTDID 4461 numeric code while the page prints "Überweisung".
EXEMPT_FIELDS: Final[frozenset[str]] = frozenset({"document_type", "payment_means_code"})

#: Same reasoning, for repeating-group cells: BT-118 is an EN16931 category letter.
EXEMPT_GROUP_CELLS: Final[frozenset[tuple[str, str]]] = frozenset(
    {("vat_breakdown", "category_code")}
)

#: Codes that are commonly printed as a symbol instead of the code itself.
_CODE_SYMBOL_VARIANTS: Final[dict[str, tuple[str, ...]]] = {
    "EUR": ("€",),
    "USD": ("$",),
    "GBP": ("£",),
    "CHF": ("SFr.", "Fr."),
}

_POLICY_BY_FIELD_TYPE: Final[dict[str, EvidencePolicy]] = {
    "STRING": EvidencePolicy.TEXT,
    "CODE": EvidencePolicy.CODE,
    "MONEY": EvidencePolicy.MONEY,
    "DATE": EvidencePolicy.DATE,
    "RATE": EvidencePolicy.RATE,
}


def policy_for_field(key: str) -> EvidencePolicy:
    """Resolve the evidence policy for a flat field from the field registry."""
    if key in EXEMPT_FIELDS:
        return EvidencePolicy.EXEMPT
    spec = FIELDS.get(key)
    if spec is None:
        raise KeyError(f"{key!r} is not a registered flat field")
    return _POLICY_BY_FIELD_TYPE[spec.field_type]


def policy_for_group_cell(group: str, cell: str) -> EvidencePolicy:
    """Resolve the evidence policy for a repeating-group cell from the registry.

    Group cells carry their own ``FieldSpec``, so policy derives from the same
    ``field_type`` source as flat fields rather than from a parallel hand-maintained
    table that could drift out of step with the schema.
    """
    if (group, cell) in EXEMPT_GROUP_CELLS:
        return EvidencePolicy.EXEMPT
    entry = REPEATING_GROUPS.get(group)
    if entry is None:
        raise KeyError(f"{group!r} is not a registered repeating group")
    _row_xpath, cells = entry
    spec = cells.get(cell)
    if spec is None:
        raise KeyError(f"{cell!r} is not a registered cell of {group!r}")
    return _POLICY_BY_FIELD_TYPE[spec.field_type]


# --------------------------------------------------------------------------------------
# Checking
# --------------------------------------------------------------------------------------

#: Densified matches shorter than this are reported weak: a 2-3 character numeric string
#: occurs incidentally all over an invoice, so its presence is not evidence.
MIN_STRONG_MATCH_LEN = 4


@dataclass(frozen=True)
class EvidenceResult:
    """The gate's verdict for one ground-truth cell, with the evidence that produced it."""

    key: str
    value: str | None
    policy: EvidencePolicy
    status: EvidenceStatus
    matched: str | None = None
    weak: bool = False

    @property
    def is_proven(self) -> bool:
        """Whether the value is deterministically evidenced and strongly so."""
        return self.status is EvidenceStatus.FOUND and not self.weak

    @property
    def needs_review(self) -> bool:
        """Whether a human must look at this cell.

        Everything that is not strong deterministic evidence needs a second opinion —
        including exempt and null cells, whose warrant comes from elsewhere entirely.
        """
        return not self.is_proven


def _search(needles: set[str], layer: TextLayer) -> str | None:
    """Return the longest needle present in the dense haystack, or None.

    Longest-first so the reported evidence is the most specific rendering that matched,
    which is what makes the ``weak`` judgement meaningful.
    """
    for needle in sorted(needles, key=len, reverse=True):
        dense_needle = "".join(needle.split()).casefold()
        if dense_needle and dense_needle in layer.dense:
            return needle
    return None


def check_value(
    key: str,
    value: str | None,
    policy: EvidencePolicy,
    layer: TextLayer,
) -> EvidenceResult:
    """Decide whether one ground-truth value has printed evidence in the text layer."""
    if policy is EvidencePolicy.EXEMPT:
        return EvidenceResult(key, value, policy, EvidenceStatus.EXEMPT)
    if value is None or not str(value).strip():
        return EvidenceResult(key, None, policy, EvidenceStatus.NULL_CLAIM)
    if not layer.exists:
        return EvidenceResult(key, value, policy, EvidenceStatus.NO_TEXT_LAYER)

    text = str(value).strip()

    if policy is EvidencePolicy.TEXT:
        needle = " ".join(fold_characters(text).split()).casefold()
        if needle and needle in layer.collapsed:
            return EvidenceResult(key, value, policy, EvidenceStatus.FOUND, matched=text)
        return EvidenceResult(key, value, policy, EvidenceStatus.NOT_FOUND)

    if policy is EvidencePolicy.CODE:
        candidates = {text, *_CODE_SYMBOL_VARIANTS.get(text.upper(), ())}
        matched = _search(candidates, layer)
        if matched is None:
            return EvidenceResult(key, value, policy, EvidenceStatus.NOT_FOUND)
        dense_len = len("".join(matched.split()))
        return EvidenceResult(
            key, value, policy, EvidenceStatus.FOUND, matched, dense_len < MIN_STRONG_MATCH_LEN
        )

    normalizer, variant_builder = {
        EvidencePolicy.MONEY: (_normalize_predicted_money, money_printed_variants),
        EvidencePolicy.DATE: (_normalize_predicted_date, date_printed_variants),
        EvidencePolicy.RATE: (_normalize_predicted_rate, rate_printed_variants),
    }[policy]

    canonical = normalizer(text)
    if canonical is None:
        # The stored value is not even parseable as its declared type; that is a GT
        # defect in its own right and must not be silently reported as "not printed".
        return EvidenceResult(key, value, policy, EvidenceStatus.UNPARSEABLE)

    variants = variant_builder(canonical) | {text}
    matched = _search(variants, layer)
    if matched is None:
        return EvidenceResult(key, value, policy, EvidenceStatus.NOT_FOUND)
    if policy is EvidencePolicy.RATE:
        # A rate is inherently short, so length says nothing about it. What separates
        # evidence from coincidence is the percent sign: "19" alone also occurs inside
        # "19.03." and "19 Stück", while "19 %" does not.
        weak = "%" not in matched
    else:
        weak = len("".join(matched.split())) < MIN_STRONG_MATCH_LEN
    return EvidenceResult(key, value, policy, EvidenceStatus.FOUND, matched, weak)


def check_gt_document(
    fields: Mapping[str, object],
    groups: Mapping[str, Sequence[Mapping[str, object]]],
    layer: TextLayer,
) -> list[EvidenceResult]:
    """Check every cell of one GT document, flat fields then repeating groups.

    Group cells are keyed ``group[row].cell`` so a result list is self-describing when
    rendered into a review sheet. Every registered flat field is checked, including the
    ones GT omitted, because an omitted field is a null CLAIM that also needs a warrant.
    """
    results = [
        check_value(key, _as_text(fields.get(key)), policy_for_field(key), layer) for key in FIELDS
    ]
    for group in REPEATING_GROUPS:
        _row_xpath, cells = REPEATING_GROUPS[group]
        for row_index, row in enumerate(groups.get(group, []) or []):
            for cell in cells:
                results.append(
                    check_value(
                        f"{group}[{row_index}].{cell}",
                        _as_text(row.get(cell)),
                        policy_for_group_cell(group, cell),
                        layer,
                    )
                )
    return results


def _as_text(value: object) -> str | None:
    """Coerce a GT value to the string form the gate searches for."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def summarize(results: list[EvidenceResult]) -> dict[str, int]:
    """Count results by status, plus the two roll-ups a caller actually acts on."""
    counts: dict[str, int] = {status.value: 0 for status in EvidenceStatus}
    for result in results:
        counts[result.status.value] += 1
    counts["proven"] = sum(1 for r in results if r.is_proven)
    counts["needs_review"] = sum(1 for r in results if r.needs_review)
    return counts
