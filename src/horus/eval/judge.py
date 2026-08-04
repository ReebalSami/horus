"""Cloud vision judge for held-out ground truth (ADR-060).

Authors held-out ground truth by reading the 300 DPI page rasters with a frontier
vision model, replacing the text-layer-drafted GT that ADR-060 proved unusable
(hallucinated values on the image-only scans; 19 of 34 flat fields covered and no
repeating groups at all, which mechanically zeroed `line_items` / `vat_breakdown` /
`document_type` in scoring).

Three design choices carry the weight:

**The output schema is DERIVED from the field registry**, never hand-written. A
hand-maintained schema would drift from `FIELDS` / `REPEATING_GROUPS` and reintroduce
exactly the coverage gap this module exists to close — a key the scorer scores but the
schema omits is silently unanswerable.

**Field semantics are reused verbatim** from `structurer.render_field_glossary()`, the
corpus-grounded, leak-free guide (ADR-049, cleaned in ADR-058). Judge and structurer
must not hold different beliefs about what `line_total_amount` means, or a scoring
disagreement becomes unattributable.

**Illegible is a first-class answer.** These are photographed till receipts; some cells
genuinely cannot be read by anything. A guess in an ANSWER KEY is worse than an
admission, because it silently penalises a correct extraction forever — which is
precisely how the superseded GT failed (`53,97` for a printed `63,97`).

The judge is a measurement instrument, never part of the delivered system: HORUS's
inference path stays fully local, and no cloud call exists in it. Per ADR-060 the
verdict is written with `verified: false` — a frontier model is a better drafter, not a
human, and only author review may set `verified: true`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS
from horus.eval.structurer import render_field_glossary

if TYPE_CHECKING:  # pragma: no cover — import cost only paid by type checkers
    from anthropic import Anthropic

EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]

DEFAULT_EFFORT: EffortLevel = "xhigh"
DEFAULT_MAX_TOKENS = 16000
#: Substrings tried in order against `client.models.list()` (newest first) to pick the
#: judge. Preference, not a pin: ADR-060 resolves the strongest model available to the
#: CALLER's account rather than hardcoding an id that may not exist by the time this
#: runs.
DEFAULT_MODEL_PREFERENCE: tuple[str, ...] = ("opus", "sonnet")

_MEDIA_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class JudgeConfig:
    """Judge invocation settings.

    ``model=None`` resolves the strongest available model at call time (see
    ``DEFAULT_MODEL_PREFERENCE``). ``effort`` maps to the Messages API
    ``output_config.effort`` lever, which is independent of the thinking budget.
    """

    model: str | None = None
    effort: EffortLevel = DEFAULT_EFFORT
    max_tokens: int = DEFAULT_MAX_TOKENS
    thinking: bool = True
    model_preference: tuple[str, ...] = DEFAULT_MODEL_PREFERENCE


@dataclass(frozen=True)
class JudgeVerdict:
    """One invoice's judged ground truth, plus what the judge could not read."""

    invoice_id: str
    model: str
    fields: dict[str, str | None]
    vat_breakdown: list[dict[str, Any]]
    skonto: list[dict[str, Any]]
    line_items: list[dict[str, Any]]
    illegible_fields: list[str]
    notes: str
    input_tokens: int
    output_tokens: int
    n_pages: int


def resolve_judge_model(
    client: Anthropic, preference: tuple[str, ...] = DEFAULT_MODEL_PREFERENCE
) -> str:
    """Return the newest available model id matching ``preference``, in order.

    `client.models.list()` returns models newest-first, so the first substring hit is
    the most recent model of that family. Falls back to the newest model overall when
    nothing matches, and raises only when the account exposes no models at all.
    """
    available = [m.id for m in client.models.list(limit=100)]
    if not available:
        raise RuntimeError("Anthropic account exposes no models — cannot select a judge.")
    for wanted in preference:
        for model_id in available:  # newest first
            if wanted in model_id.lower():
                return model_id
    return available[0]


def gt_output_schema() -> dict[str, object]:
    """Build the judge's JSON schema from the field registry.

    Every flat field in ``FIELDS`` and every cell of every group in
    ``REPEATING_GROUPS`` is required and nullable, so "absent" is stated explicitly
    rather than inferred from an omitted key — the distinction the superseded GT lost.
    All values are strings (or null) because GT stores the value AS PRINTED and
    normalization happens later in `build_groundtruth_from_mapping`.
    """
    nullable_string: dict[str, object] = {"type": ["string", "null"]}

    flat_props: dict[str, object] = {key: dict(nullable_string) for key in FIELDS}
    group_props: dict[str, object] = {}
    for group_name, (_row_xpath, cells) in REPEATING_GROUPS.items():
        group_props[group_name] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {cell: dict(nullable_string) for cell in cells},
                "required": list(cells),
                "additionalProperties": False,
            },
        }

    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "object",
                "properties": flat_props,
                "required": list(FIELDS),
                "additionalProperties": False,
            },
            **group_props,
            "illegible_fields": {
                "type": "array",
                "items": {"type": "string"},
            },
            "notes": {"type": "string"},
        },
        "required": ["fields", *REPEATING_GROUPS, "illegible_fields", "notes"],
        "additionalProperties": False,
    }


