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


_JSON_PARSE_SENTINEL = object()


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Permissive JSON-to-dict ladder.

    Returns the first successfully parsed dict; None if all attempts fail.
    See module docstring §"Permissive JSON recovery" for the 5-step ladder.

    Top-level shape gate: if the WHOLE input parses as JSON but yields a non-dict
    (list / scalar / null), return None immediately -- DO NOT fall through to
    substring extraction. This preserves the empirical signal "model failed
    top-level-object schema" rather than silently unwrapping the first dict
    found inside e.g. an array-of-pages structure ``[{...}, {...}]``. The
    substring-extraction branch is reserved for the prose-around-JSON case
    (``Here is the JSON: {...}. Hope this helps!``) where the whole input
    isn't valid JSON at all.
    """
    parsed = _safe_json_loads(text, default=_JSON_PARSE_SENTINEL)
    if isinstance(parsed, dict):
        return parsed
    if parsed is not _JSON_PARSE_SENTINEL:
        # Whole input parsed but yielded a non-dict (list / scalar / null).
        # Per the top-level-shape gate, do NOT try substring recovery.
        return None

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
    except (json.JSONDecodeError, ValueError):
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
