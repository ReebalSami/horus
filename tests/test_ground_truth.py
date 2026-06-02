"""Tests for `horus.eval.ground_truth` — CII XML → ground-truth dict (ADR-012).

Covers the 11 test cases declared in the PR(a) plan:

1. `test_parse_einfach_smoke`                          — end-to-end on canonical fixture
2. `test_buyer_vat_id_absent_in_einfach`               — tristate "absent" path
3. `test_three_route_dict_equivalence_einfach`         — factur-x ↔ FeRD sidecar ↔ Mustang
4. `test_two_route_dict_equivalence_full_corpus`       — parametrized over all paired invoices
5. `test_normalization_dates`                          — format codes 102 / 203 / 204
6. `test_normalization_money`                          — 2-decimal canonical + sign preservation
7. `test_normalization_strings`                        — NFC + whitespace handling
8. `test_fields_registry_consistency`                  — all 16 rows well-formed
9. `test_fields_registry_xpath_executable`             — XPaths compile against CII_NAMESPACES
10. `test_ground_truth_dataclass_forward_compat`       — wrapper dataclass shape proven
11. `test_tristate_semantics`                          — absent vs present-empty distinction

Run via: `uv run pytest tests/test_ground_truth.py`

Refs: ADR-012 (this), ADR-010 (XML extraction substrate), ADR-009 Amendment 1,
issue #13 (pilot #13 parent), arXiv 2510.15727 §3.4.
"""

from __future__ import annotations

import unicodedata
from dataclasses import fields as dataclass_fields
from pathlib import Path

import pytest
from lxml import etree

from horus.eval import (
    CII_NAMESPACES,
    FIELDS,
    GroundTruth,
    GroundTruthField,
    parse_cii_xml,
)
from horus.eval.ground_truth import (
    CII_NAMESPACES_V1,
    FIELDS_V1,
    _normalize_date,
    _normalize_money,
    _normalize_string,
    _passthrough,
)
from tests._corpus import skip_if_no_corpus, skip_if_no_v1_corpus
from tests.conftest import (
    EINFACH_CII,
    EINFACH_PDF,
    REPO_ROOT,
    V1_COMFORT_PDF,
    ZUGFERD_CII_DIR,
)

# ADR-023: every test in this module requires the ZUGFeRD corpus on disk
# (parses real EINFACH_CII + EINFACH_PDF + iterates ZUGFERD_CII_DIR).
# Skips automatically when the corpus is absent (CI or fresh dev clone).
pytestmark = skip_if_no_corpus

# ---------------------------------------------------------------------------
# Smoke-fixture-specific expected values (verified against PDF + XML eye-check)
# ---------------------------------------------------------------------------

EINFACH_EXPECTED: dict[str, tuple[str, str]] = {
    # english_key: (raw_value, normalized_value)
    "invoice_number": ("471102", "471102"),
    "issue_date": ("20180305", "2018-03-05"),
    "invoice_currency_code": ("EUR", "EUR"),
    "delivery_date": ("20180305", "2018-03-05"),
    "seller_name": ("Lieferant GmbH", "Lieferant GmbH"),
    "seller_vat_id": ("DE123456789", "DE123456789"),
    "seller_tax_id": ("201/113/40209", "201/113/40209"),
    "seller_gln": ("4000001123452", "4000001123452"),
    "buyer_name": ("Kunden AG Mitte", "Kunden AG Mitte"),
    "buyer_reference": ("GE2020211", "GE2020211"),
    # buyer_vat_id deliberately absent — see test_buyer_vat_id_absent_in_einfach
    "line_total_amount": ("473.00", "473.00"),
    "tax_basis_total_amount": ("473.00", "473.00"),
    "tax_total_amount": ("56.87", "56.87"),
    "grand_total_amount": ("529.87", "529.87"),
    "due_payable_amount": ("529.87", "529.87"),
}


# ---------------------------------------------------------------------------
# 1. Smoke test — parse Einfach end-to-end
# ---------------------------------------------------------------------------


def test_parse_einfach_smoke() -> None:
    """Parse `EN16931_Einfach.cii.xml` → 16-key dict; spot-check 15 present fields."""
    assert EINFACH_CII.exists(), f"Test fixture missing: {EINFACH_CII}"

    xml_bytes = EINFACH_CII.read_bytes()
    gt = parse_cii_xml(xml_bytes)

    assert isinstance(gt, GroundTruth)
    assert set(gt.header.keys()) == set(FIELDS.keys()), (
        f"Result keys diverge from FIELDS registry. "
        f"Missing: {set(FIELDS.keys()) - set(gt.header.keys())}; "
        f"Extra: {set(gt.header.keys()) - set(FIELDS.keys())}"
    )

    # Spot-check every present field against the verified-by-eye expected values.
    for key, (expected_raw, expected_norm) in EINFACH_EXPECTED.items():
        rec = gt.header[key]
        assert rec.is_present, f"Field {key} should be present in Einfach"
        assert rec.raw_value == expected_raw, (
            f"Field {key}: raw_value mismatch. Expected {expected_raw!r}, got {rec.raw_value!r}"
        )
        assert rec.normalized_value == expected_norm, (
            f"Field {key}: normalized_value mismatch. "
            f"Expected {expected_norm!r}, got {rec.normalized_value!r}"
        )


