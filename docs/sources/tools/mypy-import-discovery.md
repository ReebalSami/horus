---
source_url: "https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports"
source_title: "Running mypy — Missing imports / Missing library stubs or py.typed marker"
source_author: "mypy contributors"
source_date: ""
retrieved_date: "2026-05-23"
extracted_concepts: []
tags: ["mypy", "type-checking", "imports", "configuration"]
archived_pdf: ""
status: stub
---

<!--
Canonical reference for how mypy resolves imports and what `import-not-found`
means. Cited by ADR-022 (`scripts/` directory status).

Key facts pertinent to ADR-022:

- mypy's `import-not-found` error code fires when mypy "cannot find the
  source code or a stub file for an imported module" (per
  `mypy/docs/source/error_code_list.md`).
- For first-party project code, the standard resolution is to make the module
  discoverable via a package layout (`__init__.py` + parent dir on
  `sys.path` / `mypy_path`) — NOT via `--ignore-missing-imports` or
  per-file `# type: ignore[import-not-found]` (those are appropriate for
  third-party untyped libraries, not for owned source).
- `mypy_path` config (also surfaced as `MYPYPATH` env var or `--explicit-
  package-bases`) tells mypy where to search for first-party packages. For
  the HORUS repo with `pyproject.toml` at root + `scripts/` package directly
  under root, no extra `mypy_path` config is needed once `scripts/__init__.py`
  is acknowledged + the migration to `from scripts import X` is applied.
- mypy's incremental cache (`.mypy_cache/`) can silently mask `import-not-
  found` errors after configuration changes. The reliable verification
  command is `rm -rf .mypy_cache && uv run mypy ... --no-incremental`.

This last point is the nondeterminism trap surfaced during the
evidence-base audit conversation (`~/.windsurf/plans/audit-branch-disposition-
14db9b.md` §2c–§2d) and is the reason every typecheck verification step in
ADR-022 + ADR-023 cycles through `rm -rf .mypy_cache` first.
-->
