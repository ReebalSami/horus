r"""Predicted-side value normalizers — messy VLM output → canonical-or-None.

Shared low-level normalization layer for the prediction side of the eval
pipeline. Each function takes a raw string as emitted by a VLM (or recovered
from its JSON) and returns the canonical form that the GT-side normalizers in
``ground_truth.py`` produce — or ``None`` when the value is unparseable.

These mirror PR(a)'s GT-side normalizers (ADR-012) but are deliberately more
*lenient*: the GT side parses clean CII XML and may raise on malformed input,
whereas the prediction side must tolerate German/US locale variance, currency
symbols, percent signs, month names, and chat noise, collapsing the
unparseable case to ``None`` (which the scorer's truth table maps to FN/TN).

Two consumers (ADR-035 §"Decision" — one validate/repair home, no duplication):

  - ``src/horus/eval/scorer.py`` (ADR-013/027) — comparison-time canonicalization
    of the predicted value before the per-field-type comparator.
  - ``src/horus/eval/schema.py`` (ADR-035) — ``InvoiceFields`` post-hoc
    validate/repair: the typed structurer target that doubles as the JSON-arm
    fine-tuning target (#88).

Layering: this module depends only on the stdlib. ``scorer`` and ``schema``
both import *from* it; it imports from neither (no cycle). Functions retain
their leading-underscore names + are re-exported by ``scorer`` so existing
call sites (``from horus.eval.scorer import _normalize_predicted_money``) and
their tests keep working unchanged.

Refs: ADR-013 (scorer + original home of these), ADR-035 (the shared-reuse
extraction + the RATE type), ADR-012 (GT-side canonical forms these match).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

# German month names + common abbreviations → month number. Used by
# `_normalize_predicted_date` for the "05. März 2018" shape German invoices
# print in body text (the embedded CII date is always numeric CCYYMMDD, but a
# VLM reading the rendered page may transcribe the printed month name).
_MONTHS_DE: dict[str, int] = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "mae": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}


def _normalize_predicted_money(raw: str) -> str | None:
    """Normalize a predicted money value to canonical 2-decimal string.

    Accepts:
      - ``"529.87"`` (canonical) → ``"529.87"``
      - ``"529,87"`` (German decimal-comma) → ``"529.87"``
      - ``"1.234,56"`` (German thousand-period + decimal-comma) → ``"1234.56"``
      - ``"1,234.56"`` (US thousand-comma + decimal-period) → ``"1234.56"``
      - ``"529,87 €"`` / ``"€529,87"`` / ``"EUR 529,87"`` → ``"529.87"``
      - Negative values via leading ``-`` (preserved)

    Returns:
        Canonical 2-decimal string (matching PR(a)'s ``_normalize_money``
        output format), or ``None`` if the input doesn't parse as a number.
    """
    if not raw:
        return None
    s = raw.strip()
    # Strip currency symbols + ISO code prefixes
    s = re.sub(r"(€|EUR|USD|\$)", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    # Detect format by looking at the LAST decimal separator:
    #   "1.234,56" → ',' is the decimal (German); strip dots, replace comma with dot
    #   "1,234.56" → '.' is the decimal (US); strip commas
    #   "529,87"   → ',' is the decimal (German short)
    #   "529.87"   → '.' is the decimal (US short)
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")
    if last_comma > last_dot:
        # Comma is the decimal separator → German format
        s = s.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        # Dot is the decimal separator → US format
        s = s.replace(",", "")
    else:
        # No separator → integer (treat as exact)
        pass
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return str(d.quantize(Decimal("0.01")))


def _normalize_predicted_date(raw: str) -> str | None:
    """Normalize a predicted date to ISO-8601 (``YYYY-MM-DD``).

    Accepts:
      - ``"2018-03-05"`` (ISO, canonical) → ``"2018-03-05"``
      - ``"05.03.2018"`` (German DD.MM.YYYY) → ``"2018-03-05"``
      - ``"5.3.2018"`` (German with no zero-padding) → ``"2018-03-05"``
      - ``"05. März 2018"`` (German month name) → ``"2018-03-05"``
      - ``"05/03/2018"`` (DD/MM/YYYY) → ``"2018-03-05"``
      - ``"05-03-2018"`` (DD-MM-YYYY) → ``"2018-03-05"``

    Year-month-day vs day-month-year ambiguity: when the first component is
    4 digits, treat as ``YYYY-MM-DD``; otherwise treat as ``DD-MM-YYYY``
    (the German invoice convention).

    Returns:
        ISO-8601 date string ``"YYYY-MM-DD"``, or ``None`` if the input
        doesn't parse.
    """
    if not raw:
        return None
    s = raw.strip()
    # Try ISO first (year-first)
    iso_match = re.fullmatch(r"(\d{4})[\-./](\d{1,2})[\-./](\d{1,2})", s)
    if iso_match:
        y, m, d = (int(g) for g in iso_match.groups())
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            return None
    # German month-name pattern: "05. März 2018" or "5 März 2018"
    month_match = re.fullmatch(
        r"(\d{1,2})\.?\s+([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", s, flags=re.IGNORECASE
    )
    if month_match:
        d_str, month_name, y_str = month_match.groups()
        month_int = _MONTHS_DE.get(month_name.lower())
        if month_int is None:
            return None
        try:
            return date(int(y_str), month_int, int(d_str)).isoformat()
        except ValueError:
            return None
    # German/EU day-first: "05.03.2018" / "05/03/2018" / "05-03-2018"
    day_first = re.fullmatch(r"(\d{1,2})[\-./](\d{1,2})[\-./](\d{4})", s)
    if day_first:
        d, m, y = (int(g) for g in day_first.groups())
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            return None
    return None


def _normalize_predicted_code(raw: str, *, nfc: bool = True) -> str | None:
    """Normalize a predicted code (VAT ID, GLN, invoice number, currency code).

    Strips outer whitespace, applies optional NFC, removes internal whitespace
    in well-known formats (e.g., ``"DE 123456789"`` → ``"DE123456789"``).

    Args:
        raw: predicted value.
        nfc: if True, apply Unicode NFC normalization (default).

    Returns:
        Normalized code string, or ``None`` if input is empty.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if nfc:
        s = unicodedata.normalize("NFC", s)
    # Strip internal whitespace for VAT IDs and similar codes where spaces
    # are formatting noise (e.g., "DE 123 456 789" → "DE123456789")
    # Detect: starts with country code (2 letters) followed by digits
    if re.match(r"^[A-Z]{2}\s*\d", s):
        s = re.sub(r"\s+", "", s)
    return s