# ---------------------------------------------------------------------------
# 2. Tristate "absent" path — buyer_vat_id is missing from Einfach
# ---------------------------------------------------------------------------


def test_buyer_vat_id_absent_in_einfach() -> None:
    """`buyer_vat_id` (BT-48) is absent in Einfach → is_present=False, both values None.

    This exercises the tristate "absent" path. The Einfach fixture is a
    domestic German B2B invoice; BT-48 is only mandatory for cross-border EU
    transactions, so the FeRD-shipped XML omits it. The parser must return
    a `GroundTruthField` with `is_present=False`, `raw_value=None`, and
    `normalized_value=None` — NOT skip the key entirely (the dict shape is
    always all 16 keys; presence is signaled by the flag).
    """
    gt = parse_cii_xml(EINFACH_CII.read_bytes())
    rec = gt.header["buyer_vat_id"]

    assert rec.is_present is False, "buyer_vat_id should be ABSENT in Einfach (no BT-48 in XML)"
    assert rec.raw_value is None
    assert rec.normalized_value is None
    assert rec.bt_code == "BT-48"
    # The xpath provenance is preserved even on absence — useful for debugging
    # "why did this field come back missing?" questions.
    assert rec.xpath, "xpath provenance must be preserved on absent fields"


# ---------------------------------------------------------------------------
# 3. Three-route dict-equivalence on the smoke fixture
# ---------------------------------------------------------------------------


def _has_mustang_jar() -> bool:
    return bool(list(REPO_ROOT.glob("tools/mustangproject/Mustang-CLI-*.jar")))


def test_three_route_dict_equivalence_einfach() -> None:
    """`parse(facturx_route) == parse(ferd_route) == parse(mustang_route)` for Einfach.

    Stronger than ADR-010 Probe 2 (which proved C14N2-byte-equivalence on
    raw XML): this proves the **parser is route-invariant** at the
    `GroundTruth` level. The three routes are:

      - factur-x — `facturx.get_xml_from_pdf(pdf_bytes)` returns the embedded
        attachment as bytes
      - FeRD sidecar — read `<pdf-stem>.cii.xml` directly from the corpus
      - Mustang — independent JVM extraction via the CLI

    Skipped on the Mustang leg if the JAR isn't fetched (`make mustang-jar`);
    the two-route equality (factur-x ↔ FeRD) always runs.
    """
    import facturx  # noqa: PLC0415 — lazy: only this test needs it

    # Route 1: factur-x extraction from the PDF
    _name, facturx_bytes = facturx.get_xml_from_pdf(
        EINFACH_PDF.read_bytes(), check_xsd=True, check_schematron=True
    )
    gt_facturx = parse_cii_xml(facturx_bytes)

    # Route 2: FeRD-shipped CII sidecar
    ferd_bytes = EINFACH_CII.read_bytes()
    gt_ferd = parse_cii_xml(ferd_bytes)

    assert gt_facturx == gt_ferd, (
        "factur-x extraction and FeRD sidecar produced different GroundTruth dicts. "
        "ADR-010 Probe 2 proved C14N2 byte-equivalence on raw XML; this would mean "
        "the parser introduces route-dependent state — investigate"
    )

    # Route 3: Mustang CLI extraction (skipped if JAR absent)
    if not _has_mustang_jar():
        pytest.skip("Mustang JAR not present — run `make mustang-jar` to enable")

    from scripts.extract_zugferd_xml import (  # noqa: PLC0415
        extract_via_mustang,
        find_mustang_jar,
    )

    jar = find_mustang_jar()
    assert jar is not None  # narrow type for mypy
    mustang_bytes = extract_via_mustang(EINFACH_PDF, jar)
    gt_mustang = parse_cii_xml(mustang_bytes)

    assert gt_facturx == gt_mustang, (
        "factur-x extraction and Mustang extraction produced different GroundTruth "
        "dicts. Both routes should yield byte-identical XML (per ADR-010 Probe 1); "
        "if the parser disagrees, the divergence is in the parsing code"
    )
    assert gt_ferd == gt_mustang  # transitive sanity


# ---------------------------------------------------------------------------
# 4. Two-route dict-equivalence across the full corpus (parametrized)
# ---------------------------------------------------------------------------


