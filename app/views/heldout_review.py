"""Ground Truth Sign-off — settle the held-out Belege answer keys (ADR-040 / ADR-062).

The annotation surface for the private held-out test set, driven by the adjudication
manifest rather than by the whole schema. Three channels have read every invoice (the
text-layer draft, the ADR-060 vision judge, the ADR-061 Azure channel); the combiner
already settled the cells that carry a warrant. This page shows the author only what it
could not settle, ranked worst-first, with every channel's reading and the page text that
backs it.

Why not the old whole-schema form: re-reading 34 fields on 39 invoices is 1,326 decisions,
and a review nobody can finish is a review that does not happen — which is how the
retracted 0.5692 came to rest on an unverified answer key. 248 ranked decisions can be
finished.

Saving writes `data/self-collected/_promoted/<id>.gt.json` (git-ignored), carrying a
provenance block per cell. It deliberately does not touch `gt/`, which is still one of the
channels the combiner reads.

This is a WRITE page (like *Extract an Invoice*), the bounded exception to the read-only
research surfaces (ADR-036/039) — producing ground truth is inherently an annotation task.
It runs no models; every reading is read from disk. Nothing here leaves the machine or
enters git.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

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

# What each escalation rank means, in the author's terms. Keyed by the rank label the
# manifest carries so a new rank in `adjudication` surfaces as itself rather than crashing.
_RANK_HELP: dict[str, str] = {
    "asserted-unevidenced": "One channel claims this. Nothing prints it, nothing contradicts "
    "it — the most dangerous shape there is, because it looks fine.",
    "conflict-none-evidenced": "The channels disagree and the page cannot break the tie "
    "(either nothing is printed, or both values are).",
    "conflict-one-evidenced": "The channels disagree, but exactly one value is printed.",
    "null-disputed": "One channel found a value the page does not back; another looked and "
    "found nothing.",
    "weak-match": "The match is too short to be evidence — a 2-3 character string occurs "
    "incidentally all over an invoice.",
    "unparseable": "The value will not parse as its declared type.",
    "exempt-vocabulary": "A controlled-vocabulary value the page never prints as stored, "
    "asserted by one channel. Searching cannot help.",
    "single-channel-proven": "The value IS printed, but only one channel says it belongs to "
    "this field. The gate proves presence, never assignment.",
    "nested-readings": "Same value at different levels of detail (a logo mark vs the "
    "registered entity). EN16931 keeps legal name and trading name apart, so this is your "
    "call — but it is the same call every time.",
}

#: Sentinel for the "not on this invoice" radio option. Not a value any channel can return,
#: because it is not a value — it is the decision that the field is absent.
_ABSENT = "\u2014 not on this invoice"

#: Sentinel for "type something else".
_CUSTOM = "\u270e type my own"

#: Session key carrying the save outcome across the `st.rerun()` that follows a save.
#: Anything rendered before a rerun is discarded by it, so the message has to survive the
#: rerun rather than be written before it — and the outcome here is not decoration: it is
#: where the author learns that sign-off was WITHHELD.
_FLASH = "heldout-signoff-flash"


def _flash(level: str, message: str) -> None:
    st.session_state[_FLASH] = (level, message)


def _render_flash() -> None:
    stashed = st.session_state.pop(_FLASH, None)
    if not stashed:
        return
    level, message = stashed
    {"success": st.success, "warning": st.warning}.get(level, st.info)(message)


# Repeating groups (ADR-041/042) — rendered as variable-length grids below the
# flat fields. One row per VAT rate / Skonto tier / line item.
_REPEATING: tuple[tuple[str, str], ...] = (
    ("vat_breakdown", "VAT breakdown — one row per rate"),
    ("skonto", "Skonto — one row per discount tier"),
    ("line_items", "Line items — one row per position"),
)

st.title("Ground Truth Sign-off")
st.caption(
    "Three channels have read every invoice. Decide the cells they could not settle — worst-first."
)

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


def _field_label(key: str) -> str:
    german = field_meta.german_label(key)
    return field_meta.label(key) + (f"  ·  {german}" if german else "")


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


def _readings_of(cell: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = cell.get("readings")
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _options_for(cell: Mapping[str, Any]) -> list[str]:
    """Distinct candidate values for one escalated cell, plus the two decision sentinels.

    Duplicates are collapsed so three channels agreeing on a rendering do not produce three
    identical radio entries; `_ABSENT` is always offered because deciding a field is not on
    the invoice is the correct answer whenever a channel hallucinated one.
    """
    seen: list[str] = []
    for reading in _readings_of(cell):
        value = reading.get("value")
        if isinstance(value, str) and value.strip() and value not in seen:
            seen.append(value)
    return [*seen, _ABSENT, _CUSTOM]


def _describe_readings(cell: Mapping[str, Any]) -> None:
    """Every channel's answer, with the printed marker and confidence it carries."""
    evidenced = cell.get("evidenced_channels")
    evidenced_set = set(evidenced) if isinstance(evidenced, list) else set()
    for reading in _readings_of(cell):
        channel = str(reading.get("channel", "?"))
        if not reading.get("covered", True):
            st.caption(f"`{channel}` — *cannot express this field*")
            continue
        value = reading.get("value")
        if value is None:
            st.caption(f"`{channel}` — *found nothing*")
            continue
        confidence = reading.get("confidence")
        suffix = f" · conf {float(confidence):.2f}" if isinstance(confidence, (int, float)) else ""
        printed = " · **printed on the page**" if channel in evidenced_set else ""
        st.caption(f"`{channel}` — `{value}`{suffix}{printed}")
    context = cell.get("context")
    if isinstance(context, str) and context:
        st.caption(f"page text: …{context}…")


