"""Ground Truth Review — verify the held-out Belege answer keys (ADR-040).

The annotation surface for the private held-out test set: pick an invoice, see its
page image beside the 19 fields pre-filled by the local/Cascade draft, correct any
value against the page, tick **Verified**, and **Save**. Saving writes the answer
key to `data/self-collected/gt/<id>.gt.json` (git-ignored) and marks it verified.

This is a WRITE page (like *Extract an Invoice*), the bounded exception to the
read-only research surfaces (ADR-036/039) — producing ground truth is inherently an
annotation task. It runs no models; the draft is read from disk. Nothing here ever
leaves the machine or enters git.
"""

from __future__ import annotations

import streamlit as st

from app.components import cards, theme
from app.data import fields as field_meta
from app.data import heldout as heldout_data
from horus.eval.heldout import HeldoutItem

_GROUPS: tuple[tuple[str, str], ...] = (
    ("document", "Document"),
    ("seller", "Seller"),
    ("buyer", "Buyer"),
    ("payment", "Payment"),
    ("totals", "Totals"),
)

# Repeating groups (ADR-041/042) — rendered as variable-length grids below the
# flat fields. One row per VAT rate / Skonto tier / line item.
_REPEATING: tuple[tuple[str, str], ...] = (
    ("vat_breakdown", "VAT breakdown — one row per rate"),
    ("skonto", "Skonto — one row per discount tier"),
    ("line_items", "Line items — one row per position"),
)

st.title("Ground Truth Review")
st.caption("Verify the held-out test-set answer keys, field by field, against each invoice.")

st.markdown(
    f"<div style='background:{theme.PANEL};border:1px solid {theme.HAIRLINE};"
    f"border-left:3px solid {theme.GOLD};border-radius:0.5rem;padding:0.6rem 0.9rem;"
    f"font-size:0.9rem;color:{theme.MUTED}'>"
    f"<b style='color:{theme.INK}'>Private + local.</b> These are your real invoices and "
    "their ground truth. Everything here is read from and written to the git-ignored "
    "<code>data/self-collected/</code> tree — nothing is uploaded or committed. Your saved, "
    "verified answer keys are the anchor the held-out evaluation grades against."
    "</div>",
    unsafe_allow_html=True,
)


def _flat_values(doc: dict[str, object]) -> dict[str, str]:
    """Flat field values as edit-ready strings (None → ""), in display order."""
    raw_fields = doc.get("fields", {})
    fields = raw_fields if isinstance(raw_fields, dict) else {}
    return {
        key: ("" if fields.get(key) is None else str(fields.get(key)))
        for key in field_meta.FIELD_ORDER
    }


def _repeating_seed(doc: dict[str, object], group_key: str) -> list[dict[str, str]]:
    """Edit-ready rows for one repeating group; one blank row if empty (so columns show)."""
    sub_keys = heldout_data.repeating_subkeys(group_key)
    raw_rows = doc.get(group_key) or []
    seed: list[dict[str, str]] = []
    if isinstance(raw_rows, list):
        for row in raw_rows:
            if isinstance(row, dict):
                seed.append({k: ("" if row.get(k) is None else str(row.get(k))) for k in sub_keys})
    return seed or [dict.fromkeys(sub_keys, "")]


def _render_pages(item: HeldoutItem) -> None:
    cards.section_heading("Invoice", "The source document — read the values off this")
    images = heldout_data.page_images(item)
    if not images:
        st.info("Page image unavailable (PDF missing or unreadable on this machine).")
        return
    if len(images) == 1:
        st.image(str(images[0]), use_container_width=True)
        return
    for index, tab in enumerate(st.tabs([f"Page {i + 1}" for i in range(len(images))])):
        with tab:
            st.image(str(images[index]), use_container_width=True)


def _render_form(item: HeldoutItem) -> None:
    doc = heldout_data.load_draft(item)
    values = _flat_values(doc)
    verified = bool(doc.get("verified", False))
    notes = str(doc.get("notes", "") or "")
    cards.section_heading(
        "Answer key", "Correct any field, then tick Verified and Save (blank = not on invoice)"
    )
    with st.form(key=f"gt-{item.id}"):
        edited: dict[str, str | None] = {}
        for group_key, group_label in _GROUPS:
            st.markdown(f"**{group_label}**")
            for key in field_meta.FIELD_ORDER:
                if field_meta.group_key(key) != group_key:
                    continue
                german = field_meta.german_label(key)
                label = f"{field_meta.label(key)}" + (f"  ·  {german}" if german else "")
                edited[key] = st.text_input(label, value=values[key], key=f"f-{item.id}-{key}")

        st.divider()
        st.markdown("**Repeating groups** — add/remove rows; leave a row blank to drop it")
        edited_groups: dict[str, list[dict[str, str]]] = {}
        for group_key, group_label in _REPEATING:
            st.caption(group_label)
            edited_groups[group_key] = list(
                st.data_editor(
                    _repeating_seed(doc, group_key),
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"grid-{item.id}-{group_key}",
                )
            )

        new_notes = st.text_area("Notes (optional)", value=notes, key=f"notes-{item.id}")
        new_verified = st.checkbox(
            "Verified — I checked every field against the invoice",
            value=verified,
            key=f"v-{item.id}",
        )
        submitted = st.form_submit_button("Save answer key", type="primary")

    if submitted:
        heldout_data.save_draft(
            item,
            fields=edited,
            verified=new_verified,
            notes=new_notes,
            vat_breakdown=edited_groups["vat_breakdown"],
            skonto=edited_groups["skonto"],
            line_items=edited_groups["line_items"],
        )
        state = "verified" if new_verified else "saved (unverified)"
        st.success(f"Answer key for `{item.id}` {state}.")
        st.rerun()


def _run() -> None:
    items = heldout_data.list_items()
    if not items:
        st.warning(
            "No held-out set found. Add invoices under `data/self-collected/"
            "<language>/<channel>/` then run "
            "`uv run python scripts/heldout_manifest.py index`."
        )
        return

    n_verified, n_total = heldout_data.progress()
    st.sidebar.metric("Verified", f"{n_verified} / {n_total}")
    st.sidebar.progress(n_verified / n_total if n_total else 0.0)

    by_id = {item.id: item for item in items}

    def _label(invoice_id: str) -> str:
        item = by_id[invoice_id]
        mark = "\u2714" if item.verified else "\u25cb"
        return f"{mark}  {invoice_id}  ·  {item.language}/{item.channel}"

    selected = st.sidebar.selectbox("Invoice", options=list(by_id), format_func=_label)
    item = by_id[selected]

    image_col, form_col = st.columns([2, 3], gap="large")
    with image_col:
        _render_pages(item)
    with form_col:
        _render_form(item)


_run()