def test_two_route_dict_equivalence_en16931_corpus(
    en16931_paired_invoice: tuple[Path, Path],
) -> None:
    """For every EN16931-profile paired invoice (22 fixtures):
    `parse(facturx_route) == parse(ferd_route)`.

    Parametrized via `pytest_generate_tests` in `conftest.py` — produces one
    test item per `(pdf, cii_sidecar)` pair, filtered to the EN16931_*-prefixed
    invoices (the 22 fixtures in `FX/` that follow the EN16931 profile). The
    4 XRECHNUNG fixtures are covered by `test_xrechnung_documented_divergence`
    below — their FeRD sidecars carry a later corpus revision than the embedded
    XMLs (see ADR-012 §"Negative findings" for the forensic detail).

    The Mustang leg is omitted from the parametrized sweep (would require
    JVM startup × 22 = slow); the three-route check on the smoke fixture is
    the sufficient evidence for `parse(mustang) == parse(facturx)` per
    ADR-010 §"Empirical evidence" Probe 1.
    """
    pdf_path, cii_path = en16931_paired_invoice
    import facturx  # noqa: PLC0415

    _, facturx_bytes = facturx.get_xml_from_pdf(
        pdf_path.read_bytes(), check_xsd=False, check_schematron=False
    )
    gt_facturx = parse_cii_xml(facturx_bytes)
    gt_ferd = parse_cii_xml(cii_path.read_bytes())

    assert gt_facturx == gt_ferd, (
        f"Route divergence on {pdf_path.name}: factur-x-extracted vs FeRD sidecar "
        f"produce different GroundTruth dicts. Investigate which fields differ."
    )

    # Sanity: result has all 16 keys, all GroundTruthField instances
    assert set(gt_facturx.header.keys()) == set(FIELDS.keys())
    for rec in gt_facturx.header.values():
        assert isinstance(rec, GroundTruthField)


def test_xrechnung_documented_divergence(
    xrechnung_paired_invoice: tuple[Path, Path],
) -> None:
    """For every XRECHNUNG-profile paired invoice (4 fixtures): both routes parse
    to a well-formed 16-key dict, but `issue_date` and `delivery_date` are
    expected to diverge (corpus artifact — see ADR-012 §"Negative findings").

    Forensic finding (captured at PR(a) authoring): the FeRD-shipped `.cii.xml`
    sidecars for the 4 XRECHNUNG fixtures were revised in a later corpus
    update (all 4 sidecar `issue_date` values normalize to "2024-11-15") while
    the PDF-embedded `xrechnung.xml` attachments still carry the original
    2018 dates. The corpus README does not document the date offset; this
    test pins our observed divergence pattern so future corpus updates that
    re-align the routes will surface as test changes rather than silent drift.

    The 14 NON-date fields ARE expected to remain route-equal across the 4
    XRECHNUNG fixtures — divergence is limited to `issue_date` + `delivery_date`.
    """
    pdf_path, cii_path = xrechnung_paired_invoice
    import facturx  # noqa: PLC0415

    _, facturx_bytes = facturx.get_xml_from_pdf(
        pdf_path.read_bytes(), check_xsd=False, check_schematron=False
    )
    gt_facturx = parse_cii_xml(facturx_bytes)
    gt_ferd = parse_cii_xml(cii_path.read_bytes())

    # Both routes produce well-formed 16-key dicts
    assert set(gt_facturx.header.keys()) == set(FIELDS.keys())
    assert set(gt_ferd.header.keys()) == set(FIELDS.keys())

    # Non-date fields ARE route-equal (the corpus drift is dates-only)
    non_date_keys = {k for k in FIELDS if k not in {"issue_date", "delivery_date"}}
    for key in non_date_keys:
        assert gt_facturx.header[key] == gt_ferd.header[key], (
            f"XRECHNUNG corpus drift: non-date field {key} also diverges on "
            f"{pdf_path.name}. Expected ONLY issue_date + delivery_date to differ. "
            f"factur-x={gt_facturx.header[key]!r}, "
            f"FeRD={gt_ferd.header[key]!r}"
        )

    # The date fields diverge — pin the documented pattern: all FeRD sidecars
    # for XRECHNUNG fixtures normalize `issue_date` to "2024-11-15"
    ferd_issue = gt_ferd.header["issue_date"]
    assert ferd_issue.is_present
    assert ferd_issue.normalized_value == "2024-11-15", (
        f"XRECHNUNG corpus assumption broken: FeRD sidecar for {pdf_path.name} "
        f"has issue_date={ferd_issue.normalized_value!r}, expected '2024-11-15'. "
        f"The FeRD corpus may have been updated; revisit ADR-012 §'Negative findings'"
    )


# ---------------------------------------------------------------------------
# 5. Date normalization — format codes 102 / 203 / 204
# ---------------------------------------------------------------------------


