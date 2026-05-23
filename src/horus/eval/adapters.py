"""VLM output → predicted-dict adapter (PR(b) Layer 1 + Layer 2 per ADR-013).

Two-layer architecture:

  - **Layer 1** — per-model preprocessors. Small, model-specific cleanup
    functions that turn the model's raw output (which may carry DocTags,
    HF table-cell markup, repeat-loops, or chat-template artifacts) into
    a clean German-labeled plain-text representation. Each preprocessor
    is registered against the cohort model_ids it serves; the dispatcher
    `preprocess()` looks up the model_id and falls through to
    `_passthrough()` for unknown / already-clean outputs.

  - **Layer 2** — unified German-label extractor (`to_predicted_dict()`).
    Iterates the `FIELDS` registry and uses each `FieldSpec.german_label`
    as a label-anchored search key against the preprocessed text. Includes
    secondary heuristics for "Nr. X vom Y" patterns (invoice_number +
    issue_date from headings) + tertiary heuristics for standalone GLN
    (13-digit run) + quaternary heuristics for tax-ID patterns when label
    search fails.

The two layers are loosely coupled — Layer 2 works on ANY string output from
Layer 1, and Layer 1 preprocessors are independent of each other. This means
adding a new cohort model (PR(c) scope) is a 1-line registration in the
`_PREPROCESSORS` registry, not a deep change.

Empirical baseline (per `docs/sources/transcripts/*.txt`):

  - Granite-Docling: ~1/16 fields extractable (50× repeat-loop swallows body)
  - MinerU 2.5 Pro: ~10/16 fields (table-cell markup decodes cleanly)
  - olmOCR-2 / GLM-OCR / PaddleOCR-VL / gemma-4-it: ~5-7/16 fields
  - PaliGemma-2: ~4/16 (repeat-block hallucination)
  - 5 MONEY fields uniformly absent across the cohort (page-1 rasterization
    constraint per ADR-013; deferred to PR(c)).

Refs: ADR-013 (this PR), ADR-009 (cohort manifest), ADR-012 (parent: GT parser),
      `docs/sources/transcripts/` (empirical evidence base), `horus-config-discipline`
      (no constants in code — Layer 2 reads `FIELDS` registry from PR(a)).
"""

from __future__ import annotations

import re
import unicodedata

from horus.eval.ground_truth import FIELDS

__all__ = [
    "extract_transcript_body",
    "preprocess",
    "to_predicted_dict",
    "to_predicted_dict_multipage",
]


# ===========================================================================
# 0. Cohort transcript helper — strip the smoke-runner wrapper
# ===========================================================================
#
# `docs/sources/transcripts/<model-slug>.txt` files come from
# `scripts/cohort_smoke.py` and wrap the raw VLM output in a banner with
# model metadata. The actual model output lives between
# `"Output snippet (first NNNN chars):"` and the next `------------------------`
# separator. Integration tests + PR(c)'s harness use this helper to isolate
# the model output from the wrapper.


_TRANSCRIPT_BODY_RE = re.compile(
    r"Output snippet \(first \d+ chars\):\s*\n(.*?)\n-{20,}",
    re.DOTALL,
)


def extract_transcript_body(transcript_text: str) -> str:
    """Extract the raw VLM output from a `cohort_smoke.py`-style transcript file.

    Locates the substring between ``"Output snippet (first NNNN chars):"`` and
    the next ``------------------------`` separator. Both delimiters are
    emitted verbatim by ``scripts/cohort_smoke.py`` — the regex is anchored
    to those constants.

    Args:
        transcript_text: contents of a file under
            ``docs/sources/transcripts/<model-slug>.txt``.

    Returns:
        The raw VLM output substring (trimmed of leading/trailing whitespace).
        Empty string if no Output snippet section is found (e.g., on
        error-status transcripts where the model never produced output).
    """
    match = _TRANSCRIPT_BODY_RE.search(transcript_text)
    if match is None:
        return ""
    return match.group(1).strip()


