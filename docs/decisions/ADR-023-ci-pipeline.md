# ADR-023 — GitHub Actions CI pipeline

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-23 |
| **Milestone** | Evidence-base audit follow-ups (PR 3 of 3-PR cluster: #63 → #62 → #64) |
| **Authored by** | Cascade D evidence-base audit follow-ups (`~/.windsurf/plans/audit-followups-7e4a25.md` §2.3) |
| **Supersession trigger** | See `## Supersession trigger` below |

## Context

HORUS has had **no continuous integration** through M2D.5 (issues #12 → #54 inclusive). Every quality gate (`make lint`, `make typecheck`, `make test`) has been enforced on developer trust + `@release-manager` discipline alone. The evidence-base audit (`~/.windsurf/plans/audit-branch-disposition-14db9b.md`) surfaced that this trust-based enforcement let:

1. **5 mypy errors** persist on `main` (3 `import-not-found` + 2 `union-attr`) — closed by PR 1 (ADR-022 / #65) + PR 2 (#66).
2. **7 ruff format drift files** persist on `main` — closed by PR 2 (#66).
3. **A direct push to `main`** slip through (per `branch-and-pr-required` rule's "consequences when violated" clause).
4. **Warm-`.mypy_cache/` nondeterminism** mask `import-not-found` errors when running `make typecheck` locally without cache clearing.

The audit-followups cluster closes the immediate failures (PR 1 + PR 2). This ADR closes the **discipline-only enforcement of `make-sure-it-works` for landed PRs** by introducing GitHub Actions CI that runs the same quality gates automatically on every push-to-main + every PR against main.

This ADR is the final PR of the cluster. After merge, the L1 forcing-function for "CI from day 1 on new projects" gets queued in `cascade-system/queue/pending-review.md` for cross-project triage at next `@sprint-review`.

## Decision

Land a **single CI workflow** at `.github/workflows/ci.yml` that runs on `ubuntu-latest` on every `push` to `main` + every `pull_request` against `main`. Steps:

1. `actions/checkout@v5` — checkout
2. `astral-sh/setup-uv@<v8.1.0 SHA>` — install + cache `uv` (Astral)
3. `uv sync --locked` — install deps from `uv.lock` (frozen; CI fails if lock is stale)
4. `make lint` — `ruff check` + `ruff format --check`
5. `rm -rf .mypy_cache && make typecheck` — typecheck with **cold cache** (mandatory per the audit's nondeterminism finding)
6. `make test-ci` — `pytest -m "not requires_corpus"` (deselects corpus-touching tests)

A new `requires_corpus` pytest marker (registered in `pyproject.toml` under `[tool.pytest.ini_options] markers`) gates corpus-touching tests via three application layers:

1. **Module-level `pytestmark = pytest.mark.requires_corpus`** on 5 test files that hard-fail without the ZUGFeRD corpus:
   - `tests/test_extract_zugferd_xml.py`
   - `tests/test_ground_truth.py`
   - `tests/test_rasterize.py`
   - `tests/test_scorer_integration.py`
   - `tests/test_scorer_integration_multipage.py`
2. **Test-level `@pytest.mark.requires_corpus`** on 15 specific tests in `tests/test_harness.py` (the file mixes pure-function tests + corpus-using tests; module-level marker would be over-applied). The initial author-time audit identified 8; a CI-realism check (temporarily moving the corpus dir and running `make test-ci`) caught 7 more `test_run_cohort_*` tests that also exercise the corpus through the harness. The full set is documented in the mechanical-changes enumeration below.
3. **`pytest_collection_modifyitems` hook** in `tests/conftest.py` that auto-marks any test consuming the corpus parametrized fixtures (`paired_invoice` / `en16931_paired_invoice` / `xrechnung_paired_invoice` / `corpus_fx_pdfs` / `corpus_cii_xmls`) — single source of truth for fixture-driven corpus dependency.

`tests/test_rescore.py` is left alone — it has its own `skip_if_no_fixtures` `pytest.mark.skipif` pattern that gracefully skips without corpus; no `requires_corpus` marker needed. `tests/test_config_pilot_13.py` references corpus paths only as default-config equality assertions (no actual filesystem read) — no marker needed.

Local invocation:

- `make test` — full suite (462 tests; requires corpus). Unchanged from pre-CI baseline.
- `make test-ci` — `pytest -m "not requires_corpus"` (subset; matches what CI runs on `ubuntu-latest`).

## Current-state survey

Dated 2026-05-23. Sources consulted via web search + `context7` MCP (`mcp2_resolve-library-id` + `mcp2_query-docs` for `setup-uv` 8.1.0).

- **GitHub Actions** (`https://docs.github.com/en/actions`): workflow YAML lives at `.github/workflows/<name>.yml`; triggers via `on:` block; per-job `runs-on:` declares the runner. `ubuntu-latest` aliases to Ubuntu 24.04 currently; first-party runner with Python pre-installed (3.10–3.13 range as of 2026-05) but uv re-installs the project Python (3.14) per `.python-version`.
- **`astral-sh/setup-uv` v8.1.0** (`https://github.com/astral-sh/setup-uv`): pin by full SHA `08807647e7069bb48b6ef5acd8ec9567f424441b`. `enable-cache: true` caches both the uv binary download and the dependency wheels. Cache key invalidates on changes to `cache-dependency-glob` (default: lock file + pyproject.toml; HORUS uses explicit `pyproject.toml` + `uv.lock`). `python-version` is optional — when omitted, `uv sync` reads `.python-version` (HORUS pins 3.14) and installs the right interpreter automatically. Self-installs uv via the standard install script; no Python prerequisite on the runner (uv is a Rust binary).
- **`uv sync --locked`** (`https://docs.astral.sh/uv/`): fails fast if `uv.lock` is stale relative to `pyproject.toml`. The `--locked` flag is the canonical CI invocation (vs `uv sync` which would attempt to update the lock). Prevents accidental dependency drift between local and CI environments.
- **pytest markers** (`https://docs.pytest.org/en/stable/example/markers.html`): custom markers are declared in `[tool.pytest.ini_options] markers = ["name: description"]`; pytest warns on unknown markers when `--strict-markers` is in `addopts` (HORUS doesn't currently use strict-markers, but the explicit registration is good hygiene). `pytest -m "not X"` deselects all tests with marker `X`. `pytest_collection_modifyitems` is the canonical hook for programmatic marker application.
- **mypy incremental-cache nondeterminism** (`docs/sources/tools/mypy-import-discovery.md` — authored as part of PR 1 / ADR-022): warm `.mypy_cache/` can silently mask `import-not-found` errors after configuration changes. The reliable verification command is `rm -rf .mypy_cache && uv run mypy ... --no-incremental` (or equivalently, `rm -rf .mypy_cache && make typecheck` since `make typecheck` invokes `uv run mypy ...`). This is the trap that the evidence-base audit identified.
- **Branch protection on `main`** (per `gh api repos/ReebalSami/horus/branches/main/protection`): `required_pull_request_reviews.required_approving_review_count: 1`, `enforce_admins: false`. PR 1 + PR 2 used `--admin` override (canonical solo-dev path); CI as a `required_status_check` would be a future strengthening (out of scope for this ADR — would require an additional `gh api -X PATCH ... required_status_checks` step + the workflow to have run at least once on `main`).

## Options considered

| # | Option | Pros | Cons |
|---|---|---|---|
| 1 | **GitHub Actions on `ubuntu-latest` + corpus-skipped tests** (chosen) | Free for public repos + 2000 free minutes/month for private repos; first-party tooling; setup-uv ships a 1-line install path; corpus-skip marker is a standard pytest pattern; no infra to maintain | macOS-only smoke targets (`make inference-smoke`, `make cohort-smoke`) NOT covered — discipline alone for those; corpus tests NOT covered — discipline alone for the 26-invoice corpus sweep |
| 2 | GitHub Actions with corpus committed to git | Full test coverage in CI | Corpus is 20+ MB across `data/raw/german/zugferd-corpus/`; git LFS adds complexity + storage cost; license drift risk (FeRD corpus license not blanket "redistribute in any repo") |
| 3 | GitHub Actions with corpus pulled from S3 / external storage | Full coverage without committing to git | Adds AWS dependency + cost + secrets management; corpus is not currently in any external bucket; out of scope for solo-dev thesis project |
| 4 | Self-hosted macOS runner for full smoke coverage | macOS-only targets covered | Requires a dedicated macOS machine running self-hosted runner agent; security exposure (CI executes PR code); maintenance burden; corpus problem still unsolved |
| 5 | No CI; discipline-only enforcement | Zero infra | The audit just demonstrated this fails — 5 mypy errors + 7 format drift + a direct push-to-main all landed on `main` without anyone noticing |

**Chosen: Option 1.** Reasons (in priority order):

1. **Restores `make-sure-it-works` as an automated gate** for lint + typecheck + non-corpus tests. The discipline-only failure mode that produced the audit is closed.
2. **Free for the project's scope** — 2000 CI-minutes/month covers HORUS's PR cadence with significant headroom.
3. **Standard pattern** — `astral-sh/setup-uv` is the canonical Astral-recommended CI integration; well-trodden path with predictable cache behavior.
4. **Corpus-skip marker design preserves the local-vs-CI contract**: full suite (`make test`) runs locally with corpus; CI subset (`make test-ci`) runs without. No test is silently dropped; the marker is explicit + visible at every call site.
5. **Option 4 (self-hosted macOS) deferred** to a future ADR if/when MPS-backed smoke coverage in CI becomes load-bearing for thesis-defense reproducibility. Currently the smoke targets are exercised locally + their evidence is captured in `docs/sources/transcripts*` + MLflow run artifacts.

## Decision + integration thoughts

### Interaction with already-decided components

- **PR 1 / ADR-022** (`scripts/` package status, merged in `6a71724`): the `from scripts import …` migration + pytest `pythonpath = ["."]` config make the test imports work natively in CI without any per-file `sys.path` manipulation. CI was a forcing function for getting this right.
- **PR 2 / #62** (lint + typecheck restore, merged in `8b48723`): `make lint` + `make typecheck` are now green on `main`. CI keeps them green going forward.
- **`branch-and-pr-required` rule** (cascade-system): this ADR is the auto-enforcement layer. The agent-side discipline (refuse to push to `main`) + GitHub-side branch protection (require PR + review) + CI (require lint/typecheck/test-ci green) together form the durable defense against the audit's failure modes.
- **`make-sure-it-works` rule** (cascade-system): "Evidence over claims. Run lint/build/test/demo before declaring done." CI is the automated evidence channel; the rule shifts from "Cascade-asserted-after-local-run" to "CI-asserted-on-every-PR".
- **`@release-manager` skill** (cascade-system ADR-018): step 4 ("artifact review gate") gains an automated counterpart in `/ci-watch`. Once this ADR lands + the first CI run goes green, `@release-manager` can route through `/ci-watch <pr-number>` as a hard-gate before `/branch-merge-and-cleanup`.

### Forward-compatibility

- **Future tests touching new corpora** (e.g., a non-ZUGFeRD invoice corpus, a CORD-v2 OCR corpus) inherit the `requires_corpus` marker pattern. The auto-marking hook in `conftest.py` handles fixture-driven cases; module-level `pytestmark` handles direct-path cases.
- **Future CI steps** (e.g., `make coverage`, `make docs-build`, `make security-scan`) are additive — append after `make test-ci`. The lint + typecheck + test-ci ordering is non-load-bearing; rearrange as needed.
- **Future runners** (matrix over Python 3.14 / 3.15 / etc.) — `astral-sh/setup-uv` supports a matrix via `python-version: ${{ matrix.python-version }}`. Currently HORUS pins 3.14 only; matrix expansion is a future ADR.

### Mechanical changes (full enumeration)

1. **`pyproject.toml`** — append to `[tool.pytest.ini_options]`:
   ```toml
   markers = [
       "requires_corpus: test requires the ZUGFeRD test corpus at data/raw/german/zugferd-corpus/ (deselected by make test-ci; per ADR-023)",
   ]
   ```
2. **`tests/conftest.py`** — append a `pytest_collection_modifyitems` hook that auto-marks tests consuming corpus parametrized fixtures.
3. **5 test files** — add `pytestmark = pytest.mark.requires_corpus` at module level (after `import pytest`):
   - `tests/test_extract_zugferd_xml.py`
   - `tests/test_ground_truth.py`
   - `tests/test_rasterize.py`
   - `tests/test_scorer_integration.py`
   - `tests/test_scorer_integration_multipage.py`
4. **`tests/test_harness.py`** — add `@pytest.mark.requires_corpus` to 15 tests:
   - Initial 8 (author-time audit): `test_list_paired_invoices_matches_conftest_helper`, `test_run_cohort_single_model_single_invoice_e2e`, `test_run_cohort_resume_skips_finished_nested_runs`, `test_run_cohort_xrechnung_uses_facturx_not_sidecar`, `test_run_cohort_profile_aggregation`, `test_run_cohort_invoice_subset_from_yaml_applied`, `test_run_cohort_cli_invoice_subset_overrides_yaml`, `test_run_cohort_dev_only_tags_parent_and_nested_runs`.
   - 7 more (caught by the CI-realism check — `mv data/raw/german/zugferd-corpus /tmp/... && make test-ci`): `test_run_cohort_logs_perf_metrics_in_nested_run_mlx_backend`, `test_run_cohort_logs_perf_metrics_in_nested_run_mps_backend`, `test_run_cohort_regex_adapter_mode_is_default_back_compat`, `test_run_cohort_json_adapter_mode_with_full_overrides`, `test_run_cohort_partial_prompt_override_falls_through_to_manifest`, `test_run_cohort_adapter_mode_tag_propagates_to_nested_runs`, `test_run_cohort_dev_only_false_tags_runs_as_false`. All exercise the corpus through the harness's `_make_test_cfg(tmp_path)` + `run_cohort(cfg)` pattern.
5. **`Makefile`** — add the `test-ci` target:
   ```makefile
   test-ci:
       uv run pytest -m "not requires_corpus"
   ```
6. **`.github/workflows/ci.yml`** — new file with the workflow described in `## Decision` above.

### Known limitations (become risk items / future work)

- **macOS-only smoke targets not covered by CI** — `make inference-smoke` + `make cohort-smoke` require macOS + Metal + corpus. Currently covered by discipline + local execution evidence in `docs/sources/transcripts*` + MLflow runs. If a regression in these targets lands silently, only manual re-execution catches it. Mitigation: thesis-defense-window full re-run + the eventual ADR for self-hosted macOS CI.
- **Corpus tests not covered by CI** — same rationale as above. Locally `make test` (full suite) is the gate; CI runs `make test-ci` only. The 5+8 marker-tagged tests + the auto-marked fixture consumers are skipped on CI. Mitigation: pre-merge local `make test` run via `@release-manager` step 4 (artifact + verification review gate).
- **CI as required status check NOT YET configured** — `gh api -X PATCH ... required_status_checks` requires the workflow to have run at least once on `main` (to register the check). Post-merge of this ADR, a follow-up step will add CI as a required check (separate small PR or in-place via the GitHub UI; not load-bearing for the ADR scope).
- **Cache key invalidation on every `pyproject.toml` change** — including doc-only changes to `[project]` metadata. Acceptable trade-off for explicit, predictable cache behavior.

### First-CI-run amendments (2026-05-23)

The first CI run on PR #67 (commit `5d0074c`) caught two gaps that the author-time audit + corpus-absent local simulation missed. Both are amendments to the original Decision section; the test-marker design is unchanged.

**Amendment 1 — Platform skip on `tests/test_inference_smoke.py` (3 tests)**

ADR-007's dual-track stack (`mlx-vlm` + `transformers` + PyTorch MPS) is macOS/Apple-Silicon-only. The import-only smokes for `mlx_vlm` / `mlx.core` / `torch.backends.mps.is_available()` fail on `ubuntu-latest` with `ImportError: libmlx.so` + `AssertionError: PyTorch MPS backend not available`. Fix: add `@pytest.mark.skipif(sys.platform != "darwin", ...)` to 3 of the 4 tests in the file (`test_transformers_importable` stays unconditional — transformers is cross-platform). The `requires_macos` skipif marker is defined at module-top via `pytest.mark.skipif(sys.platform != "darwin", ...)`.

Reasoning for `skipif` over a custom marker (analogous to `requires_corpus`): platform availability is a hard environmental gate; `skipif` is the standard pytest idiom and doesn't need registration. The `requires_corpus` marker exists because corpus presence is a deliberate data-availability gate that `make test-ci` consults; macOS-only is a runtime platform gate, semantically distinct.

**Amendment 2 — Strengthen `_HAS_CORPUS` predicate in `tests/test_rescore.py`**

The original predicate `_HAS_CORPUS = CORPUS_ROOT.is_dir()` was too weak. Per `.gitignore`'s allowlist for per-corpus audit-trail records (`!data/raw/german/*/MANIFEST.md`), the `data/raw/german/zugferd-corpus/` directory exists on CI checkout containing only `MANIFEST.md` (+ `LICENSE`, `README.md`, `sha256.txt`). `is_dir()` returns True; the 3 `@skip_if_no_fixtures`-decorated tests run; factur-x extraction over non-existent PDFs returns empty → F1=0 → `assert 0.45 < 0.0` fails.

Fix: `_HAS_CORPUS = CORPUS_ROOT.is_dir() and any((CORPUS_ROOT / "XML-Rechnung" / "FX").glob("*.pdf"))`. Matches the `XML-Rechnung/FX/` layout that `tests/conftest.py` also expects. On CI: predicate evaluates to False → `skip_if_no_fixtures` correctly triggers → 3 tests skip.

**Process learning for future CI introductions**

The local CI-realism simulation (`mv data/raw/german/zugferd-corpus /tmp/...`) was insufficient — it moved the entire dir, hiding the empty-MANIFEST-only state that CI's `git clone` actually produces. A more accurate sim:

```sh
# CI-equivalent: dir present, content absent
mv data/raw/german/zugferd-corpus/XML-Rechnung /tmp/stash-X
mv data/raw/german/zugferd-corpus/unstructured /tmp/stash-X
mv data/raw/german/zugferd-corpus/{fatturaPA,incoming,other,PEPPOL,ZUGFeRDv1,ZUGFeRDv2} /tmp/stash-X
make test-ci  # the load-bearing assertion
# Restore:
mv /tmp/stash-X/* data/raw/german/zugferd-corpus/
```

The general principle: simulate the **git-checkout-only state** (tracked files only), not the **dir-absent state**. Captured in the L1 queue entry for cross-project propagation.

## Source archival

- `docs/sources/tools/github-actions.md` — GitHub Actions documentation reference stub.
- `docs/sources/tools/astral-setup-uv.md` — `astral-sh/setup-uv` v8.1.0 reference stub.
- `docs/sources/tools/mypy-import-discovery.md` *(already exists from PR 1)* — referenced for the cache-cleared-mypy invariant.
- `docs/sources/tools/pytest-pythonpath.md` *(already exists from PR 1)* — referenced for pytest config in `pyproject.toml`.

## Supersession trigger

This ADR is superseded if:

- **HORUS adopts self-hosted macOS CI** (e.g., for MPS-backed smoke coverage on every PR). The supersession ADR would document the runner setup, security model, and corpus-mount approach.
- **HORUS moves to a different CI provider** (e.g., GitLab CI for institutional reasons, Circle CI for matrix flexibility, GitHub-hosted larger runners with Metal). The supersession ADR would document the migration + cache pattern change.
- **The `requires_corpus` marker becomes load-bearing for additional gating** (e.g., coverage report exclusions, mutation testing skip lists). The supersession ADR would document the marker's expanded scope.
- **GitHub deprecates `actions/checkout@v5` or `astral-sh/setup-uv` versioning conventions** in ways that require workflow restructuring.

## Consequences

- **Positive**: lint + typecheck + non-corpus tests are auto-enforced on every PR + every push-to-`main`. The audit's failure modes are durably closed. CI run time is ~2–4 minutes (uv setup + sync from cache ~30s; lint ~5s; typecheck cache-cleared ~60s; test-ci ~30s). Token-economy favorable — Cascade no longer needs to re-run `make lint && make typecheck && make test` in every session before declaring "done"; CI does it.
- **Negative**: PR turnaround gains a ~3-minute CI wait. Solo-dev workflow: minimal disruption (PR opens → 3 min later → `/ci-watch` reports green → merge).
- **Neutral**: corpus tests + smoke targets remain discipline-enforced locally. The audit identified this exact gap as the dominant failure mode; this ADR closes 75% of it (lint + typecheck + non-corpus tests are now automated). The remaining 25% (corpus tests + macOS smoke) stays on discipline, with the L1 queue entry documenting it as a candidate for future CI strengthening.

## Related ADRs

- **ADR-001** — tool-decision discipline (mandates this ADR's 5-section shape).
- **ADR-009** — ADR numbering protocol (reserved ADR-023 in INDEX before file authoring).
- **ADR-018** — `@release-manager` release-discipline cluster. CI completes the release gate (push → PR → CI → squash-merge).
- **ADR-022** (PR 1 of this cluster, merged) — `scripts/` package status. CI was a forcing function for getting the import structure right.
- **Forthcoming** — branch-protection-required-checks ADR (out of scope for this ADR; tracked post-merge).

## L1 queue entry (post-merge)

After this PR merges, append a forcing-function entry to `~/Projects/cascade-system/queue/pending-review.md`:

```markdown
- **Insight**: `/start-project` should bootstrap `.github/workflows/ci.yml` from the L3 template's `_shared/scaffold/.github/workflows/ci.yml` (and/or `<type>/scaffold/`) so every new project has CI from day 1. The audit-followups cluster demonstrated that retrofitting CI to a project that has been running on discipline alone produces a 3-PR cluster of cleanup (lint+typecheck restore + import structure ratification + the CI workflow itself). New projects should not pay this cost.
- **Source**: ReebalSami/horus PR #65 (ADR-022), PR #66 (#62), PR #67 (ADR-023, this PR) + cascade-system audit-followups plan
- **Project**: cascade-system
- **Cascade**: D
- **Date observed**: 2026-05-23
- **Proposed L1 change**: extend `python-ml-uv` L3 template `scaffold/` (or `_shared/scaffold/`) with `.github/workflows/ci.yml` bootstrapped from the HORUS CI design. Also extend `@release-manager` step 4 (or add step 4.5) to detect "no CI configured" + surface a warning at the merge gate ("PR has no CI configured; relying on manual review only — confirm?").
- **Project-local action**: ADR-023 (this PR) ratifies the HORUS-specific CI; followup is whether to elevate to L3 default for python-ml-uv template.
```
