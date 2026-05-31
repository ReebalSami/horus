"""Tests for `src/horus/eval/transcripts.py` — shared saved-transcript loader (ADR-030).

The three helpers (`parse_transcript`, `split_per_page_texts`, `build_gt_cache`)
were lifted out of `scripts/rescore.py` so `scripts/reading_ceiling.py` and
`scripts/rescore.py` share ONE transcript parser. `test_rescore.py` continues to
exercise them via the `rescore._parse_transcript` etc. aliases; these tests pin
the canonical module directly.
"""

from __future__ import annotations

from pathlib import Path

from horus.eval import transcripts
from tests._corpus import ZUGFERD_CORPUS_DIR, skip_if_no_corpus

# ---------------------------------------------------------------------------
# parse_transcript
# ---------------------------------------------------------------------------


def test_parse_transcript_extracts_model_invoice_body(tmp_path: Path) -> None:
    """`parse_transcript` reads the Model: + Invoice: header lines + body."""
    tp = tmp_path / "m__inv.txt"
    tp.write_text(
        "# Multi-page transcript (ADR-014 PR(c))\n"
        "# Model:    google/gemma-4-E4B-it\n"
        "# Invoice:  EN16931_Einfach\n"
        "# Pages:    2\n"
        "\n"
        "===== PAGE 1 =====\n"
        "body line one\n",
        encoding="utf-8",
    )
    model_id, invoice_stem, body = transcripts.parse_transcript(tp)
    assert model_id == "google/gemma-4-E4B-it"
    assert invoice_stem == "EN16931_Einfach"
    assert "===== PAGE 1 =====" in body
    assert "body line one" in body


def test_parse_transcript_raises_on_malformed_header(tmp_path: Path) -> None:
    """Missing Model:/Invoice: header → ValueError."""
    tp = tmp_path / "broken.txt"
    tp.write_text("no header\njust body\n", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="missing Model:/Invoice: header"):
        transcripts.parse_transcript(tp)


# ---------------------------------------------------------------------------
# split_per_page_texts
# ---------------------------------------------------------------------------


def test_split_per_page_texts_splits_on_page_separators() -> None:
    """Body with `===== PAGE N =====` separators → per-page list, empties dropped."""
    body = "===== PAGE 1 =====\npage one text\n===== PAGE 2 =====\npage two text\n"
    pages = transcripts.split_per_page_texts(body)
    assert pages == ["page one text", "page two text"]


def test_split_per_page_texts_single_page() -> None:
    """A single-page body (leading separator) yields one stripped chunk."""
    pages = transcripts.split_per_page_texts("===== PAGE 1 =====\nonly page\n")
    assert pages == ["only page"]


# ---------------------------------------------------------------------------
# build_gt_cache (integration — needs corpus PDFs)
# ---------------------------------------------------------------------------


@skip_if_no_corpus
def test_build_gt_cache_loads_known_invoices() -> None:
    """`build_gt_cache` extracts GT for the paired ZUGFeRD invoices via factur-x."""
    cache = transcripts.build_gt_cache(ZUGFERD_CORPUS_DIR)
    assert cache, "GT cache should be non-empty when the corpus is present"
    assert "EN16931_Einfach" in cache, "the canonical smoke invoice must be present"
    gt = cache["EN16931_Einfach"]
    # All 16 canonical fields are present on the parsed GroundTruth header.
    assert len(gt.header) == 16
    assert gt.header["invoice_number"].is_present
