"""Tests for the transcript-answerability probe's pure logic (issue #55)."""

from __future__ import annotations

from horus.finetune.answerability import value_variants


def test_iso_date_variants() -> None:
    v = value_variants(None, "2017-05-09")
    assert "2017-05-09" in v
    assert "09.05.2017" in v
    assert "9.5.2017" in v


def test_amount_variants_german_shapes() -> None:
    v = value_variants(None, "12345.67")
    assert "12345,67" in v
    assert "12.345,67" in v
    v_small = value_variants(None, "571.04")
    assert "571,04" in v_small
    assert not any("." in s and "," in s for s in v_small)  # no grouping under 4 digits


def test_iban_grouping() -> None:
    v = value_variants("DE88200800000970375700", None)
    assert "de88 2008 0000 0970 3757 00" in v


def test_raw_and_normalized_both_seeded_and_canonicalized() -> None:
    v = value_variants("Musterfirma  GmbH", "musterfirma gmbh")
    assert v == {"musterfirma gmbh"}  # whitespace collapsed + lowercased -> single canon form


def test_empty_values() -> None:
    assert value_variants(None, None) == set()
    assert value_variants("  ", "") == set()