def test_normalization_dates() -> None:
    """`_normalize_date` handles CCYYMMDD prefix; format codes 102 / 203 / 204."""
    # Format code "102": CCYYMMDD (8 digits) — the corpus standard
    assert _normalize_date("20180305") == "2018-03-05"
    assert _normalize_date("19990101") == "1999-01-01"
    assert _normalize_date("20261231") == "2026-12-31"

    # Format code "203": CCYYMMDDHHMM (12 digits) — time component dropped
    assert _normalize_date("201803051430") == "2018-03-05"

    # Format code "204": CCYYMMDDHHMMSS (14 digits) — time component dropped
    assert _normalize_date("20180305143055") == "2018-03-05"

    # Whitespace tolerance
    assert _normalize_date("  20180305  ") == "2018-03-05"

    # Invalid inputs
    with pytest.raises(ValueError, match="too short"):
        _normalize_date("2018")
    with pytest.raises(ValueError, match="not 8 digits"):
        _normalize_date("abcdefgh")
    with pytest.raises(ValueError, match="not 8 digits"):
        _normalize_date("2018-03-05")  # already has separators — prefix is "2018-03-"


# ---------------------------------------------------------------------------
# 6. Money normalization — canonical 2-decimal + sign preservation
# ---------------------------------------------------------------------------


def test_normalization_money() -> None:
    """`_normalize_money` quantizes to 2 decimals, preserves sign."""
    # Canonical-as-shipped 2-decimal values
    assert _normalize_money("473.00") == "473.00"
    assert _normalize_money("56.87") == "56.87"
    assert _normalize_money("529.87") == "529.87"

    # Trailing-zero precision normalization
    assert _normalize_money("9.9000") == "9.90"
    assert _normalize_money("100.0") == "100.00"

    # Sign preservation (the `EN16931_Einfach_negativePaymentDue` fixture has
    # a negative `DuePayableAmount`)
    assert _normalize_money("-100.00") == "-100.00"
    assert _normalize_money("-0.01") == "-0.01"

    # Integer input → 2-decimal output
    assert _normalize_money("0") == "0.00"
    assert _normalize_money("42") == "42.00"

    # Banker's rounding (ROUND_HALF_EVEN — Decimal default)
    assert _normalize_money("0.125") == "0.12"  # rounds to even
    assert _normalize_money("0.135") == "0.14"  # rounds to even

    # Whitespace tolerance
    assert _normalize_money("  529.87  ") == "529.87"

    # Invalid inputs
    with pytest.raises(ValueError, match="not parseable as Decimal"):
        _normalize_money("not a number")


def test_normalization_money_sign_preserved_on_negative_due_fixture() -> None:
    """End-to-end: the `negativePaymentDue` fixture should parse with sign preserved."""
    cii_path = ZUGFERD_CII_DIR / "EN16931_Einfach_negativePaymentDue.cii.xml"
    assert cii_path.exists(), f"Test fixture missing: {cii_path}"

    gt = parse_cii_xml(cii_path.read_bytes())
    due = gt.header["due_payable_amount"]

    assert due.is_present, "due_payable_amount must be present in negativePaymentDue fixture"
    assert due.normalized_value is not None
    # Sign preserved through the full pipeline
    assert due.normalized_value.startswith("-"), (
        f"due_payable_amount in negativePaymentDue fixture should be negative, "
        f"got {due.normalized_value!r}"
    )


# ---------------------------------------------------------------------------
# 7. String normalization — NFC + outer whitespace strip + internal preserved
# ---------------------------------------------------------------------------


def test_normalization_strings() -> None:
    """`_normalize_string` applies NFC + strips outer whitespace + preserves internal."""
    # NFC: combining diacritic → composed form (München)
    nfd_form = "Mu\u0308nchen"  # M + u + combining diaeresis
    nfc_form = "M\u00fcnchen"  # M + ü (precomposed)
    assert _normalize_string(nfd_form) == nfc_form
    assert _normalize_string(nfc_form) == nfc_form  # idempotent

    # Internal whitespace preserved
    assert _normalize_string("Lieferant GmbH") == "Lieferant GmbH"
    assert _normalize_string("Kunden AG Mitte") == "Kunden AG Mitte"

    # Outer whitespace stripped
    assert _normalize_string("  Lieferant GmbH  ") == "Lieferant GmbH"
    assert _normalize_string("\tLieferant\n") == "Lieferant"

    # Internal newlines/tabs preserved (rare in CII but possible)
    assert _normalize_string("Line 1\nLine 2") == "Line 1\nLine 2"

    # Empty / whitespace-only input
    assert _normalize_string("") == ""
    assert _normalize_string("   ") == ""

    # Confirm NFC output property
    out = _normalize_string("café")  # may be NFC or NFD depending on source
    assert unicodedata.is_normalized("NFC", out)


