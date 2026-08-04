"""Tests for `horus.finetune.dataset` — the structurer fine-tuning data path (issue #55).

Corpus-dependent (like `tests/test_extract_zugferd_xml.py`): the GT-serialization and
self-consistency checks are exercised against the real `EN16931_Einfach` answer key, so
they are guarded by `skip_if_no_corpus` and simply don't collect when the corpus is absent.
"""

from __future__ import annotations

import json
import re

import pytest

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS, FieldSpec
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


# ---------------------------------------------------------------------------
# printed_label / rendered_label guards (ADR-059) — hermetic, no corpus needed
# ---------------------------------------------------------------------------
#
# `make audit-prompts` is the exhaustive corpus-backed gate (it measures every
# rendered label against the 146 transcripts). These run in `make test` with no
# corpus on disk, so CI catches the structural mistakes.


def _all_specs() -> list[tuple[str, FieldSpec]]:
    """Every FieldSpec rendered into the oracle transcript, flat + group cells."""
    specs: list[tuple[str, FieldSpec]] = list(FIELDS.items())
    for group, (_row_xpath, sub_fields) in REPEATING_GROUPS.items():
        specs.extend((f"{group}.{sub_key}", spec) for sub_key, spec in sub_fields.items())
    return specs


def test_printed_label_is_never_a_value_shape() -> None:
    """A printed_label must be a LABEL, never a concrete value (ADR-059).

    Same leak class the description guard blocks: `printed_label` is rendered into
    the oracle transcript the structurer reads, so a value-shaped label would hand
    the model an answer. A label legitimately contains no digits at all in this
    registry, so the check is strict.
    """
    forbidden = {
        "VAT-id shape": re.compile(r"\b[A-Z]{2}\d{6,}\b"),
        "IBAN shape": re.compile(r"\b[A-Z]{2}\d{2}[0-9A-Z]{10,}\b"),
        "German date": re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b"),
        "ISO date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        "decimal amount": re.compile(r"\b\d+[.,]\d{2}\b"),
    }
    for qualified, spec in _all_specs():
        label = spec.printed_label
        if label is None:
            continue
        for shape, pattern in forbidden.items():
            match = pattern.search(label)
            assert match is None, (
                f"{qualified} printed_label embeds a {shape}: {match.group(0)!r} — "
                "the oracle transcript would leak a ground-truth value"
            )


def test_rendered_label_prefers_printed_label_and_falls_back() -> None:
    """`rendered_label` resolves printed_label first, german_label otherwise."""
    allowance = FIELDS["allowance_total_amount"]
    assert allowance.printed_label == "Gesamtbetrag der Abschläge"
    assert allowance.rendered_label == allowance.printed_label

    # A documented no-printed-label exception falls back to the canonical term.
    doctype = FIELDS["document_type"]
    assert doctype.printed_label is None
    assert doctype.rendered_label == doctype.german_label == "Belegart"


def test_german_label_still_carries_the_spec_term() -> None:
    """The EN16931 term must NOT be overwritten by the printed form (ADR-037/059).

    `adapters.py` compiles the FROZEN regex baseline from `german_label`, so
    rewriting it in place would silently move published numbers. The two facts stay
    in two attributes; this pins the separation for the fields where they differ.
    """
    for key, printed, spec_term in (
        ("allowance_total_amount", "Gesamtbetrag der Abschläge", "Summe Nachlässe"),
        ("charge_total_amount", "Gesamtbetrag der Zuschläge", "Summe Zuschläge"),
        ("line_total_amount", "Positionssumme", "Summe Nettobeträge"),
    ):
        assert FIELDS[key].printed_label == printed
        assert FIELDS[key].german_label == spec_term


@skip_if_no_corpus
def test_render_oracle_transcript_uses_printed_labels() -> None:
    """The oracle page must print corpus wordings, not EN16931 jargon (ADR-059).

    The renderer had NO test coverage, which is how it shipped labels occurring in
    0/146 transcripts — costing the ceiling arm real accuracy on BT-107/108.
    """
    gt, err = dataset.load_groundtruth(EINFACH_PDF)
    assert err is None
    assert gt is not None

    text = dataset.render_oracle_transcript(gt)

    # Present-and-corrected: the totals block uses the FeRD display labels.
    assert "Positionssumme:" in text
    assert "Rechnungssumme ohne USt.:" in text
    assert "Bruttosumme:" in text
    # Absent: the spec jargon that no invoice prints must never reach the model.
    for jargon in (
        "Summe Nettobeträge",
        "Steuerlicher Bemessungsbetrag",
        "Umsatzsteuer gesamt",
        "Bruttobetrag",
        "Summe Nachlässe",
        "Summe Zuschläge",
    ):
        assert jargon not in text, f"oracle transcript still prints spec jargon {jargon!r}"
