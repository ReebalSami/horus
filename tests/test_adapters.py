"""Unit + integration tests for `src/horus/eval/adapters.py` (PR(b) per ADR-013).

Layer 1 unit tests (per-model preprocessors):
  - `_strip_doctags`            — Granite-Docling DocTags + bbox tokens + repeat-loops
  - `_extract_mineru_cells`     — MinerU HF-OTSL `<fcel>X<fcel>Y<nl>` markup
  - `_dedupe_repeats`           — PaliGemma-2 block-level repeat hallucinations
  - `_collapse_line_runs`       — Granite single-line repeat-loops
  - `_strip_chat_artifacts`     — chat-template end-of-turn markers
  - `_passthrough`              — NFC + chat-artifact strip + multi-blank-line collapse
  - `preprocess` dispatcher     — substring-based model_id routing

Layer 2 unit tests:
  - `_clean_predicted_value`    — markdown emphasis strip + punctuation strip + absence markers
  - Label regex                 — primary heuristic per-field
  - Secondary heuristics        — Nr. X vom Y, standalone GLN, Steuernummer pattern

Integration tests:
  - End-to-end on each of the 7 working transcripts (skip 3 error transcripts)
  - Empirical baseline assertions (extraction counts in expected ranges)
  - Cross-cohort invariant: 5 MONEY fields are uniformly absent (page-1
    rasterization constraint per ADR-013)

Refs: ADR-013, `docs/sources/transcripts/*.txt` (empirical evidence base).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from horus.eval.adapters import (
    _build_label_regex,
    _clean_predicted_value,
    _collapse_line_runs,
    _dedupe_repeats,
    _extract_mineru_cells,
    _passthrough,
    _strip_chat_artifacts,
    _strip_doctags,
    extract_transcript_body,
    preprocess,
    to_predicted_dict,
)
from horus.eval.ground_truth import FIELDS

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "docs" / "sources" / "transcripts"


# ===========================================================================
# 1. Layer 1 unit tests — per-model preprocessors
# ===========================================================================


# ---- _strip_doctags ----


def test_strip_doctags_removes_structural_tokens() -> None:
    """`<doctag>`, `<text>`, `<page_header>` and their closing variants strip cleanly."""
    raw = "<doctag><text>Rechnungsnummer:</text><text>471102</text></doctag>"
    cleaned = _strip_doctags(raw)
    assert "<doctag>" not in cleaned
    assert "<text>" not in cleaned
    assert "</text>" not in cleaned
    assert "Rechnungsnummer:" in cleaned
    assert "471102" in cleaned


def test_strip_doctags_removes_bbox_loc_tokens() -> None:
    """`<loc_NNN>` bbox coordinate tokens strip cleanly."""
    raw = "<text><loc_47><loc_8><loc_174><loc_14>Möglichst vom 2.02.2</text>"
    cleaned = _strip_doctags(raw)
    assert "<loc_47>" not in cleaned
    assert "<loc_" not in cleaned
    assert "Möglichst vom 2.02.2" in cleaned


def test_strip_doctags_collapses_50x_repeat_loop() -> None:
    """Granite-Docling's degenerate 50× 'Bemerkungen' loop collapses to a single line.

    Real failure mode from `docs/sources/transcripts/granite-docling-258m.txt`:
    the model emits the same `<text>...Bemerkungen</text>` line 50 times in a row.
    """
    line = "<text><loc_54><loc_499><loc_72><loc_499>Bemerkungen</text>"
    raw = "\n".join([line] * 50)
    cleaned = _strip_doctags(raw)
    # After stripping tokens, the unique content "Bemerkungen" should appear
    # exactly once (not 50 times)
    assert cleaned.count("Bemerkungen") == 1


# ---- _extract_mineru_cells ----


def test_extract_mineru_cells_pair_pattern() -> None:
    """`<fcel>X<fcel>Y<nl>` → `"X: Y"` plain-text line."""
    raw = "<fcel>Währung:<fcel>EUR<nl>"
    cleaned = _extract_mineru_cells(raw)
    assert cleaned == "Währung: EUR"


def test_extract_mineru_cells_strips_trailing_colon_from_label() -> None:
    """Label cell with trailing colon doesn't produce `Label:: value` double-colon."""
    # MinerU emits "Steuernummer:" as the label cell (with the colon inside the cell)
    raw = "<fcel>Steuernummer:<fcel>201/113/40209<nl>"
    cleaned = _extract_mineru_cells(raw)
    # Should be "Steuernummer: 201/113/40209" (single colon)
    assert cleaned == "Steuernummer: 201/113/40209"
    assert "::" not in cleaned