def test_normalization_passthrough() -> None:
    """`_passthrough` strips outer whitespace only; preserves case + internal structure."""
    assert _passthrough("EUR") == "EUR"
    assert _passthrough("USD") == "USD"
    assert _passthrough("  EUR  ") == "EUR"
    # Case preserved (don't lowercase)
    assert _passthrough("eur") == "eur"
    # Internal whitespace preserved (rare for code-list values but possible)
    assert _passthrough("A B") == "A B"


# ---------------------------------------------------------------------------
# 8. FIELDS registry consistency
# ---------------------------------------------------------------------------


def test_fields_registry_consistency() -> None:
    """All 19 FIELDS rows: unique BT codes, unique english_keys, well-formed metadata."""
    assert len(FIELDS) == 19, f"Expected 19 fields, found {len(FIELDS)}"

    english_keys = list(FIELDS.keys())
    assert len(set(english_keys)) == 19, "Duplicate english_keys in FIELDS"

    bt_codes = [spec.bt_code for spec in FIELDS.values()]
    assert len(set(bt_codes)) == 19, f"Duplicate BT codes in FIELDS: {bt_codes}"

    for english_key, spec in FIELDS.items():
        # Internal consistency: dict key matches FieldSpec.english_key
        assert spec.english_key == english_key, (
            f"FIELDS[{english_key!r}] has mismatched english_key={spec.english_key!r}"
        )
        assert spec.bt_code, f"FIELDS[{english_key!r}].bt_code is empty"
        # BT- for business terms; BG- for the ADR-035 address business groups (BG-5/BG-8).
        assert spec.bt_code.startswith(("BT-", "BG-")), (
            f"FIELDS[{english_key!r}].bt_code does not start with 'BT-'/'BG-': {spec.bt_code!r}"
        )
        assert spec.german_label, f"FIELDS[{english_key!r}].german_label is empty"
        assert spec.xpath, f"FIELDS[{english_key!r}].xpath is empty"
        assert spec.xpath.startswith("/rsm:"), (
            f"FIELDS[{english_key!r}].xpath should start with /rsm: root, got {spec.xpath!r}"
        )
        # XPath should NOT end with /text() — our parser reads element.text
        # (per ADR-012: distinguishes absent vs present-but-empty)
        assert not spec.xpath.rstrip().endswith("/text()"), (
            f"FIELDS[{english_key!r}].xpath ends with /text() — should end at the "
            f"element so the parser can read .text for tristate semantics"
        )
        assert callable(spec.normalize), f"FIELDS[{english_key!r}].normalize is not callable"
        # field_type added per ADR-013 (PR(b) scorer dispatch). Every row must
        # tag its comparator-dispatch type explicitly — no default; the
        # `FieldType` Literal in ground_truth.py is the closed taxonomy.
        assert spec.field_type in ("STRING", "MONEY", "DATE", "CODE", "RATE"), (
            f"FIELDS[{english_key!r}].field_type={spec.field_type!r} is not one of "
            f"STRING/MONEY/DATE/CODE/RATE (the closed FieldType taxonomy)"
        )


def test_fields_registry_field_type_consistency() -> None:
    """Every FIELDS row carries a valid `field_type` from the closed `FieldType` taxonomy.

    Closed taxonomy per ADR-013: STRING / MONEY / DATE / CODE. No defaults
    — the FieldSpec dataclass declares `field_type` without a default so a
    forgotten tag is a construction-time TypeError, not a silent fallthrough.
    """
    for english_key, spec in FIELDS.items():
        assert spec.field_type in ("STRING", "MONEY", "DATE", "CODE", "RATE"), (
            f"FIELDS[{english_key!r}].field_type={spec.field_type!r} is outside the closed taxonomy"
        )


def test_money_fields_are_exactly_the_five_totals() -> None:
    """`field_type='MONEY'` ↔ exactly the 5 EN16931-mandatory totals (BT-106/109/110/112/115).

    Locks the comparator dispatch table: PR(b)'s scorer applies
    `_normalize_predicted_money` + exact-match (Decimal-cent strict, per
    Vorsteuerabzug requirement) exactly to these five fields. Any drift
    here is a load-bearing change to legal-correctness semantics.
    """
    money_keys = {k for k, spec in FIELDS.items() if spec.field_type == "MONEY"}
    expected = {
        "line_total_amount",  # BT-106
        "tax_basis_total_amount",  # BT-109
        "tax_total_amount",  # BT-110
        "grand_total_amount",  # BT-112
        "due_payable_amount",  # BT-115
    }
    assert money_keys == expected, (
        f"MONEY fields drifted from expected 5 totals. Got {sorted(money_keys)}, "
        f"expected {sorted(expected)}. Update this test AND ADR-013 §Decision if the "
        f"comparator dispatch is intentionally changing."
    )


