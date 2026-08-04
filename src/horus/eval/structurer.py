"""Layer-2 structurer — structuring-model JSON output -> validated 19-field dict (ADR-038).

The shared structurer for BOTH extraction arms (ADR-034):

  - **Arm A (single-shot):** image -> Gemma -> JSON. Gemma is the harness
    ``working_model``; its per-page JSON output is parsed here (the harness
    dispatches ``adapter_mode="structurer"`` to this module's
    ``to_predicted_dict_multipage``).
  - **Arm B (orchestrated):** image -> Granite -> text -> Gemma -> JSON. The
    Arm-B runner (``src/horus/eval/arm_b.py``) calls ``to_predicted_dict`` on
    Gemma's single structured output over the whole Granite transcript.

Difference from the sibling ``adapters_json`` (ADR-018/029): that module is the
*bare* JSON path (``json.loads`` -> ``str``-cast, no typing). This module routes
the recovered JSON through the typed ``InvoiceFields`` + ``validate_and_repair``
(ADR-035): case-insensitive key matching, per-field-type locale coercion (German
``1.234,56`` / ``DD.MM.YYYY`` / ``19 %`` -> canonical), honest ``null`` on
missing/unparseable, unknown-key drop. The JSON-recovery ladder itself is reused
verbatim (``adapters_json.recover_json_object``) — one home, no duplication.

Public surface (mirrors ``adapters.py`` / ``adapters_json.py`` for harness-side
swappability):

    to_predicted_dict(raw_text: str, model_id: str) -> dict[str, str | None]
    to_predicted_dict_multipage(per_page_texts: list[str], model_id: str)
        -> dict[str, str | None]
    to_full_dict(raw_text: str) -> dict[str, str | None]   # +purpose_summary (demo)

All scored paths return the canonical 19-key dict (keyed by ``FIELDS``); the
non-scored ``purpose_summary`` is dropped from the scored dict (``to_scored_dict``)
and surfaced only via ``to_full_dict`` for the Streamlit demo (ADR-035/036).
Unparseable output -> all-null (honest; never raises) — the tax-domain guardrail
that a generative structurer must never invent a value.

Refs: ADR-038 (this module's ratifying ADR), ADR-035 (``InvoiceFields`` +
``validate_and_repair``), ADR-037 (19-field scoring scope), ADR-018/029
(``adapters_json`` recovery ladder this reuses), ADR-013 (scorer contract),
ADR-034 (the two arms + honesty guardrail).
"""

from __future__ import annotations

from typing import Any

from horus.eval.adapters_json import recover_json_object
from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS
from horus.eval.schema import InvoiceFields

__all__ = [
    "build_structuring_input",
    "render_field_glossary",
    "render_structuring_prompt",
    "to_full_dict",
    "to_predicted_dict",
    "to_predicted_dict_multipage",
    "to_predicted_groups",
    "to_predicted_groups_multipage",
]

# Placeholder a structuring prompt template may carry to request the
# registry-sourced field guide (ADR-049). Substituted by `render_structuring_prompt`.
_FIELD_GLOSSARY_TOKEN = "{field_glossary}"


def render_field_glossary() -> str:
    """Render the registry's per-field guide (description + German label aliases).

    One terse line per ``FIELDS`` entry that carries a ``description`` — the
    confusable scalar fields whose English key does not obviously map to the
    German label printed on the invoice (document totals vs per-line/per-rate
    values; customer-number vs order-number; ADR-049). Fields without a
    ``description`` are omitted (the prompt's bare key list already names them).
    Repeating-group cells are deliberately NOT glossed: extending the guide to
    line-item cells was measured net-negative and rejected (ADR-053). Contains
    field SEMANTICS + example German LABEL names only — never a ground-truth
    value, so the guide is identical for every invoice + locale (the generic,
    no-leakage guardrail).
    """
    lines: list[str] = []
    for key, spec in FIELDS.items():
        if spec.description is None:
            continue
        if spec.prompt_aliases:
            labels = " / ".join(spec.prompt_aliases)
            lines.append(f"- {key}: {spec.description} (printed as: {labels})")
        else:
            lines.append(f"- {key}: {spec.description}")
    return "\n".join(lines)


def render_structuring_prompt(template: str) -> str:
    """Fill the ``{field_glossary}`` placeholder with the registry field guide.

    Single substitution point (ADR-049) so every structuring path — Arm A (via
    the harness), Arm B (``run_arm_b``), and the live demo — renders the SAME
    guide from one source of truth (the ``FIELDS`` registry). Uses plain
    ``str.replace`` (NOT ``str.format``) so the literal JSON braces elsewhere in
    the prompt are left untouched. A no-op when the placeholder is absent, so
    non-structurer prompts (the frozen regex baseline, the OCR/markdown
    COHORT_MANIFEST defaults) pass through unchanged.
    """
    if _FIELD_GLOSSARY_TOKEN not in template:
        return template
    return template.replace(_FIELD_GLOSSARY_TOKEN, render_field_glossary())