def _render_escalation(
    item: HeldoutItem, cell: Mapping[str, Any], prior: str | None, *, had_prior: bool
) -> tuple[bool, str | None]:
    """One escalated cell. Returns `(answered, value)`.

    `answered` is separate from `value` because `None` is a legitimate ANSWER ("not on this
    invoice") as well as the absence of one, and collapsing the two is precisely how an
    unreviewed cell would slip into the answer key looking decided.

    A cell with no prior answer opens on no selection at all. Pre-selecting the proposed
    value would make "I have not looked at this" indistinguishable from "I agree".
    """
    key = str(cell.get("key", ""))
    rank = str(cell.get("rank") or "?")
    options = _options_for(cell)

    st.markdown(f"**{_field_label(key)}**  ·  `{rank}`")
    help_text = _RANK_HELP.get(rank)
    if help_text:
        st.caption(help_text)
    _describe_readings(cell)

    preselect: int | None = None
    if had_prior:
        if prior is None:
            preselect = options.index(_ABSENT)
        elif prior in options:
            preselect = options.index(prior)
        else:
            preselect = options.index(_CUSTOM)

    choice = st.radio(
        "Decision",
        options=options,
        index=preselect,
        key=f"pick-{item.id}-{key}",
        label_visibility="collapsed",
    )
    if choice == _CUSTOM:
        seed = prior if had_prior and prior is not None and prior not in options else ""
        typed = st.text_input(
            "Value as printed on the invoice",
            value=seed,
            key=f"typed-{item.id}-{key}",
        )
        return True, (typed.strip() or None)
    if choice == _ABSENT:
        return True, None
    if choice is None:
        return False, None
    return True, str(choice)


