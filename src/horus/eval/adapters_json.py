"""Layer-2 JSON adapter -- parses JSON-formatted VLM output into the 16-field predicted dict.

Sibling to ``src/horus/eval/adapters.py`` (the canonical regex-based path per
ADR-013). Produced by ADR-018 to support the structured-output probe (issue #53)
and the forthcoming Experiment 2 (issue #54) IF the probe ratifies the JSON path.

Public surface IDENTICAL to ``adapters.py`` for harness-side swappability:

    preprocess(raw: str, model_id: str) -> str
    to_predicted_dict(raw_text: str, model_id: str) -> dict[str, str | None]

Both modules' ``to_predicted_dict`` return the same ``dict[str, str | None]``
shape keyed by the 16 canonical FIELDS keys (per ADR-012). The harness selects
between them via ``cohort.adapter_mode: Literal["regex", "json"]`` (per ADR-018
schema addition in ``src/horus/config.py``).

Permissive JSON recovery (5-step ladder; first match wins):

    1. ``json.loads(text)`` direct attempt on the preprocessed text.
    2. Substring extraction: ``text[first_lbrace : last_rbrace + 1]`` -- handles
       models that emit prose before / after the JSON object.
    3. Trailing-comma tolerance via regex ``,\\s*([}\\]])`` -> ``\\1`` -- handles
       models that emit human-readable JSON with the trailing comma JS / Python
       convention rejects but humans use.
    4. Substring + trailing-comma applied jointly to the substring.
    5. All attempts failed -> return all-None dict (16 keys, all None).

Design decisions (locked in ADR-018 §"Decision + integration thoughts"):

    - **Top-level keys only**. Pre-registered Arm A + B prompts are flat schema;
      nested objects (e.g., ``{"seller": {"name": "X"}}``) are NOT flattened. A
      model emitting nested keys is failing the schema instruction; surface this
      as "missing canonical keys" rather than silently flatten.

    - **Case-insensitive key matching**. ``Invoice_Number`` and
      ``invoice_number`` both map to canonical ``invoice_number``. Defends
      against models that capitalize-camel-case the schema instruction.

    - **Cohort-uniform preprocess**. NO model-specific dispatch (unlike
      ``adapters.py``). JSON is its own normalization. ``model_id`` argument
      preserved for signature parity but unused; ``# noqa: ARG001`` suppresses
      the unused-argument lint warning.

    - **No new dependencies**. ``json`` (stdlib) + ``unicodedata`` (stdlib) +
      ``re`` (stdlib).

Refs:

    - ADR-018 (this module's ratifying ADR)
    - ADR-013 §"Decision + integration thoughts" (sibling adapters.py public
      surface that this module mirrors)
    - ADR-012 (FIELDS canonical 16-key registry)
    - ``tests/test_adapters_json.py`` (per-edge-case coverage matrix)
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from horus.eval.ground_truth import FIELDS

# Markdown code-fence pattern. Canonical Gemma / instruction-tuned shape is
# ```json\n...\n``` ; some Cat-1 / Cat-2 OCR-trained models that "echo" the
# prompt wrap output in a bare ```\n...\n``` fence without the lang tag.
#
# DOTALL because the JSON body may span multiple lines; non-greedy `.+?` so we
# stop at the first closing fence.
_FENCE_RE: re.Pattern[str] = re.compile(
    r"```(?:json)?\s*\n(.+?)\n\s*```",
    re.DOTALL | re.IGNORECASE,
)

# Trailing-comma sanitizer -- replaces `,\s*}` and `,\s*]` with the closing
# brace alone. Used in the substring + trailing-comma recovery branch only.
_TRAILING_COMMA_RE: re.Pattern[str] = re.compile(r",(\s*[}\]])")

# Chat-artifact tokens that VLMs emit at end-of-generation. Stripping these
# pre-JSON-parse handles the case where the model produced valid JSON followed
# by a chat-template token (MinerU / Qwen-family emit `<|im_end|>`; Gemma
# emits `<eos>`). Concatenated literals avoid any tooling that might trip on
# the angle-bracket-pipe sequence inside a single string literal.
_CHAT_ARTIFACTS: tuple[str, ...] = (
    "<" + "|im_end|" + ">",
    "<eos>",
    "<" + "|endoftext|" + ">",
)


def preprocess(raw: str, model_id: str) -> str:  # noqa: ARG001
    """Strip markdown fences + chat artifacts + NFC-normalize the raw VLM output.

    Cohort-uniform: NO model-specific dispatch. ``model_id`` is signature-parity-
    only with ``adapters.preprocess`` (which DOES dispatch on model_id for
    Layer-1 routing).

    Operations (in order):

        1. Strip leading + trailing whitespace.
        2. Strip the FIRST markdown code fence if present (``\\`\\`\\`json ... \\`\\`\\```
           or bare ``\\`\\`\\` ... \\`\\`\\```).
        3. Strip chat-artifact tokens (``_CHAT_ARTIFACTS``).
        4. Apply Unicode NFC normalization (matches GT-side normalization in
           ``ground_truth.py``; ensures composed-vs-decomposed forms compare
           equal downstream).

    Args:
        raw: raw VLM output text.
        model_id: cohort model identifier; UNUSED in this module.

    Returns:
        Preprocessed text ready for ``to_predicted_dict``.
    """
    text = raw.strip()

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    for artifact in _CHAT_ARTIFACTS:
        text = text.replace(artifact, "")

    text = unicodedata.normalize("NFC", text).strip()
    return text


def to_predicted_dict(raw_text: str, model_id: str) -> dict[str, str | None]:  # noqa: ARG001
    """Parse JSON-formatted VLM output into the 16-field predicted dict.

    Permissive JSON recovery -- see module docstring §"Permissive JSON recovery"
    for the 5-step ladder.

    Always returns a dict with all 16 canonical FIELDS keys present; missing
    keys (or all-recovery-failed cases) -> None.

    Design:

        - Top-level keys ONLY (no nested flattening).
        - Case-insensitive key matching.
        - Empty string from model -> empty string preserved (NOT collapsed to
          None; scorer's comparator handles the empty-vs-missing distinction
          per ADR-012's tristate value semantics).
        - ``null`` / Python None -> preserved as None.
        - Numeric values (int / float / bool) -> ``str(value)``.
        - List / nested object -> the canonical key maps to None for that field
          (treated as "model failed schema for this field").

    Args:
        raw_text: PREPROCESSED text (caller invokes ``preprocess`` first;
            harness call site preserves this contract).
        model_id: cohort model identifier; UNUSED in this module.

    Returns:
        dict keyed by all 16 canonical FIELDS keys, each mapped to ``str | None``.
    """
    parsed = _try_parse_json(raw_text)
    canonical_lower_to_canonical = {key.lower(): key for key in FIELDS}
    result: dict[str, str | None] = {key: None for key in FIELDS}

    if parsed is None:
        return result

    for parsed_key, parsed_value in parsed.items():
        canonical_key = canonical_lower_to_canonical.get(str(parsed_key).lower())
        if canonical_key is None:
            continue  # non-canonical key (e.g., "seller" instead of "seller_name") -- ignored
        result[canonical_key] = _normalize_predicted_value(parsed_value)

    return result


def to_predicted_dict_multipage(
    per_page_texts: list[str],
    model_id: str,
) -> dict[str, str | None]:
    """Parse per-page VLM outputs independently and merge with first-non-None-wins.

    Per ADR-019 §"Wave 3.1 architecture" — the harness's
    ``_score_single_invoice`` already has ``per_page_results: list[ExtractionResult]``
    (one per page). The single-input ``to_predicted_dict`` was silently dropping
    valid model output when models emitted per-page-valid JSON concatenated with
    ``\\n`` (Gemma-4 unfenced) or with mixed fence styles (olmOCR Arm A). Rather
    than couple the adapter to the harness's separator format (and the strip-
    before-adapter ordering at line 408 of harness.py), this multipage API
    accepts the per-page list directly.

    Pipeline:

        1. For each page text: ``preprocess(page_text, model_id)`` →
           ``to_predicted_dict(preprocessed, model_id)`` (the existing single-
           input contract; backward-compat preserved).
        2. Merge the per-page dicts with **first-non-None-wins** semantics
           (page 1 dominates).

    Merge policy — first-non-None-wins (NOT first-non-empty-wins):

        - ``None`` (key absent in the page's JSON, OR present-but-``null``)
          counts as "not extracted" → later pages may fill the slot.
        - Empty string ``""`` (key present, value is the empty string) counts
          as a present value → later pages do NOT overwrite. Per ADR-012
          §"Tristate value semantics": empty-string ≠ None; the scorer's
          comparator handles the empty-vs-missing distinction.
        - Any non-None, non-empty value from page N "locks" that field
          against pages N+1, N+2, ...

    This policy defends against:

        - **Page-2 hallucinations** (e.g., olmOCR Arm B page 2 emits
          ``"seller_name": "Joghurt Banane"`` because page 2's line-item
          table content leaked into the canonical-key namespace; page 1's
          correct ``"Lieferant GmbH"`` is preserved).
        - **Decoder-loop placeholder echo** (e.g., Granite Arm A: 8+
          identical ``<BT-N>``-shape dicts; the first parse surfaces
          placeholder values; the threshold gate in
          ``src/horus/eval/probe_verdict.py`` (Wave 3.2) catches the F1=0
          schema-mimicry case at the verdict layer).

    Args:
        per_page_texts: list of raw per-page VLM outputs. Empty list yields
            an all-None result; single-element list generalizes the
            single-page case.
        model_id: cohort model identifier; UNUSED in this module (cohort-
            uniform; ``# noqa: ARG001`` suppresses the lint warning).

    Returns:
        dict keyed by all 16 canonical FIELDS keys, each mapped to
        ``str | None``. Same shape as ``to_predicted_dict``.
    """
    merged: dict[str, str | None] = {key: None for key in FIELDS}
    for page_text in per_page_texts:
        preprocessed = preprocess(page_text, model_id)
        page_dict = to_predicted_dict(preprocessed, model_id)
        for key, value in page_dict.items():
            if merged[key] is None and value is not None:
                merged[key] = value
    return merged


_JSON_PARSE_SENTINEL = object()


def recover_json_object(text: str) -> dict[str, Any] | None:
    """Public entry point for the permissive JSON-object recovery ladder.

    Shared with the structurer (``src/horus/eval/structurer.py``, ADR-038) so a
    structuring model's reasoning-then-strict-JSON output is recovered by the
    SAME ladder the JSON adapter uses — markdown fences, prose-around-JSON,
    concatenated dicts (decoder loops), and trailing commas all handled. See
    :func:`_try_parse_json` for the full ladder. Returns the first recovered
    top-level dict, or ``None`` if no JSON object could be recovered.
    """
    return _try_parse_json(text)


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Permissive JSON-to-dict ladder.

    Returns the first successfully parsed dict; None if all attempts fail.

    Recovery ladder (first match wins):

      1. Direct ``json.loads(text)`` — handles cleanly emitted JSON.
      2. Balanced-bracket scan ``_find_first_balanced_dict`` — handles
         concatenated-dicts shapes (Granite Arm A's 8+ identical placeholder
         dicts per page; per ADR-019 B3) AND prose-around-JSON
         (``Here is the JSON: {...}. Hope this helps!``).
      3. Greedy substring ``text[first_lbrace:last_rbrace+1]`` — fallback for
         unusual mismatched-bracket cases not handled by the balanced scan.
      4. Trailing-comma sanitization applied to the greedy substring —
         handles ``{"a": "b",}`` (Python / JS-style trailing comma).

    Top-level shape gate: if the WHOLE input parses as JSON but yields a non-dict
    (list / scalar / null), return None immediately — DO NOT fall through to
    substring extraction. This preserves the empirical signal "model failed
    top-level-object schema" rather than silently unwrapping the first dict
    found inside e.g. an array-of-pages structure ``[{...}, {...}]``.
    """
    parsed = _safe_json_loads(text, default=_JSON_PARSE_SENTINEL)
    if isinstance(parsed, dict):
        return parsed
    if parsed is not _JSON_PARSE_SENTINEL:
        # Whole input parsed but yielded a non-dict (list / scalar / null).
        # Per the top-level-shape gate, do NOT try substring recovery.
        return None

    # ADR-019 Wave 3.1 recovery step: balanced-bracket scan handles the
    # case where the text contains multiple concatenated JSON dicts (e.g.,
    # Granite Arm A's 8+ identical placeholder dicts per page joined with
    # `\n\n`). The greedy substring path below would grab ALL of them and
    # fail the parse; balanced-bracket finds the FIRST complete `{...}` span.
    first_balanced = _find_first_balanced_dict(text)
    if first_balanced is not None:
        parsed = _safe_json_loads(first_balanced)
        if isinstance(parsed, dict):
            return parsed
        sanitized = _TRAILING_COMMA_RE.sub(r"\1", first_balanced)
        parsed = _safe_json_loads(sanitized)
        if isinstance(parsed, dict):
            return parsed

    first_lbrace = text.find("{")
    last_rbrace = text.rfind("}")
    if first_lbrace == -1 or last_rbrace <= first_lbrace:
        return None

    substring = text[first_lbrace : last_rbrace + 1]
    parsed = _safe_json_loads(substring)
    if isinstance(parsed, dict):
        return parsed

    sanitized = _TRAILING_COMMA_RE.sub(r"\1", substring)
    parsed = _safe_json_loads(sanitized)
    if isinstance(parsed, dict):
        return parsed

    return None


def _find_first_balanced_dict(text: str) -> str | None:
    """Find the first balanced ``{...}`` substring in text.

    Tracks brace depth from the first ``{`` and returns the span from that
    brace to the matching closing ``}`` (inclusive). Handles JSON string
    literals correctly: braces inside strings (e.g., ``"value with } in it"``)
    do NOT affect depth. Backslash-escapes inside strings are honored.

    Returns None if no balanced ``{...}`` is found OR if the input has an
    unclosed string / unbalanced braces.

    Used by ``_try_parse_json`` to extract the first valid JSON object from
    inputs containing multiple concatenated dicts (e.g., Granite Arm A's
    decoder-loop placeholder echo per ADR-019 B3) OR prose-wrapped JSON.

    Time complexity: O(n) single-pass scan.
    """
    first_lbrace = text.find("{")
    if first_lbrace == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(first_lbrace, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if in_string:
            if ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[first_lbrace : i + 1]
    return None


def _safe_json_loads(text: str, default: Any = None) -> Any:
    """``json.loads`` wrapper -- returns the parsed value, or ``default`` on JSONDecodeError.

    The ``default`` parameter exists so callers can distinguish "didn't parse at
    all" from "parsed cleanly but yielded a non-dict shape" (e.g. a literal
    ``null`` parses to Python ``None``; without a sentinel default the caller
    can't tell ``null`` apart from ``decode-error``). ``_try_parse_json`` uses
    the module-level ``_JSON_PARSE_SENTINEL`` for that distinction.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError, ValueError:
        return default


def _normalize_predicted_value(value: Any) -> str | None:
    """Map a parsed JSON value to the predicted_dict shape.

    Cases:

        None -> None
        str -> str (preserved as-is, including empty strings)
        bool -> ``str(value)`` ("True" / "False")
        int / float -> ``str(value)``
        list / dict / other -> None (model failed schema for this field)

    The bool branch is BEFORE the int branch because ``isinstance(True, int)``
    is True in Python (bool subclasses int); without explicit handling, ``True``
    would str-cast to ``"1"``.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return None