# ===========================================================================
# 1. Layer 1 — per-model preprocessors
# ===========================================================================
#
# Each preprocessor takes a raw string and returns a clean German-labeled
# plain-text representation suitable for Layer 2's label-anchored extraction.
# Preprocessors are pure (no I/O, no global state, deterministic).


# DocTags markup tokens (Granite-Docling, SmolDocling).
# - <doctag>, <text>, <page_header>, <otsl>, <list_item>, <caption>, <picture>,
#   <table>, <code>, <chart>, <formula>, <section_header>, etc. + their </closing> variants
# - <loc_NNN> bounding-box coordinate tokens (NNN = integer 0-499 typically)
_DOCTAGS_TOKEN_RE = re.compile(
    r"</?(?:doctag|text|page_header|page_footer|otsl|list_item|caption|"
    r"picture|table|code|chart|formula|section_header|footnote|paragraph|"
    r"title|smiles|inline)>"
    r"|<loc_\d+>",
)


# Chat-template end-of-turn artifacts from any model.
_CHAT_ARTIFACT_RE = re.compile(
    r"<\|im_end\|>|<\|im_start\|>|<\|endoftext\|>|<\|end\|>|<eos>|<bos>|"
    r"<\|user\|>|<\|assistant\|>|<\|system\|>",
)


# MinerU table-cell markup. The OTSL-inspired tags:
#   <fcel>  = full cell content boundary
#   <lcel>  = left/empty cell continuation
#   <ecel>  = explicitly empty cell
#   <nl>    = newline (end of row)
_MINERU_CELL_RE = re.compile(r"<(fcel|lcel|ecel|nl|ched|rhed|srow)>")


def _strip_doctags(raw: str) -> str:
    """Strip Granite-Docling DocTags markup + collapse runs of identical lines.

    DocTags emit a stream like
    ``<doctag><text><loc_47><loc_8><loc_174><loc_14>Content</text>...``
    where structural tokens (``<text>``, ``<page_header>``) and bbox coordinate
    tokens (``<loc_NNN>``) bracket the actual content. We strip the markup
    and rely on Layer 2's label-anchored regex to recover label-value pairs
    from the resulting text stream.

    Granite-Docling's degenerate failure mode (50× "Bemerkungen" repeat in the
    real cohort transcript) is handled by `_collapse_line_runs`: any line
    repeated ≥3 times consecutively collapses to a single occurrence.

    Args:
        raw: model output containing DocTags markup.

    Returns:
        Clean plain-text with markup stripped + redundant repeats collapsed.
    """
    # Drop all DocTags structural + bbox tokens
    cleaned = _DOCTAGS_TOKEN_RE.sub("", raw)
    # Collapse multi-line repeats from the degenerate-loop failure mode
    cleaned = _collapse_line_runs(cleaned)
    return cleaned


def _extract_mineru_cells(raw: str) -> str:
    """Decode MinerU's HF-OTSL table-cell markup into label-value plain text.

    MinerU 2.5 Pro emits invoice content as a sequence of table cells:

      ``<fcel>Steuernummer:<fcel>201/113/40209<nl>``

    Two adjacent ``<fcel>`` content groups separated by no closing tag form
    a label-value pair on the same row; ``<nl>`` ends the row; ``<ecel>``
    marks an empty cell that should be skipped (not emit a ":" with no value).

    The decoder:
      1. Splits on `<nl>` to get rows.
      2. Splits each row on `<fcel>` / `<lcel>` / `<ecel>` to get cells.
      3. Joins cells with ": " when there are exactly 2 non-empty cells (the
         label-value pattern); otherwise joins with " " (free-form row).
      4. Returns rows separated by newlines.

    Empty cells (``<ecel>``) are filtered out before the join.

    Args:
        raw: model output containing MinerU table-cell markup.

    Returns:
        Plain-text reformatting where each row is one line, label-value
        pairs are formatted as ``"label: value"``.
    """
    # First pass: split on <nl> to get rows
    rows = raw.split("<nl>")
    out_lines: list[str] = []
    for row in rows:
        # Split each row on cell-boundary tags
        cells = re.split(r"<(?:fcel|lcel|ecel|ched|rhed|srow)>", row)
        # Filter out empty/whitespace cells (these are real empty cells,
        # not the data we want)
        non_empty = [c.strip() for c in cells if c.strip()]
        if not non_empty:
            continue
        if len(non_empty) == 2:
            # Label + value pattern. Strip trailing colon from the label cell
            # to avoid producing "Label:: value" when the model emits the
            # colon inside the cell (MinerU does this on tax-ID rows).
            label = non_empty[0].rstrip(":").strip()
            value = non_empty[1]
            out_lines.append(f"{label}: {value}")
        else:
            # 1 cell or >2 cells — join with single space
            out_lines.append(" ".join(non_empty))
    return "\n".join(out_lines)