def _render_accepted(cells: Sequence[Mapping[str, Any]]) -> None:
    """The cells promoted without review, inspectable but not editable here.

    Read-only on purpose: these are settled by a recorded warrant, and a stray edit would
    quietly downgrade a `text-layer-proven` cell to an unrecorded opinion. Correcting one
    means re-running the review pass, not overtyping it.
    """
    accepted = [c for c in cells if c.get("auto_accepted")]
    asserted = [c for c in accepted if c.get("value") is not None]
    absent = len(accepted) - len(asserted)
    with st.expander(
        f"{len(asserted)} cells accepted on their warrant · {absent} undisputed absences",
        expanded=False,
    ):
        st.caption(
            "Read-only. Each of these carries a recorded provenance class; to change one, "
            "fix the channel and re-run `scripts/review_heldout_gt.py`."
        )
        for cell in asserted:
            key = str(cell.get("key", ""))
            st.markdown(
                f"**{_field_label(key)}** — `{cell.get('value')}`  "
                f"<span style='color:{theme.MUTED}'>· {cell.get('provenance')}</span>",
                unsafe_allow_html=True,
            )


def _render_sign_off(item: HeldoutItem, document: Mapping[str, Any]) -> None:
    """The escalation queue for one invoice, worst-first."""
    _render_flash()
    cells = heldout_data.manifest_cells(document)
    escalations = [c for c in cells if not c.get("auto_accepted")]
    escalations.sort(key=lambda c: (c.get("rank_order") or 99, str(c.get("key"))))
    saved_doc = heldout_data.load_promotion(item)
    resumed = heldout_data.resume_decisions(item)

    summary = document.get("summary")
    tier = str(document.get("tier", "?"))
    if isinstance(summary, Mapping):
        st.markdown(
            f"Tier **{tier}** · **{summary.get('asserted_auto_accepted', 0)}** of "
            f"**{summary.get('asserted_total', 0)}** asserted cells settled without review · "
            f"**{len(escalations)}** need you."
        )

    _render_accepted(cells)

    cards.section_heading(
        "Cells needing a decision",
        "Worst-first. Pick a channel's reading, type your own, or mark the field absent.",
    )
    if not escalations:
        st.success("Nothing escalated for this invoice — every asserted cell carried a warrant.")

    with st.form(key=f"signoff-{item.id}"):
        decisions: dict[str, object] = {}
        for cell in escalations:
            key = str(cell.get("key", ""))
            with st.container(border=True):
                answered, value = _render_escalation(
                    item, cell, resumed.get(key), had_prior=key in resumed
                )
            if answered:
                decisions[key] = value

        st.divider()
        st.markdown("**Repeating groups** — rows come from the vision judge; correct them here")
        st.caption(
            "Not adjudicated cell-by-cell: rows do not align across channels, so a positional "
            "comparison would invent conflicts out of how each reader split the table. Row-count "
            "disagreement is reported instead."
        )
        _render_row_counts(document)
        judge_doc = (
            saved_doc
            or heldout_data.load_channel_document(item, "judge")
            or heldout_data.load_draft(item)
        )
        edited_groups: dict[str, list[dict[str, str]]] = {}
        for group_key, group_label in _REPEATING:
            st.caption(group_label)
            edited_groups[group_key] = list(
                st.data_editor(
                    _repeating_seed(judge_doc, group_key),
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"grid-{item.id}-{group_key}",
                )
            )

        new_notes = st.text_area(
            "Notes (optional)",
            value=str((saved_doc or {}).get("notes", "") or ""),
            key=f"notes-{item.id}",
        )
        new_verified = st.checkbox(
            "Signed off — every escalated cell above is decided",
            value=bool((saved_doc or {}).get("verified", False)),
            key=f"v-{item.id}",
        )
        submitted = st.form_submit_button("Save sign-off", type="primary")

    if not submitted:
        return

    # Prior answers survive a partial pass: a cell the author has not touched this session
    # keeps whatever they decided last time rather than reverting to undecided.
    merged: dict[str, object] = {**resumed, **decisions}
    path = heldout_data.save_promotion(
        item,
        cells=cells,
        decisions=merged,
        verified=new_verified,
        notes=new_notes,
        vat_breakdown=edited_groups["vat_breakdown"],
        skonto=edited_groups["skonto"],
        line_items=edited_groups["line_items"],
    )
    decided, total = heldout_data.sign_off_progress(cells, merged)
    if new_verified and decided < total:
        _flash(
            "warning",
            f"Saved to `{path.name}`, but sign-off is WITHHELD: {total - decided} escalated "
            "cell(s) still have no decision. A verified flag over an unfinished document is "
            "how the last held-out figure had to be retracted.",
        )
    elif new_verified:
        _flash("success", f"`{item.id}` signed off — all {total} decisions recorded.")
    else:
        _flash("success", f"`{item.id}` saved — {decided}/{total} decided.")
    st.rerun()


