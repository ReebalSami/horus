"""ZUGFeRD-corpus loader for the EDA Book chapter 1 (ADR-025 Phase B).

This module factors out every ZUGFeRD-specific helper that
`experiments/eda-zugferd.py` (Phase 1, the original ZUGFeRD-only EDA)
inlined directly. The chapter notebook is now thin narrative + cells
that call into this loader; library code lives here.

Public surface:

  - :func:`walk` — extends :func:`horus.eda.corpus_walk.walk` with
    ZUGFeRD-specific extension classification (`.cii.xml` / `.ubl.xml`
    → `.xml`) and `is_pdf` / `is_xml` boolean columns.
  - :func:`get_page_count` — pypdfium2-backed PDF page-count parser
    (None on failure; surfaces in §9 Anomalies).
  - :data:`PROFILE_PATTERNS` + :func:`profile_from_filename` — Factur-X /
    ZUGFeRD profile detection from filename. BASICWL precedes BASIC by
    deliberate dict-iteration order (see BUG-CATCH note in source).
  - :func:`extract_xml_and_level` — factur-x extracts (xml_bytes, flavor,
    level) from a Factur-X-attached PDF; suppresses verbose schema noise.
  - :func:`parse_one_gt` — wraps :func:`horus.eval.ground_truth.parse_cii_xml`
    with `None`-safe handling (None input, malformed XML, or non-CII root all
    → None). The shared parser handles BOTH ZUGFeRD v2 and v1 since ADR-033.
  - :func:`gt_has_any_field` — predicate distinguishing "GT-parseable but
    empty" from "GT-meaningful" (≥1 field with non-None normalized value).
    (Pre-ADR-033 the main empty-GT source was the v1 namespace; v1 now parses.)
  - :func:`field_value_present` — IS_GT predicate per ADR-013 truth table.
  - :func:`gt_field_values` — extracts non-None normalized values for one
    field key across an iterable of GroundTruths.
  - :func:`line_item_count` — XPath line-item count from the ZUGFeRDv2
    CII namespace (returns None for v1 / non-ZUGFeRD XMLs).
  - :func:`assign_complexity_tier` — applies the pre-committed
    :class:`ComplexityTierConfig` thresholds (HARKing-safe per ADR-024).
  - :func:`extract_country_codes_from_gt` — VAT-ID prefix → (role,
    country) pairs for the §8 locale section.

Refs: ADR-024 (visualization stack), ADR-025 (Phase B refactor),
ADR-013 (16-field F1 truth table), ADR-014 (factur-x XML extraction).
"""

from __future__ import annotations

import io
import logging
import re
import sys
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import facturx
import pandas as pd
import pypdfium2 as pdfium
from lxml import etree

from horus.config import ComplexityTierConfig
from horus.eda.corpus_walk import DEFAULT_SKIP_NAMES
from horus.eda.corpus_walk import walk as _shared_walk
from horus.eval.ground_truth import GroundTruth, parse_cii_xml

# ---------------------------------------------------------------------------
# CII namespaces (ZUGFeRDv2 / Factur-X) — LOCAL to this loader, used only by
# `line_item_count` below. The GROUND-TRUTH parser (`horus.eval.ground_truth`)
# handles both v2 and v1 since ADR-033 (#75); this local v2-only map means v1
# line-item COUNTING here still returns 0 (a separate, documented limitation —
# see `line_item_count`). NOT used by `parse_one_gt`, which delegates to the
# v1-aware shared parser.
# ---------------------------------------------------------------------------
CII_NAMESPACES: dict[str, str] = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": ("urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"),
}


# ---------------------------------------------------------------------------
# Filesystem walk — ZUGFeRD-specific extension classification.
# ---------------------------------------------------------------------------


def _classify_extension(path: Path) -> str:
    """Map filename to a normalized extension class.

    `.cii.xml` and `.ubl.xml` collapse to plain `.xml` since the schema
    distinction is captured by `subdir` (XML-Rechnung/CII vs UBL).
    """
    name = path.name.lower()
    if name.endswith(".pdf"):
        return ".pdf"
    if name.endswith(".xml"):
        return ".xml"
    return path.suffix.lower() or "(none)"