def _dedupe_repeats(raw: str) -> str:
    """Collapse blocks of ≥3 lines repeated ≥3 times to first occurrence.

    Handles PaliGemma-2's degenerate hallucination pattern where the model
    emits the same ~10-line block 3-4 times in a row (visible in
    `docs/sources/transcripts/paligemma2-3b-mix-448.txt`). A sliding-window
    detector finds the block period; if a block of length k ≥ 3 repeats ≥ 3
    times consecutively, we keep only the first occurrence.

    Algorithm:
      1. Split into lines.
      2. For block_size ∈ [3, 15]:
         - Walk forward; at position i check if lines[i:i+k] == lines[i+k:i+2k]
           == lines[i+2k:i+3k]. If yes, drop the duplicated copies (preserve i:i+k).
      3. Re-join lines.

    Args:
        raw: model output potentially containing repeat-block hallucination.

    Returns:
        Plain text with the repeat blocks collapsed.
    """
    lines = raw.split("\n")
    if len(lines) < 9:  # Need ≥ 9 lines for a 3-line block × 3 repeats
        return raw

    # Try increasing block sizes; once we collapse, we don't recurse — one
    # pass per file is sufficient for the empirical pattern.
    for block_size in range(3, 16):
        i = 0
        result: list[str] = []
        while i < len(lines):
            # Need 3 consecutive blocks of block_size to trigger collapse
            if i + 3 * block_size <= len(lines):
                block_a = lines[i : i + block_size]
                block_b = lines[i + block_size : i + 2 * block_size]
                block_c = lines[i + 2 * block_size : i + 3 * block_size]
                if block_a == block_b == block_c:
                    # Found a repeat — keep one copy, skip past all repeats
                    result.extend(block_a)
                    j = i + 3 * block_size
                    # Continue skipping further identical copies
                    while j + block_size <= len(lines) and lines[j : j + block_size] == block_a:
                        j += block_size
                    i = j
                    continue
            result.append(lines[i])
            i += 1
        if len(result) < len(lines):
            # We made progress — return after a single block-size pass
            return "\n".join(result)
        # No collapse at this block_size — try next
        lines = result

    return "\n".join(lines)


def _collapse_line_runs(raw: str) -> str:
    """Collapse runs of ≥3 identical consecutive lines to a single line.

    Handles the Granite-Docling "Bemerkungen × 50" degenerate-loop pattern
    (per `docs/sources/transcripts/granite-docling-258m.txt`). A simpler
    variant of `_dedupe_repeats` for single-line repeats (block_size=1).
    """
    lines = raw.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        # Count run-length of identical consecutive lines starting at i
        run_end = i + 1
        while run_end < len(lines) and lines[run_end] == lines[i]:
            run_end += 1
        if run_end - i >= 3:
            # Run of ≥3 identical lines — keep first, skip the rest
            i = run_end
        else:
            i += 1
    return "\n".join(out)


