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

from horus.eval.adapters_json import recover_json_object
from horus.eval.ground_truth import FIELDS
from horus.eval.schema import InvoiceFields, validate_and_repair

__all__ = [
    "build_structuring_input",
    "to_full_dict",
    "to_predicted_dict",
    "to_predicted_dict_multipage",
]


def build_structuring_input(structuring_prompt: str, reader_text: str) -> str:
    """Compose the structurer's text input: the instruction + the reader transcript.

    The YAML ``prompt_template_override`` carries only the *instruction* (what to
    extract, the honesty rule, the key list); the reader's transcript text is
    appended here under a clear delimiter so the prompt stays readable in config
    and the text-injection lives in one place. Shared by the offline Arm-B runner
    (``arm_b.run_arm_b``) and the live demo page (``live.run_read_then_structure``)
    so the two paths compose the structuring prompt identically (ADR-038/ADR-039).
    """
    return (
        f"{structuring_prompt}\n\n"
        "Invoice text (read by a specialist document model):\n"
        "<<<\n"
        f"{reader_text}\n"
        ">>>\n"
    )


def to_predicted_dict(raw_text: str, model_id: str) -> dict[str, str | None]:  # noqa: ARG001
    """Parse one structuring-model output into the scored 19-key predicted dict.

    Pipeline: recover the JSON object from the (possibly reasoning-wrapped,
    fenced, or trailing-token) model text via the shared ``adapters_json``
    ladder -> ``InvoiceFields`` validate/repair -> the canonical 19-key
    ``dict[str, str | None]`` the scorer consumes. Unrecoverable JSON yields an
    all-null dict (honest; the model is treated as having extracted nothing).

    ``model_id`` is accepted for harness-side signature parity with
    ``adapters.py`` / ``adapters_json.py`` but is unused — structuring is
    model-agnostic (the recovery ladder + typed repair need no per-model
    dispatch). ``# noqa: ARG001`` suppresses the unused-argument warning.
    """
    parsed = recover_json_object(raw_text)
    return validate_and_repair(parsed)


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


def to_full_dict(raw_text: str) -> dict[str, str | None]:
    """Parse one structuring-model output into the FULL 20-key dict (incl. purpose_summary).

    Same recovery + validate/repair as :func:`to_predicted_dict`, but returns
    ``InvoiceFields.to_full_dict()`` — the 19 scored fields PLUS the non-scored
    ``purpose_summary`` (for the Streamlit demo per ADR-035/036). The scorer
    never sees this; use :func:`to_predicted_dict` on the scoring path.
    """
    parsed = recover_json_object(raw_text)
    if parsed is None:
        parsed = {}
    return InvoiceFields.model_validate(parsed).to_full_dict()
