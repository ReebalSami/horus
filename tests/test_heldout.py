"""Tests for the held-out Belege loader (`horus.eval.heldout`, ADR-040).

All fixtures here are SYNTHETIC (hand-written dicts + temp files) — never real
invoice content — so the suite runs in CI without the private corpus. The real
held-out corpus lives under the git-ignored `data/self-collected/**` and is
exercised only on the author's machine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus.eval.ground_truth import FIELDS
from horus.eval.heldout import (
    GT_SCHEMA_VERSION,
    HeldoutItem,
    build_groundtruth_from_json,
    build_groundtruth_from_mapping,
    build_gt_cache,
    empty_gt_fields,
    gt_document,
    load_heldout_index,
)
from horus.eval.scorer import score

# A small synthetic invoice: 7 present fields (one per relevant type) + the rest
# absent. Values are written in messy German/locale form to exercise repair.
SAMPLE_FIELDS: dict[str, str | None] = {
    "invoice_number": "RG-2024-001",
    "issue_date": "15.01.2024",
    "invoice_currency_code": "EUR",
    "seller_name": "Muster GmbH",
    "tax_rate": "19 %",
    "tax_total_amount": "197,12",
    "grand_total_amount": "1.234,56",
}

# The canonical forms the GT-side repair must produce (must match what the
# prediction-side normalizers produce for a correct extraction).
EXPECTED_CANONICAL: dict[str, str] = {
    "invoice_number": "RG-2024-001",
    "issue_date": "2024-01-15",
    "invoice_currency_code": "EUR",
    "seller_name": "Muster GmbH",
    "tax_rate": "19",
    "tax_total_amount": "197.12",
    "grand_total_amount": "1234.56",
}


# ---------------------------------------------------------------------------
# build_groundtruth_from_mapping — shape, presence, locale repair, honesty
# ---------------------------------------------------------------------------


def test_mapping_yields_all_nineteen_keys() -> None:
    """The header always carries exactly the 19 scored FIELDS keys."""
    gt = build_groundtruth_from_mapping({})
    assert set(gt.header) == set(FIELDS)


def test_present_fields_are_locale_repaired_to_canonical() -> None:
    """Messy German/locale values canonicalize to the scorer's exact-match form."""
    gt = build_groundtruth_from_mapping(SAMPLE_FIELDS)
    for key, expected in EXPECTED_CANONICAL.items():
        field = gt.header[key]
        assert field.is_present is True, key
        assert field.normalized_value == expected, key
        assert field.raw_value == SAMPLE_FIELDS[key], key


def test_absent_fields_are_honest_null() -> None:
    """Missing keys, explicit null, and empty strings all read as absent."""
    gt = build_groundtruth_from_mapping(
        {"invoice_number": "X-1", "buyer_name": None, "buyer_vat_id": "   "}
    )
    for key in ("delivery_date", "buyer_name", "buyer_vat_id", "seller_gln"):
        field = gt.header[key]
        assert field.is_present is False, key
        assert field.raw_value is None, key
        assert field.normalized_value is None, key


def test_case_insensitive_key_matching() -> None:
    """JSON keys may use any casing (mirrors InvoiceFields' before-validator)."""
    gt = build_groundtruth_from_mapping({"Invoice_Number": "A-9", "ISSUE_DATE": "2024-01-15"})
    assert gt.header["invoice_number"].normalized_value == "A-9"
    assert gt.header["issue_date"].normalized_value == "2024-01-15"


def test_present_but_unparseable_preserves_raw_and_nulls_normalized() -> None:
    """A present-but-garbage typed value stays present with raw kept, normalized None.

    This is the audit path: the author sees a present field that failed to
    canonicalize and fixes the data-entry error at review.
    """
    gt = build_groundtruth_from_mapping({"grand_total_amount": "not-a-number"})
    field = gt.header["grand_total_amount"]
    assert field.is_present is True
    assert field.raw_value == "not-a-number"
    assert field.normalized_value is None


# ---------------------------------------------------------------------------
# build_groundtruth_from_json — file round-trip + validation
# ---------------------------------------------------------------------------


def test_json_round_trip_full_document(tmp_path: Path) -> None:
    """A gt_document() written to disk reloads to the same GroundTruth as the mapping."""
    doc = gt_document(
        invoice_id="belege-de-email-001",
        language="german",
        channel="email",
        fields=SAMPLE_FIELDS,
        verified=True,
        verified_date="2026-06-07",
    )
    path = tmp_path / "belege-de-email-001.gt.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    from_file = build_groundtruth_from_json(path)
    from_mapping = build_groundtruth_from_mapping(SAMPLE_FIELDS)
    assert from_file == from_mapping


def test_json_accepts_bare_field_mapping(tmp_path: Path) -> None:
    """A file containing a bare field object (no 'fields' wrapper) is accepted."""
    path = tmp_path / "bare.gt.json"
    path.write_text(json.dumps(SAMPLE_FIELDS, ensure_ascii=False), encoding="utf-8")
    gt = build_groundtruth_from_json(path)
    assert gt.header["grand_total_amount"].normalized_value == "1234.56"


def test_json_rejects_non_object(tmp_path: Path) -> None:
    """A JSON array (not an object) raises ValueError."""
    path = tmp_path / "bad.gt.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        build_groundtruth_from_json(path)


