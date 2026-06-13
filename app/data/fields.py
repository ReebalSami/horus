"""Display metadata for the 19 scored invoice fields.

Human-readable English labels + a stable group ordering for the per-field table.
The grouping (seller / buyer / totals / document) and the German labels are read
from the project's own registries (`scorer.FIELD_GROUPS` / `scorer.DOCUMENT_FIELDS`
and `ground_truth.FIELDS`) so this module never drifts from the scored schema — it
only adds presentation (English labels + within-group order) on top.
"""

from __future__ import annotations

from horus.eval.ground_truth import FIELDS
from horus.eval.scorer import DOCUMENT_FIELDS, FIELD_GROUPS

# English display labels for the 19 canonical keys. German labels come from
# FIELDS[key].german_label (the audience is German tax professionals, so both
# are surfaced in the per-field table).
LABELS: dict[str, str] = {
    "invoice_number": "Invoice number",
    "issue_date": "Issue date",
    "delivery_date": "Delivery date",
    "invoice_currency_code": "Currency",
    "tax_rate": "VAT rate",
    "seller_name": "Seller name",
    "seller_address": "Seller address",
    "seller_vat_id": "Seller VAT ID",
    "seller_tax_id": "Seller tax number",
    "seller_gln": "Seller GLN",
    "buyer_name": "Buyer name",
    "buyer_address": "Buyer address",
    "buyer_vat_id": "Buyer VAT ID",
    "buyer_reference": "Buyer reference",
    "line_total_amount": "Line total (net)",
    "tax_basis_total_amount": "Tax basis total",
    "tax_total_amount": "Tax total (VAT)",
    "grand_total_amount": "Grand total (gross)",
    "due_payable_amount": "Amount due",
    # --- ADR-041 Step 1a additions ---
    "document_type": "Document type",
    "buyer_order_reference": "Order reference",
    "billing_period_start": "Billing period start",
    "billing_period_end": "Billing period end",
    "payment_due_date": "Payment due date",
    "payment_means_code": "Payment means (code)",
    "payment_means_text": "Payment means",
    "seller_iban": "IBAN",
    "seller_bic": "BIC",
    "seller_account_name": "Account holder",
    "payment_reference": "Payment reference",
    "prepaid_amount": "Prepaid amount",
    "allowance_total_amount": "Allowances total",
    "charge_total_amount": "Charges total",
    "rounding_amount": "Rounding",
}

# Stable display order: document identity first, then the parties, then the money.
FIELD_ORDER: tuple[str, ...] = (
    "invoice_number",
    "issue_date",
    "delivery_date",
    "invoice_currency_code",
    "tax_rate",
    "seller_name",
    "seller_address",
    "seller_vat_id",
    "seller_tax_id",
    "seller_gln",
    "buyer_name",
    "buyer_address",
    "buyer_vat_id",
    "buyer_reference",
    "line_total_amount",
    "tax_basis_total_amount",
    "tax_total_amount",
    "grand_total_amount",
    "due_payable_amount",
    # --- ADR-041 Step 1a additions ---
    "document_type",
    "buyer_order_reference",
    "billing_period_start",
    "billing_period_end",
    "payment_due_date",
    "payment_means_code",
    "payment_means_text",
    "seller_iban",
    "seller_bic",
    "seller_account_name",
    "payment_reference",
    "prepaid_amount",
    "allowance_total_amount",
    "charge_total_amount",
    "rounding_amount",
)

GROUP_DISPLAY: dict[str, str] = {
    "document": "Document",
    "seller": "Seller",
    "buyer": "Buyer",
    "payment": "Payment",
    "totals": "Totals",
}

# Integrity guard: the display order must cover exactly the scored field set
# (the scorer asserts FIELD_GROUPS ∪ DOCUMENT_FIELDS == FIELDS). Fail fast at
# import if the registry grows and this presentation layer drifts from it.
_PARTITION: frozenset[str] = frozenset().union(*FIELD_GROUPS.values()) | DOCUMENT_FIELDS
assert set(FIELD_ORDER) == _PARTITION, (
    "app.data.fields.FIELD_ORDER drifted from the scorer's field partition; "
    "update LABELS + FIELD_ORDER to match the current FIELDS registry"
)


def group_key(english_key: str) -> str:
    """Return the group a field belongs to (`document` / `seller` / `buyer` / `totals`).

    Falls back to `document` for any key outside the party/totals groups — matches
    the scorer partition where the document-level scalars are the non-group set.
    """
    for group, members in FIELD_GROUPS.items():
        if english_key in members:
            return group
    return "document"


def group_display(english_key: str) -> str:
    """Human-readable group name for a field."""
    return GROUP_DISPLAY.get(group_key(english_key), "Document")


def label(english_key: str) -> str:
    """Human-readable English label for a field key."""
    return LABELS.get(english_key, english_key.replace("_", " ").capitalize())


def german_label(english_key: str) -> str:
    """German label for a field key (from the canonical FIELDS registry)."""
    spec = FIELDS.get(english_key)
    return spec.german_label if spec is not None else ""