def walk(corpus_root: Path) -> pd.DataFrame:
    """Walk ZUGFeRD corpus root, returning one-row-per-file DataFrame.

    Layered on top of :func:`horus.eda.corpus_walk.walk`: the shared helper
    handles dotfile + metadata filtering; this wrapper adds:

    - ZUGFeRD-specific extension classification (`.cii.xml` / `.ubl.xml`
      collapsed to `.xml`).
    - `is_pdf` / `is_xml` boolean columns for the per-flavor coverage
      table in §2.

    The shared :data:`horus.eda.corpus_walk.DEFAULT_SKIP_NAMES` already
    filters MANIFEST / sha256 / README / LICENSE; this loader doesn't
    extend that list (ZUGFeRD corpus has no extra metadata files
    requiring exclusion).
    """
    df = _shared_walk(corpus_root)
    # Re-classify extension column with ZUGFeRD-specific .cii.xml/.ubl.xml
    # collapse, replacing the shared walker's plain suffix-based extension.
    df = df.copy()
    df["extension"] = df["path"].apply(_classify_extension)
    df["is_pdf"] = df["extension"] == ".pdf"
    df["is_xml"] = df["extension"] == ".xml"
    return df


# Re-exported so chapter notebooks can show the skip-list value table
# without importing `corpus_walk` separately.
__all__ = [
    "CII_NAMESPACES",
    "DEFAULT_SKIP_NAMES",
    "PROFILE_PATTERNS",
    "assign_complexity_tier",
    "extract_country_codes_from_gt",
    "extract_xml_and_level",
    "field_value_present",
    "get_page_count",
    "gt_field_values",
    "gt_has_any_field",
    "line_item_count",
    "parse_one_gt",
    "profile_from_filename",
    "suppress_facturx_warnings",
    "walk",
]


# ---------------------------------------------------------------------------
# PDF page count via pypdfium2.
# ---------------------------------------------------------------------------


def get_page_count(pdf_path: Path) -> int | None:
    """Return PDF page count via pypdfium2; None on parse failure.

    Uses the canonical try/finally + `.close()` pattern from
    `src/horus/eval/rasterize.py` (pypdfium2 4.30 lacks `__exit__`,
    so the `with` statement is unsupported per the upstream API).

    Failures (corrupt PDF, encrypted, etc.) return None and surface
    in §9 Anomalies; callers typically guard with `.notna()` filters.
    """
    try:
        doc = pdfium.PdfDocument(str(pdf_path))
    except Exception:  # noqa: BLE001 — surfaces in §9 Anomalies, not here
        return None
    try:
        return len(doc)
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001 — cleanup; weakref.finalize is the safety net
            pass


# ---------------------------------------------------------------------------
# Factur-X / ZUGFeRD profile detection from filename.
# ---------------------------------------------------------------------------
#
# `\b` word boundaries DON'T work here because `_` is a word char in Python
# regex (\w includes underscore). Filenames like `zugferd_2p0_EN16931_Einfach.pdf`
# have `_` on both sides of the profile token — no word boundary exists. Use
# explicit `(?:^|[_/-])` and `(?:[_/-.]|$)` separators instead, plus IGNORECASE
# for camelcase variants.
# Char classes use `-` LAST to mean a literal hyphen (otherwise `[_/-.]` parses
# `/-.` as a malformed range from `/` to `.`).
#
# BUG-CATCH: BASICWL must precede BASIC in this dict because the dict-iteration
# order matches lookup order in `profile_from_filename()`. The previous
# `BASIC(?:WL)?` form matched both BASIC and BASICWL filenames but always
# returned key "BASIC", causing 6 of 10 route-disagreement false positives
# in §4 (e.g., `Facture_DOM_BASICWL.pdf` filename → "BASIC", XML → "BASICWL").
# Separate explicit pattern (allowing space, underscore, or hyphen between
# "BASIC" and "WL", since `BASIC WL/` and `BASIC-WL_` both appear in corpus).
PROFILE_PATTERNS: dict[str, re.Pattern[str]] = {
    "BASICWL": re.compile(r"(?:^|[_/-])BASIC[ _-]?WL(?:[_/.-]|$)", re.IGNORECASE),
    "MINIMUM": re.compile(r"(?:^|[_/-])MINIMUM(?:[_/.-]|$)", re.IGNORECASE),
    "BASIC": re.compile(r"(?:^|[_/-])BASIC(?:[_/.-]|$)", re.IGNORECASE),
    "EN16931": re.compile(r"(?:^|[_/-])EN[_]?16931(?:[_/.-]|$)", re.IGNORECASE),
    "EXTENDED": re.compile(r"(?:^|[_/-])(EXTENDED|Erweitert)(?:[_/.-]|$)", re.IGNORECASE),
    "XRECHNUNG": re.compile(r"(?:^|[_/-])XRECHNUNG(?:[_/.-]|$)", re.IGNORECASE),
}