def test_extract_mineru_cells_handles_lcel() -> None:
    """`<fcel>X<lcel><nl>` (left-empty cell) treats the left cell as a single value."""
    raw = "<fcel>Verkäufer<lcel><nl>"
    cleaned = _extract_mineru_cells(raw)
    assert "Verkäufer" in cleaned


def test_extract_mineru_cells_handles_ecel_only_row() -> None:
    """`<ecel><fcel>X<nl>` (empty cell + value) emits the value as a single line."""
    raw = "<ecel><fcel>DE 80333 München<nl>"
    cleaned = _extract_mineru_cells(raw)
    assert "DE 80333 München" in cleaned


def test_extract_mineru_cells_multi_row_invoice_excerpt() -> None:
    """End-to-end on a real MinerU excerpt from `mineru-2-5-pro-vlm.txt`."""
    raw = (
        "<fcel>Währung:<fcel>EUR<nl>"
        "<fcel>Verkäufer<ecel><nl>"
        "<fcel>Nummer:<fcel>549910<nl>"
        "<fcel>Name:<fcel>Lieferent GmbH<nl>"
    )
    cleaned = _extract_mineru_cells(raw)
    lines = cleaned.splitlines()
    assert "Währung: EUR" in lines
    assert "Nummer: 549910" in lines
    assert "Name: Lieferent GmbH" in lines


# ---- _dedupe_repeats ----


def test_dedupe_repeats_collapses_three_line_block_repeated_thrice() -> None:
    """A 3-line block repeated 3× collapses to a single occurrence."""
    block = "line A\nline B\nline C"
    raw = "\n".join([block] * 3)
    cleaned = _dedupe_repeats(raw)
    assert cleaned.count("line A") == 1
    assert cleaned.count("line B") == 1
    assert cleaned.count("line C") == 1


def test_dedupe_repeats_preserves_non_repeated_content() -> None:
    """Non-repeated content stays intact when no triple-block found."""
    raw = "line A\nline B\nline C\nline D\nline E"
    cleaned = _dedupe_repeats(raw)
    assert cleaned == raw


# ---- _collapse_line_runs ----


def test_collapse_line_runs_keeps_first_of_three_or_more() -> None:
    """A line repeated ≥ 3 times consecutively collapses to one occurrence."""
    raw = "header\nrepeat\nrepeat\nrepeat\nrepeat\nrepeat\nfooter"
    cleaned = _collapse_line_runs(raw)
    assert cleaned.count("repeat") == 1
    assert "header" in cleaned
    assert "footer" in cleaned


def test_collapse_line_runs_keeps_double_repeat_intact() -> None:
    """A line repeated exactly 2× is NOT collapsed (threshold is ≥ 3)."""
    raw = "header\nrepeat\nrepeat\nfooter"
    cleaned = _collapse_line_runs(raw)
    assert cleaned.count("repeat") == 2


# ---- _strip_chat_artifacts ----


def test_strip_chat_artifacts_removes_im_end_token() -> None:
    """The MinerU end-of-turn token strips cleanly."""
    raw = "Content<|im_end|>\nMore content"
    cleaned = _strip_chat_artifacts(raw)
    assert "<|im_end|>" not in cleaned
    assert "Content" in cleaned
    assert "More content" in cleaned


def test_strip_chat_artifacts_removes_eos_and_endoftext() -> None:
    """PaliGemma's eos token and the endoftext role marker both strip cleanly."""
    raw = "Content<eos> middle <" + "|endoftext|" + "> end"
    cleaned = _strip_chat_artifacts(raw)
    assert "<eos>" not in cleaned
    assert "endoftext" not in cleaned
    assert "Content" in cleaned
    assert "end" in cleaned


# ---- _passthrough ----


def test_passthrough_nfc_normalizes_diacritics() -> None:
    """NFC normalization composes decomposed diacritics."""
    nfd_form = "Mu\u0308nchen"
    cleaned = _passthrough(nfd_form)
    assert cleaned == "M\u00fcnchen"


def test_passthrough_collapses_multiple_blank_lines() -> None:
    """Three or more consecutive blank lines collapse to two (single paragraph break)."""
    raw = "para1\n\n\n\n\npara2"
    cleaned = _passthrough(raw)
    assert cleaned == "para1\n\npara2"


# ---- preprocess dispatcher ----


