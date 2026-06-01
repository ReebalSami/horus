"""ZUGFeRD corpus availability gate + skipif decorators.

Single source of truth for "does this test need the ZUGFeRD corpus and is
the corpus available in the current environment?". Imported by test
modules (`from tests._corpus import skip_if_no_corpus`) and by
`tests/conftest.py` (for the path constants).

## Pattern: `pytest.mark.skipif` with content-aware predicates

Per pytest's official recommendation (`docs.pytest.org/en/stable/reference/`
reference.html`): *"It is better to use the pytest.mark.skipif marker
when possible to declare a test to be skipped under certain conditions
like mismatching platforms or dependencies."* — and from the skipping
docs: *"A skip means that you expect your test to pass only if some
conditions are met... Common examples are skipping windows-only tests
on non-windows platforms, or **skipping tests that depend on an external
resource which is not available at the moment**."*

Mirrors `scikit-learn`'s `sklearn/utils/_testing.py` named-skipif-
decorator pattern (e.g., `skip_if_array_api_compat_not_configured`).
ADR-023 chose this pattern over a custom `requires_corpus` marker +
CLI-flag-deselect after the first CI run on PR #67 exposed the
marker pattern's footguns (predicate-strength bugs, CLI-flag
forgetting, marker/skipif inconsistency vs. the existing
`skip_if_no_fixtures` in `tests/test_rescore.py`).

## Content-aware predicate (ADR-023 first-CI-run amendment)

`ZUGFERD_CORPUS_DIR.is_dir()` alone is too weak: `data/raw/german/
zugferd-corpus/MANIFEST.md` is git-tracked (per `.gitignore`'s
allowlist `!data/raw/german/*/MANIFEST.md` for the per-corpus
audit-trail record), so on CI checkout the directory exists with
only MANIFEST.md + LICENSE + README.md + sha256.txt. The
`_HAS_CORPUS` predicate must inspect actual PDF content under
`XML-Rechnung/FX/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants — single source of truth for corpus locations
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
ZUGFERD_CORPUS_DIR = REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus"
ZUGFERD_FX_DIR = ZUGFERD_CORPUS_DIR / "XML-Rechnung" / "FX"
ZUGFERD_CII_DIR = ZUGFERD_CORPUS_DIR / "XML-Rechnung" / "CII"
ZUGFERD_UNSTRUCTURED_DIR = ZUGFERD_CORPUS_DIR / "unstructured"

# Smoke-fixture invoice paths (canonical across ADR-010 / ADR-012 / pilot-13).
EINFACH_PDF = ZUGFERD_FX_DIR / "EN16931_Einfach.pdf"
EINFACH_CII = ZUGFERD_CII_DIR / "EN16931_Einfach.cii.xml"
HETZNER_PDF = ZUGFERD_UNSTRUCTURED_DIR / "RE-E-974-Hetzner_2016-01-19_R0005532486.pdf"

# ZUGFeRD v1 (FeRD 2014, `CrossIndustryDocument`) corpus — gitignored like the
# rest of the corpus. The COMFORT "Einfach" example is the canonical v1
# rendering of the same FeRD example invoice as the v2 `EN16931_Einfach`
# fixture (per ADR-033 / #75). v1 PDFs embed `ZUGFeRD-invoice.xml`; factur-x
# extracts it transparently (verified at #75 impl time).
ZUGFERD_V1_DIR = ZUGFERD_CORPUS_DIR / "ZUGFeRDv1"
V1_COMFORT_PDF = ZUGFERD_V1_DIR / "correct" / "Intarsys" / "ZUGFeRD_1p0_COMFORT_Einfach.pdf"

# Transcript archive (ADR-014 Step 7 evidence) — git-tracked.
TRANSCRIPTS_DIR = REPO_ROOT / "docs" / "sources" / "transcripts-multipage"

# ---------------------------------------------------------------------------
# Availability predicates — evaluated once at module import
# ---------------------------------------------------------------------------

_HAS_CORPUS = ZUGFERD_FX_DIR.is_dir() and any(ZUGFERD_FX_DIR.glob("*.pdf"))
_HAS_TRANSCRIPTS = TRANSCRIPTS_DIR.is_dir() and any(TRANSCRIPTS_DIR.glob("*.txt"))
_HAS_FIXTURES = _HAS_CORPUS and _HAS_TRANSCRIPTS
_HAS_V1_CORPUS = ZUGFERD_V1_DIR.is_dir() and any(ZUGFERD_V1_DIR.rglob("*.pdf"))

# ---------------------------------------------------------------------------
# Skipif decorators — the public surface
# ---------------------------------------------------------------------------

skip_if_no_corpus = pytest.mark.skipif(
    not _HAS_CORPUS,
    reason=(
        "Requires ZUGFeRD test corpus content at "
        "data/raw/german/zugferd-corpus/XML-Rechnung/FX/*.pdf "
        "(gitignored per .gitignore; only MANIFEST.md is git-tracked). "
        "Skips automatically on CI (ubuntu-latest, no corpus available) "
        "and on developer clones without the corpus fetched. Per ADR-023."
    ),
)

skip_if_no_fixtures = pytest.mark.skipif(
    not _HAS_FIXTURES,
    reason=(
        "Requires docs/sources/transcripts-multipage/*.txt (ADR-014 Step 7 "
        "evidence — git-tracked) AND data/raw/german/zugferd-corpus/"
        "XML-Rechnung/FX/*.pdf (gitignored content). Skips automatically "
        "when either input is absent. Per ADR-023."
    ),
)

skip_if_no_v1_corpus = pytest.mark.skipif(
    not _HAS_V1_CORPUS,
    reason=(
        "Requires ZUGFeRD v1 corpus content at "
        "data/raw/german/zugferd-corpus/ZUGFeRDv1/**/*.pdf (gitignored). "
        "Skips automatically on CI and on clones without the v1 corpus. "
        "Per ADR-023 / #75 / ADR-033."
    ),
)
