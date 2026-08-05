"""Tests for `horus.finetune.dataset` — the structurer fine-tuning data path (issue #55).

Corpus-dependent (like `tests/test_extract_zugferd_xml.py`): the GT-serialization and
self-consistency checks are exercised against the real `EN16931_Einfach` answer key, so
they are guarded by `skip_if_no_corpus` and simply don't collect when the corpus is absent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from horus.eval.ground_truth import (
    FIELDS,
    REPEATING_GROUPS,
    FieldSpec,
    GroundTruth,
    GroundTruthField,
)
from horus.eval.harness import _model_slug
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


@skip_if_no_corpus
def test_oracle_group_cells_separate_label_from_value() -> None:
    """Every repeating-group cell must render as ``<label>: <value>`` (ADR-059).

    The regression guard for a 103-cell loss on PERFECT input. Cells used to render
    as ``"<label> <value>"``, which only reads correctly while the labels are long
    German compounds. Once the corpus-measured short labels landed,
    ``"Positionsnummer 1"`` became ``"Pos 1"`` and the structurer returned
    ``line_id="Pos 1"``; ``"Umsatzsteuer S"`` made it emit ``category_code=null``.
    Both are label/value ambiguity, not model weakness — so the invariant is
    structural: the label must be recoverable from the cell by splitting on ": ".
    """
    gt, _ = dataset.load_groundtruth(EINFACH_PDF)
    assert gt is not None

    known_labels = {
        spec.rendered_label
        for _group, (_row_xpath, sub_fields) in REPEATING_GROUPS.items()
        for spec in sub_fields.values()
    }
    # A group row is either "  - <cells>" or "  <position>. <cells>"; matching on
    # that shape avoids duplicating the renderer's private group-title dict, which
    # would silently stop matching if a title were reworded.
    row_re = re.compile(r"^ {2}(?:- |(?P<ordinal>\S+)\. )(?P<cells>.+)$")

    checked = 0
    for line in dataset.render_oracle_transcript(gt).splitlines():
        match = row_re.match(line)
        if match is None:
            continue
        for cell in match.group("cells").split(" | "):
            assert ": " in cell, (
                f"group cell {cell!r} has no label/value separator — a short label "
                "glued to its value is indistinguishable from the value itself"
            )
            label = cell.split(": ", 1)[0]
            assert label in known_labels, (
                f"group cell {cell!r} does not start with a registry label; "
                f"parsed {label!r}, which is not one of the known cell labels"
            )
            checked += 1
    assert checked, "no group cells rendered — the invariant was not exercised"


def test_oracle_group_row_survives_a_multiline_cell_value() -> None:
    """A group row occupies exactly ONE line, whatever the value contains (ADR-059).

    Hermetic on purpose — the corpus is gitignored, so a corpus-gated test would
    never run in CI, and this is the invariant that silently broke there. Some CII
    ``name`` elements carry a whole product block rather than a name
    ("GTIN 4123456000014\\nArt-Nr-Lieferant ZS9997\\nZitronensäure 100ml"), which
    split one line item across four lines on 1 of 29 val invoices: the "perfect"
    page stopped parsing as a table at all.

    Flat fields keep their newlines, so the test pins BOTH behaviours: a multi-line
    address under one label is what a real page prints.
    """
    absent = {
        key: GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=None,
            normalized_value=None,
            xpath=spec.xpath,
            is_present=False,
        )
        for key, spec in FIELDS.items()
    }
    address = "MUSTERLIEFERANT GMBH\nBahnstr. 42\n12345 Musterstadt"
    absent["seller_address"] = GroundTruthField(
        bt_code=FIELDS["seller_address"].bt_code,
        raw_value=address,
        normalized_value=address,
        xpath=FIELDS["seller_address"].xpath,
        is_present=True,
    )

    _row_xpath, line_item_fields = REPEATING_GROUPS["line_items"]
    multiline_name = "GTIN 4123456000014\nArt-Nr-Lieferant ZS9997\nZitronensäure 100ml"
    values = {"line_id": "1", "name": multiline_name, "net_price": "10.00"}
    row = {
        key: GroundTruthField(
            bt_code=spec.bt_code,
            raw_value=values[key],
            normalized_value=values[key],
            xpath=spec.xpath,
            is_present=True,
        )
        for key, spec in line_item_fields.items()
        if key in values
    }

    text = dataset.render_oracle_transcript(GroundTruth(header=absent, line_items=[row]))
    body = text.split("Rechnungspositionen:", 1)[1].strip()

    assert len(body.splitlines()) == 1, f"one line item rendered across >1 line:\n{body}"
    assert "Art-Nr-Lieferant ZS9997 Zitronensäure 100ml" in body
    # The flat address keeps its line breaks — no row contract applies to it.
    assert address in text


@skip_if_no_corpus
def test_oracle_line_item_ordinal_is_the_gt_position() -> None:
    """A row's leading number must be its GT position, never a counter (ADR-059).

    The renderer used ``enumerate(rows, start=1)``, so a page could assert a
    position the GT contradicts — on a 0-based invoice the GT line_ids are "0"/"1"
    while the page printed "1."/"2.". A "perfect" transcript that disagrees with the
    ground truth it was rendered from cannot bound anything.
    """
    gt, _ = dataset.load_groundtruth(EINFACH_PDF)
    assert gt is not None
    assert gt.line_items, "fixture has no line items to exercise the ordinal"

    expected = [row["line_id"].normalized_value for row in gt.line_items]
    text = dataset.render_oracle_transcript(gt)
    body = text.split("Rechnungspositionen:", 1)[1]

    rendered: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            if rendered:
                break
            continue
        match = re.match(r"^ {2}(\S+)\. ", line)
        assert match is not None, f"line-item row {line!r} lost its position ordinal"
        rendered.append(match.group(1))

    assert rendered == expected, (
        f"rendered line-item positions {rendered} do not match the GT {expected}"
    )
    # The position must not ALSO appear as a labelled cell: emitting both is what
    # made the structurer return the labelled form verbatim (line_id="Pos: 1").
    assert "Pos: " not in text


# ---------------------------------------------------------------------------
# build_heldout_records — the private Belege set as InvoiceRecords (ADR-040)
# ---------------------------------------------------------------------------

# Source filenames deliberately DIFFER from the sanitized ids, so a test asserting
# `stem == id` actually proves the id is used rather than coinciding with it. These
# stand in for the private originals (vendor + subject in the filename).
_HELDOUT_PDFS: dict[str, str] = {
    "belege-de-email-001": "german/email/Rechnung_Musterfirma_2024-03.pdf",
    "belege-de-email-002": "german/iphone-pdf-scan/IMG_4821.pdf",
}
_HELDOUT_CHANNELS: dict[str, str] = {
    "belege-de-email-001": "email",
    "belege-de-email-002": "iphone-pdf-scan",
}


def _write_heldout_corpus(
    tmp_path: Path,
    *,
    broken_gt_for: str | None = None,
    gt_dirname: str = dataset.DEFAULT_HELDOUT_GT_DIRNAME,
    verified: bool = True,
) -> Path:
    """Create a synthetic held-out corpus tree (index.json + one GT file per id).

    Synthetic by construction — never real invoice content — so this runs in CI
    without the private corpus, which `.gitignore` blocks in full. Ids are written to
    the index unsorted to exercise the sort.

    Answer keys are written to `gt_dirname`, which defaults to the tree a grading run
    actually reads (`_promoted/`, ADR-062), so these tests exercise the real default
    rather than a path only the tests use.
    """
    corpus = tmp_path / "self-collected"
    (corpus / gt_dirname).mkdir(parents=True)
    for invoice_id in _HELDOUT_PDFS:
        gt_path = corpus / gt_dirname / f"{invoice_id}.gt.json"
        if invoice_id == broken_gt_for:
            gt_path.write_text("{ this is not valid json", encoding="utf-8")
            continue
        gt_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": invoice_id,
                    "verified": verified,
                    "fields": {"invoice_number": "RG-001", "grand_total_amount": "1.234,56"},
                }
            ),
            encoding="utf-8",
        )
    index = {
        "items": [
            {
                "id": invoice_id,
                "pdf": pdf_rel,
                "gt": f"gt/{invoice_id}.gt.json",
                "language": "german",
                "channel": _HELDOUT_CHANNELS[invoice_id],
                "verified": False,
            }
            for invoice_id, pdf_rel in reversed(list(_HELDOUT_PDFS.items()))
        ]
    }
    (corpus / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return corpus


def test_heldout_record_stems_are_sanitized_ids_not_filenames(tmp_path: Path) -> None:
    """`stem` must be the sanitized index id, never the private source filename.

    `stem` names the output transcript, so a leaked source filename would write a
    file whose NAME carries vendor and subject — the one identifier ADR-040 forbids
    outside the ignored tree. Returned sorted, like the synthetic path.
    """
    corpus = _write_heldout_corpus(tmp_path)
    records = dataset.build_heldout_records(corpus, transcript_dir=tmp_path / "out")

    assert [rec.stem for rec in records] == ["belege-de-email-001", "belege-de-email-002"]
    for rec in records:
        assert rec.stem != rec.pdf_path.stem, (
            f"stem {rec.stem!r} equals the source filename stem — the private "
            "filename has leaked into the transcript name"
        )


def test_heldout_records_load_gt_and_group_by_language_channel(tmp_path: Path) -> None:
    """GT comes from the hand-authored JSON, repaired; subdir is language/channel."""
    corpus = _write_heldout_corpus(tmp_path)
    records = dataset.build_heldout_records(corpus, transcript_dir=tmp_path / "out")

    assert [rec.subdir for rec in records] == ["german/email", "german/iphone-pdf-scan"]
    first = records[0]
    assert first.has_gt
    assert first.gt is not None
    # Locale repair must run on the GT side, identically to the prediction side.
    assert first.gt.header["grand_total_amount"].normalized_value == "1234.56"
    assert first.gt.header["invoice_number"].is_present
    # A field absent from the draft stays an honest null, never an invented value.
    assert not first.gt.header["seller_name"].is_present


def test_heldout_records_absent_corpus_is_empty(tmp_path: Path) -> None:
    """No index.json → [] so CI and fresh clones auto-skip (ADR-023)."""
    assert dataset.build_heldout_records(tmp_path / "nonexistent") == []


def test_heldout_records_survive_a_malformed_gt(tmp_path: Path) -> None:
    """One unparseable hand-authored GT must not abort the whole set.

    Same per-invoice robustness contract `load_groundtruth` gives the factur-x route:
    the bad record comes back with `gt=None` and a recorded reason, and the good one
    is unaffected. Silently dropping it would shrink the set without saying so.
    """
    corpus = _write_heldout_corpus(tmp_path, broken_gt_for="belege-de-email-001")
    records = dataset.build_heldout_records(corpus, transcript_dir=tmp_path / "out")

    assert len(records) == 2
    broken, intact = records[0], records[1]
    assert broken.stem == "belege-de-email-001"
    assert broken.gt is None
    assert broken.gt_error is not None
    assert not broken.has_gt
    assert intact.has_gt


def test_heldout_records_detect_an_existing_transcript(tmp_path: Path) -> None:
    """transcript_path is set iff a reader-slug-named transcript already exists.

    This is what makes the reader pass resume-safe over the held-out set.
    """
    corpus = _write_heldout_corpus(tmp_path)
    out = tmp_path / "out"
    out.mkdir()

    before = dataset.build_heldout_records(corpus, transcript_dir=out)
    assert all(rec.transcript_path is None for rec in before)

    slug = _model_slug(dataset.DEFAULT_READER_MODEL)
    (out / f"{slug}__belege-de-email-001.txt").write_text("transcript", encoding="utf-8")

    after = dataset.build_heldout_records(corpus, transcript_dir=out)
    assert after[0].has_transcript
    assert not after[1].has_transcript


def test_grading_reads_the_signed_off_key_not_the_draft(tmp_path: Path) -> None:
    """The default answer-key tree is `_promoted/`, never `gt/`.

    `gt/` is one of the channels adjudication reads (ADR-062). Grading against it means
    grading against an unverified draft that partly produced the very key it is being
    compared to — the cause of the retracted held-out figure.
    """
    assert dataset.DEFAULT_HELDOUT_GT_DIRNAME == "_promoted"
    corpus = _write_heldout_corpus(tmp_path)
    assert (corpus / "_promoted").is_dir()
    assert not (corpus / "gt").exists()

    records = dataset.build_heldout_records(corpus, transcript_dir=tmp_path / "out")
    assert all(rec.has_gt for rec in records)


def test_the_superseded_draft_key_is_still_reachable_on_request(tmp_path: Path) -> None:
    """Reproducing the old measurement must stay possible — explicitly, never by default."""
    corpus = _write_heldout_corpus(tmp_path, gt_dirname="gt")
    assert dataset.build_heldout_records(corpus, transcript_dir=tmp_path / "out")[0].gt is None

    records = dataset.build_heldout_records(
        corpus, transcript_dir=tmp_path / "out", gt_dirname="gt"
    )
    assert all(rec.has_gt for rec in records)


def test_a_missing_signed_off_key_is_reported_never_silently_substituted(tmp_path: Path) -> None:
    """An invoice with no promoted key must come back unusable, not fall back to the draft.

    A silent fallback would grade part of the corpus against the draft while the run
    still reported a whole-corpus number.
    """
    corpus = _write_heldout_corpus(tmp_path, gt_dirname="gt")
    records = dataset.build_heldout_records(corpus, transcript_dir=tmp_path / "out")

    assert [rec.gt for rec in records] == [None, None]
    for rec in records:
        assert rec.gt_error is not None
        assert "_promoted" in rec.gt_error


def test_heldout_default_paths_stay_inside_the_private_tree() -> None:
    """Held-out transcripts and rasters must never default outside the ignored tree.

    A real invoice's transcript reproduces its content verbatim. Pointing this at the
    tracked `docs/sources/` tree the synthetic corpus uses would commit private
    documents, so the invariant is pinned rather than left to reviewer attention.
    """
    assert dataset.DEFAULT_HELDOUT_CORPUS_ROOT == Path("data/self-collected")
    for path in (
        dataset.DEFAULT_HELDOUT_TRANSCRIPT_DIR,
        dataset.DEFAULT_HELDOUT_RASTER_CACHE,
    ):
        assert path.is_relative_to(dataset.DEFAULT_HELDOUT_CORPUS_ROOT)
        assert "docs" not in path.parts
