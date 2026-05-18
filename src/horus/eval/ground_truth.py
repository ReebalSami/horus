"""HORUS ground-truth XML parser — CII → 16-field English-keyed dict (ADR-012).

Parses a UN/CEFACT Cross Industry Invoice (CII) XML byte string and returns a
canonical `GroundTruth` dataclass whose `header` field maps 16 English-keyed
EN16931 business terms to `GroundTruthField` records carrying raw + normalized
value + provenance (xpath, presence flag, BT code).

The parser is route-invariant: feeding it the same CII XML extracted via
factur-x, MinerU's `pdfextractxml`, the Mustang Project CLI, or read directly
from a FeRD `.cii.xml` sidecar produces identical `GroundTruth` instances
(post-C14N2 canonicalization, the byte-level diff is line-ending cosmetic per
ADR-010 §"Empirical evidence"; this module operates on parsed lxml trees so
the cosmetic diff doesn't propagate).

Public surface (re-exported by `horus.eval`):
  - `CII_NAMESPACES`   — XPath namespace resolution table (single source of truth)
  - `FieldSpec`        — frozen dataclass; one row in the `FIELDS` catalog
  - `FIELDS`           — `dict[english_key, FieldSpec]` of 16 in-scope BT terms
  - `GroundTruthField` — frozen dataclass; one extracted record (raw + normalized
                         + provenance + presence)
  - `GroundTruth`      — frozen dataclass; top-level container with `header` dict
                         (future amendments may add `line_items` as an additional
                         optional field; see ADR-012 §"What this ADR does NOT decide")
  - `parse_cii_xml`    — entry point: `bytes` → `GroundTruth`

Tristate value semantics (load-bearing for PR(b)'s scorer):
  - field absent → `is_present=False`, `raw_value=None`, `normalized_value=None`
  - present, empty text → `is_present=True`, `raw_value=""`, `normalized_value=""`
  - present, content → `is_present=True`, `raw_value=<as XML>`,
    `normalized_value=<canonical>`
  - present, normalizer rejects → `is_present=True`, `raw_value=<as XML>`,
    `normalized_value=None` (corpus anomaly path; WARNING logged)

Refs: ADR-012 (this), ADR-010 (XML extraction substrate), ADR-009 Amendment 1
(XML-grounded F1 ground truth), issue #13 (pilot #13 parent), arXiv 2510.15727
§3.4 (DocILE-aligned field-vs-line-item separation).
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

from lxml import etree

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. CII namespace map — single source of truth for XPath namespace resolution
# ---------------------------------------------------------------------------

CII_NAMESPACES: Final[dict[str, str]] = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
    "xs": "http://www.w3.org/2001/XMLSchema",
}


# ---------------------------------------------------------------------------
# 2. Normalizer functions — pure, deterministic, no I/O
# ---------------------------------------------------------------------------
#
# Each FieldSpec in `FIELDS` binds one of these to its `normalize` attribute.
# Adding a new field is a 1-line FIELDS entry — no edit to a central if/else
# cascade keyed by field name. Open/closed at the registry boundary.
#
# Contract for every normalizer:
#   - Input is the raw text content of the matched XML element (stripped of
#     XML markup but otherwise as-in-source).
#   - Output is the canonical form for that field type (PR(b)'s exact-match
#     comparator runs against the normalized value).
#   - May raise `ValueError` on inputs that don't conform to the expected
#     shape; the parser catches + downgrades to `normalized_value=None` and
#     logs a WARNING (corpus anomaly path).


def _normalize_string(raw: str) -> str:
    """Strip outer whitespace + apply Unicode NFC. Preserve internal whitespace.

    German names with combining diacritics ("München" as `M\u00fc` vs `M\u0075\u0308`)
    become byte-equal post-NFC. Internal whitespace (e.g., "Lieferant GmbH") is
    preserved verbatim. Empty/whitespace-only input collapses to "".
    """
    return unicodedata.normalize("NFC", raw.strip())


def _normalize_date(raw: str) -> str:
    """Parse a UN/CEFACT CII date string and return ISO 8601 (`YYYY-MM-DD`).

    Reads the first 8 characters as `CCYYMMDD` (format code "102" per
    UN/EDIFACT 2379). Permissive on suffix: format codes "203" (`CCYYMMDDHHMM`)
    and "204" (`CCYYMMDDHHMMSS`) collapse to the date prefix — the time
    component is irrelevant for header dates per EN16931 semantics.

    Raises `ValueError` on inputs shorter than 8 characters or with non-digit
    `CCYYMMDD` prefix.
    """
    s = raw.strip()
    if len(s) < 8:
        raise ValueError(f"Date string too short for CCYYMMDD: {raw!r}")
    yyyy, mm, dd = s[:4], s[4:6], s[6:8]
    if not (yyyy.isdigit() and mm.isdigit() and dd.isdigit()):
        raise ValueError(f"Date prefix is not 8 digits: {raw!r}")
    return f"{yyyy}-{mm}-{dd}"


def _normalize_money(raw: str) -> str:
    """Parse a CII money string and return a canonical 2-decimal string.

    Quantizes to exactly 2 decimal places using `Decimal.quantize` with the
    default `ROUND_HALF_EVEN` (banker's rounding — matches IEEE 754 default).
    Sign preserved (negative amounts are valid per EN16931, e.g., the
    `EN16931_Einfach_negativePaymentDue` fixture).

    The currency code lives in a separate field (BT-5 `invoice_currency_code`)
    so this normalizer outputs the amount as a bare decimal string with no
    currency symbol or suffix.

    Raises `ValueError` on inputs that don't parse as `Decimal`.
    """
    s = raw.strip()
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Money string is not parseable as Decimal: {raw!r}") from exc
    return str(d.quantize(Decimal("0.01")))


def _passthrough(raw: str) -> str:
    """Pass-through normalizer for already-canonical short codes.

    Strips outer whitespace only; preserves case + internal structure. Used
    for ISO 4217 currency codes (BT-5) and similar code-list values that are
    canonical-as-shipped in valid CII XML.
    """
    return raw.strip()


# ---------------------------------------------------------------------------
# 3. FieldSpec — static catalog row per EN16931 business term
# ---------------------------------------------------------------------------


FieldType = Literal["STRING", "MONEY", "DATE", "CODE"]
r"""Discriminator for the per-field-type comparator dispatch in PR(b)'s scorer.

Additive ADR-012 amendment per ADR-013 — every `FieldSpec` row in `FIELDS`
must tag its `field_type` explicitly (no default; forces conscious choice).
The scorer (`src/horus/eval/scorer.py`) dispatches comparison strategy on
this discriminator:

  - ``STRING`` → ANLS\* with literature-default threshold 0.5 (Biten+ ICCV'19,
    Peer+ 2024 arXiv 2402.03848) — tolerates OCR character errors on names.
  - ``MONEY``  → exact match on canonical 2-decimal Decimal string
    (post-`_normalize_predicted_money`); strict per Vorsteuerabzug.
  - ``DATE``   → exact match on ISO 8601 (post-`_normalize_predicted_date`);
    accepts German `DD.MM.YYYY` + month-name + ISO + US-slash on the pred side.
  - ``CODE``   → exact match on whitespace-stripped NFC; invoice numbers,
    VAT IDs, GLN, currency codes — typos invalidate the legal record so no
    OCR tolerance is granted.
"""


@dataclass(frozen=True)
class FieldSpec:
    """Static metadata for one EN16931 business term in scope for pilot #13.

    One row in the `FIELDS` registry per field. Carries everything needed to
    extract + normalize one BT value from a CII XML; per-invoice extracted
    data lives in `GroundTruthField`.

    Attributes:
        english_key: HORUS-canonical English snake_case name (e.g., "invoice_number").
            Used as the dict key in `FIELDS` and in `GroundTruth.header`.
        bt_code: EN16931 business-term code (e.g., "BT-1"). Standards anchor;
            preserved on every `GroundTruthField` record so the EN16931 standard
            mapping is never lost.
        german_label: German rendering of the field name (e.g., "Rechnungsnummer").
            Lives here (one row per field) so per-invoice records stay lean — NOT
            duplicated 26×16 times on every extracted record. Also re-used by
            PR(b)'s Layer 2 adapter as the search anchor when extracting the
            predicted value from raw VLM text.
        xpath: lxml XPath expression returning element node(s). Resolved against
            `CII_NAMESPACES`. Convention: ends at the leaf element, NOT at
            `/text()` — the parser reads `.text` from the element so it can
            distinguish absent (XPath returns []) from present-but-empty
            (XPath returns element with `.text is None`).
        normalize: pure callable applied to the raw element text. Must accept
            an empty string (and short-circuit to ""); may raise `ValueError`
            on malformed input (parser catches + downgrades).
        field_type: comparator-dispatch discriminator for PR(b)'s scorer
            (ADR-013). One of ``STRING`` / ``MONEY`` / ``DATE`` / ``CODE``.
            Has no default — every `FieldSpec` row must tag its dispatch
            choice explicitly. Open/closed at the registry boundary (mirrors
            the `normalize` design): adding a new field is a 1-line FIELDS
            entry, no edit to the scorer's dispatch cascade.
    """

    english_key: str
    bt_code: str
    german_label: str
    xpath: str
    normalize: Callable[[str], str]
    field_type: FieldType


# ---------------------------------------------------------------------------
# 4. FIELDS registry — 16 EN16931 business terms in scope for pilot #13
# ---------------------------------------------------------------------------
#
# Scope rationale (locked by Socratic walk in plan file
# `~/.windsurf/plans/horus-issue-13-pra-cii-parser-c482cf.md`):
#
#   - 11 EN16931-mandatory header + totals fields
#   - 3 VAT-compliance fields (seller VAT ID, seller Steuernummer, buyer VAT ID)
#   - 2 ADR-009-continuity fields (seller GLN BT-29, delivery date BT-72)
#
# Line items (BG-25), per-VAT-rate breakdown (BG-23), address fields, and
# charge/allowance/prepaid totals are out of scope — see ADR-012 §"What this
# ADR does NOT decide" for the deferral rationale + forward-compat clause.

# Container-path prefixes (DRY across XPaths)
_HEADER_AGREEMENT = (
    "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement"
)
_HEADER_DELIVERY = (
    "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeDelivery"
)
_HEADER_SETTLEMENT = (
    "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement"
)
_SETTLEMENT_TOTALS = f"{_HEADER_SETTLEMENT}/ram:SpecifiedTradeSettlementHeaderMonetarySummation"


FIELDS: Final[dict[str, FieldSpec]] = {
    # 1. Invoice number (BT-1) — exactly 1 per invoice (EN16931-mandatory).
    "invoice_number": FieldSpec(
        english_key="invoice_number",
        bt_code="BT-1",
        german_label="Rechnungsnummer",
        xpath="/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:ID",
        normalize=_normalize_string,
        field_type="CODE",
    ),
    # 2. Issue date (BT-2) — exactly 1 per invoice (EN16931-mandatory).
    # Raw text is `CCYYMMDD` (UN/CEFACT format code "102"); normalized to ISO.
    "issue_date": FieldSpec(
        english_key="issue_date",
        bt_code="BT-2",
        german_label="Rechnungsdatum",
        xpath=(
            "/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString"
        ),
        normalize=_normalize_date,
        field_type="DATE",
    ),
    # 3. Invoice currency code (BT-5) — exactly 1 per invoice (EN16931-mandatory).
    # ISO 4217 3-letter code; passthrough normalizer.
    "invoice_currency_code": FieldSpec(
        english_key="invoice_currency_code",
        bt_code="BT-5",
        german_label="Währung",
        xpath=f"{_HEADER_SETTLEMENT}/ram:InvoiceCurrencyCode",
        normalize=_passthrough,
        field_type="CODE",
    ),
    # 4. Delivery date (BT-72) — 0..1 per invoice (mandatory iff differs from
    # issue date in some profiles; ZUGFeRD often populates it equal to issue
    # date for compliance robustness). Same shape as BT-2.
    "delivery_date": FieldSpec(
        english_key="delivery_date",
        bt_code="BT-72",
        german_label="Liefer-/Leistungsdatum",
        xpath=(
            f"{_HEADER_DELIVERY}/ram:ActualDeliverySupplyChainEvent"
            "/ram:OccurrenceDateTime/udt:DateTimeString"
        ),
        normalize=_normalize_date,
        field_type="DATE",
    ),
    # 5. Seller name (BT-27) — exactly 1 per invoice (EN16931-mandatory).
    "seller_name": FieldSpec(
        english_key="seller_name",
        bt_code="BT-27",
        german_label="Verkäufer",
        xpath=f"{_HEADER_AGREEMENT}/ram:SellerTradeParty/ram:Name",
        normalize=_normalize_string,
        field_type="STRING",
    ),
    # 6. Seller VAT identifier (BT-31), scheme VA. 0..1 in EN16931, near-always
    # present on German B2B invoices. The schemeID predicate filters to exactly
    # this Tax-Registration row (other rows may carry Steuernummer with FC).
    "seller_vat_id": FieldSpec(
        english_key="seller_vat_id",
        bt_code="BT-31",
        german_label="USt-IdNr. (Verkäufer)",
        xpath=(
            f"{_HEADER_AGREEMENT}/ram:SellerTradeParty"
            "/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']"
        ),
        normalize=_normalize_string,
        field_type="CODE",
    ),
    # 7. Seller Steuernummer (BT-32), scheme FC. German-specific; not in
    # EN16931-mandatory core but common on German invoices alongside VAT ID.
    "seller_tax_id": FieldSpec(
        english_key="seller_tax_id",
        bt_code="BT-32",
        german_label="Steuernummer",
        xpath=(
            f"{_HEADER_AGREEMENT}/ram:SellerTradeParty"
            "/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='FC']"
        ),
        normalize=_normalize_string,
        field_type="CODE",
    ),
    # 8. Seller GLN (BT-29), scheme 0088 (GS1 Global Location Number). 0..1;
    # in ADR-009 evidence base. Tracked for continuity with the cohort smoke.
    "seller_gln": FieldSpec(
        english_key="seller_gln",
        bt_code="BT-29 (scheme 0088)",
        german_label="GLN (Verkäufer)",
        xpath=(f"{_HEADER_AGREEMENT}/ram:SellerTradeParty/ram:GlobalID[@schemeID='0088']"),
        normalize=_normalize_string,
        field_type="CODE",
    ),
    # 9. Buyer name (BT-44) — exactly 1 per invoice (EN16931-mandatory).
    "buyer_name": FieldSpec(
        english_key="buyer_name",
        bt_code="BT-44",
        german_label="Käufer",
        xpath=f"{_HEADER_AGREEMENT}/ram:BuyerTradeParty/ram:Name",
        normalize=_normalize_string,
        field_type="STRING",
    ),
    # 10. Buyer identifier (BT-46) — 0..1; buyer's internal customer number.
    # Matched plain (no schemeID predicate) — some corpus invoices use a
    # schemeID, others don't; the EN16931 binding allows both.
    "buyer_reference": FieldSpec(
        english_key="buyer_reference",
        bt_code="BT-46",
        german_label="Kundennummer",
        xpath=f"{_HEADER_AGREEMENT}/ram:BuyerTradeParty/ram:ID",
        normalize=_normalize_string,
        field_type="CODE",
    ),
    # 11. Buyer VAT identifier (BT-48), scheme VA. 0..1; conditionally
    # mandatory in EN16931 (B2B cross-border EU). Deliberately included to
    # exercise the `is_present=False` path on `EN16931_Einfach.pdf` which
    # lacks this field.
    "buyer_vat_id": FieldSpec(
        english_key="buyer_vat_id",
        bt_code="BT-48",
        german_label="USt-IdNr. (Käufer)",
        xpath=(
            f"{_HEADER_AGREEMENT}/ram:BuyerTradeParty"
            "/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']"
        ),
        normalize=_normalize_string,
        field_type="CODE",
    ),
    # 12. Sum of line net amounts (BT-106) — EN16931-mandatory.
    "line_total_amount": FieldSpec(
        english_key="line_total_amount",
        bt_code="BT-106",
        german_label="Summe Nettobeträge",
        xpath=f"{_SETTLEMENT_TOTALS}/ram:LineTotalAmount",
        normalize=_normalize_money,
        field_type="MONEY",
    ),
    # 13. Invoice total without VAT / tax basis (BT-109) — EN16931-mandatory.
    "tax_basis_total_amount": FieldSpec(
        english_key="tax_basis_total_amount",
        bt_code="BT-109",
        german_label="Steuerlicher Bemessungsbetrag",
        xpath=f"{_SETTLEMENT_TOTALS}/ram:TaxBasisTotalAmount",
        normalize=_normalize_money,
        field_type="MONEY",
    ),
    # 14. Invoice total VAT amount (BT-110) — EN16931-mandatory.
    "tax_total_amount": FieldSpec(
        english_key="tax_total_amount",
        bt_code="BT-110",
        german_label="Umsatzsteuer gesamt",
        xpath=f"{_SETTLEMENT_TOTALS}/ram:TaxTotalAmount",
        normalize=_normalize_money,
        field_type="MONEY",
    ),
    # 15. Invoice total amount with VAT / grand total (BT-112) — EN16931-mandatory.
    "grand_total_amount": FieldSpec(
        english_key="grand_total_amount",
        bt_code="BT-112",
        german_label="Bruttobetrag",
        xpath=f"{_SETTLEMENT_TOTALS}/ram:GrandTotalAmount",
        normalize=_normalize_money,
        field_type="MONEY",
    ),
    # 16. Amount due for payment (BT-115) — EN16931-mandatory.
    "due_payable_amount": FieldSpec(
        english_key="due_payable_amount",
        bt_code="BT-115",
        german_label="Zahlbetrag",
        xpath=f"{_SETTLEMENT_TOTALS}/ram:DuePayableAmount",
        normalize=_normalize_money,
        field_type="MONEY",
    ),
}


# ---------------------------------------------------------------------------
# 5. GroundTruthField — one extracted-and-normalized field record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroundTruthField:
    """One extracted field value with provenance + presence flag.

    Frozen for hashable-free equality semantics (auto-generated `__eq__`
    compares all five attributes); used by the three-route equivalence tests
    to assert `parse(facturx_route) == parse(ferd_route) == parse(mustang_route)`.

    See module docstring for the full tristate value-semantics contract.

    Attributes:
        bt_code: the EN16931 business-term code (e.g., "BT-1"); copied from
            the `FieldSpec` that produced this record. Lets PR(b)'s scorer
            answer "which EN16931 field is this?" without a `FIELDS` lookup.
        raw_value: the as-in-XML text content. `None` if the field was absent;
            `""` if the element was present but had no text content.
        normalized_value: the canonical form per the `FieldSpec.normalize`
            callable. `None` if absent OR if the normalizer rejected the
            raw value (corpus anomaly path; WARNING logged). `""` if
            present-but-empty (normalizer is short-circuited).
        xpath: the XPath that produced this record (copied from `FieldSpec`).
            Provenance trace for debugging + thesis writeup tables.
        is_present: `True` iff the XPath matched at least one element. The
            normalized value may still be `None` (normalizer rejection); the
            raw value may still be `""` (present-but-empty element).
    """

    bt_code: str
    raw_value: str | None
    normalized_value: str | None
    xpath: str
    is_present: bool


# ---------------------------------------------------------------------------
# 6. GroundTruth — top-level container; forward-compat for line items
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroundTruth:
    """Top-level container for one invoice's parsed CII ground truth.

    Forward-compatibility design: future amendments may add optional fields
    (most notably `line_items: list[LineItemGT] | None = None` for BG-25)
    without breaking call sites that only access `.header`. The wrapper
    dataclass shape is deliberate per ADR-012 §"What this ADR does NOT
    decide".

    Equality semantics: two `GroundTruth` instances compare equal iff their
    `header` dicts compare equal, which compares the 16 `GroundTruthField`
    records field-by-field. Used by `test_three_route_dict_equivalence_einfach`
    and the corpus-wide parametrized equivalence test.

    Attributes:
        header: `dict[str, GroundTruthField]` keyed by `FIELDS` english_keys.
            The result always has all 16 keys present; absence of the field
            in the XML is signaled by `is_present=False` on the record, NOT
            by missing dict entries.
    """

    header: dict[str, GroundTruthField]


# ---------------------------------------------------------------------------
# 7. parse_cii_xml — main entry point
# ---------------------------------------------------------------------------


def parse_cii_xml(xml_bytes: bytes) -> GroundTruth:
    """Parse one CII XML byte string into a `GroundTruth` dict of 16 header fields.

    Iterates the `FIELDS` registry, executes each `FieldSpec.xpath` against
    the parsed XML tree, applies `FieldSpec.normalize` to the raw element
    text if present, and assembles one `GroundTruthField` record per entry.
    The output `GroundTruth.header` always has all 16 keys; presence of the
    field in the source XML is signaled by `is_present` on each record.

    Multi-match behavior: an XPath that matches more than one element
    (corpus anomaly — none of the 16 in-scope fields should multi-match
    in valid EN16931 CII XML) triggers a `WARNING` log entry and takes the
    first match in document order. Multi-valued semantics are deferred to
    future BG-25 (line items) work per ADR-012 §"What this ADR does NOT decide".

    Normalizer failure: if a `FieldSpec.normalize` callable raises `ValueError`
    on a non-empty raw value, the parser catches the exception, logs a
    `WARNING`, and sets `normalized_value=None` while preserving
    `raw_value=<as-in-XML>` and `is_present=True`. The raw value remains
    available for audit.

    Args:
        xml_bytes: a UN/CEFACT CII XML byte string (the embedded factur-x.xml
            attachment of a ZUGFeRD PDF, or a standalone `.cii.xml` sidecar).
            Must be non-None — see ADR-010 for the `extract_via_facturx`
            wrapper that handles the no-attachment case.

    Returns:
        `GroundTruth(header={english_key: GroundTruthField, ...})` with one
        entry per `FIELDS` row.

    Raises:
        `lxml.etree.XMLSyntaxError`: if `xml_bytes` is malformed XML.
    """
    tree = etree.fromstring(xml_bytes)
    header: dict[str, GroundTruthField] = {}

    for english_key, spec in FIELDS.items():
        elements = tree.xpath(spec.xpath, namespaces=CII_NAMESPACES)

        if not elements:
            # XPath matched 0 elements — field absent from this XML.
            header[english_key] = GroundTruthField(
                bt_code=spec.bt_code,
                raw_value=None,
                normalized_value=None,
                xpath=spec.xpath,
                is_present=False,
            )
            continue

        if len(elements) > 1:
            # Multi-match — corpus anomaly path. Log + take first.
            logger.warning(
                "Field %s (%s) matched %d elements; taking first in document order. XPath: %s",
                english_key,
                spec.bt_code,
                len(elements),
                spec.xpath,
            )

        # `tree.xpath` returns lxml `_Element` instances (not text nodes) when
        # the XPath does not end in `/text()`. Read `.text` for the element's
        # direct text content; `None` means no text (e.g., self-closing `<X/>`
        # or empty element `<X></X>`); we collapse that to `""` so the
        # tristate contract distinguishes "absent" (raw_value=None) from
        # "present-but-empty" (raw_value="").
        el = elements[0]
        raw_str = el.text if el.text is not None else ""

        # Apply normalizer ONLY when there's content to normalize; empty
        # raw_str short-circuits to empty normalized_str (avoids `ValueError`
        # from `_normalize_date` etc. on legitimately-empty elements).
        normalized: str | None
        if raw_str:
            try:
                normalized = spec.normalize(raw_str)
            except ValueError as exc:
                logger.warning(
                    "Field %s (%s) normalizer rejected raw value %r: %s. "
                    "Setting normalized_value=None; raw_value preserved.",
                    english_key,
                    spec.bt_code,
                    raw_str,
                    exc,
                )
                normalized = None
        else:
            normalized = ""

        header[english_key] = GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=raw_str,
            normalized_value=normalized,
            xpath=spec.xpath,
            is_present=True,
        )

    return GroundTruth(header=header)
