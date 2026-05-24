---
source_url: "https://docs.pytest.org/en/stable/reference/reference.html#confval-pythonpath"
source_title: "Configuration reference — `pythonpath` ini option"
source_author: "pytest-dev contributors"
source_date: ""
retrieved_date: "2026-05-23"
extracted_concepts: []
tags: ["pytest", "configuration", "sys-path", "test-discovery"]
archived_pdf: ""
status: stub
---

<!--
Canonical reference for pytest's `pythonpath` configuration option. Cited by
ADR-022 (`scripts/` directory status) as the authoritative source for
adding the repo root to `sys.path` during test collection.

Key facts pertinent to ADR-022:

- `pythonpath` is a list-of-strings ini option (supported in `pyproject.toml`
  under `[tool.pytest.ini_options]`). Paths are relative to the `rootdir`
  (the directory containing the pytest config file — for HORUS, the repo
  root where `pyproject.toml` lives).
- pytest inserts these paths into `sys.path` at the start of the test session
  and removes them at the end (`_configure_python_path` / `_unconfigure_
  python_path` in `_pytest/config.py`). The insertion is at position 0, so
  these paths take priority over later entries.
- Canonical use: `pythonpath = ["src"]` for src-layout projects (per
  `https://docs.pytest.org/en/stable/explanation/goodpractices.html`).
- For HORUS, the analogue is `pythonpath = ["."]` so the repo root is on
  `sys.path`, making `from scripts import X` discoverable at collection
  time WITHOUT requiring per-test-file `sys.path` manipulation.

See also: pytest goodpractices (test layout), `_pytest/config.py` source.
-->