def test_date_fields_are_exactly_issue_and_delivery() -> None:
    """`field_type='DATE'` ↔ exactly `issue_date` (BT-2) + `delivery_date` (BT-72).

    Locks the comparator dispatch table for DATE: PR(b)'s scorer applies
    `_normalize_predicted_date` (parses DD.MM.YYYY / German-month-name /
    ISO / US-slash) then exact-compares ISO strings. Only these two fields
    are date-typed in the 16-field scope; line-item dates land via BG-25
    in a future amendment.
    """
    date_keys = {k for k, spec in FIELDS.items() if spec.field_type == "DATE"}
    expected = {"issue_date", "delivery_date"}
    assert date_keys == expected, (
        f"DATE fields drifted from expected (issue_date, delivery_date). "
        f"Got {sorted(date_keys)}, expected {sorted(expected)}."
    )


def test_string_fields_are_names_and_addresses() -> None:
    """`field_type='STRING'` ↔ exactly `seller_name` (BT-27) + `buyer_name` (BT-44).

    These are the only fields where ANLS\\* tolerance applies — names tolerate
    OCR character errors. Codes, dates, and money are strict. Locks the
    cross-product invariant: STRING fields use ANLS\\* (Biten+ ICCV'19); all
    others use exact-on-normalized.
    """
    string_keys = {k for k, spec in FIELDS.items() if spec.field_type == "STRING"}
    expected = {"seller_name", "buyer_name", "seller_address", "buyer_address"}
    assert string_keys == expected, (
        f"STRING fields drifted from expected names + addresses. "
        f"Got {sorted(string_keys)}, expected {sorted(expected)}."
    )


def test_code_fields_cover_the_remaining_seven() -> None:
    """`field_type='CODE'` covers the 7 strict-equality fields (IDs / currency / refs).

    Closure assertion: STRING (2) + MONEY (5) + DATE (2) + CODE (7) = 16.
    If new fields land via FIELDS amendment without a corresponding
    field_type tag, this closure check fails before the comparator dispatch
    silently mis-routes.
    """
    code_keys = {k for k, spec in FIELDS.items() if spec.field_type == "CODE"}
    expected = {
        "invoice_number",  # BT-1
        "invoice_currency_code",  # BT-5
        "seller_vat_id",  # BT-31
        "seller_tax_id",  # BT-32
        "seller_gln",  # BT-29
        "buyer_reference",  # BT-46
        "buyer_vat_id",  # BT-48
    }
    assert code_keys == expected, (
        f"CODE fields drifted from expected 7. Got {sorted(code_keys)}, "
        f"expected {sorted(expected)}."
    )

    # Closure: STRING(4) + MONEY(5) + DATE(2) + CODE(7) + RATE(1) = 19 (ADR-035)
    by_type: dict[str, int] = {"STRING": 0, "MONEY": 0, "DATE": 0, "CODE": 0, "RATE": 0}
    for spec in FIELDS.values():
        by_type[spec.field_type] += 1
    assert by_type == {"STRING": 4, "MONEY": 5, "DATE": 2, "CODE": 7, "RATE": 1}, (
        f"FieldType partition drift: {by_type}. Expected STRING=4, MONEY=5, "
        f"DATE=2, CODE=7, RATE=1 (total 19)."
    )


def test_fields_registry_xpath_executable() -> None:
    """Every FIELDS XPath compiles syntactically against CII_NAMESPACES.

    Uses `etree.XPath` to validate the expression at compile time without
    needing a runtime invoice. Catches typos (e.g., mismatched brackets,
    unknown prefixes) at the registry boundary.
    """
    for english_key, spec in FIELDS.items():
        try:
            etree.XPath(spec.xpath, namespaces=CII_NAMESPACES)
        except etree.XPathSyntaxError as exc:
            pytest.fail(
                f"FIELDS[{english_key!r}].xpath does not compile against "
                f"CII_NAMESPACES: {spec.xpath!r}: {exc}"
            )


# ---------------------------------------------------------------------------
# 9. GroundTruth dataclass — forward-compat for line items
# ---------------------------------------------------------------------------