def profile_from_filename(name: str) -> str | None:
    """Return the canonical profile key for a filename, or None if unknown.

    Iterates :data:`PROFILE_PATTERNS` in insertion order (Python dicts
    preserve insertion order since 3.7); first match wins. The order is
    deliberate (BASICWL precedes BASIC; see BUG-CATCH note above).
    """
    for profile, pat in PROFILE_PATTERNS.items():
        if pat.search(name):
            return profile
    return None


# ---------------------------------------------------------------------------
# Factur-X XML extraction + GT parsing.
# ---------------------------------------------------------------------------


@contextmanager
def suppress_facturx_warnings() -> Iterator[None]:
    """Context manager: suppress factur-x's verbose schema-warning stderr noise.

    factur-x emits raw schema-validation warnings to stderr during bulk
    parsing. They are NOT errors and are surfaced explicitly in §9
    Anomalies via the structured failure-mode counts. Suppressing here
    keeps the `make eda` / `make eda-book` console output readable.
    """
    saved_stderr = sys.stderr
    devnull = io.StringIO()
    saved_log_level = logging.getLogger("facturx").level
    logging.getLogger("facturx").setLevel(logging.ERROR)
    try:
        sys.stderr = devnull
        yield
    finally:
        sys.stderr = saved_stderr
        logging.getLogger("facturx").setLevel(saved_log_level)


def extract_xml_and_level(
    pdf_path: Path,
) -> tuple[bytes | None, str | None, str | None]:
    """Return (xml_bytes, flavor, level) or (None, None, None) on failure.

    Uses ``factur-x`` with ``check_xsd=False`` + ``check_schematron=False``
    for bulk EDA — corpus has known-invalid PDFs in `fail/` subdirs that
    are intentional robustness substrate.

    The (flavor, level) tuple is the factur-x-classified Factur-X / ZUGFeRD
    profile + version: flavor in `{"factur-x", "zugferd", "order-x"}`
    (`zugferd` indicates v1 namespace, parser-incompatible with the §5/§6/§8
    GroundTruth schema); level in `{"minimum", "basic", "basicwl", "en16931",
    "extended", "xrechnung", ...}`.
    """
    try:
        pdf_bytes = pdf_path.read_bytes()
        with suppress_facturx_warnings():
            result = facturx.get_xml_from_pdf(pdf_bytes, check_xsd=False, check_schematron=False)
        if not result or not result[0]:
            return None, None, None
        _name, xml_bytes = result
        try:
            tree = etree.fromstring(xml_bytes)
            with suppress_facturx_warnings():
                flavor = facturx.get_flavor(tree)
                level = facturx.get_level(tree)
        except Exception:  # noqa: BLE001
            return xml_bytes, None, None
        return xml_bytes, flavor, level
    except Exception:  # noqa: BLE001
        return None, None, None


def parse_one_gt(xml_bytes: bytes | None) -> GroundTruth | None:
    """Parse a single CII XML to a :class:`GroundTruth`; None on failure.

    Wraps :func:`horus.eval.ground_truth.parse_cii_xml` with `None`-safe
    handling. Returns None for: None input, malformed XML
    (`lxml.etree.XMLSyntaxError`), or a non-CII root (`ValueError` — neither
    `CrossIndustryInvoice` v2 nor `CrossIndustryDocument` v1). Since ADR-033
    (#75) the shared parser handles BOTH v2 AND v1, so v1 XMLs now yield a
    populated GroundTruth (they no longer silently parse to empty); use
    :func:`gt_has_any_field` to filter the "parser-meaningful" subset.
    """
    if xml_bytes is None:
        return None
    try:
        return parse_cii_xml(xml_bytes)
    except Exception:  # noqa: BLE001
        return None


def gt_has_any_field(gt: GroundTruth | None) -> bool:
    """True iff the parsed GT has at least 1 field with a non-None normalized value.

    The "parser-meaningful" predicate — distinguishes a populated GroundTruth
    from `None` (parse failure) or an all-absent GroundTruth.

    HISTORICAL NOTE: pre-ADR-033, ZUGFeRDv1-namespace PDFs parsed into an empty
    GroundTruth (the shared parser was v2-XPath-only), artificially capping the
    §5 mandatory-field presence rates at ~84% (the v1-silent finding from the
    2026-05-25 audit, ADR-025 §"Context"). Since ADR-033 (#75) v1 parses
    correctly, so that cap is lifted and the v1 corpus PDFs now contribute real
    fields. The predicate remains the canonical meaningful-vs-empty filter.
    """
    if gt is None:
        return False
    return any(f.normalized_value is not None for f in gt.header.values())


