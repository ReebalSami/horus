"""Azure `prebuilt-invoice` output → the HORUS field registry (ADR-061, channel 2).

Held-out Tier B is `0 / 338` cells proven by printed evidence — by definition, since those
documents carry no text layer at all. A second, *independent* reading is therefore the only
thing that can warrant a value there, and independence is the whole design constraint:
Azure's `prebuilt-invoice` is a specialist (dedicated OCR plus a field model trained on
invoices), so it fails differently from the generalist vision judge of ADR-060. Agreement
between two systems that fail the same way would be nearly worthless.

This module is the **pure** half of the channel: mapping and merging, no network, no SDK
objects. It consumes the plain JSON that `AnalyzeResult.as_dict()` emits — REST wire names,
verified empirically rather than assumed (`valueCurrency`/`currencyCode`/`boundingRegions`
→ `pageNumber`, all camelCase). Keeping the boundary at plain JSON is what lets every test
run against a recorded fixture with no credentials and no billable call.

Three decisions carry the weight.

**`content`, not `value_*`.** Azure returns both the literal page text (`content`) and its
own typed interpretation (`valueDate`, `valueCurrency`, …). Held-out GT stores values AS
PRINTED (ADR-058), so `content` is the reading and the typed value is at most a cross-check.
Taking `valueDate` would silently rewrite a printed `28.09.2022` into `2022-09-28` and
destroy the as-printed contract — the same class of one-sided normalization that once
inverted a correct answer in this codebase.

**Silence is three-valued, not two.** `prebuilt-invoice` has no notion of BT-46
`buyer_reference`, BT-81 `payment_means_code`, BT-118 category codes, IBAN/BIC, or GLN. If
"Azure said nothing" collapsed into "the field is absent", a Tier B null would gain a
confirmation it never earned — the exact way an answer key becomes confidently wrong. So a
field resolves to :class:`AzureCoverage` ``VALUE`` / ``NOT_PRESENT`` / ``NOT_COVERED``, and
only the first two are evidence about the page.

**The vocabulary is measured, not asserted.** Microsoft documents the authoritative field
list behind a link rather than inline, so hardcoding a table from memory would be an
unverified claim about data — precisely what ADR-058 was written to stop after 34 invented
`prompt_alias` entries scored 0/146. :data:`AZURE_FIELD_MAP` therefore holds *candidate*
keys, and :func:`unmapped_azure_fields` reports every key a real response contained that the
table does not consume. The runner prints that report, so the true vocabulary arrives as an
observation.

Confidence is carried, and is deliberately **not** a warrant: it orders a review list and
nothing more. A confidently-wrong OCR read is the failure this two-channel design exists to
catch.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS

__all__ = [
    "AZURE_ARRAY_FIELD_MAP",
    "AZURE_FIELD_MAP",
    "AZURE_VALUE_FILTERS",
    "AZURE_ITEM_CELL_MAP",
    "AZURE_MODEL_ID",
    "AZURE_TAX_DETAIL_CELL_MAP",
    "KNOWN_UNUSED_AZURE_FIELDS",
    "AzureCoverage",
    "AzureReading",
    "array_source_fields",
    "coverage_summary",
    "merge_page_groups",
    "merge_page_readings",
    "not_covered_fields",
    "read_analyzed_document",
    "read_groups",
    "unmapped_azure_fields",
]

#: The prebuilt model id. Not configurable: a *custom* model would have to be trained on
#: this corpus, which would make the channel a second measurement of our own data rather
#: than an independent reading.
AZURE_MODEL_ID: Final[str] = "prebuilt-invoice"


class AzureCoverage(Enum):
    """Why a HORUS field has (or lacks) an Azure reading.

    The distinction between the last two is the reason this enum exists instead of an
    ``str | None``: they look identical downstream and mean opposite things.
    """

    VALUE = "value"
    NOT_PRESENT = "not_present"
    NOT_COVERED = "not_covered"


@dataclass(frozen=True)
class AzureReading:
    """One channel-2 reading of one cell, with the provenance to defend it."""

    key: str
    value: str | None
    coverage: AzureCoverage
    confidence: float | None = None
    page: int | None = None
    azure_field: str | None = None

    @property
    def is_evidence(self) -> bool:
        """Whether this reading says anything about the page at all.

        ``NOT_COVERED`` says something about *Azure*, not about the document, so it is
        excluded — a field the model cannot express is not a channel agreeing that the
        value is absent.
        """
        return self.coverage is not AzureCoverage.NOT_COVERED


#: HORUS flat field → candidate Azure field names, in preference order.
#:
#: An empty tuple means `prebuilt-invoice` has no equivalent concept, which is recorded as
#: ``NOT_COVERED`` rather than silently reported as absent. Several entries are deliberately
#: *ambiguous* and share a source (`SubTotal` can plausibly answer either BT-106 or BT-109);
#: the ambiguity is preserved rather than resolved by guessing, because a wrong assignment
#: in an answer key is permanent. Both candidates read the same Azure field, both are
#: reported, and the adjudication step decides — which is what the escalation ranking is for.
#:
#: Names beyond the set confirmed in the retrieved docs are listed as *candidates*: if the
#: service does not return them they simply never match, and if it returns something absent
#: from this table :func:`unmapped_azure_fields` surfaces it. No entry here is load-bearing
#: on memory.
AZURE_FIELD_MAP: Final[dict[str, tuple[str, ...]]] = {
    # --- document identity -------------------------------------------------------------
    "invoice_number": ("InvoiceId",),
    "issue_date": ("InvoiceDate",),
    # Currency is not a standalone Azure field; it rides on the currency-typed totals and
    # is recovered by `_currency_code_from` rather than from `content`.
    "invoice_currency_code": ("InvoiceTotal", "AmountDue", "SubTotal"),
    # BT-3: `prebuilt-invoice` always reports docType "invoice" regardless of whether the
    # page says Rechnung, Gutschrift or Korrektur, so it cannot distinguish a credit note
    # and must not be allowed to vote on one.
    "document_type": (),
    # --- seller ------------------------------------------------------------------------
    # `VendorAddressRecipient` is the name line inside the vendor address block. Observed
    # empirically on a live response (2026-08-05) and kept as a FALLBACK only: when Azure
    # reports no `VendorName`, the address recipient is still a reading of the seller name.
    "seller_name": ("VendorName", "VendorAddressRecipient"),
    "seller_address": ("VendorAddress",),
    # Azure exposes ONE merged vendor tax id, but German invoices print USt-IdNr (BT-31)
    # and Steuernummer (BT-32) as different numbers. Feeding the same value into both slots
    # would guarantee one of them is wrong, so the value is routed by FORMAT instead:
    # a VAT id is a country prefix plus alphanumerics, a Steuernummer never starts with
    # letters. See `AZURE_VALUE_FILTERS` — deterministic, and it abstains when unsure rather
    # than asserting into both.
    "seller_vat_id": ("VendorTaxId",),
    "seller_tax_id": ("VendorTaxId",),
    "seller_gln": (),
    # --- buyer -------------------------------------------------------------------------
    "buyer_name": ("CustomerName", "CustomerAddressRecipient", "BillingAddressRecipient"),
    "buyer_address": ("CustomerAddress", "BillingAddress"),
    "buyer_vat_id": ("CustomerTaxId",),
    "buyer_reference": (),
    "buyer_order_reference": ("PurchaseOrder", "OrderNumber"),
    # --- dates -------------------------------------------------------------------------
    "delivery_date": ("ServiceStartDate",),
    "billing_period_start": ("ServiceStartDate",),
    "billing_period_end": ("ServiceEndDate",),
    "payment_due_date": ("DueDate",),
    # --- totals ------------------------------------------------------------------------
    "line_total_amount": ("SubTotal",),
    "tax_basis_total_amount": ("SubTotal",),
    "tax_total_amount": ("TotalTax",),
    "grand_total_amount": ("InvoiceTotal",),
    "due_payable_amount": ("AmountDue",),
    # BT-119 is a single flat rate. `TaxDetails[].Rate` already feeds `vat_breakdown`
    # per-rate, and collapsing several rates into one scalar would be a derivation rather
    # than a reading — ADR-045/052 exclude the flat scalar for multi-rate and single-zero-
    # rate invoices precisely because it is ill-posed there. A GT channel reads; it does
    # not infer.
    "tax_rate": (),
    # BT-113 is money already paid. Azure's `PreviousUnpaidBalance` is the opposite
    # (outstanding), so mapping them would invert the meaning of the cell.
    "prepaid_amount": (),
    "allowance_total_amount": ("TotalDiscount",),
    "charge_total_amount": (),
    "rounding_amount": (),
    # --- payment ---------------------------------------------------------------------
    # BT-81 is a UNTDID 4461 numeric code and BT-82 its printed wording; Azure's
    # `PaymentTerm` is payment *terms* prose ("30 days net"), a different business term.
    "payment_means_code": (),
    "payment_means_text": (),
    # BT-84 is a payment ACCOUNT IDENTIFIER, which EN16931 allows to be a domestic account
    # number rather than an IBAN — so `BankAccountNumber` is a legitimate fallback behind
    # the `PaymentDetails[].IBAN` read below. Observed once in the corpus. If it disagrees
    # with the judge the cell escalates, which is the safe direction to fail.
    "seller_iban": ("BankAccountNumber",),
    "seller_bic": (),
    # BT-85 is the ACCOUNT HOLDER's name. Azure has no such field — `BankAccountNumber` is
    # a number, not a name, so mapping it here would put the wrong kind of value in the cell.
    "seller_account_name": (),
    "payment_reference": (),
}

#: A VAT identifier: ISO 3166 alpha-2 country prefix followed by alphanumerics (DE123456789,
#: ATU12345678). A German Steuernummer (`12/345/67890`) never matches, which is exactly the
#: discrimination needed to route Azure's single `VendorTaxId` to the right EN16931 slot.
_VAT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2}[A-Z0-9]{6,14}$")


def _looks_like_vat_id(value: str) -> bool:
    compact = "".join(value.split()).replace("-", "").upper()
    return bool(_VAT_ID_PATTERN.match(compact))


#: Per-field acceptance test applied to a candidate Azure value.
#:
#: Returning False means "this value does not belong in this field", which is recorded as
#: NOT_PRESENT rather than forced into the cell. Introduced because mapping Azure's single
#: merged tax id into both BT-31 and BT-32 produced 29 escalations that were artefacts of the
#: mapping rather than genuine disagreement about the documents.
AZURE_VALUE_FILTERS: Final[dict[str, Callable[[str], bool]]] = {
    "seller_vat_id": _looks_like_vat_id,
    "seller_tax_id": lambda value: not _looks_like_vat_id(value),
    "buyer_vat_id": _looks_like_vat_id,
}

#: HORUS flat field → (Azure ARRAY field, row cell) for values Azure nests inside an array.
#:
#: Discovered by `scripts/audit_azure_vocabulary.py`, not by reading the quickstart: the
#: bank block arrives as `PaymentDetails[]` with `IBAN` (19 pages) and `SWIFT` (21 pages)
#: cells. Before the audit these two fields were wrongly declared structurally uncoverable,
#: which would have left every IBAN and BIC in the corpus resting on a single channel.
#:
#: Takes precedence over :data:`AZURE_FIELD_MAP` for the same key, since a dedicated payment
#: block is a stronger source than a loose top-level field.
AZURE_ARRAY_FIELD_MAP: Final[dict[str, tuple[str, str]]] = {
    "seller_iban": ("PaymentDetails", "IBAN"),
    "seller_bic": ("PaymentDetails", "SWIFT"),
}

#: `line_items` cell → Azure `Items[]` row cell.
AZURE_ITEM_CELL_MAP: Final[dict[str, tuple[str, ...]]] = {
    "line_id": (),  # Azure does not number rows; position is the only identity
    "name": ("Description",),
    "seller_assigned_id": ("ProductCode",),
    "net_price": ("UnitPrice",),
    "quantity": ("Quantity",),
    # `TaxRate` IS an Items cell (observed on 40 rows) — the audit corrected an earlier
    # assumption that only the per-line `Tax` amount was available.
    "vat_rate": ("TaxRate",),
    "line_amount": ("Amount",),
}

#: `vat_breakdown` cell → Azure `TaxDetails[]` row cell (candidates; see AZURE_FIELD_MAP).
AZURE_TAX_DETAIL_CELL_MAP: Final[dict[str, tuple[str, ...]]] = {
    "category_code": (),  # EN16931 category letter — no Azure equivalent
    "rate_percent": ("Rate",),
    "taxable_amount": ("NetAmount",),
    "tax_amount": ("Amount",),
}

#: Azure fields that exist and are deliberately NOT consumed, with the reason.
#:
#: Suppression only — this list keeps :func:`unmapped_azure_fields` reporting genuine
#: discoveries instead of drowning them in fields we already decided against. A wrong name
#: here is harmless (it simply never matches), which is why membership is allowed to rest on
#: the documented vocabulary; :data:`AZURE_FIELD_MAP` gets no such latitude, because a wrong
#: name there would silently drop a reading.
KNOWN_UNUSED_AZURE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        # EN16931 ship-to (BG-13) is not in the 34-field registry, so there is nothing to
        # map these onto. Not a gap — a scope boundary.
        "ShippingAddress",
        "ShippingAddressRecipient",
        # Seller-assigned customer number. BT-46 `buyer_reference` is the opposite direction
        # — a reference the BUYER asks to have printed (cost centre, Leitweg-ID) — so these
        # are different business terms and conflating them would corrupt the cell.
        "CustomerId",
        # Payment TERMS prose ("30 days net"). BT-82 `payment_means_text` is the payment
        # MEANS wording ("Überweisung", "SEPA-Lastschrift") — a different business term, and
        # a terms string in that cell would be a wrong answer, not a partial one.
        "PaymentTerm",
        # Where a service was rendered / where to remit. Neither is in the 34-field registry.
        "ServiceAddress",
        "ServiceAddressRecipient",
        "RemittanceAddress",
        "RemittanceAddressRecipient",
        # Contact details. EN16931 models these (BT-43, BT-58 …) but HORUS does not extract
        # them, so there is no cell to fill.
        "BillingEmail",
        "VendorEmail",
        "BillingPhoneNumber",
        "ShippingPhoneNumber",
    }
)

#: Azure array fields feeding HORUS repeating groups.
_GROUP_SOURCES: Final[dict[str, tuple[str, dict[str, tuple[str, ...]]]]] = {
    "line_items": ("Items", AZURE_ITEM_CELL_MAP),
    "vat_breakdown": ("TaxDetails", AZURE_TAX_DETAIL_CELL_MAP),
    # Skonto (early-payment discount tiers) has no `prebuilt-invoice` counterpart at all.
    "skonto": ("", {}),
}


def _content_of(field: Mapping[str, Any]) -> str | None:
    """The field's value AS PRINTED, or None when it carries no text.

    Falls back to `valueString` only when `content` is missing: a composite address field
    can report a structured value without a flat content span, and dropping it would lose a
    reading we have.
    """
    for candidate in (field.get("content"), field.get("valueString")):
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def _confidence_of(field: Mapping[str, Any]) -> float | None:
    raw = field.get("confidence")
    if raw is None:
        return None
    try:
        return float(raw)
    except TypeError, ValueError:
        return None


def _page_of(field: Mapping[str, Any]) -> int | None:
    """1-based page number of the field's first bounding region, when present.

    This is what lets an escalated Tier B cell point at the page it came from, so
    adjudication does not require hunting through a PDF.
    """
    regions = field.get("boundingRegions")
    if not isinstance(regions, Sequence) or isinstance(regions, str | bytes):
        return None
    for region in regions:
        if not isinstance(region, Mapping):
            continue
        number = region.get("pageNumber")
        if number is None:
            continue
        try:
            return int(number)
        except TypeError, ValueError:
            continue
    return None


def _currency_code_from(field: Mapping[str, Any]) -> str | None:
    """ISO 4217 code off a currency-typed field, or None.

    BT-5 is never its own field on an invoice — the currency is printed next to the amounts
    — so it is recovered from the typed currency value rather than from `content`. This is
    the one place a typed value beats `content`: `content` here is the amount text, not the
    currency.
    """
    value = field.get("valueCurrency")
    if not isinstance(value, Mapping):
        return None
    code = value.get("currencyCode")
    if code is None:
        return None
    text = str(code).strip().upper()
    return text or None


def _document_fields(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """The `fields` dict of an analyzed document, keyed by Azure field name."""
    raw = document.get("fields")
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, Mapping)}


def _read_from_array(
    azure_fields: Mapping[str, Mapping[str, Any]], key: str
) -> AzureReading | None:
    """Read a flat HORUS field out of a cell nested in an Azure array field.

    The bank block is the motivating case: `seller_iban` and `seller_bic` live in
    `PaymentDetails[].IBAN` / `.SWIFT`, not at the top level.

    Takes the FIRST row carrying the cell. An invoice normally prints one payment account;
    when it prints several, taking the first is a claim rather than a fact — but it is a
    claim the other channel can contradict, and a contradiction escalates to the author
    rather than silently entering the answer key.

    Returns None when the array, the rows, or the cell are absent, so the caller can fall
    back to the flat mapping.
    """
    source_name, cell_name = AZURE_ARRAY_FIELD_MAP[key]
    source = azure_fields.get(source_name)
    if not isinstance(source, Mapping):
        return None
    rows = source.get("valueArray")
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes):
        return None

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        cells = row.get("valueObject")
        if not isinstance(cells, Mapping):
            continue
        cell = cells.get(cell_name)
        if not isinstance(cell, Mapping):
            continue
        value = _content_of(cell)
        if value is None:
            continue
        return AzureReading(
            key=key,
            value=value,
            coverage=AzureCoverage.VALUE,
            confidence=_confidence_of(cell),
            page=_page_of(cell),
            azure_field=f"{source_name}[].{cell_name}",
        )
    return None


def read_analyzed_document(document: Mapping[str, Any]) -> dict[str, AzureReading]:
    """Map one analyzed document onto all 34 HORUS flat fields.

    Every registered field gets a reading, including the ones Azure cannot express — an
    omitted key would be indistinguishable from an absent value, which is the ambiguity
    this channel exists to remove.

    Args:
        document: one entry of `AnalyzeResult.as_dict()["documents"]`.

    Returns:
        `{horus_key: AzureReading}` over exactly `FIELDS`.
    """
    azure_fields = _document_fields(document)
    readings: dict[str, AzureReading] = {}

    for key in FIELDS:
        candidates = AZURE_FIELD_MAP.get(key, ())
        array_source = AZURE_ARRAY_FIELD_MAP.get(key)
        if not candidates and array_source is None:
            readings[key] = AzureReading(key, None, AzureCoverage.NOT_COVERED)
            continue

        # The nested payment block outranks a loose top-level field for the same key.
        reading: AzureReading | None = (
            _read_from_array(azure_fields, key) if array_source is not None else None
        )
        for azure_name in () if reading is not None else candidates:
            field = azure_fields.get(azure_name)
            if field is None:
                continue
            value = (
                _currency_code_from(field) if key == "invoice_currency_code" else _content_of(field)
            )
            if value is None:
                continue
            accepts = AZURE_VALUE_FILTERS.get(key)
            if accepts is not None and not accepts(value):
                continue
            reading = AzureReading(
                key=key,
                value=value,
                coverage=AzureCoverage.VALUE,
                confidence=_confidence_of(field),
                page=_page_of(field),
                azure_field=azure_name,
            )
            break
        if reading is None:
            fallback_name = (
                f"{array_source[0]}[].{array_source[1]}"
                if array_source is not None
                else candidates[0]
            )
            reading = AzureReading(key, None, AzureCoverage.NOT_PRESENT, azure_field=fallback_name)
        readings[key] = reading
    return readings


def read_groups(document: Mapping[str, Any]) -> dict[str, list[dict[str, str | None]]]:
    """Map one analyzed document's array fields onto the HORUS repeating groups.

    Rows keep Azure's document order. A cell the Azure row does not carry, or that has no
    mapping at all, becomes `None` — a group row is a shape claim about the page, and
    padding it with invented cells would score as phantom content forever.

    `skonto` always yields `[]`: `prebuilt-invoice` has no early-payment-discount concept,
    so this channel abstains rather than voting.
    """
    azure_fields = _document_fields(document)
    groups: dict[str, list[dict[str, str | None]]] = {}

    for group_name in REPEATING_GROUPS:
        source_name, cell_map = _GROUP_SOURCES.get(group_name, ("", {}))
        _row_xpath, registry_cells = REPEATING_GROUPS[group_name]
        rows: list[dict[str, str | None]] = []
        source = azure_fields.get(source_name) if source_name else None
        raw_rows = source.get("valueArray") if isinstance(source, Mapping) else None

        if isinstance(raw_rows, Sequence) and not isinstance(raw_rows, str | bytes):
            for raw_row in raw_rows:
                if not isinstance(raw_row, Mapping):
                    continue
                cells = raw_row.get("valueObject")
                if not isinstance(cells, Mapping):
                    continue
                row: dict[str, str | None] = {}
                for cell in registry_cells:
                    row[cell] = None
                    for azure_cell in cell_map.get(cell, ()):
                        field = cells.get(azure_cell)
                        if isinstance(field, Mapping):
                            value = _content_of(field)
                            if value is not None:
                                row[cell] = value
                                break
                if any(value is not None for value in row.values()):
                    rows.append(row)
        groups[group_name] = rows
    return groups


def merge_page_readings(
    per_page: Sequence[Mapping[str, AzureReading]],
) -> dict[str, AzureReading]:
    """Collapse per-page readings of one invoice into one document-level set.

    Requests are per rasterized page (which is what dissolves both F0 caps), so a field
    printed on page 2 is absent from page 1's response. Merging must therefore prefer an
    actual reading over silence, and among competing readings prefer the more confident
    one; a reading with no confidence at all loses to one that has any, since an unscored
    guess is the weaker claim.

    ``NOT_COVERED`` is sticky: no page can supply a field the model cannot express, so it
    can never be upgraded to ``NOT_PRESENT`` by accumulating pages that also said nothing.
    """
    merged: dict[str, AzureReading] = {}
    for key in FIELDS:
        best: AzureReading | None = None
        for page_readings in per_page:
            candidate = page_readings.get(key)
            if candidate is None:
                continue
            if candidate.coverage is AzureCoverage.NOT_COVERED:
                best = best or candidate
                continue
            if best is None or best.coverage is not AzureCoverage.VALUE:
                best = candidate
                continue
            if candidate.coverage is AzureCoverage.VALUE and _beats(candidate, best):
                best = candidate
        merged[key] = best or AzureReading(key, None, AzureCoverage.NOT_COVERED)
    return merged


def _beats(candidate: AzureReading, incumbent: AzureReading) -> bool:
    """Whether `candidate` is the better of two VALUE readings of the same field."""
    if candidate.confidence is None:
        return False
    if incumbent.confidence is None:
        return True
    return candidate.confidence > incumbent.confidence


def merge_page_groups(
    per_page: Sequence[Mapping[str, list[dict[str, str | None]]]],
) -> dict[str, list[dict[str, str | None]]]:
    """Concatenate per-page group rows in page order.

    Concatenation, not de-duplication: a genuine invoice can repeat a line across pages,
    and silently collapsing two identical rows would delete real content. Duplicate
    detection belongs to adjudication, where a human can see both.
    """
    merged: dict[str, list[dict[str, str | None]]] = {group: [] for group in REPEATING_GROUPS}
    for page_groups in per_page:
        for group, rows in page_groups.items():
            if group in merged:
                merged[group].extend(rows)
    return merged


def unmapped_azure_fields(document: Mapping[str, Any]) -> set[str]:
    """Azure field names present in a response that no mapping table consumes.

    The measurement that keeps :data:`AZURE_FIELD_MAP` honest. Microsoft documents the
    authoritative `prebuilt-invoice` vocabulary behind a link rather than inline, so the
    table is a hypothesis; this reports where the hypothesis is incomplete instead of
    letting a silently-ignored field look like an absent one.
    """
    mapped = {name for names in AZURE_FIELD_MAP.values() for name in names}
    mapped |= array_source_fields()
    mapped |= {source for source, _cell in AZURE_ARRAY_FIELD_MAP.values()}
    mapped |= KNOWN_UNUSED_AZURE_FIELDS
    return {name for name in _document_fields(document) if name not in mapped}


def array_source_fields() -> frozenset[str]:
    """Azure array field names that feed HORUS repeating groups.

    Exposed so the vocabulary audit can tell "consumed as a group source" apart from
    "unknown", which is the distinction that makes its report actionable.
    """
    return frozenset(source for source, _cells in _GROUP_SOURCES.values() if source)


def not_covered_fields() -> tuple[str, ...]:
    """HORUS fields `prebuilt-invoice` structurally cannot answer, in registry order.

    Stated as data so the datasheet and the review sheet can both say *why* a cell has
    only one channel, rather than leaving a reader to infer that Azure disagreed.
    """
    return tuple(
        key
        for key in FIELDS
        if not AZURE_FIELD_MAP.get(key, ()) and key not in AZURE_ARRAY_FIELD_MAP
    )


def coverage_summary(readings: Mapping[str, AzureReading]) -> dict[str, int]:
    """Count readings by coverage — safe to print (counts only, no values)."""
    counts = {coverage.value: 0 for coverage in AzureCoverage}
    for reading in readings.values():
        counts[reading.coverage.value] += 1
    return counts