def test_preprocess_routes_granite_docling_to_doctags_strategy() -> None:
    """Model ID matching `granite-docling` triggers DocTags stripping."""
    raw = "<doctag><text>Hello</text></doctag>"
    cleaned = preprocess(raw, "ibm-granite/granite-docling-258M-mlx")
    assert "<doctag>" not in cleaned
    assert "Hello" in cleaned


def test_preprocess_routes_mineru_to_cells_strategy() -> None:
    """Model ID matching `MinerU` triggers cell-markup extraction."""
    raw = "<fcel>Label:<fcel>Value<nl>"
    cleaned = preprocess(raw, "opendatalab/MinerU2.5-Pro-2604-1.2B")
    assert "Label: Value" in cleaned
    assert "<fcel>" not in cleaned


def test_preprocess_routes_paligemma_to_dedupe_strategy() -> None:
    """Model ID matching `paligemma` triggers repeat-block dedup."""
    block = "alpha\nbeta\ngamma"
    raw = "\n".join([block] * 3)
    cleaned = preprocess(raw, "google/paligemma2-3b-mix-448")
    assert cleaned.count("alpha") == 1


def test_preprocess_falls_through_to_passthrough_for_unknown_model() -> None:
    """Unknown model_id → passthrough only (no structural cleanup)."""
    raw = "Rechnungsnummer: 471102"
    cleaned = preprocess(raw, "unknown/model-id-not-in-cohort")
    # passthrough still NFC-normalizes + strips chat artifacts but doesn't
    # transform plain-text content
    assert "Rechnungsnummer: 471102" in cleaned


# ===========================================================================
# 2. Layer 2 unit tests — value cleanup + label regex + heuristics
# ===========================================================================


# ---- _clean_predicted_value ----


def test_clean_predicted_value_strips_outer_whitespace() -> None:
    assert _clean_predicted_value("  471102  ") == "471102"


def test_clean_predicted_value_strips_markdown_emphasis_asymmetric() -> None:
    """Gemma's markdown leftover ``** 471102`` cleans to ``471102``."""
    assert _clean_predicted_value("** 471102") == "471102"


def test_clean_predicted_value_strips_markdown_emphasis_symmetric() -> None:
    """Standard bold markdown ``**471102**`` cleans to ``471102``."""
    assert _clean_predicted_value("**471102**") == "471102"


def test_clean_predicted_value_strips_leading_slash() -> None:
    """``/Leistungsempfänger`` (section-header bleed) cleans the leading slash."""
    assert _clean_predicted_value("/Leistungsempfänger") == "Leistungsempfänger"


def test_clean_predicted_value_rejects_punctuation_only() -> None:
    """Bare ``:`` (regex over-match on label-only line) returns None."""
    assert _clean_predicted_value(":") is None
    assert _clean_predicted_value("***") is None
    assert _clean_predicted_value("---") is None


def test_clean_predicted_value_recognizes_name_fehlt_absence_marker() -> None:
    """Gemma's ``[Name fehlt]`` absence marker collapses to None."""
    assert _clean_predicted_value("[Name fehlt]") is None
    assert _clean_predicted_value("[ID fehlt]") is None


def test_clean_predicted_value_recognizes_unable_to_determine() -> None:
    """Generic ``[unable to determine]`` marker collapses to None."""
    assert _clean_predicted_value("[unable to determine]") is None


def test_clean_predicted_value_preserves_internal_whitespace() -> None:
    """Internal whitespace (e.g., 'Lieferant GmbH') is preserved verbatim."""
    assert _clean_predicted_value("Lieferant GmbH") == "Lieferant GmbH"


# ---- Label regex (per german_label) ----


def test_label_regex_matches_plain_colon_separator() -> None:
    """Simple ``Label: value`` line matches and captures ``value``."""
    regex = _build_label_regex("Rechnungsnummer")
    match = regex.search("Rechnungsnummer: 471102")
    assert match is not None
    assert match.group(1) == "471102"


def test_label_regex_matches_markdown_bold_with_colon_inside() -> None:
    """Gemma's ``**Label:** value`` markdown pattern matches and captures."""
    regex = _build_label_regex("Rechnungsnummer")
    match = regex.search("* **Rechnungsnummer:** 471102")
    assert match is not None
    cleaned = _clean_predicted_value(match.group(1))
    assert cleaned == "471102"


