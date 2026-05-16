"""Extract the embedded factur-x / ZUGFeRD XML attachment from a PDF/A-3 invoice.

Canonical XML-extraction script for HORUS's ZUGFeRD pipeline (ADR-010). Produces
the ground-truth XML that pilot #13's evaluation harness consumes for XML-grounded
F1 scoring of VLM predictions (per ADR-009 Amendment 1).

The primary engine is `factur-x` (Akretion / Alexis de Lattre; PyPI `factur-x`),
ratified by ADR-005 for ZUGFeRD generation and extended by ADR-010 to also be
HORUS's canonical extraction route. An opt-in `--cross-check-mustang` flag adds
an independent extraction via the Mustang Project CLI (ADR-005) for three-route
ground-truth agreement evidence (factur-x + Mustang + FeRD `.cii.xml` sidecar
when present in the corpus).

Wrapper deltas over upstream `facturx-pdfextractxml`:
  1. No-attachment graceful skip (exit 0, not 1) — issue #15 acceptance criterion
  2. Sidecar-path default (`<input>.cii.xml`) — matches FeRD corpus convention
  3. Opt-in Mustang cross-check — independent codebase verification
  4. HORUS code-style alignment — mirrors `scripts/validate_zugferd.py`

Usage:
    uv run python scripts/extract_zugferd_xml.py <input.pdf> [output.xml]
                  [--no-validate]
                  [--cross-check-mustang]
                  [--log-level {debug,info,warn,error}]

Exit codes:
    0 — extraction OK (or PDF had no attachment and was skipped)
    1 — input path invalid OR factur-x failed to parse the PDF
    2 — `--cross-check-mustang` set but JAR absent
    3 — Mustang and factur-x routes disagree under C14N2 canonical comparison

Refs: ADR-010, ADR-005 (dual-track factur-x + Mustang), ADR-009 Amendment 1
(XML-grounded ground truth), issue #15, pilot #13 (parent issue).
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import facturx
from lxml import etree

REPO_ROOT = Path(__file__).resolve().parent.parent
MUSTANG_JAR_GLOB = "tools/mustangproject/Mustang-CLI-*.jar"

logger = logging.getLogger("extract_zugferd_xml")


def find_mustang_jar() -> Path | None:
    """Locate the Mustang JAR fetched via `make mustang-jar`. Return None if absent."""
    matches = sorted(REPO_ROOT.glob(MUSTANG_JAR_GLOB))
    return matches[-1] if matches else None


def canonical_xml_bytes(xml_bytes: bytes) -> bytes:
    """Return the C14N2-canonicalized form of an XML byte string.

    Used for cross-route equivalence assertions (factur-x vs Mustang vs FeRD
    sidecar). The bytes-level diff between the three routes is line-ending
    cosmetic (CRLF in PDF attachments vs LF in standalone sidecars per the
    empirical probe captured in ADR-010 §"Empirical evidence"); the C14N2
    form normalizes this and any whitespace/declaration formatting variance.
    """
    tree = etree.fromstring(xml_bytes)
    return etree.tostring(tree, method="c14n2")


def extract_via_facturx(pdf_path: Path, validate: bool) -> tuple[str, bytes] | None:
    """Extract embedded XML via factur-x. Return None if no attachment was found."""
    pdf_bytes = pdf_path.read_bytes()
    name, xml_bytes = facturx.get_xml_from_pdf(
        pdf_bytes,
        check_xsd=validate,
        check_schematron=validate,
    )
    # facturx returns (False, False) on PDFs without a recognized attachment.
    # Treat any falsy return as "no attachment found".
    if not name or not xml_bytes:
        return None
    return name, xml_bytes


def extract_via_mustang(pdf_path: Path, jar: Path) -> bytes:
    """Extract embedded XML via Mustang CLI subprocess. Raise on failure.

    Uses a TemporaryDirectory to host the output path: Mustang refuses to
    overwrite an existing file (`ensureFileNotExists`), so we must pass a path
    that does NOT yet exist. The TemporaryDirectory cleanup removes both the
    Mustang-written XML and the dir at the end.
    """
    with tempfile.TemporaryDirectory(prefix="horus-mustang-extract-") as tmpdir:
        out_path = Path(tmpdir) / "mustang_out.xml"
        cmd = [
            "java",
            "-jar",
            str(jar),
            "--action",
            "extract",
            "--source",
            str(pdf_path),
            "--out",
            str(out_path),
            "--disable-file-logging",
        ]
        logger.debug("Invoking Mustang: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Mustang --action extract failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(
                f"Mustang reported success but produced no output at {out_path}.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return out_path.read_bytes()


def cross_check_mustang(pdf_path: Path, facturx_xml: bytes, jar: Path) -> bool:
    """Run Mustang extract on the same PDF; return True if C14N2-canonical-equal.

    Logs both sizes + the canonical-equality verdict; on disagreement, logs a
    1-line diff hint so the user can investigate.
    """
    logger.info("Cross-check: invoking Mustang --action extract on %s", pdf_path.name)
    mustang_xml = extract_via_mustang(pdf_path, jar)

    facturx_c14n = canonical_xml_bytes(facturx_xml)
    mustang_c14n = canonical_xml_bytes(mustang_xml)

    logger.info(
        "Cross-check: factur-x=%d bytes raw / %d bytes C14N2; "
        "Mustang=%d bytes raw / %d bytes C14N2",
        len(facturx_xml),
        len(facturx_c14n),
        len(mustang_xml),
        len(mustang_c14n),
    )

    if facturx_c14n == mustang_c14n:
        logger.info("Cross-check: PASS — factur-x and Mustang routes are C14N2-equal")
        return True

    logger.error("Cross-check: FAIL — routes disagree under C14N2 canonical comparison")
    # Find first byte position where canonical forms diverge for debugging.
    # strict=False because canonical forms may differ in length (we just confirmed
    # they're not equal); we only iterate until the first divergence anyway.
    for i, (a, b) in enumerate(zip(facturx_c14n, mustang_c14n, strict=False)):
        if a != b:
            lo = max(0, i - 30)
            hi = min(len(facturx_c14n), i + 30)
            logger.error("  first diff at C14N2 byte %d:", i)
            logger.error("    factur-x: ...%r...", facturx_c14n[lo:hi])
            logger.error("    Mustang : ...%r...", mustang_c14n[lo:hi])
            break
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_zugferd_xml.py",
        description=(
            "Extract the embedded factur-x / ZUGFeRD XML attachment from a "
            "PDF/A-3 invoice. See docs/decisions/ADR-010 for the full rationale."
        ),
    )
    parser.add_argument(
        "input_pdf",
        type=Path,
        help="Path to the input ZUGFeRD / Factur-X PDF.",
    )
    parser.add_argument(
        "output_xml",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "Path to the output XML sidecar (default: <input>.cii.xml next to "
            "the input PDF; matches FeRD corpus convention)."
        ),
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help=(
            "Skip factur-x's built-in XSD + Schematron checks during extraction "
            "(default: validate)."
        ),
    )
    parser.add_argument(
        "--cross-check-mustang",
        action="store_true",
        help=(
            "Also run Mustang --action extract and assert C14N2-canonical "
            "equivalence with factur-x's extraction. Requires the JAR fetched "
            "via `make mustang-jar` (see ADR-005)."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warn", "error"],
        default="info",
        help="Log level (default: info).",
    )
    args = parser.parse_args(argv)

    # factur-x calls logging.basicConfig at import time (installs a StreamHandler
    # with format "%(asctime)s [%(levelname)s] %(message)s" on the root logger).
    # We piggyback on its handler+formatter (identical to ours) and only adjust
    # the level so our INFO logs propagate. NOT using force=True here, because
    # that would remove pytest's caplog handler and break the test suite.
    logging.getLogger().setLevel(args.log_level.upper())

    # --- Input validation ---
    input_pdf: Path = args.input_pdf
    if not input_pdf.is_absolute():
        input_pdf = (REPO_ROOT / input_pdf).resolve()
    if not input_pdf.exists():
        logger.error("Input PDF not found: %s", input_pdf)
        return 1
    if not input_pdf.is_file():
        logger.error("Input path is not a file: %s", input_pdf)
        return 1

    output_xml: Path = args.output_xml or input_pdf.with_suffix(".cii.xml")
    if not output_xml.is_absolute():
        output_xml = (REPO_ROOT / output_xml).resolve()

    # --- Optional pre-flight: locate Mustang JAR if cross-check requested ---
    mustang_jar: Path | None = None
    if args.cross_check_mustang:
        mustang_jar = find_mustang_jar()
        if mustang_jar is None:
            logger.error(
                "--cross-check-mustang requires the Mustang JAR. Run "
                "`make mustang-jar` first (see ADR-005)."
            )
            return 2

    # --- Primary extraction: factur-x ---
    logger.info("Extracting embedded XML from %s", input_pdf)
    try:
        result = extract_via_facturx(input_pdf, validate=not args.no_validate)
    except Exception as exc:  # noqa: BLE001 — clean error surface for CLI users
        logger.error("factur-x failed to parse PDF: %s: %s", type(exc).__name__, exc)
        return 1

    if result is None:
        logger.warning(
            "No factur-x XML attachment found in %s; skipping (not an error)",
            input_pdf,
        )
        return 0

    attachment_name, xml_bytes = result
    tree = etree.fromstring(xml_bytes)
    flavor = facturx.get_flavor(tree)
    level = facturx.get_level(tree)
    logger.info(
        "Extracted '%s' (flavor=%s, level=%s, %d bytes)",
        attachment_name,
        flavor,
        level,
        len(xml_bytes),
    )

    # --- Optional cross-check: Mustang independent extraction ---
    if args.cross_check_mustang:
        assert mustang_jar is not None  # guarded above
        try:
            agreed = cross_check_mustang(input_pdf, xml_bytes, mustang_jar)
        except Exception as exc:  # noqa: BLE001 — surface clean error
            logger.error("Mustang cross-check raised: %s: %s", type(exc).__name__, exc)
            # Still write the factur-x output (preserve debugging artefact)
            output_xml.parent.mkdir(parents=True, exist_ok=True)
            output_xml.write_bytes(xml_bytes)
            return 3
        if not agreed:
            # Routes disagree; preserve the factur-x output for debugging.
            output_xml.parent.mkdir(parents=True, exist_ok=True)
            output_xml.write_bytes(xml_bytes)
            logger.error(
                "Cross-check disagreement; factur-x output still written to %s for investigation",
                output_xml,
            )
            return 3

    # --- Write the sidecar ---
    output_xml.parent.mkdir(parents=True, exist_ok=True)
    if output_xml.exists():
        logger.warning("Output file %s exists; overwriting", output_xml)
    output_xml.write_bytes(xml_bytes)
    logger.info("Wrote %d bytes to %s", len(xml_bytes), output_xml)
    return 0


if __name__ == "__main__":
    sys.exit(main())