def _strip_chat_artifacts(raw: str) -> str:
    """Drop chat-template end-of-turn markers from any model output.

    Targets the literal substrings emitted by chat-tuned models when they
    don't strip their own end-of-turn tokens. Examples from cohort
    transcripts: MinerU's im_end token, PaliGemma's eos token, and the
    standard endoftext / end / user / assistant / system role markers.
    The full set is enumerated in ``_CHAT_ARTIFACT_RE`` above.
    """
    return _CHAT_ARTIFACT_RE.sub("", raw)


def _passthrough(raw: str) -> str:
    """Default preprocessor: NFC + chat-artifact strip + multi-blank-line collapse.

    Used for models whose outputs are already plain text or markdown without
    structural markup — olmOCR-2, GLM-OCR, PaddleOCR-VL, gemma-4-it. These
    only need light cleanup (Unicode normalization + chat-template artifact
    removal + blank-line collapse for readability).

    Args:
        raw: model output that's already in plain-text / markdown form.

    Returns:
        NFC-normalized + chat-artifact-stripped text with multiple consecutive
        blank lines collapsed to single blank lines.
    """
    cleaned = unicodedata.normalize("NFC", raw)
    cleaned = _strip_chat_artifacts(cleaned)
    # Collapse 3+ consecutive blank lines to 2 (preserve paragraph breaks)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Layer 1 dispatcher
# ---------------------------------------------------------------------------
#
# Per-model preprocessing strategies. Model IDs come from
# `scripts/cohort_smoke.py`'s COHORT_MANIFEST (ADR-009) — keep keys in sync
# when PR(c) extends the cohort.


_PREPROCESSORS: dict[str, list[str]] = {
    # Strategy → list of model_id substrings that route to this strategy.
    # Matching is by substring (case-sensitive); the dispatcher takes the
    # first strategy whose substring set hits.
    "doctags": [
        "granite-docling",
        "smoldocling",
    ],
    "mineru_cells": [
        "MinerU",
        "mineru",
    ],
    "dedupe_repeats": [
        "paligemma",
        "PaliGemma",
    ],
}


def preprocess(raw: str, model_id: str) -> str:
    """Apply Layer 1 preprocessing for a given cohort model.

    Dispatches based on substring match against ``model_id``:

      - ``doctags`` strategy → `_strip_doctags` + `_passthrough` cleanup
      - ``mineru_cells`` strategy → `_extract_mineru_cells` + cleanup
      - ``dedupe_repeats`` strategy → `_dedupe_repeats` + cleanup
      - any other model_id → `_passthrough` only

    All strategies finish by running `_passthrough` so the output is always
    NFC-normalized + chat-artifact-stripped regardless of route.

    Args:
        raw: the raw VLM output (post-transcript-body-extraction).
        model_id: cohort model identifier from `scripts/cohort_smoke.py`'s
            COHORT_MANIFEST (e.g., ``"ibm-granite/granite-docling-258M-mlx"``).

    Returns:
        Preprocessed plain-text representation ready for Layer 2 label
        extraction.
    """
    for strategy, patterns in _PREPROCESSORS.items():
        if any(p in model_id for p in patterns):
            if strategy == "doctags":
                return _passthrough(_strip_doctags(raw))
            if strategy == "mineru_cells":
                return _passthrough(_extract_mineru_cells(raw))
            if strategy == "dedupe_repeats":
                return _passthrough(_dedupe_repeats(raw))
    # No strategy matched — passthrough only
    return _passthrough(raw)


# ===========================================================================
# 2. Layer 2 — unified German-label extractor (`to_predicted_dict`)
# ===========================================================================
#
# Iterates the FIELDS registry; for each english_key, applies a primary
# label-anchored regex against the preprocessed text. Falls through to
# secondary / tertiary / quaternary heuristics for fields embedded in
# headings or bare numeric patterns.


