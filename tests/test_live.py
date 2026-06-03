"""Tests for the live extraction orchestration (`src/horus/eval/live.py`, ADR-039).

The two methods + the page-prep + the merge are exercised with a MOCKED extractor
(no model load, no Metal, no network) so they run in `make test` / CI. The real
model path is verified manually via `make app` (upload an invoice). What we assert
here: method dispatch + result shape + the no-scoring full-dict (incl.
`purpose_summary`) + multi-page first-non-None merge + the honest error surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus.eval import live
from horus.eval.live import (
    LiveResult,
    prepare_pages,
    run_read_then_structure,
    run_single_shot,
)
from horus.vlm_extractor import DEFAULT_MAX_TOKENS, ExtractionResult


class _FakeImageExtractor:
    """An ImageExtractor stand-in: returns canned text per `.extract()` call."""

    backend_name = "fake"

    def __init__(
        self,
        texts: list[str],
        *,
        model_id: str = "fake/reader",
        load_seconds: float = 1.5,
        extract_seconds: float = 2.0,
        error: str | None = None,
    ) -> None:
        self.model_id = model_id
        self._texts = texts
        self._load_seconds = load_seconds
        self._extract_seconds = extract_seconds
        self._error = error
        self.calls: list[tuple[Path, str, int]] = []

    def extract(
        self, image_path: Path, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> ExtractionResult:
        idx = len(self.calls)
        self.calls.append((image_path, prompt, max_tokens))
        text = self._texts[idx] if idx < len(self._texts) else ""
        return ExtractionResult(
            model_id=self.model_id,
            backend_name=self.backend_name,
            text="" if self._error else text,
            load_seconds=self._load_seconds,
            extract_seconds=self._extract_seconds,
            error=self._error,
        )


class _FakeTextExtractor:
    """A TextExtractor stand-in: returns canned text from `.extract_text()`."""

    backend_name = "fake"

    def __init__(
        self,
        text: str,
        *,
        model_id: str = "fake/structurer",
        load_seconds: float = 3.0,
        extract_seconds: float = 4.0,
        error: str | None = None,
    ) -> None:
        self.model_id = model_id
        self._text = text
        self._load_seconds = load_seconds
        self._extract_seconds = extract_seconds
        self._error = error
        self.calls: list[tuple[str, int]] = []

    def extract_text(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> ExtractionResult:
        self.calls.append((prompt, max_tokens))
        return ExtractionResult(
            model_id=self.model_id,
            backend_name=self.backend_name,
            text="" if self._error else self._text,
            load_seconds=self._load_seconds,
            extract_seconds=self._extract_seconds,
            error=self._error,
        )


# --- prepare_pages ---------------------------------------------------------


def test_prepare_pages_image_is_single_page_no_raster(tmp_path: Path) -> None:
    """An uploaded image is its own single page — no rasterization."""
    img = tmp_path / "scan.PNG"  # upper-case suffix must still match
    img.write_bytes(b"not-a-real-png")
    assert prepare_pages(img, cache_dir=tmp_path) == [img]


def test_prepare_pages_pdf_rasterizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A PDF is delegated to `rasterize_pdf` at the evaluation DPI."""
    seen: dict[str, object] = {}

    def _fake_rasterize(pdf_path: Path, *, dpi: int, cache_dir: Path, **_: object) -> list[Path]:
        seen["dpi"] = dpi
        return [cache_dir / "page-1.png", cache_dir / "page-2.png"]

    monkeypatch.setattr(live, "rasterize_pdf", _fake_rasterize)
    pages = prepare_pages(tmp_path / "invoice.pdf", cache_dir=tmp_path)
    assert len(pages) == 2
    assert seen["dpi"] == live.EVAL_DPI == 300


# --- Method A (single-shot) ------------------------------------------------


def test_run_single_shot_parses_fields_and_summary() -> None:
    """Single-shot returns the 20-key full dict incl. the non-scored purpose_summary."""
    extractor = _FakeImageExtractor(
        ['{"invoice_number": "R-001", "purpose_summary": "Office supplies"}']
    )
    result = run_single_shot(
        [Path("page-1.png")], extractor=extractor, prompt="EXTRACT", max_tokens=1234
    )
    assert isinstance(result, LiveResult)
    assert result.method == "arm_a"
    assert result.fields["invoice_number"] == "R-001"
    assert result.purpose_summary == "Office supplies"
    assert result.reader_transcript is None  # single-shot has no reader
    assert "purpose_summary" in result.fields  # full dict, not the scored 19-key dict
    # The caller's prompt + token budget are passed through to the model.
    assert extractor.calls[0][1] == "EXTRACT"
    assert extractor.calls[0][2] == 1234