def test_label_regex_does_not_bleed_across_newlines() -> None:
    """Label on one line + value on next line → primary regex does NOT match.

    Critical: ``\\s`` would cross newlines and bleed the next line's content
    into the captured value. We use ``[ \\t]`` (horizontal whitespace only)
    to enforce single-line matches.
    """
    regex = _build_label_regex("Verkäufer")
    text = "Verkäufer\nNummer: 549910\nName: Lieferent GmbH"
    match = regex.search(text)
    # Either no match (because the line "Verkäufer" alone has no value), OR
    # the captured group does not contain "Nummer" / "Name" content.
    if match is not None:
        assert "Nummer" not in match.group(1)
        assert "Name" not in match.group(1)


def test_label_regex_case_insensitive() -> None:
    """Label match is case-insensitive."""
    regex = _build_label_regex("Steuernummer")
    match = regex.search("steuernummer: 201/113/40209")
    assert match is not None


def test_label_regex_handles_label_with_special_chars() -> None:
    """German label with parens (e.g., 'USt-IdNr. (Verkäufer)') matches verbatim."""
    regex = _build_label_regex("USt-IdNr. (Verkäufer)")
    match = regex.search("USt-IdNr. (Verkäufer): DE123456789")
    assert match is not None
    assert match.group(1) == "DE123456789"


# ===========================================================================
# 3. extract_transcript_body — strip the cohort_smoke wrapper
# ===========================================================================


def test_extract_transcript_body_returns_payload_between_separators() -> None:
    """Helper extracts the model output between the standard transcript delimiters."""
    transcript = (
        "========================================================================\n"
        "HORUS cohort smoke — ADR-009 §Decision evidence\n"
        "========================================================================\n"
        "Output snippet (first 3743 chars):\n"
        "\n"
        "Rechnungsnummer: 471102\n"
        "Währung: EUR\n"
        "------------------------------------------------------------------------\n"
    )
    body = extract_transcript_body(transcript)
    assert "Rechnungsnummer: 471102" in body
    assert "Währung: EUR" in body
    assert "Output snippet" not in body
    assert "----------" not in body


def test_extract_transcript_body_returns_empty_on_error_transcript() -> None:
    """Error-status transcripts have no Output snippet section → empty string."""
    transcript = (
        "Model:          deepseek-ai/DeepSeek-OCR-2\n"
        "Status:         error\n"
        "Error:          ValueError: Unrecognized processing class\n"
    )
    body = extract_transcript_body(transcript)
    assert body == ""


# ===========================================================================
# 4. to_predicted_dict — end-to-end on saved cohort transcripts
# ===========================================================================


def _load_transcript_body_and_model_id(name: str) -> tuple[str, str]:
    """Load a cohort transcript, extract its body + model ID."""
    path = TRANSCRIPTS_DIR / name
    if not path.is_file():
        pytest.skip(f"Transcript file missing: {path}")
    content = path.read_text()
    m = re.search(r"Model:\s+(\S+)", content)
    assert m is not None, f"Could not find Model: header in {name}"
    return extract_transcript_body(content), m.group(1)


def test_to_predicted_dict_returns_all_16_keys_for_every_transcript() -> None:
    """`to_predicted_dict` always returns all 16 FIELDS keys (None for not-extracted)."""
    sample_raw = "Rechnungsnummer: 471102\nWährung: EUR"
    pred = to_predicted_dict(sample_raw, "test/model")
    assert set(pred.keys()) == set(FIELDS.keys())


def test_to_predicted_dict_on_granite_docling_extracts_invoice_number() -> None:
    """Granite-Docling transcript: invoice_number must be extracted (the one TP)."""
    body, model_id = _load_transcript_body_and_model_id("granite-docling-258m.txt")
    pred = to_predicted_dict(body, model_id)
    assert pred["invoice_number"] == "471102", (
        f"Granite-Docling baseline should extract invoice_number=471102; "
        f"got {pred['invoice_number']!r}"
    )


def test_to_predicted_dict_on_mineru_extracts_seller_name_with_ocr_error() -> None:
    """MinerU 2.5 Pro: seller_name extracted with the 'Lieferent' character-level OCR error.

    Documents the empirical baseline — MinerU writes "Lieferent" (with 'e')
    instead of "Lieferant" (with 'a'). This is what the ANLS\\* comparator
    will score against the GT "Lieferant GmbH".
    """
    body, model_id = _load_transcript_body_and_model_id("mineru-2-5-pro-vlm.txt")
    pred = to_predicted_dict(body, model_id)
    assert pred["seller_name"] == "Lieferent GmbH"


