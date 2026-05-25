"""parsee-ai-invoices-example loader for the EDA Book chapter 5 (ADR-025 Phase C).

Loads + characterizes the Parsee AI Invoices Example dataset
(`parsee-ai/invoices-example` on HuggingFace, MIT license): 45
prompt / truth-answer pairs generated from 15 underlying invoice PDFs
on app.parsee.ai. Designed for evaluating LLMs on RAG-style invoice
question answering. **Bilingual** — en + de — unique among the HORUS
7-dataset substrate.

On disk: a single parquet file `invoices_parsee.parquet` (45 rows × 5
string columns):

  - `source_identifier`: SHA256-like hash of the source PDF (accessible
    at `https://app.parsee.ai/documents/view/<source_identifier>`)
  - `template_id`: MongoDB ObjectId-like string identifying the
    parsee-internal extraction template (e.g., `65ef0d5f9012fa0ca62df5d0`)
  - `element_identifier`: short label for the element/field being asked
    about (e.g., `general0`, `line_item0`, `meta0`)
  - `FEATURE_full_prompt`: the full prompt text supplied to the LLM
    (includes the question + RAG-style text fragments from the source PDF)
  - `TRUTH_answer`: the ground-truth answer in parsee's structured format
    (e.g., `(main question): 119.0\\n(meta0): $ EUR $\\n(meta1): 19%\\nSources: [22]`)

Public surface:

  - :func:`walk` — return one row per parquet file (here always one row).
  - :func:`load_examples` — load all 45 rows + derive lightweight
    per-row features (prompt length, truth length, parsed main answer).
  - :func:`parse_truth_answer` — split parsee's structured TRUTH format
    into a dict of section keys → values.

Refs: ADR-025, `docs/sources/datasets/parsee-ai-invoices-example.md`,
`data/raw/english/parsee-ai-invoices-example/MANIFEST.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Regex for parsee's TRUTH_answer format. Sections are of the form
# "(key): value" with each section separated by a literal "\n". The final
# section is always "Sources: [list-of-ints]" (without parens).
_TRUTH_SECTION_PATTERN = re.compile(r"\(([^)]+)\):\s*(.*?)(?=\n\([^)]+\):|\nSources:|$)", re.DOTALL)
_TRUTH_SOURCES_PATTERN = re.compile(r"Sources:\s*(\[[^\]]*\])")


def walk(corpus_root: Path) -> pd.DataFrame:
    """Walk parsee-ai corpus root, returning one-row-per-parquet-file DataFrame.

    Looks for `invoices_parsee.parquet` at the corpus root (no subdirectory;
    HF's parsee-ai/invoices-example is flat). Per-row metadata only — no full
    parquet load.

    Args:
        corpus_root: dataset root (typically
            `data/raw/english/parsee-ai-invoices-example`).

    Returns:
        DataFrame with columns:
          - `path`: absolute Path to the parquet file
          - `filename`: bare filename
          - `size_bytes`: stat() size
          - `n_rows`: row count from parquet metadata

    Raises:
        FileNotFoundError: if the parquet file is absent (suggests partial
            download).
    """
    parquet_path = corpus_root / "invoices_parsee.parquet"
    if not parquet_path.is_file():
        raise FileNotFoundError(
            f"parsee-ai parquet not found: {parquet_path}. "
            f"Acquire the corpus first; see "
            f"data/raw/english/parsee-ai-invoices-example/MANIFEST.md."
        )
    import pyarrow.parquet as pq

    meta = pq.read_metadata(parquet_path)
    return pd.DataFrame(
        [
            {
                "path": parquet_path,
                "filename": parquet_path.name,
                "size_bytes": parquet_path.stat().st_size,
                "n_rows": meta.num_rows,
            }
        ]
    )


def load_examples(corpus_root: Path) -> pd.DataFrame:
    """Load all parsee-ai rows + derive lightweight per-row features.

    Args:
        corpus_root: dataset root.

    Returns:
        DataFrame with one row per (prompt, truth) pair. Columns:
          - `source_identifier`: SHA256-like hash of the source PDF
          - `template_id`: parsee-internal extraction template ObjectId
          - `element_identifier`: short label for the field/element asked
          - `prompt_text`: full prompt supplied to the LLM (=FEATURE_full_prompt)
          - `truth_text`: ground-truth answer (=TRUTH_answer)
          - `prompt_len`: character length of the prompt
          - `truth_len`: character length of the truth answer
          - `n_truth_sections`: count of `(key): value` sections in the truth
          - `main_answer`: extracted `(main question): VALUE` if present, else None

    Raises:
        FileNotFoundError: if the parquet file is absent.
    """
    file_index = walk(corpus_root)
    parquet_path = file_index.iloc[0]["path"]
    df_raw = pd.read_parquet(parquet_path)
    derived = pd.DataFrame(
        {
            "source_identifier": df_raw["source_identifier"].astype(str),
            "template_id": df_raw["template_id"].astype(str),
            "element_identifier": df_raw["element_identifier"].astype(str),
            "prompt_text": df_raw["FEATURE_full_prompt"].astype(str),
            "truth_text": df_raw["TRUTH_answer"].astype(str),
        }
    )
    derived["prompt_len"] = derived["prompt_text"].str.len()
    derived["truth_len"] = derived["truth_text"].str.len()
    derived["n_truth_sections"] = derived["truth_text"].apply(lambda t: len(parse_truth_answer(t)))
    derived["main_answer"] = derived["truth_text"].apply(
        lambda t: parse_truth_answer(t).get("main question")
    )
    return derived


def parse_truth_answer(truth: str) -> dict[str, str]:
    """Parse parsee's TRUTH_answer format into a dict of section → value.

    The format is a sequence of `(key): value` sections separated by `\\n`
    (literal backslash-n in the parquet rendered as actual newlines on
    parquet read), followed by a `Sources: [...]` trailer. This function
    extracts the `(key): value` sections and the sources list.

    Args:
        truth: raw TRUTH_answer string.

    Returns:
        Dict with section keys (without parens) and string values. The
        sources list is keyed as `"Sources"` (without parens).

    Examples:
        >>> parse_truth_answer("(main question): 119.0\\n(meta0): $ EUR $\\nSources: [22]")
        {'main question': '119.0', 'meta0': '$ EUR $', 'Sources': '[22]'}
    """
    result: dict[str, str] = {}
    for match in _TRUTH_SECTION_PATTERN.finditer(truth):
        key = match.group(1).strip()
        value = match.group(2).strip()
        result[key] = value
    sources_match = _TRUTH_SOURCES_PATTERN.search(truth)
    if sources_match:
        result["Sources"] = sources_match.group(1).strip()
    return result
