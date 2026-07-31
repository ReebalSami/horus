"""Tests for `horus.finetune.reader_pass` — the resume/skip control flow (issue #55).

The transcription itself is model-heavy (Granite via MLX) and is validated end-to-end by the
`scripts/finetune_reader_pass.py` run, not here. These tests pin the *control flow* that makes
the pass safe + resumable WITHOUT loading a model: a record with no answer key is ignored, and a
record that already has a transcript is skipped (so re-invoking never re-transcribes or loads
the model when there is nothing to do).
"""

from __future__ import annotations

from pathlib import Path

from horus.finetune import dataset
from horus.finetune.dataset import InvoiceRecord
from horus.finetune.reader_pass import run_reader_pass
from tests._corpus import EINFACH_PDF, skip_if_no_corpus


def test_run_reader_pass_ignores_records_without_gt() -> None:
    """A GT-less record is neither transcribed nor counted as skipped — and no model loads.

    `run_reader_pass` only constructs the extractor when there is at least one target; a corpus
    of pure GT-failures must return early (this test would hang/download if that were broken).
    """
    rec = InvoiceRecord(
        pdf_path=Path("nonexistent.pdf"),
        stem="nonexistent",
        subdir="unstructured",
        gt=None,
        gt_error="no factur-x attachment",
        transcript_path=None,
    )

    result = run_reader_pass([rec])

    assert result.written == []
    assert result.skipped == []
    assert result.failures == []


@skip_if_no_corpus
def test_run_reader_pass_skips_already_transcribed() -> None:
    """A GT-bearing record with an existing transcript is skipped (resume-safety; no load)."""
    gt, _ = dataset.load_groundtruth(EINFACH_PDF)
    assert gt is not None

    rec = InvoiceRecord(
        pdf_path=EINFACH_PDF,
        stem="EN16931_Einfach",
        subdir="XML-Rechnung",
        gt=gt,
        gt_error=None,
        transcript_path=Path("already-there.txt"),
    )

    result = run_reader_pass([rec])

    assert result.skipped == ["EN16931_Einfach"]
    assert result.written == []
    assert result.failures == []