def build_structuring_input(structuring_prompt: str, reader_text: str) -> str:
    """Compose the structurer's text input: the instruction + the reader transcript.

    The YAML ``prompt_template_override`` carries only the *instruction* (what to
    extract, the honesty rule, the key list, and optionally a ``{field_glossary}``
    placeholder); the registry field guide is substituted via
    ``render_structuring_prompt`` (ADR-049) and the reader's transcript text is
    appended here under a clear delimiter so the prompt stays readable in config
    and the text-injection lives in one place. Shared by the offline Arm-B runner
    (``arm_b.run_arm_b``) and the live demo page (``live.run_read_then_structure``)
    so the two paths compose the structuring prompt identically (ADR-038/ADR-039).
    """
    rendered_prompt = render_structuring_prompt(structuring_prompt)
    return (
        f"{rendered_prompt}\n\n"
        "Invoice text (read by a specialist document model):\n"
        "<<<\n"
        f"{reader_text}\n"
        ">>>\n"
    )


# The backfill below reads three registry-defined names. Bind them to the registry
# at import time so a rename in `ground_truth` fails LOUDLY here instead of silently
# turning the repair into a no-op (the same fail-fast-at-boot discipline the config
# layer uses). A silently-disabled repair would re-introduce the BT-119 zero this
# function exists to fix, and nothing downstream would notice.
_TAX_RATE_KEY = "tax_rate"
_VAT_GROUP_KEY = "vat_breakdown"
_VAT_RATE_CELL = "rate_percent"

if _TAX_RATE_KEY not in FIELDS:
    raise RuntimeError(
        f"structurer: flat field {_TAX_RATE_KEY!r} is missing from the FIELDS registry; "
        "the single-rate tax_rate backfill (ADR-058) cannot be wired."
    )
if _VAT_GROUP_KEY not in REPEATING_GROUPS:
    raise RuntimeError(
        f"structurer: repeating group {_VAT_GROUP_KEY!r} is missing from REPEATING_GROUPS; "
        "the single-rate tax_rate backfill (ADR-058) cannot be wired."
    )
if _VAT_RATE_CELL not in REPEATING_GROUPS[_VAT_GROUP_KEY][1]:
    raise RuntimeError(
        f"structurer: cell {_VAT_RATE_CELL!r} is missing from the {_VAT_GROUP_KEY!r} group; "
        "the single-rate tax_rate backfill (ADR-058) cannot be wired."
    )


def _backfill_single_tax_rate(
    flat: dict[str, str | None],
    full: dict[str, Any],
) -> dict[str, str | None]:
    """Fill a null flat ``tax_rate`` from the model's OWN single-rate VAT breakdown.

    ADR-058. The oracle probe (perfect GT-rendered input) showed the structurer
    reliably filling ``vat_breakdown[].rate_percent`` while leaving the flat
    ``tax_rate`` null — the flat key reads as redundant once the table is emitted.
    BT-119 is the *document-level* rate, which is well-defined exactly when the
    invoice carries ONE distinct rate (the multi-rate case is scored EXCLUDED per
    ADR-045/052), so this copies the value across in precisely that case.

    Repair, not invention — the same charter as ``validate_and_repair`` (ADR-035):
    the value comes from the model's own emission, never from the ground truth.
    No-ops when the flat value is already set, when no breakdown was emitted, or
    when two or more distinct rates appear (there is no single document rate to
    state, and null is then the correct answer).
    """
    if flat.get(_TAX_RATE_KEY) is not None:
        return flat
    rows = full.get(_VAT_GROUP_KEY)
    if not isinstance(rows, list):
        return flat
    # `rate_percent` is already a canonical RATE string here: the schema's
    # `_coerce_by_type` ran during `model_validate`, so 19 / 19.0 / "19 %" / "19,00"
    # all arrive as "19" and an unparseable rate arrives as None. No re-coercion.
    rates = {
        row[_VAT_RATE_CELL]
        for row in rows
        if isinstance(row, dict) and row.get(_VAT_RATE_CELL) is not None
    }
    if len(rates) == 1:
        flat[_TAX_RATE_KEY] = next(iter(rates))
    return flat