def _normalize_predicted_string(raw: str, *, nfc: bool = True) -> str | None:
    """Normalize a predicted free-text string (names, addresses).

    Strips outer whitespace + applies NFC (preserves internal whitespace).
    Returns None on empty input.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if nfc:
        s = unicodedata.normalize("NFC", s)
    return s


def _normalize_predicted_rate(raw: str) -> str | None:
    """Normalize a predicted VAT rate (BT-119) to a canonical numeric string.

    The faithful prediction-side counterpart of ``ground_truth._normalize_rate``
    (ADR-035 tax_rate = "CODE-like exact-on-normalized"). The scorer's CODE
    normalizer only NFC-strips and cannot numerically canonicalize, so rates
    get their own ``RATE`` field_type with this numeric normalizer on both
    sides (GT + predicted produce byte-identical canonical strings → exact
    match works).

    Accepts:
      - ``"19"`` / ``"19.0"`` / ``"19.00"`` / ``"19,00"`` → ``"19"``
      - ``"19%"`` / ``"19 %"`` / ``"19.0 %"`` → ``"19"``
      - ``"7.5"`` / ``"7,5"`` / ``"7,50 %"`` → ``"7.5"``
      - ``"0"`` / ``"0.00"`` (zero-rated / reverse-charge) → ``"0"``

    Canonical form: ``format(Decimal(...).normalize(), "f")`` — strips trailing
    zeros and any exponent (``19.00`` → ``"19"``, ``7.50`` → ``"7.5"``), no
    thousands separators, ``.`` as the decimal point. Matches
    ``_normalize_rate`` byte-for-byte (locked by a cross-check test).

    Returns:
        Canonical rate string, or ``None`` if the input doesn't parse.
    """
    if not raw:
        return None
    s = raw.strip()
    # Strip a trailing percent sign + surrounding whitespace.
    s = s.replace("%", "").strip()
    if not s:
        return None
    # Locale decimal handling (same rule as money): comma-as-decimal → German.
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")
    if last_comma > last_dot:
        s = s.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return format(d.normalize(), "f")


# EN16931 VAT category codes (UNTDID 5305 subset; BT-118/BT-151). The GT side
# stores these letters verbatim from `ram:CategoryCode`; a VLM reads the page,
# which prints the GERMAN WORD ("Umsatzsteuer"), never the code, so a faithful
# predicted-side normalizer must recover the code from the model's rendering.
_EN16931_VAT_CATEGORY_CODES: frozenset[str] = frozenset(
    {"S", "Z", "E", "AE", "K", "G", "O", "L", "M", "B"}
)

# Parenthesized trailing code, e.g. "Umsatzsteuer (S)" → group 1 == "S".
_PAREN_VAT_CODE_RE = re.compile(r"\(\s*([A-Za-z]{1,2})\s*\)")

# German / English VAT-category phrasings → EN16931 code. Ordered SPECIFIC →
# GENERIC: the substring scan returns the first hit, so the narrow exemption /
# reverse-charge / intra-community phrases must precede the generic standard-rate
# words (a "Reverse Charge" line also contains "Umsatzsteuer"). A reduced rate
# (7 %, "ermäßigter Steuersatz") is still EN16931 category S.
_VAT_CATEGORY_SYNONYMS: tuple[tuple[str, str], ...] = (
    ("steuerschuldnerschaft des leistungsempfängers", "AE"),
    ("reverse charge", "AE"),
    ("innergemeinschaftliche lieferung", "K"),
    ("innergemeinschaftlich", "K"),
    ("intra-community", "K"),
    ("intra community", "K"),
    ("steuerbefreiung", "E"),
    ("steuerfrei", "E"),
    ("steuerbefreit", "E"),
    ("exempt", "E"),
    ("ausfuhrlieferung", "G"),
    ("ausfuhr", "G"),
    ("export", "G"),
    # NOTE: keys are matched against a `str.casefold()`ed haystack, which maps
    # ß → "ss"; this key is therefore written in the casefolded "ss" form so it
    # matches BOTH the "ermäßigter" (ß) and "ermässigter" (ss) spellings.
    ("ermässigter steuersatz", "S"),
    ("regelsteuersatz", "S"),
    ("umsatzsteuer", "S"),
    ("mehrwertsteuer", "S"),
    ("mwst", "S"),
    ("ust", "S"),
)


def _normalize_predicted_vat_category(raw: str) -> str | None:
    """Recover the EN16931 VAT-category code (BT-118) from a model's rendering.

    The GT is a controlled-vocabulary letter ("S", "AE", "K", …) that is never
    printed on the page. A VLM reads the German word and may emit any of:

      - the bare code already — ``"S"`` / ``"ae"`` → ``"S"`` / ``"AE"``
      - the word with the code in parens — ``"Umsatzsteuer (S)"`` → ``"S"``
      - the bare German/English word — ``"Umsatzsteuer"`` → ``"S"``,
        ``"innergemeinschaftliche Lieferung"`` → ``"K"``, ``"steuerfrei"`` → ``"E"``

    This canonicalizes representation only — it never changes correctness: a
    model that names the WRONG category in German still maps to the wrong code
    and scores FN. Unrecognized input is returned stripped (honest; FN if it
    doesn't match the GT code). ``None`` on empty input.
    """
    if not raw:
        return None
    s = unicodedata.normalize("NFC", raw.strip())
    if not s:
        return None
    # 1. Bare EN16931 code already.
    if s.upper() in _EN16931_VAT_CATEGORY_CODES:
        return s.upper()
    # 2. Parenthesized code the model supplied alongside the word.
    m = _PAREN_VAT_CODE_RE.search(s)
    if m and m.group(1).upper() in _EN16931_VAT_CATEGORY_CODES:
        return m.group(1).upper()
    # 3. German / English category phrase → code (specific-first scan).
    low = s.casefold()
    for phrase, code in _VAT_CATEGORY_SYNONYMS:
        if phrase in low:
            return code
    # 4. No mapping — return stripped (honest: FN unless it equals the GT code).
    return s


# Leading invoice-number LABEL the page prints next to the value ("Rechnung
# Nr. 471102", "Rechnungsnr.: 471102"). A REQUIRED separator after the label core
# ([.:#] and/or whitespace) is what makes this safe: a genuine identifier that
# merely starts with these letters ("NR-2024-001", "INV-001") has no such
# separator, so it is never eaten. Anchored at the start; stripped once.
_INVOICE_NUMBER_LABEL_RE = re.compile(
    r"^\s*"
    r"(?:invoice\s+|rechnungs?[-\s]*)?"  # optional qualifier word (Rechnung[s]/Invoice)
    r"(?:nr|no|nummer|number)"  # the number-label core
    r"(?:[.:#]+\s*|\s+)",  # REQUIRED separator run (guards against eating a real ID)
    re.IGNORECASE,
)


def _normalize_predicted_invoice_number(raw: str) -> str | None:
    """Strip a leading invoice-number LABEL the model echoed, then CODE-normalize.

    invoice_number (BT-1) is ``field_type="CODE"``; the GT is the bare identifier
    read from ``ram:ID`` (e.g. ``"471102"``). A VLM reading the page often
    transcribes the printed LABEL together with the value — ``"Nr. 471102"``,
    ``"Rechnung Nr. 471102"`` — so a literal-CODE comparison manufactures an FN
    over a label the model faithfully copied (the same as-printed-vs-as-stored
    class as ADR-046/048). Strip a leading number-label ONLY when a separator
    follows (so a genuine identifier like ``"NR-2024-001"`` is never eaten), then
    apply the standard predicted-CODE normalization.

    Representation-only: a model that reads the WRONG number still scores FN; a
    value with no label is unchanged. ``None`` on empty input. Falls back to the
    un-stripped string if stripping would empty it (raw was a bare label).
    """
    if not raw:
        return None
    s = unicodedata.normalize("NFC", raw.strip())
    if not s:
        return None
    stripped = _INVOICE_NUMBER_LABEL_RE.sub("", s, count=1).strip()
    candidate = stripped if stripped else s
    return _normalize_predicted_code(candidate, nfc=True)


def _normalize_predicted_optional_zero_money(raw: str) -> str | None:
    """Optional EN16931 totals (BT-107/108/113/114): a predicted 0 → absent.

    ADR-043 established that a structural ``0.00`` in these optional totals
    (allowance / charge / prepaid / rounding) is conventionally not rendered on
    the page, so the GT side treats it as ABSENT. This is the symmetric
    PREDICTED-side rule (ADR-051): a model that faithfully echoes the
    page's/structure's ``0.00`` must not be penalized as a spurious emission (FP)
    against that now-absent GT. A zero value → ``None`` (scored TN vs an absent
    GT); any genuine NON-zero value → normal money normalization, so a real
    prepaid/allowance is still scored against its GT (never masked). ``None`` on
    empty/unparseable input.
    """
    norm = _normalize_predicted_money(raw)
    if norm is None:
        return None
    try:
        if Decimal(norm) == 0:
            return None
    except InvalidOperation:
        return norm
    return norm


# A model often appends the line's GTIN/EAN to the seller article number with an
# explicit "(GTIN)" marker: "PFA5 4000001234578 (GTIN)" or, run-on,
# "KR3M4012345001235(GTIN)". The GT BT-155 is the bare seller article id
# ("PFA5" / "KR3M"). Strip the trailing GTIN ONLY when the explicit marker is
# present (so an article id that merely contains digits is never truncated) and
# only for an EAN-13 (the corpus standard) — matching exactly 13 digits avoids
# the boundary ambiguity when the article id itself ends in a digit
# ("TB100A4" + "4012345001235" → keep "TB100A4", not "TB100A").
_SELLER_ID_GTIN_RE = re.compile(
    r"[\s/]*\d{13}\s*\(\s*GTIN\s*\)\s*$",
    re.IGNORECASE,
)


def _normalize_predicted_seller_assigned_id(raw: str) -> str | None:
    """Strip a trailing GTIN/EAN the model appended to the seller article id.

    seller_assigned_id (BT-155) is ``field_type="CODE"``; the GT is the bare
    article number from ``ram:SellerAssignedID``. A VLM reading the page often
    concatenates the line's GTIN/EAN with an explicit "(GTIN)" marker
    (``"PFA5 4000001234578 (GTIN)"``), so a literal-CODE comparison manufactures
    an FN over a value the model read faithfully (the same as-printed-vs-as-stored
    class as ADR-048/050). Remove a trailing EAN-13 + "(GTIN)" marker, then apply
    the standard predicted-CODE normalization.

    Representation-only: a model that reads the WRONG article id still scores FN;
    an id with no GTIN marker is unchanged. ``None`` on empty input. Falls back to
    the un-stripped string if stripping would empty it.
    """
    if not raw:
        return None
    s = unicodedata.normalize("NFC", raw.strip())
    if not s:
        return None
    stripped = _SELLER_ID_GTIN_RE.sub("", s).strip()
    candidate = stripped if stripped else s
    return _normalize_predicted_code(candidate, nfc=True)