def test_ground_truth_dataclass_forward_compat() -> None:
    """`GroundTruth` is a frozen dataclass with a `header` field.

    Proves the forward-compatibility shape: a future amendment adding
    `line_items: list[LineItemGT] | None = None` is a non-breaking change.
    Existing call sites only access `.header`; the future field will default
    to None and not affect equality semantics for pilot #13.

    See ADR-012 §"What this ADR does NOT decide" for the forward-compat clause.
    """
    from dataclasses import FrozenInstanceError  # noqa: PLC0415

    # Frozen — assignment after construction raises FrozenInstanceError
    sample = GroundTruth(header={})
    with pytest.raises(FrozenInstanceError):
        # Type-ignore: the test deliberately violates the frozen contract to
        # prove the runtime enforcement; mypy correctly objects at compile time.
        sample.header = {}  # type: ignore[misc]

    # Has exactly one field today, named "header"
    fields = dataclass_fields(GroundTruth)
    field_names = [f.name for f in fields]
    assert "header" in field_names, "GroundTruth must expose a `header` field"

    # Can construct with only the header arg — confirms a future optional
    # `line_items` field could be added without breaking this call shape
    parsed = parse_cii_xml(EINFACH_CII.read_bytes())
    assert isinstance(parsed, GroundTruth)
    assert parsed.header is not None
    assert len(parsed.header) == 19

    # Equality semantics work: two parses of the same XML produce equal dicts
    parsed_again = parse_cii_xml(EINFACH_CII.read_bytes())
    assert parsed == parsed_again, "Parser must be deterministic"


# ---------------------------------------------------------------------------
# 10. Tristate value semantics — absent vs present-but-empty vs present
# ---------------------------------------------------------------------------


# Minimal CII XML with an empty (`<ram:Name/>`) seller_name element. Used to
# exercise the present-but-empty path in `test_tristate_semantics_present_but_empty`.
# All other fields are absent — tests the parser's behavior on a sparsely-
# populated XML rather than a fully-realistic invoice.
_MINIMAL_CII_EMPTY_SELLER_NAME = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument>
    <ram:ID>TEST-001</ram:ID>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name></ram:Name>
      </ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""


def test_tristate_semantics_absent() -> None:
    """Absent field: `is_present=False`, `raw_value=None`, `normalized_value=None`."""
    gt = parse_cii_xml(_MINIMAL_CII_EMPTY_SELLER_NAME.encode("utf-8"))

    # buyer_name was never in the minimal XML
    rec = gt.header["buyer_name"]
    assert rec.is_present is False
    assert rec.raw_value is None
    assert rec.normalized_value is None


def test_tristate_semantics_present_but_empty() -> None:
    """Present-but-empty: `is_present=True`, `raw_value=""`, `normalized_value=""`.

    The minimal XML above has `<ram:Name></ram:Name>` (seller_name element
    present, no text content). The parser must distinguish this from absence:
    the element WAS present → `is_present=True`, but its text was empty →
    `raw_value=""` and `normalized_value=""` (normalizer is short-circuited
    to avoid spurious ValueError on legitimately-empty elements).
    """
    gt = parse_cii_xml(_MINIMAL_CII_EMPTY_SELLER_NAME.encode("utf-8"))

    rec = gt.header["seller_name"]
    assert rec.is_present is True, "<ram:Name></ram:Name> should produce is_present=True, not False"
    assert rec.raw_value == "", f"Expected raw_value='', got {rec.raw_value!r}"
    assert rec.normalized_value == "", f"Expected normalized_value='', got {rec.normalized_value!r}"


def test_tristate_semantics_present_with_value() -> None:
    """Present with content: `is_present=True`, both raw and normalized are non-empty."""
    gt = parse_cii_xml(_MINIMAL_CII_EMPTY_SELLER_NAME.encode("utf-8"))

    rec = gt.header["invoice_number"]
    assert rec.is_present is True
    assert rec.raw_value == "TEST-001"
    assert rec.normalized_value == "TEST-001"


# ---------------------------------------------------------------------------
# 12. ZUGFeRD v1 (CrossIndustryDocument) support — #75 / ADR-033
# ---------------------------------------------------------------------------
#
# ZUGFeRD 1.0 (FeRD 2014) uses the older `CrossIndustryDocument` root + the
# :12 / :15 ram/udt namespaces. `parse_cii_xml` auto-detects the schema by
# root element and selects `FIELDS_V1` / `CII_NAMESPACES_V1`. The 16 EN16931
# leaf paths are identical to v2; only 7 container element names + the
# namespace URNs differ.
#
# Expected values verified by extracting the embedded `ZUGFeRD-invoice.xml`
# from the real v1 COMFORT fixture — the v1 rendering of the SAME canonical
# FeRD example invoice as `EN16931_Einfach` (v2). Note the 2013 dates (the
# 2014-era v1.0 sample) vs the v2 fixture's 2018 dates.
V1_COMFORT_EXPECTED: dict[str, tuple[str, str]] = {
    "invoice_number": ("471102", "471102"),
    "issue_date": ("20130305", "2013-03-05"),
    "invoice_currency_code": ("EUR", "EUR"),
    "delivery_date": ("20130305", "2013-03-05"),
    "seller_name": ("Lieferant GmbH", "Lieferant GmbH"),
    "seller_vat_id": ("DE123456789", "DE123456789"),
    "seller_tax_id": ("201/113/40209", "201/113/40209"),
    "seller_gln": ("4000001123452", "4000001123452"),
    "buyer_name": ("Kunden AG Mitte", "Kunden AG Mitte"),
    "buyer_reference": ("GE2020211", "GE2020211"),
    # buyer_vat_id deliberately absent (no BT-48) — asserted separately below.
    "line_total_amount": ("473.00", "473.00"),
    "tax_basis_total_amount": ("473.00", "473.00"),
    "tax_total_amount": ("56.87", "56.87"),
    "grand_total_amount": ("529.87", "529.87"),
    "due_payable_amount": ("529.87", "529.87"),
}