def _render_row_counts(document: Mapping[str, Any]) -> None:
    """Per-group row counts per channel; only shown where the channels disagree."""
    counts = document.get("group_row_counts")
    if not isinstance(counts, Mapping):
        return
    for group, per_channel in counts.items():
        if not isinstance(per_channel, Mapping) or len(set(per_channel.values())) <= 1:
            continue
        rendered = " · ".join(f"{name}={n}" for name, n in per_channel.items())
        st.caption(f"`{group}` row counts disagree: {rendered}")


def _render_draft_form(item: HeldoutItem) -> None:
    """The pre-adjudication whole-schema form.

    Retained as the fallback for an invoice with no manifest entry (a newly added document,
    or a corpus where the review pass has not been run). Kept rather than deleted because
    without it such an invoice would have no annotation surface at all.
    """
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


def _render_corpus_summary(manifest: Mapping[str, Any]) -> None:
    """The collapse ratio, over asserted cells.

    Asserted-only is the headline because roughly half the schema is legitimately absent on
    any given invoice, and counting undisputed absences as collapsed work reports a much
    prettier number without a single extra cell being settled.
    """
    summary = manifest.get("summary")
    if not isinstance(summary, Mapping):
        return
    asserted = int(summary.get("asserted_total", 0) or 0)
    accepted = int(summary.get("asserted_auto_accepted", 0) or 0)
    st.sidebar.metric("Settled without review", f"{accepted} / {asserted}")
    st.sidebar.progress(accepted / asserted if asserted else 0.0)
    st.sidebar.caption(
        f"{int(summary.get('asserted_escalated', 0) or 0)} cells need a decision. "
        f"Excludes {int(summary.get('null_claims', 0) or 0)} undisputed absences."
    )


def _run() -> None:
    items = heldout_data.list_items()
    if not items:
        st.warning(
            "No held-out set found. Add invoices under `data/self-collected/"
            "<language>/<channel>/` then run "
            "`uv run python scripts/heldout_manifest.py index`."
        )
        return

    manifest = heldout_data.load_manifest()
    documents = heldout_data.manifest_documents(manifest) if manifest else {}
    if manifest is None:
        st.info(
            "No adjudication manifest yet — falling back to the whole-schema form. Run "
            "`uv run python scripts/review_heldout_gt.py` to collapse the answer key to the "
            "cells that actually need you."
        )
    else:
        _render_corpus_summary(manifest)

    by_id = {item.id: item for item in items}

    def _label(invoice_id: str) -> str:
        document = documents.get(invoice_id)
        if document is None:
            return f"\u25cb  {invoice_id}  ·  no manifest entry"
        raw_pending = document.get("escalated_keys")
        pending = len(raw_pending) if isinstance(raw_pending, list) else 0
        mark = "\u2714" if pending == 0 else "\u25cb"
        tier = document.get("tier", "?")
        return f"{mark}  {invoice_id}  ·  Tier {tier}  ·  {pending} open"

    selected = st.sidebar.selectbox("Invoice", options=list(by_id), format_func=_label)
    item = by_id[selected]
    document = documents.get(selected)

    image_col, form_col = st.columns([2, 3], gap="large")
    with image_col:
        _render_pages(item)
    with form_col:
        if document is None:
            _render_draft_form(item)
        else:
            _render_sign_off(item, document)


_run()
