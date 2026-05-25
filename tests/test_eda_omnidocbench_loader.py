"""Tests for `horus.eda.omnidocbench_loader` (ADR-025 Phase C, chapter 3).

Pure-function tests run unconditionally (no I/O); corpus-aware tests
gated behind `skip_if_no_omnidocbench_corpus`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from horus.eda.omnidocbench_loader import (
    category_counts,
    load_image_bytes,
    load_index,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OMNIDOCBENCH_CORPUS = REPO_ROOT / "data" / "raw" / "multilingual" / "omnidocbench"
OMNIDOCBENCH_JSON = OMNIDOCBENCH_CORPUS / "OmniDocBench.json"

_HAS_OMNIDOCBENCH = OMNIDOCBENCH_JSON.is_file()
skip_if_no_omnidocbench_corpus = pytest.mark.skipif(
    not _HAS_OMNIDOCBENCH,
    reason=(
        "Requires OmniDocBench.json at "
        "data/raw/multilingual/omnidocbench/OmniDocBench.json "
        "(gitignored per .gitignore). Skips on CI + dev clones without "
        "the corpus fetched. Per ADR-023."
    ),
)


def test_load_index_raises_on_missing_json(tmp_path: Path) -> None:
    """Missing OmniDocBench.json → FileNotFoundError with helpful message."""
    with pytest.raises(FileNotFoundError, match="OmniDocBench.json not found"):
        load_index(tmp_path)


def test_load_index_parses_synthetic_fixture(tmp_path: Path) -> None:
    """Synthetic 2-entry fixture exercises the column-hoisting logic."""
    fixture = [
        {
            "page_info": {
                "page_no": 0,
                "width": 1653,
                "height": 2339,
                "image_path": "page-aaa.png",
                "page_attribute": {
                    "data_source": "book",
                    "language": "english",
                    "layout": "single_column",
                    "subset": "v1.5",
                    "special_issue": ["watermark"],
                },
            },
            "layout_dets": [
                {"category_type": "text_block"},
                {"category_type": "title"},
                {"category_type": "text_block"},
            ],
            "extra": {"relation": []},
        },
        {
            "page_info": {
                "page_no": 0,
                "width": 1500,
                "height": 2000,
                "image_path": "page-bbb.png",
                "page_attribute": {
                    "data_source": "academic_literature",
                    "language": "simplified_chinese",
                    "layout": "double_column",
                    "subset": "v1.5",
                    "special_issue": [],
                },
            },
            "layout_dets": [{"category_type": "equation_isolated"}],
            "extra": {"relation": []},
        },
    ]
    (tmp_path / "OmniDocBench.json").write_text(json.dumps(fixture), encoding="utf-8")
    df = load_index(tmp_path)
    assert len(df) == 2
    assert df.iloc[0]["data_source"] == "book"
    assert df.iloc[0]["language"] == "english"
    assert df.iloc[0]["layout"] == "single_column"
    assert df.iloc[0]["special_issues"] == ("watermark",)
    assert df.iloc[0]["n_layout_dets"] == 3
    assert df.iloc[0]["category_types"] == frozenset({"text_block", "title"})
    assert df.iloc[1]["language"] == "simplified_chinese"
    assert df.iloc[1]["n_layout_dets"] == 1


def test_category_counts_aggregates_pages_with_each_category() -> None:
    """`category_counts` counts pages-where-category-appears, not boxes."""
    df = pd.DataFrame(
        {
            "category_types": [
                frozenset({"text_block", "title"}),
                frozenset({"text_block", "table"}),
                frozenset({"text_block", "title", "table"}),
            ]
        }
    )
    counts = category_counts(df)
    assert counts.loc["text_block", "n_pages"] == 3
    assert counts.loc["title", "n_pages"] == 2
    assert counts.loc["table", "n_pages"] == 2


def test_load_image_bytes_returns_none_for_missing(tmp_path: Path) -> None:
    """Non-existent image → None (no raise)."""
    (tmp_path / "images").mkdir()
    assert load_image_bytes(tmp_path, "does-not-exist.png") is None


def test_load_image_bytes_returns_bytes_when_present(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    payload = b"\x89PNG\r\n\x1a\nfake-png-content"
    (tmp_path / "images" / "fake.png").write_bytes(payload)
    assert load_image_bytes(tmp_path, "fake.png") == payload


# ---------------------------------------------------------------------------
# Corpus-aware tests
# ---------------------------------------------------------------------------


@skip_if_no_omnidocbench_corpus
def test_load_index_real_corpus_row_count() -> None:
    """Per the on-disk audit (2026-05-25): 1651 entries in OmniDocBench.json."""
    df = load_index(OMNIDOCBENCH_CORPUS)
    assert len(df) == 1651


@skip_if_no_omnidocbench_corpus
def test_real_corpus_languages_are_chinese_and_english_mix() -> None:
    df = load_index(OMNIDOCBENCH_CORPUS)
    languages = set(df["language"].unique())
    # Per the empirical audit (2026-05-25): the 5 distinct values.
    expected = {
        "simplified_chinese",
        "english",
        "en_ch_mixed",
        "traditional_chinese",
        "other",
    }
    assert expected.issuperset(languages)
    # Chinese + English dominate.
    n_chinese = int(
        (df["language"] == "simplified_chinese").sum()
        + (df["language"] == "traditional_chinese").sum()
    )
    n_english = int((df["language"] == "english").sum())
    assert n_chinese > 700
    assert n_english > 700


@skip_if_no_omnidocbench_corpus
def test_real_corpus_has_no_invoice_data_source() -> None:
    """Empirical finding (ADR-025 Phase C step 2): OmniDocBench has zero
    invoice-class entries. data_source ranges over book / PPT2PDF /
    academic_literature / exam_paper / etc. — but NOT invoices.
    """
    df = load_index(OMNIDOCBENCH_CORPUS)
    sources = set(df["data_source"].unique())
    invoice_sources = {s for s in sources if "invoice" in str(s).lower()}
    assert invoice_sources == set()


@skip_if_no_omnidocbench_corpus
def test_real_corpus_category_types_include_text_block() -> None:
    df = load_index(OMNIDOCBENCH_CORPUS)
    counts = category_counts(df)
    # `text_block` is the dominant category per the audit.
    assert "text_block" in counts.index
    assert counts.loc["text_block", "n_pages"] > 1000