@skip_if_no_v1_corpus
def test_parse_v1_comfort_real_fixture() -> None:
    """Real ZUGFeRD v1 PDF → factur-x extract → parse_cii_xml → 16-field dict.

    Exercises the v1 (`CrossIndustryDocument`) branch end-to-end on a real
    fixture via the SAME factur-x extraction route the cohort harness uses
    (`_extract_groundtruth_via_facturx`). Proves the 24 v1 corpus PDFs are now
    usable ground truth (#75). `check_xsd/schematron=False` because factur-x
    ships v2 schemas; v1 schema validation is out of scope (extract + parse is
    what the harness needs).
    """
    import facturx  # noqa: PLC0415 — lazy: only this test needs it

    assert V1_COMFORT_PDF.exists(), f"v1 fixture missing: {V1_COMFORT_PDF}"
    name, xml_bytes = facturx.get_xml_from_pdf(
        V1_COMFORT_PDF.read_bytes(), check_xsd=False, check_schematron=False
    )
    assert name == "ZUGFeRD-invoice.xml", (
        f"Expected the v1 attachment name ZUGFeRD-invoice.xml, got {name!r}"
    )

    gt = parse_cii_xml(xml_bytes)

    assert isinstance(gt, GroundTruth)
    assert set(gt.header.keys()) == set(FIELDS.keys()), (
        "v1 parse must yield the same 16-key header as v2 (route-invariant shape)"
    )
    # buyer_vat_id is genuinely absent in this invoice → tristate "absent".
    assert gt.header["buyer_vat_id"].is_present is False

    for key, (raw, norm) in V1_COMFORT_EXPECTED.items():
        rec = gt.header[key]
        assert rec.is_present is True, f"{key}: expected present in v1 COMFORT fixture"
        assert rec.raw_value == raw, f"{key}: raw {rec.raw_value!r} != expected {raw!r}"
        assert rec.normalized_value == norm, (
            f"{key}: normalized {rec.normalized_value!r} != expected {norm!r}"
        )


def test_v1_fields_registry_xpath_executable() -> None:
    """Every `FIELDS_V1` XPath compiles + resolves against `CII_NAMESPACES_V1`.

    Corpus-independent structural check (mirrors the v2
    `test_fields_registry_xpath_executable`): builds an empty v1-root document
    and confirms each derived v1 XPath executes (returns []) without raising,
    and that the derivation actually retargeted the root to the v1
    `CrossIndustryDocument` (guards against a silent v2-passthrough bug).
    """
    assert set(FIELDS_V1.keys()) == set(FIELDS.keys()), (
        "FIELDS_V1 must cover exactly the same 19 business terms as FIELDS"
    )
    empty_v1_doc = etree.fromstring(
        b'<rsm:CrossIndustryDocument xmlns:rsm="urn:ferd:CrossIndustryDocument:invoice:1p0"/>'
    )
    for english_key, spec in FIELDS_V1.items():
        result = empty_v1_doc.xpath(spec.xpath, namespaces=CII_NAMESPACES_V1)
        assert result == [], (
            f"{english_key}: v1 XPath unexpectedly matched on an empty doc: {spec.xpath}"
        )
        assert "/rsm:CrossIndustryDocument" in spec.xpath, (
            f"{english_key}: v1 XPath should target the v1 root, got {spec.xpath!r}"
        )
        assert "CrossIndustryInvoice" not in spec.xpath, (
            f"{english_key}: v1 XPath still references the v2 root: {spec.xpath!r}"
        )


def test_parse_cii_xml_unrecognized_root_raises() -> None:
    """`parse_cii_xml` raises ValueError on a non-CII root element.

    Corpus-independent. Covers the `_select_schema` guard: anything that is
    neither `CrossIndustryInvoice` (v2) nor `CrossIndustryDocument` (v1) is
    rejected loudly rather than silently producing an all-absent dict.
    """
    not_cii = b'<foo:Bar xmlns:foo="urn:example:not-an-invoice"/>'
    with pytest.raises(ValueError, match="Unrecognized CII root element"):
        parse_cii_xml(not_cii)