def field_value_present(gt: GroundTruth, key: str) -> bool:
    """True iff the field has a non-None normalized value (IS_GT per ADR-013).

    Per `src/horus/eval/ground_truth.py:GroundTruthField` schema:

      - `is_present=False` → field absent from XML → NO_GT
      - `is_present=True` + `normalized_value is None` → present but
        normalizer rejected → EXCLUDED (per ADR-013 §Truth table)
      - `normalized_value is not None` → IS_GT (countable for F1)
    """
    field = gt.header.get(key)
    if field is None:
        return False
    return field.normalized_value is not None


def gt_field_values(gts: Iterable[GroundTruth], field_key: str) -> list[object]:
    """Collect non-None normalized values for `field_key` across `gts`.

    Used by the §6 per-field value-distribution plots. Skips fields that
    are absent OR present-but-normalizer-rejected (i.e., returns only the
    IS_GT subset per :func:`field_value_present`).
    """
    out: list[object] = []
    for gt in gts:
        f = gt.header.get(field_key)
        if f is None or f.normalized_value is None:
            continue
        out.append(f.normalized_value)
    return out


# ---------------------------------------------------------------------------
# CII line-item count (XPath against ZUGFeRDv2 namespace).
# ---------------------------------------------------------------------------


def line_item_count(xml_bytes: bytes | None) -> int | None:
    """Count `IncludedSupplyChainTradeLineItem` elements in a CII XML.

    Returns None for unparseable XML. NOTE: this counter uses the LOCAL
    v2-only :data:`CII_NAMESPACES`, so a v1-namespace XML matches 0 elements
    and returns 0 (NOT a meaningful count). This is now a SEPARATE limitation
    from the GT parser, which handles v1 since ADR-033 (#75) — v1 line-item
    counting here is intentionally left v2-scoped (out of #75's GT-path scope;
    a follow-up could make it version-aware). Callers use this for the §7
    complexity-tier denominator.
    """
    if xml_bytes is None:
        return None
    try:
        tree = etree.fromstring(xml_bytes)
        items = tree.xpath("//ram:IncludedSupplyChainTradeLineItem", namespaces=CII_NAMESPACES)
        return len(items) if isinstance(items, list) else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Complexity-tier assignment per pre-committed YAML thresholds.
# ---------------------------------------------------------------------------


def assign_complexity_tier(
    pages: int | None,
    items: int | None,
    *,
    cfg: ComplexityTierConfig,
) -> str:
    """Apply pre-committed complexity thresholds to one PDF.

    Rule (HARKing-safe — thresholds locked in `configs/eda-zugferd.yaml`
    BEFORE the EDA runs, per ADR-024 + brainstorm v2 §2):

      - `simple` if pages ≤ `simple_max_pages` AND items ≤ `simple_max_line_items`
      - `medium` if pages ≤ `medium_max_pages` AND items ≤ `medium_max_line_items`
      - `complex` otherwise
      - `(unknown)` if either input is None (unparseable)

    Args:
        pages: page count from :func:`get_page_count`.
        items: line-item count from :func:`line_item_count`.
        cfg: :class:`ComplexityTierConfig` from the chapter's YAML.

    Returns:
        One of `"simple" | "medium" | "complex" | "(unknown)"`.
    """
    if pages is None or items is None:
        return "(unknown)"
    if pages <= cfg.simple_max_pages and items <= cfg.simple_max_line_items:
        return "simple"
    if pages <= cfg.medium_max_pages and items <= cfg.medium_max_line_items:
        return "medium"
    return "complex"


# ---------------------------------------------------------------------------
# Locale / country extraction from VAT-ID prefix.
# ---------------------------------------------------------------------------

_VAT_PREFIX_PATTERN = re.compile(r"^([A-Z]{2})")


def extract_country_codes_from_gt(gt: GroundTruth) -> list[tuple[str, str]]:
    """Return [(role, country)] pairs derived from VAT-ID prefixes.

    Roles: `"seller"` (from `seller_vat_id` field) + `"buyer"` (from
    `buyer_vat_id`). Country is the leading 2-letter ISO-3166 alpha-2
    prefix conventional for EU VAT IDs (`DE123456789` → `DE`).

    Drops fields that are absent OR fail the prefix regex (non-EU VAT
    formats, malformed values).
    """
    out: list[tuple[str, str]] = []
    for role, key in (("seller", "seller_vat_id"), ("buyer", "buyer_vat_id")):
        field = gt.header.get(key)
        if field is None or field.normalized_value is None:
            continue
        match = _VAT_PREFIX_PATTERN.match(str(field.normalized_value))
        if match is None:
            continue
        out.append((role, match.group(1)))
    return out
