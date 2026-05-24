---
source_url: "https://github.com/astral-sh/setup-uv"
source_title: "astral-sh/setup-uv — Set up uv in GitHub Actions"
source_author: "Astral / uv contributors"
source_date: ""
retrieved_date: "2026-05-23"
extracted_concepts: []
tags: ["ci", "github-actions", "uv", "python", "caching"]
archived_pdf: ""
status: stub
---

<!--
Canonical reference for the `astral-sh/setup-uv` GitHub Action — the
recommended way to install + cache `uv` (Astral) in CI. Cited by ADR-023.

Key facts pertinent to ADR-023:

- Pinned to v8.1.0 by SHA `08807647e7069bb48b6ef5acd8ec9567f424441b` (per the
  Astral docs canonical example as of 2026-05-23 via Context7
  `/astral-sh/setup-uv`).
- `enable-cache: true` caches the uv download + the dependency wheels. Cache
  key invalidates on changes to `cache-dependency-glob` (default: lock file
  + pyproject.toml).
- `python-version` is optional — when omitted, uv reads `.python-version`
  during `uv sync`. HORUS pins Python 3.14 in `.python-version`; setup-uv
  + uv sync handle the install transparently.
- Cache glob for HORUS: `pyproject.toml` + `uv.lock` (both at repo root).
- `version-file: "pyproject.toml"` reads `[project] requires-python` for the
  uv version itself (not the Python version). Not currently used by HORUS;
  the default-latest uv suffices.
- Outputs surfaced: `uv-version`, `cache-hit`, `cache-key`, `venv`. Used in
  ADR-023's CI workflow only via `steps.setup-uv.outputs.cache-hit` for
  optional logging (not gating).
- Self-installs uv via the standard install script; no Python prerequisite
  on the runner (uv is a Rust binary).
-->