def judge_instructions() -> str:
    """Instructions for authoring an answer key (not for extraction).

    The framing matters: the model is told it is producing ground truth that will
    permanently judge another system, so an unsupported guess is a worse error than an
    admitted gap. That is the inverse of the extraction prompt's incentive.
    """
    return f"""You are producing GROUND TRUTH for an invoice-extraction benchmark by
reading the attached page image(s) of ONE invoice.

Your output becomes the permanent answer key. Another system's accuracy will be
measured against it forever. Therefore:

- A WRONG value is far worse than an honest null. If you cannot read a value with
  confidence, set the field to null and add its key to `illegible_fields`.
- NEVER infer, derive, or compute a value that is not printed. Do not add up line
  items to produce a total, do not subtract tax to produce a net amount, do not
  convert a date format.
- NEVER copy a value from a different field to fill a gap.
- Transcribe values EXACTLY AS PRINTED, preserving the document's own formatting:
  German decimal comma and thousands dot stay as printed (`1.234,56`), dates stay in
  the printed form (`28.09.2022`, `March 27, 2024`), percentages are the bare
  number (`19`).
- `null` means the value is genuinely not on the page. Most invoices leave many
  fields absent; that is normal and expected.

Document types you may encounter include B2B invoices, credit notes, and RETAIL TILL
RECEIPTS (Kassenbelege) photographed with a phone. A till receipt legitimately has no
buyer, no buyer address, and often no invoice number in the formal sense — leave those
null rather than inventing them. A product BRAND printed next to a line item is not
the buyer.

Amount fields refer to WHOLE-DOCUMENT totals (typically under a
`Summe`/`Belegsummen`/`Total` block), never to a single line and never to one VAT
rate's subtotal. Per-rate figures belong in `vat_breakdown`; per-line figures belong
in `line_items`.

`document_type` is one of exactly: "invoice", "credit_note", "correction".

For the array fields, emit one object per row actually printed, in document order, and
`[]` when the document has none:
- `vat_breakdown` — per VAT rate: category_code, rate_percent, taxable_amount,
  tax_amount
- `skonto` — early-payment discount tiers: percent, days, basis_amount
- `line_items` — per product/service line: line_id, name, seller_assigned_id,
  net_price, quantity, vat_rate, line_amount

Field guide — choose the key by the label printed on the document:
{render_field_glossary()}

Use `notes` for anything an author reviewing this key should know: poor legibility,
ambiguous labels, an unusual document type, or a value you deliberately left null
despite a partial reading."""


def _image_block(path: Path) -> dict[str, object]:
    """Build one base64 image content block; the SDK encodes the file itself."""
    media_type = _MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(f"unsupported image type {path.suffix!r} for judge input: {path}")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": path},
    }


def _response_text(message: Any) -> str:
    """Concatenate the text blocks of a Messages response, skipping thinking blocks."""
    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


def judge_invoice(
    client: Anthropic,
    page_paths: list[Path],
    *,
    invoice_id: str,
    config: JudgeConfig | None = None,
) -> JudgeVerdict:
    """Judge ONE invoice from its page images and return the authored ground truth.

    All pages go in a single request so the judge sees the whole document: totals on a
    later page must be reconcilable with line items on an earlier one, which a
    per-page pass structurally cannot do.
    """
    import json  # local: keeps module import cheap for callers that only need schemas

    if not page_paths:
        raise ValueError(f"no page images supplied for {invoice_id}.")
    cfg = config or JudgeConfig()
    model = cfg.model or resolve_judge_model(client, cfg.model_preference)

    content: list[dict[str, object]] = [{"type": "text", "text": judge_instructions()}]
    content.extend(_image_block(p) for p in page_paths)

    request: dict[str, Any] = {
        "model": model,
        "max_tokens": cfg.max_tokens,
        "messages": [{"role": "user", "content": content}],
        "output_config": {
            "effort": cfg.effort,
            "format": {"type": "json_schema", "schema": gt_output_schema()},
        },
    }
    if cfg.thinking:
        request["thinking"] = {"type": "adaptive"}

    message = client.messages.create(**request)
    raw = _response_text(message)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"judge returned non-JSON for {invoice_id} "
            f"(stop_reason={getattr(message, 'stop_reason', None)!r}): {exc}"
        ) from exc

    fields_obj = parsed.get("fields", {})
    return JudgeVerdict(
        invoice_id=invoice_id,
        model=model,
        fields={key: cast(str | None, fields_obj.get(key)) for key in FIELDS},
        vat_breakdown=list(parsed.get("vat_breakdown") or []),
        skonto=list(parsed.get("skonto") or []),
        line_items=list(parsed.get("line_items") or []),
        illegible_fields=list(parsed.get("illegible_fields") or []),
        notes=str(parsed.get("notes") or ""),
        input_tokens=int(getattr(message.usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(message.usage, "output_tokens", 0) or 0),
        n_pages=len(page_paths),
    )


def verdict_to_gt_document(
    verdict: JudgeVerdict, *, language: str, channel: str, schema_version: int = 1
) -> dict[str, object]:
    """Render a verdict as a `<id>.gt.json` document.

    Shape matches what `build_groundtruth_from_json` reads: flat values under
    ``fields``, repeating groups at the TOP level. ``verified`` stays False — only
    author review may flip it (ADR-060), and the datasheet reports drafted-vs-verified
    separately so the distinction survives into the thesis.
    """
    notes = verdict.notes
    if verdict.illegible_fields:
        illegible = ", ".join(sorted(verdict.illegible_fields))
        prefix = f"ILLEGIBLE (judge could not read; left null): {illegible}."
        notes = f"{prefix} {notes}".strip()
    return {
        "schema_version": schema_version,
        "id": verdict.invoice_id,
        "language": language,
        "channel": channel,
        "drafted_by": verdict.model,
        "verified": False,
        "verified_date": None,
        "notes": notes,
        "fields": verdict.fields,
        "vat_breakdown": verdict.vat_breakdown,
        "skonto": verdict.skonto,
        "line_items": verdict.line_items,
    }
