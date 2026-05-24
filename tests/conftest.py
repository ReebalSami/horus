"""Shared pytest fixtures + corpus path constants for the HORUS test suite.

Centralizes the ZUGFeRD corpus paths so individual test modules don't hardcode
deep relative paths like `data/raw/german/zugferd-corpus/XML-Rechnung/FX/...`
(refactor hazard — if the corpus moves, only this file needs updating).

Path constants + availability predicates + skipif decorators (`skip_if_no_corpus`,
`skip_if_no_fixtures`) live in `tests/_corpus.py` (the canonical helper module
per ADR-023; mirrors scikit-learn's `sklearn/utils/_testing.py` pattern). This
file re-exports the path constants for backward compatibility with test
modules that already import them from `tests.conftest`, and defines the
parametrized fixtures.

Public constants (re-exported from `tests._corpus`):
  - `REPO_ROOT`             — repo root (absolute Path)
  - `ZUGFERD_CORPUS_DIR`    — root of the ZUGFeRD test corpus
  - `ZUGFERD_FX_DIR`        — Factur-X (PDF) sub-directory
  - `ZUGFERD_CII_DIR`       — Cross Industry Invoice (.cii.xml) sub-directory
  - `ZUGFERD_UNSTRUCTURED_DIR` — PDFs without embedded factur-x XML (negative-test fixtures)
  - `EINFACH_PDF`           — canonical smoke-fixture PDF (`EN16931_Einfach.pdf`)
  - `EINFACH_CII`           — paired FeRD CII sidecar for the smoke fixture
  - `HETZNER_PDF`           — paired no-attachment fixture (per ADR-010)

Public fixtures:
  - `corpus_fx_pdfs`        — sorted list of all PDF paths in `FX/` with a paired sidecar
  - `corpus_cii_xmls`       — sorted list of all `.cii.xml` paths in `CII/`
  - `paired_invoice`        — parametrized fixture yielding (pdf_path, cii_sidecar_path) pairs

These constants + fixtures were extracted from individual test modules in PR(a)
(ADR-012) so corpus path drift becomes a one-file change.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

# Re-export path constants from the canonical helper module so existing
# `from tests.conftest import ZUGFERD_FX_DIR` imports keep working.
from tests._corpus import (
    EINFACH_CII,
    EINFACH_PDF,
    HETZNER_PDF,
    REPO_ROOT,
    ZUGFERD_CII_DIR,
    ZUGFERD_CORPUS_DIR,
    ZUGFERD_FX_DIR,
    ZUGFERD_UNSTRUCTURED_DIR,
)

__all__ = [
    "EINFACH_CII",
    "EINFACH_PDF",
    "HETZNER_PDF",
    "REPO_ROOT",
    "ZUGFERD_CII_DIR",
    "ZUGFERD_CORPUS_DIR",
    "ZUGFERD_FX_DIR",
    "ZUGFERD_UNSTRUCTURED_DIR",
    "corpus_cii_xmls",
    "corpus_fx_pdfs",
    "en16931_paired_invoice",
    "paired_invoice",
    "pytest_generate_tests",
    "xrechnung_paired_invoice",
]


# ---------------------------------------------------------------------------
# Pytest fixtures — parametrized corpus iterators
# ---------------------------------------------------------------------------


def _list_paired_invoices(
    prefix: str | None = None,
) -> list[tuple[Path, Path]]:
    """Return `(pdf_path, cii_sidecar_path)` pairs for every PDF in `FX/` whose
    name matches a sidecar in `CII/`. Skips orphans on either side.

    Args:
        prefix: optional filename-stem prefix filter (e.g., `"EN16931_"` returns
            only the 22 EN16931-profile invoices; `"XRECHNUNG_"` returns the 4
            XRECHNUNG-profile ones). `None` returns all 26 paired invoices.

    Result is sorted by PDF filename for deterministic test ordering.
    """
    if not ZUGFERD_FX_DIR.is_dir() or not ZUGFERD_CII_DIR.is_dir():
        return []

    pairs: list[tuple[Path, Path]] = []
    for pdf_path in sorted(ZUGFERD_FX_DIR.glob("*.pdf")):
        if prefix is not None and not pdf_path.stem.startswith(prefix):
            continue
        sidecar = ZUGFERD_CII_DIR / f"{pdf_path.stem}.cii.xml"
        if sidecar.is_file():
            pairs.append((pdf_path, sidecar))
    return pairs


@pytest.fixture(scope="session")
def corpus_fx_pdfs() -> list[Path]:
    """All PDF paths in `XML-Rechnung/FX/` with a paired CII sidecar. Sorted."""
    return [pdf for pdf, _ in _list_paired_invoices()]


@pytest.fixture(scope="session")
def corpus_cii_xmls() -> list[Path]:
    """All `.cii.xml` paths in `XML-Rechnung/CII/` with a paired FX PDF. Sorted."""
    return [cii for _, cii in _list_paired_invoices()]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize the corpus-iteration fixtures at collection time.

    Three parametrized fixtures, each producing `(pdf_path, cii_sidecar_path)`
    tuples filtered to a specific corpus segment:

      - `en16931_paired_invoice`  — the 22 EN16931-profile invoices (route-equal)
      - `xrechnung_paired_invoice` — the 4 XRECHNUNG-profile invoices (documented divergence)
      - `paired_invoice`           — all 26 paired invoices (full corpus sweep)

    Test IDs use the PDF stem for human-readable pytest output:
    `test_foo[EN16931_Einfach]`, `test_foo[XRECHNUNG_Elektron]`, …

    Using `pytest_generate_tests` instead of `@pytest.fixture(params=...)`
    so the parametrization runs at collection time and produces one test
    item per invoice (rather than one test item that internally iterates).
    """
    if "en16931_paired_invoice" in metafunc.fixturenames:
        pairs = _list_paired_invoices(prefix="EN16931_")
        ids = [pdf.stem for pdf, _ in pairs]
        metafunc.parametrize("en16931_paired_invoice", pairs, ids=ids, scope="session")
    if "xrechnung_paired_invoice" in metafunc.fixturenames:
        pairs = _list_paired_invoices(prefix="XRECHNUNG_")
        ids = [pdf.stem for pdf, _ in pairs]
        metafunc.parametrize("xrechnung_paired_invoice", pairs, ids=ids, scope="session")
    if "paired_invoice" in metafunc.fixturenames:
        pairs = _list_paired_invoices()
        ids = [pdf.stem for pdf, _ in pairs]
        metafunc.parametrize("paired_invoice", pairs, ids=ids, scope="session")