# Absence markers — when a model signals "field is missing" rather than
# extracting a value. Detected as a substring match on the value side of a
# label-value pair; if matched, the predicted value collapses to None.
_ABSENCE_MARKERS = (
    "[Name fehlt]",
    "[ID fehlt]",
    "[Adresse fehlt]",
    "[unable to determine]",
    "[unknown]",
    "[fehlt]",
    "[missing]",
    "[N/A]",
    "N/A",
    "Sorry, as a base VLM",
)


def _is_absence_marker(value: str) -> bool:
    """True if `value` is one of the recognized 'field is missing' indicators."""
    v = value.strip()
    if not v:
        return True
    return any(marker.lower() in v.lower() for marker in _ABSENCE_MARKERS)


def _clean_predicted_value(value: str) -> str | None:
    """Trim + drop empty/punctuation-only + recognize absence markers.

    Strips:
      - Outer whitespace.
      - Leading/trailing markdown emphasis characters (asterisks, backticks,
        underscores) on each side independently — handles asymmetric
        leftovers like ``"** 471102"`` (gemma-4-it markdown bleed).
      - Leading punctuation (``/``, ``:``, ``-``) that's a remnant of
        section-header subtitle text (e.g., ``"/Leistungsempfänger"`` after
        matching the ``Käufer`` label against ``"Käufer/Leistungsempfänger"``).
      - Trailing punctuation (``.,;:``).

    Returns ``None`` if:
      - The cleaned value is empty.
      - The cleaned value contains no alphanumeric characters (e.g., bare
        ``":"`` from a label-only line that the regex over-matched).
      - The cleaned value matches an absence marker (``[Name fehlt]`` etc.).
    """
    v = value.strip()
    # Strip markdown emphasis on each side independently
    v = v.lstrip("*`_").lstrip()
    v = v.rstrip("*`_").rstrip()
    # Strip leading section-header punctuation (/, :, -) that remains when
    # the label regex over-matches a section title like
    # "Käufer/Leistungsempfänger" (captures "/Leistungsempfänger").
    v = v.lstrip("/-:").strip()
    # Strip trailing punctuation
    v = v.rstrip(".,;:")
    if not v or _is_absence_marker(v):
        return None
    # Require at least one alphanumeric character (rejects bare ":" leftover)
    if not any(c.isalnum() for c in v):
        return None
    return v


def _build_label_regex(german_label: str) -> re.Pattern[str]:
    r"""Build a line-anchored label-value regex from a `german_label` string.

    The pattern matches lines like:
      ``Steuernummer: 201/113/40209``
      ``Steuernummer 201/113/40209``  (no colon)
      ``**Steuernummer:** 201/113/40209``  (markdown-bold label — colon INSIDE bold)
      ``**Steuernummer**: 201/113/40209``  (colon OUTSIDE bold)
      ``* **Steuernummer:** 201/113/40209``  (markdown list item)

    Robustness:
      - Label match is case-insensitive (some models lowercase headings).
      - Optional leading markdown bullet/whitespace.
      - Permissive separator class around the label: any combination of
        horizontal whitespace + colon + emphasis chars (``*`` / `` ` `` / ``_``).
      - **Horizontal whitespace only** (``[ \t]``) in separators — ``\s``
        would include newline and bleed the value into the next line.
      - Tolerant of German diacritics in the label (re.escape preserves them).
    """
    # Escape the label for regex (handles parentheses, periods, etc. in
    # labels like "USt-IdNr. (Verkäufer)")
    label_escaped = re.escape(german_label)
    # Pattern uses [ \t] (horizontal whitespace) instead of \s to avoid
    # crossing newlines. The separator class around the label admits any
    # mix of colon + markdown emphasis + horizontal whitespace.
    pattern = (
        r"^[ \t\-\*\u2022]*"  # optional leading bullet/horizontal whitespace
        r"[*`_]*"  # optional opening markdown emphasis
        + label_escaped
        + r"[ \t:*`_]*"  # permissive separator: ws + colon + emphasis
        + r"(.+?)"  # captured value (lazy)
        + r"[ \t]*$"  # trailing horizontal whitespace only (not newline)
    )
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


