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
