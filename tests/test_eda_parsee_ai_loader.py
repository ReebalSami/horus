"""Tests for `horus.eda.parsee_ai_loader` (ADR-025 Phase C, chapter 5)."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from horus.eda.parsee_ai_loader import (
    load_examples,
    parse_truth_answer,
    walk,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PARSEE_CORPUS = REPO_ROOT / "data" / "raw" / "english" / "parsee-ai-invoices-example"
PARSEE_PARQUET = PARSEE_CORPUS / "invoices_parsee.parquet"

_HAS_PARSEE = PARSEE_PARQUET.is_file()
skip_if_no_parsee_ai_corpus = pytest.mark.skipif(
    not _HAS_PARSEE,
    reason=(
        "Requires parsee-ai-invoices-example parquet under "
        "data/raw/english/parsee-ai-invoices-example/. "
        "Skips on CI per ADR-023."
    ),
)


# ---------------------------------------------------------------------------
# Pure-function tests (no corpus required)
# ---------------------------------------------------------------------------


def test_walk_raises_on_missing_parquet(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="parsee-ai parquet not found"):
        walk(tmp_path)


def test_walk_finds_synthetic_parquet(tmp_path: Path) -> None:
    """Synthetic mini-corpus exercises the parquet-discovery code path."""
    parquet_path = tmp_path / "invoices_parsee.parquet"
    table = pa.table(
        {
            "source_identifier": ["aaa", "bbb"],
            "template_id": ["t1", "t1"],
            "element_identifier": ["general0", "general1"],
            "FEATURE_full_prompt": ["prompt one", "prompt two"],
            "TRUTH_answer": ["(main question): 1.0\nSources: [0]", "(meta0): foo\nSources: [1]"],
        }
    )
    pq.write_table(table, parquet_path)
    df = walk(tmp_path)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["filename"] == "invoices_parsee.parquet"
    assert row["n_rows"] == 2
    assert row["size_bytes"] > 0


def test_load_examples_derives_features(tmp_path: Path) -> None:
    parquet_path = tmp_path / "invoices_parsee.parquet"
    table = pa.table(
        {
            "source_identifier": ["aaa", "bbb"],
            "template_id": ["t1", "t1"],
            "element_identifier": ["general0", "general1"],
            "FEATURE_full_prompt": [
                "short prompt",
                "a substantially longer prompt with more content",
            ],
            "TRUTH_answer": [
                "(main question): 119.0\n(meta0): EUR\nSources: [22]",
                "(line_item0): widget\nSources: [3]",
            ],
        }
    )
    pq.write_table(table, parquet_path)
    df = load_examples(tmp_path)
    assert len(df) == 2
    assert set(df.columns) >= {
        "source_identifier",
        "template_id",
        "element_identifier",
        "prompt_text",
        "truth_text",
        "prompt_len",
        "truth_len",
        "n_truth_sections",
        "main_answer",
    }
    # Row 0 has main question → main_answer extracted.
    row0 = df.iloc[0]
    assert row0["main_answer"] == "119.0"
    assert row0["n_truth_sections"] == 3  # main question, meta0, Sources
    # Row 1 has no main question → main_answer is None.
    row1 = df.iloc[1]
    assert row1["main_answer"] is None
    assert row1["n_truth_sections"] == 2  # line_item0, Sources
    # prompt_len ordering.
    assert int(row0["prompt_len"]) < int(row1["prompt_len"])


def test_parse_truth_answer_main_question() -> None:
    truth = "(main question): 119.0\n(meta0): $ EUR $\n(meta1): 19%\nSources: [22]"
    parsed = parse_truth_answer(truth)
    assert parsed["main question"] == "119.0"
    assert parsed["meta0"] == "$ EUR $"
    assert parsed["meta1"] == "19%"
    assert parsed["Sources"] == "[22]"


def test_parse_truth_answer_no_main_question() -> None:
    truth = "(line_item0): widget\n(line_item1): gadget\nSources: [3, 4]"
    parsed = parse_truth_answer(truth)
    assert "main question" not in parsed
    assert parsed["line_item0"] == "widget"
    assert parsed["line_item1"] == "gadget"
    assert parsed["Sources"] == "[3, 4]"


def test_parse_truth_answer_empty_sources() -> None:
    """A truth answer with empty sources list still parses."""
    truth = "(main question): null\nSources: []"
    parsed = parse_truth_answer(truth)
    assert parsed["main question"] == "null"
    assert parsed["Sources"] == "[]"


def test_parse_truth_answer_multiline_value() -> None:
    """A `(key): value` section where the value spans multiple lines."""
    truth = "(main question): line one\nline two of the same value\n(meta0): foo\nSources: [1]"
    parsed = parse_truth_answer(truth)
    assert "line one" in parsed["main question"]
    assert "line two" in parsed["main question"]
    assert parsed["meta0"] == "foo"


# ---------------------------------------------------------------------------
# Corpus-aware tests (require parsee-ai parquet on disk)
# ---------------------------------------------------------------------------


@skip_if_no_parsee_ai_corpus
def test_walk_real_corpus_row_count() -> None:
    """Per the MANIFEST: 45 rows in the parsee-ai parquet."""
    df = walk(PARSEE_CORPUS)
    assert len(df) == 1
    assert int(df.iloc[0]["n_rows"]) == 45


@skip_if_no_parsee_ai_corpus
def test_load_examples_real_corpus_balance() -> None:
    """Empirical: 15 unique source PDFs × 3 element types = 45 rows."""
    df = load_examples(PARSEE_CORPUS)
    assert len(df) == 45
    assert int(df["source_identifier"].nunique()) == 15
    # Per the empirical inspection: 3 distinct element identifiers, each appearing 15 times.
    element_counts = df["element_identifier"].value_counts()
    assert len(element_counts) == 3
    assert (element_counts == 15).all()


@skip_if_no_parsee_ai_corpus
def test_load_examples_real_corpus_main_answer_extraction() -> None:
    """Per the parsee schema: only `general0` rows have `(main question): VALUE`."""
    df = load_examples(PARSEE_CORPUS)
    n_main = int(df["main_answer"].notna().sum())
    # 15 general0 rows have main_answer; the other 30 (general1 + general2) do not.
    assert n_main == 15


@skip_if_no_parsee_ai_corpus
def test_load_examples_real_corpus_template_uniformity() -> None:
    """All 45 parsee-ai rows use the same extraction template (single template_id)."""
    df = load_examples(PARSEE_CORPUS)
    assert int(df["template_id"].nunique()) == 1