def test_gt_document_shape_and_field_filtering() -> None:
    """gt_document always carries 19 fields + metadata; unknown keys are dropped."""
    doc = gt_document(
        invoice_id="x",
        language="english",
        channel="email",
        fields={"invoice_number": "N-1", "not_a_field": "ignored"},
    )
    assert doc["schema_version"] == GT_SCHEMA_VERSION
    assert set(doc["fields"]) == set(FIELDS)
    assert doc["fields"]["invoice_number"] == "N-1"
    assert "not_a_field" not in doc["fields"]
    assert empty_gt_fields()["invoice_number"] is None


# ---------------------------------------------------------------------------
# load_heldout_index + build_gt_cache — discovery over a temp corpus tree
# ---------------------------------------------------------------------------


def _write_corpus(tmp_path: Path, *, verified_flags: tuple[bool, bool] = (True, True)) -> Path:
    """Create a synthetic held-out corpus tree (index.json + 2 GT files)."""
    corpus = tmp_path / "self-collected"
    (corpus / "gt").mkdir(parents=True)
    ids = ["belege-de-email-002", "belege-de-email-001"]  # deliberately unsorted
    for invoice_id, verified in zip(ids, verified_flags, strict=True):
        doc = gt_document(
            invoice_id=invoice_id,
            language="german",
            channel="email",
            fields=SAMPLE_FIELDS,
            verified=verified,
        )
        (corpus / "gt" / f"{invoice_id}.gt.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8"
        )
    index = {
        "name": "belege-heldout-test",
        "items": [
            {
                "id": invoice_id,
                "pdf": f"german/email/{invoice_id}.pdf",
                "gt": f"gt/{invoice_id}.gt.json",
                "language": "german",
                "channel": "email",
                "verified": verified,
                "pages": 1,
            }
            for invoice_id, verified in zip(ids, verified_flags, strict=True)
        ],
    }
    (corpus / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return corpus


def test_load_index_sorts_and_resolves_paths(tmp_path: Path) -> None:
    """Items come back sorted by id with corpus-relative paths resolved to absolute."""
    corpus = _write_corpus(tmp_path)
    items = load_heldout_index(corpus)
    assert [it.id for it in items] == ["belege-de-email-001", "belege-de-email-002"]
    first = items[0]
    assert isinstance(first, HeldoutItem)
    assert first.pdf_path == corpus / "german/email/belege-de-email-001.pdf"
    assert first.gt_path == corpus / "gt/belege-de-email-001.gt.json"
    assert first.language == "german"
    assert first.channel == "email"
    assert first.n_pages == 1


def test_load_index_absent_returns_empty(tmp_path: Path) -> None:
    """No index.json → [] (so corpus-absent tests/eval auto-skip; ADR-023)."""
    assert load_heldout_index(tmp_path / "nonexistent") == []


def test_build_gt_cache_loads_all(tmp_path: Path) -> None:
    """build_gt_cache returns {id: GroundTruth} for every indexed invoice."""
    corpus = _write_corpus(tmp_path)
    cache = build_gt_cache(corpus)
    assert set(cache) == {"belege-de-email-001", "belege-de-email-002"}
    assert cache["belege-de-email-001"].header["grand_total_amount"].normalized_value == "1234.56"


def test_build_gt_cache_verified_only_filters(tmp_path: Path) -> None:
    """verified_only=True drops unverified drafts (the safe grading default)."""
    corpus = _write_corpus(tmp_path, verified_flags=(False, True))
    cache = build_gt_cache(corpus, verified_only=True)
    assert set(cache) == {"belege-de-email-001"}  # the verified one only


def test_build_gt_cache_skips_missing_gt_file(tmp_path: Path) -> None:
    """An indexed item whose GT file is missing is skipped, not fatal."""
    corpus = _write_corpus(tmp_path)
    (corpus / "gt" / "belege-de-email-001.gt.json").unlink()
    cache = build_gt_cache(corpus)
    assert set(cache) == {"belege-de-email-002"}


# ---------------------------------------------------------------------------
# End-to-end: the held-out GT plugs into the existing scorer unchanged
# ---------------------------------------------------------------------------


def test_perfect_prediction_scores_micro_f1_one() -> None:
    """A prediction equal to the GT scores micro-F1 == 1.0 through scorer.score."""
    gt = build_groundtruth_from_mapping(SAMPLE_FIELDS)
    predicted: dict[str, str | None] = dict.fromkeys(FIELDS)
    predicted.update(SAMPLE_FIELDS)  # same messy values; scorer normalizes both sides
    result = score(predicted, gt, invoice_id="belege-de-email-001", model_id="test")
    assert result.micro_f1 == pytest.approx(1.0)


def test_empty_prediction_scores_zero_against_present_fields() -> None:
    """Extracting nothing where GT has values scores micro-F1 == 0.0 (all FN)."""
    gt = build_groundtruth_from_mapping(SAMPLE_FIELDS)
    predicted: dict[str, str | None] = dict.fromkeys(FIELDS)
    result = score(predicted, gt, invoice_id="belege-de-email-001", model_id="test")
    assert result.micro_f1 == pytest.approx(0.0)
