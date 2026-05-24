---
title: pytest — skip + skipif + custom markers (test gating patterns)
source: https://docs.pytest.org/en/stable/how-to/skipping.html
source_secondary:
  - https://docs.pytest.org/en/stable/reference/reference.html
  - https://docs.pytest.org/en/stable/example/markers.html
  - https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/utils/_testing.py
  - https://huggingface.co/docs/transformers/testing
author: pytest-dev contributors
publisher: pytest documentation (canonical)
license: MIT (pytest); BSD-3-Clause (scikit-learn)
accessed: 2026-05-23
cited_in:
  - docs/decisions/ADR-023-ci-pipeline.md (Iteration 3 — skipif-unification redesign + §Design evolution)
adr_relevance: ratifies the `pytest.mark.skipif` decorator pattern as HORUS's canonical test-gating mechanism for environmental conditions (corpus availability, platform availability, etc.) over the alternative custom-marker + CLI-deselect pattern. Cited verbatim in ADR-023 §"Decision".
---

# pytest — skip + skipif + custom markers (test gating patterns)

> **Stub** — content body to be filled when Obsidian web-clipper imports the canonical docs.

## Why this is archived

ADR-023's test-gating design (Iteration 3) is load-bearing on pytest's official-recommended pattern. Two specific quotes are cited verbatim:

1. From the **pytest API reference**:

   > *"It is **better to use the `pytest.mark.skipif` marker when possible** to declare a test to be skipped under certain conditions like mismatching platforms or dependencies."*

2. From the **pytest skipping docs** (`how-to/skipping.html`):

   > *"A skip means that you expect your test to pass only if some conditions are met, otherwise pytest should skip running the test altogether. Common examples are **skipping windows-only tests on non-windows platforms, or skipping tests that depend on an external resource which is not available at the moment**."*

The second sentence is verbatim the HORUS corpus-availability case.

## Secondary sources

- **`pytest.mark.skipif` shared markers pattern** (`how-to/skipping.html`): *"For larger test suites it's usually a good idea to have one file where you define the markers which you then consistently apply throughout your test suite."* This is the rationale for HORUS's `tests/_corpus.py` helper module.

- **scikit-learn precedent** (`sklearn/utils/_testing.py`): the most-relevant scientific Python project uses exactly the named-skipif-decorator pattern. Example: `skip_if_array_api_compat_not_configured = pytest.mark.skipif(not ARRAY_API_COMPAT_FUNCTIONAL, reason="SCIPY_ARRAY_API not set, or versions of NumPy/SciPy too old.")`. HORUS's `skip_if_no_corpus` + `skip_if_no_fixtures` mirror this pattern.

- **HuggingFace transformers contrast** (`docs/transformers/testing`): uses custom markers (`@slow`, `@require_torch`, `@require_torch_gpu`) for **opt-in integration tests** where the developer chooses via `--run-slow` CLI flag whether to run them. *"Pull request CI skips slow tests, but the nightly schedule runs them."* This is a different category (developer-choice opt-in) from "external resource availability" (the HORUS case).

- **pytest custom markers** (`example/markers.html`): custom markers are declared in `[tool.pytest.ini_options] markers`. Pattern is appropriate for opt-in categorization (slow, network, gpu) where `pytest -m "marker"` and `pytest -m "not marker"` are the intended CLI interactions. Not appropriate for environmental-availability gating where the test should always-skip in certain environments.

## ADR-023 application

- `tests/_corpus.py` defines `skip_if_no_corpus = pytest.mark.skipif(not _HAS_CORPUS, ...)` + `skip_if_no_fixtures = pytest.mark.skipif(not _HAS_FIXTURES, ...)`.
- 5 test modules apply `pytestmark = skip_if_no_corpus` at module level.
- 15 tests in `tests/test_harness.py` apply `@skip_if_no_corpus` at test level.
- `tests/test_inference_smoke.py` uses sibling `requires_macos = pytest.mark.skipif(sys.platform != "darwin", ...)` on 3 macOS-only tests.
- `tests/test_rescore.py` uses pre-existing `skip_if_no_fixtures` (now imported from `tests._corpus`).
- No `pyproject.toml` marker registration needed; no `make test-ci` target; no `pytest_collection_modifyitems` hook.

## Design rejected (audit trail)

ADR-023 Iterations 1 + 2 used a custom `requires_corpus` marker + `make test-ci = pytest -m "not requires_corpus"`. First CI run exposed the CLI-flag-forgetting footgun + the marker-vs-skipif inconsistency (the file `tests/test_rescore.py` already used `@skip_if_no_fixtures`). Iteration 3 unified everything to skipif per pytest's official recommendation. Full trail in ADR-023 §"Design evolution".