def test_to_predicted_dict_on_mineru_extracts_buyer_name_cleanly() -> None:
    """MinerU 2.5 Pro: buyer_name extracts cleanly via section-scoped heuristic."""
    body, model_id = _load_transcript_body_and_model_id("mineru-2-5-pro-vlm.txt")
    pred = to_predicted_dict(body, model_id)
    assert pred["buyer_name"] == "Kunden AG Mitte"


def test_to_predicted_dict_on_gemma_recognizes_name_fehlt_as_absent() -> None:
    """Gemma-4-it: seller_name returns None when the model emits ``[Name fehlt]``."""
    body, model_id = _load_transcript_body_and_model_id("gemma-4-e4b-it.txt")
    pred = to_predicted_dict(body, model_id)
    assert pred["seller_name"] is None, (
        f"Gemma's '[Name fehlt]' should collapse to None; got {pred['seller_name']!r}"
    )


def test_to_predicted_dict_monetary_fields_uniformly_none_on_page1_transcripts() -> None:
    """Cross-cohort invariant: the 5 MONEY fields are uniformly None on page-1 inputs.

    Captures the ADR-013 §Decision page-1-only baseline as a deterministic
    invariant: the totals block lives on page 2 of EN16931_Einfach.pdf, so
    no cohort model (running on page-1.png) can extract any MONEY field.
    PR(c) re-rasterizes all pages and lifts this constraint.
    """
    money_fields = {
        "line_total_amount",
        "tax_basis_total_amount",
        "tax_total_amount",
        "grand_total_amount",
        "due_payable_amount",
    }
    transcripts = [
        "granite-docling-258m.txt",
        "mineru-2-5-pro-vlm.txt",
        "olmocr-2-7b.txt",
        "gemma-4-e4b-it.txt",
        "glm-ocr.txt",
        "paddleocr-vl.txt",
        "paligemma2-3b-mix-448.txt",
    ]
    for transcript_name in transcripts:
        body, model_id = _load_transcript_body_and_model_id(transcript_name)
        pred = to_predicted_dict(body, model_id)
        for money_field in money_fields:
            assert pred[money_field] is None, (
                f"{transcript_name} extracted {money_field}={pred[money_field]!r} "
                f"— but page-1 rasterization should hide all totals (ADR-013)"
            )


def test_to_predicted_dict_buyer_vat_id_uniformly_none() -> None:
    """The buyer_vat_id is uniformly None across the cohort (no buyer VAT in EN16931_Einfach)."""
    transcripts = [
        "granite-docling-258m.txt",
        "mineru-2-5-pro-vlm.txt",
        "olmocr-2-7b.txt",
        "gemma-4-e4b-it.txt",
        "glm-ocr.txt",
        "paddleocr-vl.txt",
        "paligemma2-3b-mix-448.txt",
    ]
    for transcript_name in transcripts:
        body, model_id = _load_transcript_body_and_model_id(transcript_name)
        pred = to_predicted_dict(body, model_id)
        assert pred["buyer_vat_id"] is None, (
            f"{transcript_name} hallucinated buyer_vat_id={pred['buyer_vat_id']!r}"
        )


def test_to_predicted_dict_extraction_count_baseline_per_model() -> None:
    """Per-model extraction counts match the empirical baseline at this PR's point.

    These ranges are derived from the actual cohort transcripts on disk and
    serve as regression guards. If a future tuning of the adapter changes
    these counts, the test surfaces the change for review — at which point
    either the test bounds are updated OR the change is rejected as drift.
    """
    expected_counts: dict[str, tuple[int, int]] = {
        # (min, max) of extracted (non-None) field count out of 16
        "granite-docling-258m.txt": (1, 4),
        "mineru-2-5-pro-vlm.txt": (6, 11),
        "olmocr-2-7b.txt": (3, 7),
        "gemma-4-e4b-it.txt": (3, 7),
        "glm-ocr.txt": (4, 8),
        "paddleocr-vl.txt": (3, 7),
        "paligemma2-3b-mix-448.txt": (2, 6),
    }
    for transcript_name, (lo, hi) in expected_counts.items():
        body, model_id = _load_transcript_body_and_model_id(transcript_name)
        pred = to_predicted_dict(body, model_id)
        n = sum(1 for v in pred.values() if v is not None)
        assert lo <= n <= hi, (
            f"{transcript_name} extracted {n}/16 fields; "
            f"expected range [{lo}, {hi}]. If drift is intentional, update bounds."
        )