# Pre-compile per-field label regexes at module load (small + immutable; no
# need to rebuild per to_predicted_dict call).
_LABEL_REGEX_BY_KEY: dict[str, re.Pattern[str]] = {
    key: _build_label_regex(spec.german_label) for key, spec in FIELDS.items()
}


# Secondary heuristic — "Nr. X vom Y" pattern that embeds invoice_number +
# issue_date in a single line (Granite-Docling, MinerU, PaddleOCR-VL emit this).
# Examples from real transcripts:
#   "Handelsrechnung (380) Nr. 471102 vom 05.03.2018"
#   "Handelsrechnung (380) Nr. 471102 vom 05.08.2018"   (model misread "3" as "8")
_NR_VOM_RE = re.compile(
    r"Nr\.?\s+(?P<number>\S+)\s+vom\s+(?P<date>\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4})",
    re.IGNORECASE,
)


# Tertiary heuristic — standalone 13-digit GLN run, optionally trailed by "(GLN)".
# EAN/GS1 Global Location Numbers are exactly 13 digits.
_GLN_RE = re.compile(r"\b(\d{13})\b(?:\s*\(GLN\))?")


# Quaternary heuristics — tax-ID patterns when label search fails.
# German Steuernummer: "201/113/40209" or "201/123/45678" (three groups separated by /).
_STEUERNUMMER_RE = re.compile(r"\b(\d{2,3}/\d{2,4}/\d{4,5})\b")
# German USt-IdNr: "DE123456789" (DE + 9 digits, possibly with whitespace).
_VAT_DE_RE = re.compile(r"\b(DE\s*\d{9})\b")

# Section-scoped Name: extractor. Invoice layouts use "Verkäufer" / "Käufer"
# as section HEADERS (often with subtitles like "Käufer/Leistungsempfänger");
# the actual party NAME is on a separate "Name: X" line within the section.
# EN16931 BT-27 (seller_name) and BT-44 (buyer_name) map onto the "Name:"
# sub-label in this layout, not the section header itself. This heuristic
# OVERRIDES the primary label-anchored regex for these two fields.
_VERKAUFER_HEADER_RE = re.compile(
    r"^[ \t\-\*\u2022]*[*`_]*Verkäufer\b", re.IGNORECASE | re.MULTILINE
)
_KAUFER_HEADER_RE = re.compile(r"^[ \t\-\*\u2022]*[*`_]*Käufer\b", re.IGNORECASE | re.MULTILINE)

