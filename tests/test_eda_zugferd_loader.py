"""Tests for `horus.eda.zugferd_loader` (ADR-025 Phase B).

The loader extracts ZUGFeRD-specific helpers from the original
`experiments/eda-zugferd.py` notebook into a tested library module.
Tests cover:

  - Pure-function helpers (no I/O): `profile_from_filename`,
    `assign_complexity_tier`, `gt_has_any_field`, `field_value_present`,
    `extract_country_codes_from_gt`, `gt_field_values`, `_classify_extension`.
    These run unconditionally (no corpus needed).
  - Corpus-aware helpers: `walk`, `get_page_count`, `extract_xml_and_level`,
    `parse_one_gt`, `line_item_count` — gated behind `skip_if_no_corpus`
    per ADR-023 + tests/_corpus.py.

Refs: ADR-025 §"Decision + integration thoughts" §`src/horus/eda/`,
ADR-013 (16-field F1 truth table), ADR-024 (visualization stack).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from horus.config import ComplexityTierConfig
from horus.eda.zugferd_loader import (
    PROFILE_PATTERNS,
    _classify_extension,
    assign_complexity_tier,
    extract_country_codes_from_gt,
    field_value_present,
    gt_field_values,
    gt_has_any_field,
    line_item_count,
    profile_from_filename,
    walk,
)
from horus.eval.ground_truth import GroundTruth, GroundTruthField
from tests._corpus import (
    EINFACH_PDF,
    ZUGFERD_CORPUS_DIR,
    skip_if_no_corpus,
)

# ---------------------------------------------------------------------------
# Pure-function tests (no I/O, no corpus dependency).
# ---------------------------------------------------------------------------


# --- _classify_extension --------------------------------------------------


def test_classify_extension_collapses_cii_xml_to_xml() -> None:
    assert _classify_extension(Path("invoice.cii.xml")) == ".xml"
    assert _classify_extension(Path("invoice.ubl.xml")) == ".xml"
    assert _classify_extension(Path("plain.xml")) == ".xml"


def test_classify_extension_pdf_lowercased() -> None:
    assert _classify_extension(Path("INVOICE.PDF")) == ".pdf"
    assert _classify_extension(Path("invoice.pdf")) == ".pdf"


def test_classify_extension_other_falls_through() -> None:
    assert _classify_extension(Path("readme.txt")) == ".txt"
    assert _classify_extension(Path("noext")) == "(none)"


# --- profile_from_filename ------------------------------------------------


def test_profile_basicwl_precedes_basic_per_dict_order() -> None:
    """BUG-CATCH: BASICWL must be detected as BASICWL, not collapsed to BASIC.

    Pre-fix (the dict had BASIC checked before BASICWL with `BASIC(?:WL)?`),
    `Facture_DOM_BASICWL.pdf` matched the BASIC pattern and returned "BASIC",
    causing 6 false-positive route disagreements in §4. Phase A (the prior
    fix) made BASICWL its own pattern checked first; this test guards
    against accidental dict re-ordering during refactors.
    """
    assert profile_from_filename("ZUGFeRD_2p0_BASICWL_Einfach.pdf") == "BASICWL"
    assert profile_from_filename("Facture_DOM_BASICWL.pdf") == "BASICWL"
    # Space + hyphen variants seen in the corpus.
    assert profile_from_filename("ZUGFeRD_BASIC WL_Einfach.pdf") == "BASICWL"
    assert profile_from_filename("ZUGFeRD_BASIC-WL_Einfach.pdf") == "BASICWL"
    # Plain BASIC still matches BASIC (not BASICWL).
    assert profile_from_filename("ZUGFeRD_2p0_BASIC_Einfach.pdf") == "BASIC"


def test_profile_canonical_keys_match() -> None:
    assert profile_from_filename("foo_MINIMUM_bar.pdf") == "MINIMUM"
    assert profile_from_filename("foo_EN16931_bar.pdf") == "EN16931"
    assert profile_from_filename("foo_EXTENDED_bar.pdf") == "EXTENDED"
    assert profile_from_filename("foo_Erweitert_bar.pdf") == "EXTENDED"
    assert profile_from_filename("foo_XRECHNUNG_bar.pdf") == "XRECHNUNG"


def test_profile_returns_none_on_unknown_filename() -> None:
    assert profile_from_filename("random_invoice.pdf") is None
    assert profile_from_filename("ZUGFeRD_unknown_token.pdf") is None
    assert profile_from_filename("") is None


def test_profile_patterns_dict_iteration_order() -> None:
    """Lookup order is BASICWL, MINIMUM, BASIC, EN16931, EXTENDED, XRECHNUNG."""
    assert list(PROFILE_PATTERNS.keys()) == [
        "BASICWL",
        "MINIMUM",
        "BASIC",
        "EN16931",
        "EXTENDED",
        "XRECHNUNG",
    ]


# --- assign_complexity_tier -----------------------------------------------


def _default_complexity_config() -> ComplexityTierConfig:
    return ComplexityTierConfig(
        simple_max_pages=1,
        simple_max_line_items=5,
        medium_max_pages=3,
        medium_max_line_items=20,
    )


def test_complexity_tier_simple_when_under_simple_thresholds() -> None:
    cfg = _default_complexity_config()
    assert assign_complexity_tier(1, 5, cfg=cfg) == "simple"
    assert assign_complexity_tier(1, 1, cfg=cfg) == "simple"


def test_complexity_tier_medium_when_under_medium_thresholds() -> None:
    cfg = _default_complexity_config()
    assert assign_complexity_tier(2, 10, cfg=cfg) == "medium"
    assert assign_complexity_tier(3, 20, cfg=cfg) == "medium"


def test_complexity_tier_complex_when_over_medium() -> None:
    cfg = _default_complexity_config()
    assert assign_complexity_tier(4, 5, cfg=cfg) == "complex"
    assert assign_complexity_tier(2, 21, cfg=cfg) == "complex"
    assert assign_complexity_tier(10, 100, cfg=cfg) == "complex"


def test_complexity_tier_unknown_when_inputs_none() -> None:
    cfg = _default_complexity_config()
    assert assign_complexity_tier(None, 5, cfg=cfg) == "(unknown)"
    assert assign_complexity_tier(2, None, cfg=cfg) == "(unknown)"
    assert assign_complexity_tier(None, None, cfg=cfg) == "(unknown)"


# --- GroundTruth predicates -----------------------------------------------


def _make_gt_with(fields: dict[str, object]) -> GroundTruth:
    """Build a minimal GroundTruth with named fields populated.

    Builds `GroundTruthField` records using the real schema (`bt_code` /
    `raw_value` / `normalized_value` / `xpath` / `is_present`). Tests don't
    need real BT codes or XPaths; placeholder values keep the dataclass
    happy. The `is_present=True` + `normalized_value=None` combination is
    the canonical "present-but-normalizer-rejected" case per ADR-013.
    """
    header: dict[str, GroundTruthField] = {}
    for key, value in fields.items():
        header[key] = GroundTruthField(
            bt_code="BT-test",
            raw_value=str(value) if value is not None else None,
            normalized_value=str(value) if value is not None else None,
            xpath="/test/xpath",
            is_present=True,
        )
    return GroundTruth(header=header)


def test_gt_has_any_field_true_when_at_least_one_normalized() -> None:
    gt = _make_gt_with({"invoice_number": "INV-001"})
    assert gt_has_any_field(gt) is True


def test_gt_has_any_field_false_when_all_normalized_none() -> None:
    gt = _make_gt_with({"invoice_number": None, "issue_date": None})
    assert gt_has_any_field(gt) is False


def test_gt_has_any_field_false_when_gt_is_none() -> None:
    assert gt_has_any_field(None) is False


def test_gt_has_any_field_false_when_header_empty() -> None:
    gt = GroundTruth(header={})
    assert gt_has_any_field(gt) is False


def test_field_value_present_true_for_normalized() -> None:
    gt = _make_gt_with({"invoice_number": "INV-001"})
    assert field_value_present(gt, "invoice_number") is True


def test_field_value_present_false_for_missing_key() -> None:
    gt = _make_gt_with({"invoice_number": "INV-001"})
    assert field_value_present(gt, "buyer_vat_id") is False


def test_field_value_present_false_for_normalizer_rejected() -> None:
    """Per ADR-013: is_present=True + normalized_value=None → EXCLUDED."""
    gt = _make_gt_with({"invoice_number": None})
    assert field_value_present(gt, "invoice_number") is False


# --- gt_field_values ------------------------------------------------------


def test_gt_field_values_collects_non_none_values() -> None:
    gts = [
        _make_gt_with({"invoice_currency_code": "EUR"}),
        _make_gt_with({"invoice_currency_code": "GBP"}),
        _make_gt_with({"invoice_currency_code": None}),  # excluded
        _make_gt_with({"other_field": "x"}),  # missing key — excluded
    ]
    out = gt_field_values(gts, "invoice_currency_code")
    assert out == ["EUR", "GBP"]


def test_gt_field_values_empty_when_no_matches() -> None:
    gts = [_make_gt_with({"other_field": "x"})]
    assert gt_field_values(gts, "invoice_currency_code") == []


# --- extract_country_codes_from_gt ----------------------------------------


def test_country_codes_from_seller_and_buyer_vat() -> None:
    gt = _make_gt_with({"seller_vat_id": "DE123456789", "buyer_vat_id": "FR987654321"})
    assert extract_country_codes_from_gt(gt) == [
        ("seller", "DE"),
        ("buyer", "FR"),
    ]


def test_country_codes_skip_missing_vat_ids() -> None:
    gt = _make_gt_with({"seller_vat_id": "DE123456789"})
    assert extract_country_codes_from_gt(gt) == [("seller", "DE")]


def test_country_codes_skip_malformed_prefix() -> None:
    """Non-EU VAT formats (e.g., bare digits) lack the 2-letter prefix."""
    gt = _make_gt_with({"seller_vat_id": "1234567890", "buyer_vat_id": "DE123456789"})
    assert extract_country_codes_from_gt(gt) == [("buyer", "DE")]


def test_country_codes_empty_when_neither_present() -> None:
    gt = _make_gt_with({"invoice_number": "INV-001"})
    assert extract_country_codes_from_gt(gt) == []


# ---------------------------------------------------------------------------
# Corpus-aware tests (gated behind skip_if_no_corpus).
# ---------------------------------------------------------------------------


@skip_if_no_corpus
def test_walk_returns_dataframe_with_zugferd_columns() -> None:
    df = walk(ZUGFERD_CORPUS_DIR)
    expected_extra = {"is_pdf", "is_xml"}
    assert expected_extra.issubset(df.columns)
    assert df["is_pdf"].dtype == bool
    assert df["is_xml"].dtype == bool


@skip_if_no_corpus
def test_walk_collapses_cii_xml_to_xml() -> None:
    df = walk(ZUGFERD_CORPUS_DIR)
    cii_files = df[df["filename"].str.endswith(".cii.xml")]
    if len(cii_files) > 0:
        assert (cii_files["extension"] == ".xml").all()
        assert (cii_files["is_xml"]).all()
        assert (~cii_files["is_pdf"]).all()


@skip_if_no_corpus
def test_walk_finds_at_least_some_pdfs_and_xmls() -> None:
    df = walk(ZUGFERD_CORPUS_DIR)
    assert int(df["is_pdf"].sum()) > 0
    assert int(df["is_xml"].sum()) > 0


@skip_if_no_corpus
def test_get_page_count_on_einfach_pdf() -> None:
    """EN16931_Einfach.pdf is a 2-page invoice (canonical fixture).

    Verified empirically on 2026-05-25: the canonical pilot-13 fixture
    has 2 pages (page 1 = invoice header + line items; page 2 = footer
    / payment terms continuation). Used as a smoke check that
    pypdfium2 returns a sensible page count on a known-good fixture.
    """
    from horus.eda.zugferd_loader import get_page_count

    n = get_page_count(EINFACH_PDF)
    assert n == 2


def test_get_page_count_returns_none_for_missing_file(tmp_path: Path) -> None:
    """Failure path: missing file → None (not raised)."""
    from horus.eda.zugferd_loader import get_page_count

    missing = tmp_path / "does-not-exist.pdf"
    assert get_page_count(missing) is None


def test_line_item_count_returns_none_for_none_xml() -> None:
    assert line_item_count(None) is None


def test_line_item_count_returns_none_for_malformed_xml() -> None:
    assert line_item_count(b"<not valid xml") is None


@skip_if_no_corpus
def test_extract_xml_and_level_on_einfach_pdf() -> None:
    """Canonical fixture is EN16931 v2; expect non-None xml_bytes + flavor."""
    from horus.eda.zugferd_loader import extract_xml_and_level

    xml_bytes, flavor, level = extract_xml_and_level(EINFACH_PDF)
    assert xml_bytes is not None
    assert flavor in {"factur-x", "zugferd", "order-x", None}
    assert level is not None


def test_extract_xml_and_level_returns_none_tuple_for_missing_file(
    tmp_path: Path,
) -> None:
    from horus.eda.zugferd_loader import extract_xml_and_level

    missing = tmp_path / "nope.pdf"
    xml, flavor, level = extract_xml_and_level(missing)
    assert (xml, flavor, level) == (None, None, None)


def test_parse_one_gt_returns_none_for_none_input() -> None:
    from horus.eda.zugferd_loader import parse_one_gt

    assert parse_one_gt(None) is None


def test_parse_one_gt_returns_empty_gt_for_non_cii_xml() -> None:
    """Non-CII XML parses cleanly into an EMPTY GroundTruth (not None).

    `parse_cii_xml` is graceful with non-matching XPaths — it returns a
    GroundTruth with all 16 fields present-as-absent (`is_present=False`,
    `normalized_value=None`). Callers distinguish this from a real GT via
    `gt_has_any_field()` rather than checking for None.

    `parse_one_gt` returns None ONLY on actual exceptions (e.g.,
    well-formed XML that triggers a parser bug). The intentional design
    is that ZUGFeRDv1-namespace inputs (which DO parse but match 0 v2
    XPaths) flow through the same code path as malformed XML.
    """
    from horus.eda.zugferd_loader import gt_has_any_field, parse_one_gt

    gt = parse_one_gt(b"<not-cii/>")
    # Returns a GroundTruth, not None.
    assert gt is not None
    # But the GT is empty (no field has a non-None normalized_value).
    assert gt_has_any_field(gt) is False


def test_parse_one_gt_returns_none_for_malformed_xml_bytes() -> None:
    """Truly malformed XML bytes (lxml parser error) → None."""
    from horus.eda.zugferd_loader import parse_one_gt

    # Unclosed tag — lxml.etree.fromstring raises XMLSyntaxError.
    assert parse_one_gt(b"<not valid xml") is None


@skip_if_no_corpus
def test_parse_one_gt_yields_meaningful_gt_for_einfach_pdf() -> None:
    """End-to-end: extract XML from PDF + parse to GroundTruth + verify
    at least 1 field is non-None (the parser-meaningful predicate).
    """
    from horus.eda.zugferd_loader import (
        extract_xml_and_level,
        gt_has_any_field,
        parse_one_gt,
    )

    xml_bytes, _, _ = extract_xml_and_level(EINFACH_PDF)
    gt = parse_one_gt(xml_bytes)
    assert gt is not None
    assert gt_has_any_field(gt)


def test_assign_complexity_tier_uses_provided_cfg() -> None:
    """Verify cfg threshold values are honored (not hardcoded)."""
    cfg_strict = ComplexityTierConfig(
        simple_max_pages=1,
        simple_max_line_items=2,
        medium_max_pages=2,
        medium_max_line_items=5,
    )
    cfg_loose = ComplexityTierConfig(
        simple_max_pages=5,
        simple_max_line_items=50,
        medium_max_pages=10,
        medium_max_line_items=100,
    )
    # Same input → different tier under different configs.
    assert assign_complexity_tier(2, 5, cfg=cfg_strict) == "medium"
    assert assign_complexity_tier(2, 5, cfg=cfg_loose) == "simple"


def test_pure_function_imports_dont_require_corpus() -> None:
    """Module imports + pure functions must work without corpus on disk.

    Guards against accidental file-side-effect-at-import-time bugs
    (matters for CI, where ADR-023 corpus tests skip via skipif).
    """
    # The mock here is just to assert the module loads + this test runs.
    mock = MagicMock()
    mock.assert_not_called()
    assert profile_from_filename("EN16931.pdf") == "EN16931"
