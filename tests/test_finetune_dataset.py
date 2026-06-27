"""Tests for `horus.finetune.dataset` — the structurer fine-tuning data path (issue #55).

Corpus-dependent (like `tests/test_extract_zugferd_xml.py`): the GT-serialization and
self-consistency checks are exercised against the real `EN16931_Einfach` answer key, so
they are guarded by `skip_if_no_corpus` and simply don't collect when the corpus is absent.
"""

from __future__ import annotations

import json

import pytest

from horus.eval.ground_truth import FIELDS
from horus.finetune import dataset
from tests._corpus import EINFACH_PDF, skip_if_no_corpus

_EINFACH_STEM = "EN16931_Einfach"
_GRANITE_TRANSCRIPT = (
    dataset.DEFAULT_TRANSCRIPT_DIR / f"ibm-granite__granite-docling-258m-mlx__{_EINFACH_STEM}.txt"
)


@skip_if_no_corpus
def test_groundtruth_to_target_has_full_schema_shape() -> None:
    """The target JSON carries every scored flat field + the 3 groups + purpose_summary."""
    gt, err = dataset.load_groundtruth(EINFACH_PDF)
    assert err is None
    assert gt is not None

    target = dataset.groundtruth_to_target(gt)

    for key in FIELDS:
        assert key in target, f"flat field {key!r} missing from target"
    for group in ("vat_breakdown", "skonto", "line_items"):
        assert group in target
    assert "purpose_summary" in target
    assert target["purpose_summary"] is None  # non-scored; answer key carries no summary

    # Core mandatory fields are present (non-null) on this clean invoice.
    assert target["invoice_number"]
    assert target["seller_name"]
    # The whole object must be JSON-serializable (it becomes the training answer).
    assert json.loads(json.dumps(target, ensure_ascii=False)) == target


@skip_if_no_corpus
def test_target_self_score_is_clean_for_einfach() -> None:
    """A GT-derived target must score ~1.0 against its own GT, with zero spurious emission.

    This is the make-sure-it-works guard: a malformed target can never silently teach the
    model a wrong answer. `EN16931_Einfach` is one of the corpus's clean (non-flagged) invoices.
    """
    gt, _ = dataset.load_groundtruth(EINFACH_PDF)
    assert gt is not None

    scores = dataset.target_self_score(gt)

    assert scores.micro_f1 == pytest.approx(1.0)
    assert scores.overall_micro_f1 == pytest.approx(1.0)
    assert scores.spurious_emission_rate == pytest.approx(0.0)


@skip_if_no_corpus
def test_build_example_composes_question_and_json_answer() -> None:
    """`build_example` threads the prompt + reader text into the question and emits JSON."""
    if not _GRANITE_TRANSCRIPT.is_file():
        pytest.skip(f"cached reader transcript not present: {_GRANITE_TRANSCRIPT}")
    gt, _ = dataset.load_groundtruth(EINFACH_PDF)
    assert gt is not None

    rec = dataset.InvoiceRecord(
        pdf_path=EINFACH_PDF,
        stem=_EINFACH_STEM,
        subdir="XML-Rechnung",
        gt=gt,
        gt_error=None,
        transcript_path=_GRANITE_TRANSCRIPT,
    )
    prompt = "Extract the invoice fields. Return ONE JSON object.\n{field_glossary}"

    example = dataset.build_example(rec, structuring_prompt=prompt)

    assert example["stem"] == _EINFACH_STEM
    assert "Extract the invoice fields" in example["question"]
    # The reader transcript text is appended into the question (matches arm_b input).
    assert len(example["question"]) > len(prompt)
    # The answer is a valid JSON object keyed by the schema.
    parsed = json.loads(example["answer"])
    assert isinstance(parsed, dict)
    assert "invoice_number" in parsed
