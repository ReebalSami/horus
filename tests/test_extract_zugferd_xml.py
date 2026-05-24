"""Tests for scripts.extract_zugferd_xml — ZUGFeRD XML extractor (ADR-010).

Covers the 4 behavioral contracts documented in ADR-010 §"Decision":

1. Valid ZUGFeRD PDF → extract via factur-x, write sidecar, three-route
   C14N2-canonical agreement with the FeRD-shipped .cii.xml sidecar.
2. Path that does not exist / is not a file → clean error, exit 1, no sidecar.
3. PDF without embedded factur-x XML → skip + log warning, exit 0, no sidecar.
4. --cross-check-mustang flag — three-route ground-truth agreement
   (factur-x ↔ Mustang BYTE-equal; both ↔ FeRD sidecar C14N2-equal).
   Skipped when Mustang JAR is absent.

Run via: `uv run pytest tests/test_extract_zugferd_xml.py`

Refs: ADR-010, ADR-005, ADR-009 Amendment 1, issue #15, pilot #13.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

# ADR-023: every test in this module requires the ZUGFeRD corpus on disk
# (hard `assert ... .exists()` calls + factur-x extraction from real PDFs).
# Deselected by `make test-ci` on the ubuntu-latest CI runner.
pytestmark = pytest.mark.requires_corpus

REPO_ROOT = Path(__file__).resolve().parent.parent
ZUGFERD_FX_DIR = REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus" / "XML-Rechnung" / "FX"
ZUGFERD_CII_DIR = REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus" / "XML-Rechnung" / "CII"
ZUGFERD_UNSTRUCTURED_DIR = REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus" / "unstructured"
MUSTANG_JAR_GLOB = "tools/mustangproject/Mustang-CLI-*.jar"

# Canonical fixtures — verified to exist during planning (ADR-010 §"Current-state survey").
EN16931_PDF = ZUGFERD_FX_DIR / "EN16931_Einfach.pdf"
EN16931_FERD_SIDECAR = ZUGFERD_CII_DIR / "EN16931_Einfach.cii.xml"
HETZNER_PDF = ZUGFERD_UNSTRUCTURED_DIR / "RE-E-974-Hetzner_2016-01-19_R0005532486.pdf"


def _has_mustang_jar() -> bool:
    return bool(list(REPO_ROOT.glob(MUSTANG_JAR_GLOB)))


def _canonical(xml_bytes: bytes) -> bytes:
    """Return C14N2 canonical-XML bytes for cross-route comparison."""
    from lxml import etree  # noqa: PLC0415

    return etree.tostring(etree.fromstring(xml_bytes), method="c14n2")


def test_extract_valid_zugferd_pdf(tmp_path: Path) -> None:
    """Happy path: extracts EN16931_Einfach.pdf to a sidecar.

    Asserts the wrapper produces:
    - exit code 0
    - sidecar file exists and non-empty
    - sidecar XML byte-equal to a direct facturx.get_xml_from_pdf call
    - sidecar XML C14N2-canonical equal to FeRD's standalone .cii.xml sidecar
      (the THIRD ground-truth route per ADR-010 §"Decision")
    """
    from scripts.extract_zugferd_xml import main  # noqa: PLC0415

    assert EN16931_PDF.exists(), f"Test fixture missing: {EN16931_PDF}"
    assert EN16931_FERD_SIDECAR.exists(), f"FeRD sidecar missing: {EN16931_FERD_SIDECAR}"

    output_xml = tmp_path / "extracted.cii.xml"
    exit_code = main([str(EN16931_PDF), str(output_xml)])

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert output_xml.exists(), "Sidecar file was not written"
    assert output_xml.stat().st_size > 0, "Sidecar file is empty"

    extracted_bytes = output_xml.read_bytes()

    # Sanity: agrees with a direct facturx.get_xml_from_pdf call (validates
    # we're not accidentally mutating bytes in the wrapper).
    import facturx  # noqa: PLC0415

    name, direct_bytes = facturx.get_xml_from_pdf(
        EN16931_PDF.read_bytes(), check_xsd=True, check_schematron=True
    )
    assert name == "factur-x.xml", f"Expected factur-x.xml attachment, got {name!r}"
    assert extracted_bytes == direct_bytes, (
        "Wrapper output diverges from direct facturx.get_xml_from_pdf call — "
        "the wrapper is mutating bytes it shouldn't"
    )

    # Three-route ground-truth check: factur-x extraction ↔ FeRD sidecar
    # agree at C14N2 canonical-XML level (the line-ending difference is
    # corpus-assembly artifact, not content; see ADR-010 §"Empirical evidence").
    ferd_sidecar_bytes = EN16931_FERD_SIDECAR.read_bytes()
    assert _canonical(extracted_bytes) == _canonical(ferd_sidecar_bytes), (
        "factur-x extraction and FeRD-shipped .cii.xml sidecar disagree under "
        "C14N2 canonical-XML comparison — this would invalidate the three-route "
        "ground-truth claim in ADR-009 Amendment 1 and ADR-010"
    )


def test_extract_invalid_pdf(tmp_path: Path) -> None:
    """Garbage non-PDF input → exit 1, no sidecar written."""
    from scripts.extract_zugferd_xml import main  # noqa: PLC0415

    garbage = tmp_path / "garbage.pdf"
    garbage.write_bytes(b"not a pdf")
    output_xml = tmp_path / "out.cii.xml"

    exit_code = main([str(garbage), str(output_xml)])

    assert exit_code == 1, f"Expected exit 1 for invalid PDF, got {exit_code}"
    assert not output_xml.exists(), (
        "Sidecar should NOT be written when factur-x fails to parse the PDF"
    )


def test_extract_nonexistent_path(tmp_path: Path) -> None:
    """Path that does not exist → exit 1, clean error."""
    from scripts.extract_zugferd_xml import main  # noqa: PLC0415

    nonexistent = tmp_path / "does_not_exist.pdf"
    output_xml = tmp_path / "out.cii.xml"

    exit_code = main([str(nonexistent), str(output_xml)])

    assert exit_code == 1, f"Expected exit 1 for missing path, got {exit_code}"
    assert not output_xml.exists()


def test_extract_pdf_without_attachment(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """PDF with no embedded factur-x XML → exit 0 (skip), no sidecar, warning logged.

    This is the issue #15 acceptance criterion's "skip + log warning" path —
    the wrapper's primary behavioral value-add over upstream `facturx-pdfextractxml`
    (which exits 1 on this path).
    """
    from scripts.extract_zugferd_xml import main  # noqa: PLC0415

    assert HETZNER_PDF.exists(), f"Test fixture missing: {HETZNER_PDF}"

    output_xml = tmp_path / "should_not_be_written.cii.xml"
    with caplog.at_level(logging.WARNING, logger="extract_zugferd_xml"):
        exit_code = main([str(HETZNER_PDF), str(output_xml)])

    assert exit_code == 0, (
        f"Expected exit 0 (skip-not-error) for PDF without attachment, got {exit_code}"
    )
    assert not output_xml.exists(), (
        "Sidecar must NOT be written when the PDF has no factur-x XML attachment"
    )
    # Verify the wrapper's own warning fired (not just facturx's internal one).
    warning_messages = [
        rec.message
        for rec in caplog.records
        if rec.name == "extract_zugferd_xml" and rec.levelno >= logging.WARNING
    ]
    assert any("No factur-x XML attachment found" in msg for msg in warning_messages), (
        f"Wrapper did not log the expected 'No factur-x XML attachment found' "
        f"warning. Captured wrapper records: {warning_messages}"
    )


@pytest.mark.skipif(
    not _has_mustang_jar(),
    reason="Mustang JAR not found (run `make mustang-jar` to enable cross-check tests)",
)
def test_extract_with_mustang_cross_check(tmp_path: Path) -> None:
    """Three-route ground-truth agreement on EN16931_Einfach.pdf.

    Skipped when Mustang JAR is absent. When present, asserts:
    - --cross-check-mustang exits 0 (routes agree)
    - factur-x extraction BYTE-equal Mustang extraction (Probe 1 in ADR-010)
    - factur-x extraction (C14N2) equal to FeRD sidecar (C14N2) (Probe 2)
    """
    from scripts.extract_zugferd_xml import (  # noqa: PLC0415
        extract_via_facturx,
        extract_via_mustang,
        find_mustang_jar,
        main,
    )

    output_xml = tmp_path / "extracted_with_xcheck.cii.xml"
    exit_code = main([str(EN16931_PDF), str(output_xml), "--cross-check-mustang"])
    assert exit_code == 0, (
        f"Expected exit 0 (cross-check passes), got {exit_code} — "
        "this indicates factur-x and Mustang extractions disagree, which would "
        "invalidate the three-route ground-truth claim in ADR-010"
    )
    assert output_xml.exists()

    # Direct extraction probes for cross-route byte-equality assertions
    # (mirrors ADR-010 §"Empirical evidence" Probes 1 + 2).
    facturx_result = extract_via_facturx(EN16931_PDF, validate=True)
    assert facturx_result is not None, "factur-x extraction returned None unexpectedly"
    _, facturx_bytes = facturx_result

    jar = find_mustang_jar()
    assert jar is not None, "Mustang JAR not found despite skip-marker check"
    mustang_bytes = extract_via_mustang(EN16931_PDF, jar)

    # Probe 1: factur-x ↔ Mustang are BYTE-identical (both extract the
    # PDF/A-3 attachment as-is, preserving CRLF line endings).
    assert facturx_bytes == mustang_bytes, (
        "factur-x and Mustang extractions diverge byte-wise; one of the two "
        f"libraries changed its extraction behavior. "
        f"factur-x size={len(facturx_bytes)}, Mustang size={len(mustang_bytes)}"
    )

    # Probe 2: factur-x ↔ FeRD .cii.xml sidecar are C14N2-canonical-equal
    # (FeRD normalized CRLF→LF during corpus assembly; content is identical).
    ferd_bytes = EN16931_FERD_SIDECAR.read_bytes()
    assert _canonical(facturx_bytes) == _canonical(ferd_bytes), (
        "factur-x extraction and FeRD-shipped .cii.xml sidecar disagree under "
        "C14N2 canonical-XML comparison; ADR-009 Amendment 1's 'two routes give "
        "identical content' claim would be wrong"
    )