# Field keys whose German label is a SECTION HEADER (not a value-bearing label).
# These fields are extracted via the section-scoped `_extract_section_name`
# heuristic, NOT the primary label-anchored regex.
_SECTION_HEADER_KEYS: frozenset[str] = frozenset({"seller_name", "buyer_name"})
# "Name:" line — but NOT "Globale Nummer" / "Name fehlt" / similar. Anchored
# to the start of the line + horizontal-whitespace separator (no newline).
_NAME_LINE_RE = re.compile(
    r"^[ \t\-\*\u2022]*[*`_]*Name[*`_]*[ \t:*`_]+(.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_section_name(text: str, section_start: int, section_end: int) -> str | None:
    """Find the first ``Name: X`` line in ``text[section_start:section_end]``.

    Returns the cleaned value of ``X`` or ``None`` if no such line is found
    (or all candidates are absence-markers / punctuation-only).
    """
    if section_start < 0 or section_start >= section_end:
        return None
    region = text[section_start:section_end]
    for match in _NAME_LINE_RE.finditer(region):
        cleaned = _clean_predicted_value(match.group(1))
        if cleaned is not None:
            return cleaned
    return None


def to_predicted_dict(raw_text: str, model_id: str) -> dict[str, str | None]:
    """Convert raw VLM output into the 16-field predicted dict.

    This is the public surface of Layer 2 — the unified German-label
    extractor. Pipeline:

      1. Run Layer 1 ``preprocess(raw_text, model_id)``.
      2. For each ``english_key`` in ``FIELDS``:

         a. **Primary** — search for ``<german_label>:? <value>`` lines using
            the pre-compiled label-anchored regex.
         b. **Secondary** — for ``invoice_number`` and ``issue_date``, fall
            back to the ``"Nr. X vom Y"`` heading pattern when the primary
            label match fails.
         c. **Tertiary** — for ``seller_gln``, fall back to a standalone
            13-digit GLN run.
         d. **Quaternary** — for ``seller_tax_id`` / ``seller_vat_id`` /
            ``buyer_vat_id``, fall back to pattern matches for German
            Steuernummer (``XXX/XXX/XXXXX``) or VAT-IDs (``DE...``).

      3. Detect absence markers (``[Name fehlt]`` etc.) — these collapse
         the predicted value to ``None`` regardless of which heuristic
         extracted them.
      4. Return a dict with all 16 ``english_keys`` present; values are
         strings (when extracted) or ``None`` (when not extracted /
         absence-marked).

    Args:
        raw_text: model output (post-transcript-body extraction). Pass the
            string returned by ``extract_transcript_body()`` when working
            with ``docs/sources/transcripts/*.txt`` files; pass the raw
            ``vlm_extractor`` output directly otherwise.
        model_id: cohort model identifier (drives Layer 1 dispatch).

    Returns:
        ``dict[english_key, str | None]`` with all 16 keys from
        ``horus.eval.ground_truth.FIELDS``.

    Example:
        >>> from horus.eval.adapters import to_predicted_dict
        >>> raw = "Rechnungsnummer: 471102\\nWährung: EUR"
        >>> pred = to_predicted_dict(raw, "test/model")
        >>> pred["invoice_number"]
        '471102'
        >>> pred["invoice_currency_code"]
        'EUR'
        >>> pred["buyer_name"] is None
        True
    """
    preprocessed = preprocess(raw_text, model_id)
    predicted: dict[str, str | None] = {key: None for key in FIELDS}

    # ---- Primary heuristic: per-field label-anchored regex ----
    # Skipped for seller_name + buyer_name: their German labels ("Verkäufer" /
    # "Käufer") are SECTION HEADERS in real invoice layouts, not field labels.
    # The section-scoped Name: extractor below handles them.
    for english_key, regex in _LABEL_REGEX_BY_KEY.items():
        if english_key in _SECTION_HEADER_KEYS:
            continue
        match = regex.search(preprocessed)
        if match is not None:
            cleaned = _clean_predicted_value(match.group(1))
            if cleaned is not None:
                predicted[english_key] = cleaned

    # ---- Section-scoped heuristic: seller_name + buyer_name from "Name:" lines ----
    # Find "Verkäufer" and "Käufer" section header positions; extract the first
    # "Name: X" line within each section.
    verkaufer_match = _VERKAUFER_HEADER_RE.search(preprocessed)
    kaufer_match = _KAUFER_HEADER_RE.search(preprocessed)
    verkaufer_pos = verkaufer_match.start() if verkaufer_match else -1
    kaufer_pos = kaufer_match.start() if kaufer_match else -1

    if verkaufer_pos >= 0:
        # Seller section: from Verkäufer header to Käufer header (or EOF)
        end = kaufer_pos if kaufer_pos > verkaufer_pos else len(preprocessed)
        predicted["seller_name"] = _extract_section_name(preprocessed, verkaufer_pos, end)

    if kaufer_pos >= 0:
        # Buyer section: from Käufer header to EOF
        predicted["buyer_name"] = _extract_section_name(preprocessed, kaufer_pos, len(preprocessed))

    # ---- Secondary heuristic: "Nr. X vom Y" embeds invoice_number + issue_date ----
    if predicted["invoice_number"] is None or predicted["issue_date"] is None:
        nr_match = _NR_VOM_RE.search(preprocessed)
        if nr_match is not None:
            if predicted["invoice_number"] is None:
                predicted["invoice_number"] = nr_match.group("number")
            if predicted["issue_date"] is None:
                predicted["issue_date"] = nr_match.group("date")

    # ---- Tertiary heuristic: standalone 13-digit GLN run ----
    if predicted["seller_gln"] is None:
        gln_match = _GLN_RE.search(preprocessed)
        if gln_match is not None:
            predicted["seller_gln"] = gln_match.group(1)

    # ---- Quaternary heuristics: pattern-based tax IDs ----
    if predicted["seller_tax_id"] is None:
        stn_match = _STEUERNUMMER_RE.search(preprocessed)
        if stn_match is not None:
            predicted["seller_tax_id"] = stn_match.group(1)

    if predicted["seller_vat_id"] is None:
        vat_match = _VAT_DE_RE.search(preprocessed)
        if vat_match is not None:
            # Normalize "DE 123456789" → "DE123456789"
            predicted["seller_vat_id"] = re.sub(r"\s+", "", vat_match.group(1))

    # NOTE: buyer_vat_id deliberately NOT pattern-extracted — the
    # EN16931_Einfach corpus has no buyer VAT-ID and pattern-matching a
    # bare "DE..." against the seller_vat_id area would mis-attribute it.
    # Only the primary label-anchored regex extracts buyer_vat_id (because
    # the label "USt-IdNr. (Käufer)" is unambiguous).

    return predicted


def to_predicted_dict_multipage(
    per_page_texts: list[str],
    model_id: str,
) -> dict[str, str | None]:
    """Multipage public-surface parity mirror for ``adapters_json.to_predicted_dict_multipage``.

    Per ADR-019 §"Wave 3.1 architecture" — the harness dispatches to either
    ``adapters`` (regex) or ``adapters_json`` (JSON) based on
    ``cohort.adapter_mode``; both modules must expose
    ``to_predicted_dict_multipage(per_page_texts, model_id)`` so the harness
    can swap modules uniformly.

    For the regex adapter, multi-page robustness comes "for free" — the
    label-anchored German-label regex finds labels (``Rechnungsnummer:``,
    ``Zahlbetrag:``, etc.) regardless of which page they appear on. The
    pre-existing ``tests/test_scorer_integration_multipage.py`` empirically
    demonstrates this on the MinerU multi-page transcripts (Step 7 evidence,
    micro_F1 ≈ 0.75 on EN16931_Einfach via page-2 totals block lift).

    Implementation: join per-page texts with ``\\n\\n`` (preserves the
    inter-page blank line that the LEGACY harness path produced via
    ``_strip_page_separators(concatenated)``; that path stripped the
    ``===== PAGE N =====`` separator lines but left the surrounding newlines
    intact, yielding ``\\n<p1>\\n\\n<p2>`` shape). Joining with ``\\n\\n``
    here keeps the multipage rewire byte-equivalent to the legacy shape for
    the regex adapter, preserving the pinned ADR-014 Step 7 F1 baseline at
    ``tests/test_rescore.py::test_rescore_baseline_only_matches_legacy_ablation_at_tau_0_5``.

    The single-input ``to_predicted_dict`` (delegated to) calls ``preprocess``
    internally (line 611), so we don't double-preprocess here.

    Args:
        per_page_texts: list of raw per-page VLM outputs.
        model_id: cohort model identifier (used by Layer 1 ``preprocess``
            dispatch inside the delegated ``to_predicted_dict`` call).

    Returns:
        ``dict[english_key, str | None]`` with all 16 canonical FIELDS keys.
        Same shape as ``to_predicted_dict``.
    """
    joined = "\n\n".join(per_page_texts)
    return to_predicted_dict(joined, model_id)