def test_run_single_shot_merges_pages_first_non_none_wins() -> None:
    """Across pages, an earlier page's value is never overwritten by a later one."""
    extractor = _FakeImageExtractor(
        [
            '{"invoice_number": "R-001"}',  # page 1
            '{"invoice_number": "R-999", "seller_name": "ACME"}',  # page 2
        ]
    )
    result = run_single_shot([Path("p1.png"), Path("p2.png")], extractor=extractor, prompt="X")
    assert result.fields["invoice_number"] == "R-001"  # page 1 dominates
    assert result.fields["seller_name"] == "ACME"  # filled from page 2
    assert result.extract_seconds == pytest.approx(4.0)  # 2 pages × 2.0s each
    assert result.load_seconds == pytest.approx(1.5)


def test_run_single_shot_raises_on_extractor_error() -> None:
    """A backend failure surfaces as a RuntimeError carrying the model's message."""
    extractor = _FakeImageExtractor([""], error="MetalOOM: out of memory")
    with pytest.raises(RuntimeError, match="MetalOOM"):
        run_single_shot([Path("p.png")], extractor=extractor, prompt="X")


# --- Method B (read-then-structure) ----------------------------------------


def test_run_read_then_structure_pipes_reader_into_structurer() -> None:
    """Reader transcripts (joined) feed the structurer; fields come from the structurer."""
    reader = _FakeImageExtractor(["PAGE ONE TEXT", "PAGE TWO TEXT"])
    structurer = _FakeTextExtractor('{"invoice_number": "R-042", "purpose_summary": "Rent"}')
    result = run_read_then_structure(
        [Path("p1.png"), Path("p2.png")],
        reader=reader,
        structurer=structurer,
        reader_prompt="READ",
        structuring_prompt="STRUCTURE",
    )
    assert result.method == "arm_b"
    assert result.fields["invoice_number"] == "R-042"
    assert result.purpose_summary == "Rent"
    # The reader transcript (the middle artifact) is preserved, page-joined.
    assert result.reader_transcript == "PAGE ONE TEXT\n\nPAGE TWO TEXT"
    # The structurer's single text input embeds the instruction + both page texts.
    structuring_input = structurer.calls[0][0]
    assert "STRUCTURE" in structuring_input
    assert "PAGE ONE TEXT" in structuring_input
    assert "PAGE TWO TEXT" in structuring_input
    # Timings aggregate reader (2×2.0) + structurer (4.0); loads sum both models.
    assert result.extract_seconds == pytest.approx(2.0 + 2.0 + 4.0)
    assert result.load_seconds == pytest.approx(1.5 + 3.0)


def test_run_read_then_structure_raises_on_reader_error() -> None:
    """A reader failure surfaces before the structurer is ever called."""
    reader = _FakeImageExtractor([""], error="reader crashed")
    structurer = _FakeTextExtractor("{}")
    with pytest.raises(RuntimeError, match="reader crashed"):
        run_read_then_structure(
            [Path("p.png")],
            reader=reader,
            structurer=structurer,
            reader_prompt="READ",
            structuring_prompt="STRUCTURE",
        )
    assert structurer.calls == []  # never reached the structuring pass


def test_run_read_then_structure_raises_on_structurer_error() -> None:
    """A structurer failure surfaces as a RuntimeError carrying its message."""
    reader = _FakeImageExtractor(["some text"])
    structurer = _FakeTextExtractor("", error="structurer OOM")
    with pytest.raises(RuntimeError, match="structurer OOM"):
        run_read_then_structure(
            [Path("p.png")],
            reader=reader,
            structurer=structurer,
            reader_prompt="READ",
            structuring_prompt="STRUCTURE",
        )


def test_unparseable_output_is_all_null_never_raises() -> None:
    """Honest guardrail: junk model text yields all-null fields, not an invented value."""
    extractor = _FakeImageExtractor(["I could not read this invoice, sorry."])
    result = run_single_shot([Path("p.png")], extractor=extractor, prompt="X")
    assert all(value is None for value in result.fields.values())
