---
source_url: "https://docs.github.com/en/actions"
source_title: "GitHub Actions documentation"
source_author: "GitHub, Inc."
source_date: ""
retrieved_date: "2026-05-23"
extracted_concepts: []
tags: ["ci", "github-actions", "workflows", "automation"]
archived_pdf: ""
status: stub
---

<!--
Canonical reference for GitHub Actions: workflow YAML syntax, event triggers,
runner images, action versioning, secrets management. Cited by ADR-023 as the
authoritative substrate for `.github/workflows/ci.yml`.

Key facts pertinent to ADR-023:

- Workflows live at `.github/workflows/<name>.yml`. Each file is a separate
  workflow; multiple workflows can coexist (e.g., `ci.yml`, `release.yml`,
  `nightly.yml`).
- Event triggers used in HORUS CI: `push` (filtered to `main`) and
  `pull_request` (filtered to PRs targeting `main`). This covers both
  branch-protection enforcement (PRs gated by CI) and post-merge regression
  detection (any direct push to `main` re-runs CI as a safety net).
- Runner: `ubuntu-latest` — currently aliases to Ubuntu 24.04. Sufficient for
  pure-Python + lint + typecheck + corpus-skipped tests. macOS-only smoke
  targets (`make inference-smoke`, `make cohort-smoke`) require macOS + Metal;
  out of scope for free-tier CI.
- Action versioning: pin actions by full SHA (not floating `@v5` tag) when
  supply-chain risk matters. ADR-023 pins `astral-sh/setup-uv` to the v8.1.0
  SHA; `actions/checkout` uses `@v5` (acceptable risk for a first-party
  GitHub action with reproducible builds).
- Secrets: HORUS CI does NOT require secrets (no deploy, no external API
  calls). All inputs come from the checked-out repo + `pyproject.toml`.
-->