@pytest.fixture(scope="session")
def paired_invoice(request: pytest.FixtureRequest) -> Iterator[tuple[Path, Path]]:
    """Yields one `(pdf_path, cii_sidecar_path)` pair per invoice in `FX/`.

    Populated by `pytest_generate_tests` above; raw fixture body unused.
    """
    yield request.param  # pragma: no cover — populated by pytest_generate_tests


@pytest.fixture(scope="session")
def en16931_paired_invoice(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[Path, Path]]:
    """Yields one paired invoice per EN16931_*-prefixed fixture (22 invoices)."""
    yield request.param  # pragma: no cover — populated by pytest_generate_tests


@pytest.fixture(scope="session")
def xrechnung_paired_invoice(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[Path, Path]]:
    """Yields one paired invoice per XRECHNUNG_*-prefixed fixture (4 invoices)."""
    yield request.param  # pragma: no cover — populated by pytest_generate_tests


# ADR-023: the auto-mark `pytest_collection_modifyitems` hook from the
# original marker design was deleted in the skipif-unification amendment.
# Fixture-driven corpus dependency is now handled by `_list_paired_invoices`
# returning `[]` when the corpus is absent → pytest's parametrize produces
# zero items → tests using these fixtures simply don't get collected. No
# explicit marking needed. See ADR-023 §"Decision" for the unified design.