def to_predicted_dict(raw_text: str, model_id: str) -> dict[str, str | None]:  # noqa: ARG001
    """Parse one structuring-model output into the scored 19-key predicted dict.

    Pipeline: recover the JSON object from the (possibly reasoning-wrapped,
    fenced, or trailing-token) model text via the shared ``adapters_json``
    ladder -> ``InvoiceFields`` validate/repair -> the canonical 19-key
    ``dict[str, str | None]`` the scorer consumes. Unrecoverable JSON yields an
    all-null dict (honest; the model is treated as having extracted nothing).

    One cross-field repair runs last: ``_backfill_single_tax_rate`` copies a
    single-rate VAT breakdown into the flat ``tax_rate`` (ADR-058).

    ``model_id`` is accepted for harness-side signature parity with
    ``adapters.py`` / ``adapters_json.py`` but is unused — structuring is
    model-agnostic (the recovery ladder + typed repair need no per-model
    dispatch). ``# noqa: ARG001`` suppresses the unused-argument warning.
    """
    # One recover + one validate: `to_scored_dict` and `to_full_dict` are two views
    # of the SAME validated model, so the cross-field repair costs no second parse.
    parsed = recover_json_object(raw_text)
    fields = InvoiceFields.model_validate(parsed if parsed is not None else {})
    return _backfill_single_tax_rate(fields.to_scored_dict(), fields.to_full_dict())


def to_predicted_dict_multipage(
    per_page_texts: list[str],
    model_id: str,
) -> dict[str, str | None]:  # noqa: ARG001
    """Parse per-page structuring outputs and merge with first-non-None-wins.

    The Arm-A path: the harness runs the structuring model (Gemma) once per
    rasterized page, so it hands this module a list of per-page outputs. Each is
    parsed independently via :func:`to_predicted_dict`; the per-page dicts are
    merged with **first-non-None-wins** (page 1 dominates), matching the
    ``adapters_json.to_predicted_dict_multipage`` semantics (ADR-019 W3.1) so a
    later page's spurious value cannot overwrite an earlier page's honest one.

    ``model_id`` is signature-parity-only (unused; ``# noqa: ARG001``).
    """
    merged: dict[str, str | None] = {key: None for key in FIELDS}
    for page_text in per_page_texts:
        page_dict = to_predicted_dict(page_text, model_id)
        for key, value in page_dict.items():
            if merged[key] is None and value is not None:
                merged[key] = value
    return merged


def to_predicted_groups(raw_text: str) -> dict[str, list[dict[str, str | None]]]:
    """Parse one structuring output into the repeating-group rows (ADR-042).

    Returns ``{group_key: [row dicts]}`` for vat_breakdown / skonto / line_items
    (empty list when the model emitted none) — the shape `scorer.score`'s
    ``predicted_groups`` consumes. Cells are already locale-coerced by
    ``InvoiceFields`` (same repair as the flat path). Unrecoverable JSON yields
    all-empty groups (honest; the model extracted no rows).
    """
    full = to_full_dict(raw_text)
    groups: dict[str, list[dict[str, str | None]]] = {}
    for group_key in REPEATING_GROUPS:
        rows = full.get(group_key)
        groups[group_key] = [dict(row) for row in rows] if isinstance(rows, list) else []
    return groups


def to_predicted_groups_multipage(
    per_page_texts: list[str],
    model_id: str,  # noqa: ARG001
) -> dict[str, list[dict[str, str | None]]]:
    """Merge per-page repeating groups: the first page with a non-empty group wins.

    Mirrors the flat first-non-None-wins merge (page 1 dominant; ADR-019 W3.1). A
    cross-page line-item concatenation is a documented follow-up; for the
    single-page synthetic corpus + typical short invoices this is exact.
    ``model_id`` is signature-parity-only (unused).
    """
    merged: dict[str, list[dict[str, str | None]]] = {key: [] for key in REPEATING_GROUPS}
    for page_text in per_page_texts:
        page_groups = to_predicted_groups(page_text)
        for group_key, rows in page_groups.items():
            if not merged[group_key] and rows:
                merged[group_key] = rows
    return merged


def to_full_dict(raw_text: str) -> dict[str, Any]:
    """Parse one structuring-model output into the FULL dict (flat + groups + summary).

    Same recovery + validate/repair as :func:`to_predicted_dict`, but returns
    ``InvoiceFields.to_full_dict()`` — the 34 scored flat fields PLUS the non-scored
    ``purpose_summary`` and the repeating-group lists (vat_breakdown / skonto /
    line_items; for the Streamlit demo + `to_predicted_groups`). The flat scorer
    never sees this; use :func:`to_predicted_dict` on the flat scoring path.
    """
    parsed = recover_json_object(raw_text)
    if parsed is None:
        parsed = {}
    return InvoiceFields.model_validate(parsed).to_full_dict()
