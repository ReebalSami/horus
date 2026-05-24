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
6. `make test` — full pytest suite; corpus-dependent tests auto-skip via `pytest.mark.skipif`

### Test gating via `pytest.mark.skipif` (canonical pytest pattern)

Corpus-dependent tests and macOS-only tests are gated via **`pytest.mark.skipif` decorators** stored in `tests/_corpus.py` and `tests/test_inference_smoke.py`. This is pytest's official-recommended pattern:

> "*It is **better to use the `pytest.mark.skipif` marker when possible** to declare a test to be skipped under certain conditions like mismatching platforms or dependencies.*" — [pytest API reference](https://docs.pytest.org/en/stable/reference/reference.html)

> "*A skip means that you expect your test to pass only if some conditions are met... Common examples are skipping windows-only tests on non-windows platforms, or **skipping tests that depend on an external resource which is not available at the moment**.*" — [pytest skipping docs](https://docs.pytest.org/en/stable/how-to/skipping.html)

Mirrors `scikit-learn`'s `sklearn/utils/_testing.py` named-skipif-decorator pattern (e.g., `skip_if_array_api_compat_not_configured = pytest.mark.skipif(not ARRAY_API_COMPAT_FUNCTIONAL, reason=...)`).

**Three application layers, one mechanism:**

1. **Module-level `pytestmark = skip_if_no_corpus`** on 5 test files that hard-fail without the ZUGFeRD corpus:
   - `tests/test_extract_zugferd_xml.py`
   - `tests/test_ground_truth.py`
   - `tests/test_rasterize.py`
   - `tests/test_scorer_integration.py`
   - `tests/test_scorer_integration_multipage.py`
2. **Test-level `@skip_if_no_corpus`** on 15 specific tests in `tests/test_harness.py` (the file mixes pure-function tests + corpus-using tests; module-level marker would be over-applied). All exercise the corpus through `_make_test_cfg(tmp_path)` + `run_cohort(cfg)`.
3. **Parametrized-fixture auto-disappearance** — `_list_paired_invoices()` returns `[]` when the corpus content is absent → pytest's parametrize produces zero items → tests using `paired_invoice` / `en16931_paired_invoice` / `xrechnung_paired_invoice` / `corpus_fx_pdfs` / `corpus_cii_xmls` simply don't get collected. **No explicit marking needed**; the empty-list mechanism is the gate.

`tests/test_rescore.py` uses the sibling `@skip_if_no_fixtures` decorator (predicate combines `_HAS_CORPUS` AND `_HAS_TRANSCRIPTS` — the test_rescore tests need both the FX/*.pdf corpus AND the git-tracked `docs/sources/transcripts-multipage/*.txt`). Same skipif pattern. Same `tests/_corpus.py` module. `tests/test_inference_smoke.py` uses `@requires_macos = pytest.mark.skipif(sys.platform != "darwin", ...)` on 3 of the 4 tests (MLX + MPS are Apple-Silicon-only).

### Content-aware corpus predicate

```python
# tests/_corpus.py
_HAS_CORPUS = ZUGFERD_FX_DIR.is_dir() and any(ZUGFERD_FX_DIR.glob("*.pdf"))
```

`ZUGFERD_FX_DIR.is_dir()` alone is **too weak**: per `.gitignore`'s allowlist for per-corpus audit-trail records (`!data/raw/german/*/MANIFEST.md`), the `data/raw/german/zugferd-corpus/` directory exists on CI checkout containing only `MANIFEST.md` + `LICENSE` + `README.md` + `sha256.txt`. `is_dir()` returns True. The content-aware predicate inspects actual PDF presence.

### Local + CI invocation: same target

```
make test
```

Locally with corpus → 462 tests pass. Locally without corpus → 342 pass + 71 skip (corpus) + 3 skip (rescore) = 416 total non-collected/skipped (49 parametrized invoice tests don't collect; 71 explicit skipif fires). CI on `ubuntu-latest` → identical to local-without-corpus state. **No `make test-ci` target. No `-m "not X"` filter. No CLI flag gymnastics.**

## Current-state survey

Dated 2026-05-23. Sources consulted via web search + `context7` MCP (`mcp2_resolve-library-id` + `mcp2_query-docs` for `setup-uv` 8.1.0). Test-gating design decision validated through additional deep web research (see `## Design evolution` below).

- **GitHub Actions** (`https://docs.github.com/en/actions`): workflow YAML lives at `.github/workflows/<name>.yml`; triggers via `on:` block; per-job `runs-on:` declares the runner. `ubuntu-latest` aliases to Ubuntu 24.04 currently; first-party runner with Python pre-installed (3.10–3.13 range as of 2026-05) but uv re-installs the project Python (3.14) per `.python-version`.
- **`astral-sh/setup-uv` v8.1.0** (`https://github.com/astral-sh/setup-uv`): pin by full SHA `08807647e7069bb48b6ef5acd8ec9567f424441b`. `enable-cache: true` caches both the uv binary download and the dependency wheels. Cache key invalidates on changes to `cache-dependency-glob` (default: lock file + pyproject.toml; HORUS uses explicit `pyproject.toml` + `uv.lock`). `python-version` is optional — when omitted, `uv sync` reads `.python-version` (HORUS pins 3.14) and installs the right interpreter automatically. Self-installs uv via the standard install script; no Python prerequisite on the runner (uv is a Rust binary).
- **`uv sync --locked`** (`https://docs.astral.sh/uv/`): fails fast if `uv.lock` is stale relative to `pyproject.toml`. The `--locked` flag is the canonical CI invocation (vs `uv sync` which would attempt to update the lock). Prevents accidental dependency drift between local and CI environments.
- **pytest `skipif` vs custom markers** (`https://docs.pytest.org/en/stable/how-to/skipping.html` + `https://docs.pytest.org/en/stable/reference/reference.html`): pytest officially recommends `skipif` for environmental-condition gating (platform, dependency, data availability); custom markers are for opt-in test categorization (slow, network, gpu — where the developer chooses via CLI flag). Named skipif decorators (`skip_if_X = pytest.mark.skipif(...)`) are the canonical reuse pattern: *"For larger test suites it's usually a good idea to have one file where you define the markers which you then consistently apply throughout your test suite."*
- **scikit-learn precedent** (`https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/utils/_testing.py`): the most-relevant scientific Python project uses exactly this pattern — named skipif decorators in a centralized `_testing.py` helper module (e.g., `skip_if_array_api_compat_not_configured`).
- **mypy incremental-cache nondeterminism** (`docs/sources/tools/mypy-import-discovery.md` — authored as part of PR 1 / ADR-022): warm `.mypy_cache/` can silently mask `import-not-found` errors after configuration changes. The reliable verification command is `rm -rf .mypy_cache && uv run mypy ... --no-incremental` (or equivalently, `rm -rf .mypy_cache && make typecheck` since `make typecheck` invokes `uv run mypy ...`). This is the trap that the evidence-base audit identified.
- **Branch protection on `main`** (per `gh api repos/ReebalSami/horus/branches/main/protection`): `required_pull_request_reviews.required_approving_review_count: 1`, `enforce_admins: false`. PR 1 + PR 2 used `--admin` override (canonical solo-dev path); CI as a `required_status_check` would be a future strengthening (out of scope for this ADR — would require an additional `gh api -X PATCH ... required_status_checks` step + the workflow to have run at least once on `main`).

## Options considered

### Macro decision — CI provider + scope

| # | Option | Pros | Cons |
|---|---|---|---|
| 1 | **GitHub Actions on `ubuntu-latest` + corpus-skipped tests** (chosen) | Free for public repos + 2000 free minutes/month for private repos; first-party tooling; setup-uv ships a 1-line install path; corpus tests auto-skip via pytest standard pattern; no infra to maintain | macOS-only smoke targets (`make inference-smoke`, `make cohort-smoke`) NOT covered — discipline alone for those; corpus tests NOT covered — discipline alone for the 26-invoice corpus sweep |
| 2 | GitHub Actions with corpus committed to git | Full test coverage in CI | Corpus is 145+ MB; git LFS adds complexity + storage cost; license drift risk (FeRD corpus license not blanket "redistribute in any repo") |
| 3 | GitHub Actions with corpus pulled from S3 / external storage | Full coverage without committing to git | Adds AWS dependency + cost + secrets management; corpus is not currently in any external bucket; out of scope for solo-dev thesis project |
| 4 | Self-hosted macOS runner for full smoke coverage | macOS-only targets covered | Requires a dedicated macOS machine running self-hosted runner agent; security exposure (CI executes PR code); maintenance burden; corpus problem still unsolved |
| 5 | No CI; discipline-only enforcement | Zero infra | The audit just demonstrated this fails — 5 mypy errors + 7 format drift + a direct push-to-main all landed on `main` without anyone noticing |

**Chosen: Option 1.** Reasons (in priority order):

1. **Restores `make-sure-it-works` as an automated gate** for lint + typecheck + non-corpus tests. The discipline-only failure mode that produced the audit is closed.
2. **Free for the project's scope** — 2000 CI-minutes/month covers HORUS's PR cadence with significant headroom.
3. **Standard pattern** — `astral-sh/setup-uv` is the canonical Astral-recommended CI integration; well-trodden path with predictable cache behavior.
4. **Local + CI use the same `make test` invocation** — single mechanism, single mental model. Tests skip with informative reasons in both environments; no parallel `test-ci` target to maintain.
5. **Option 4 (self-hosted macOS) deferred** to a future ADR if/when MPS-backed smoke coverage in CI becomes load-bearing for thesis-defense reproducibility. Currently the smoke targets are exercised locally + their evidence is captured in `docs/sources/transcripts*` + MLflow run artifacts.

### Micro decision — test gating mechanism

| Pattern | Use case | HORUS fit |
|---|---|---|
| `pytest.mark.skipif(predicate)` (chosen) | Environmental-condition gating where tests **should always skip** when conditions aren't met (platform, dependency, data, hardware) | ✅ Correct fit. Mirrors existing `skip_if_no_fixtures` in `tests/test_rescore.py`. Mirrors scikit-learn's `sklearn/utils/_testing.py` pattern. Pytest's official-recommended pattern. |
| Custom marker + `-m "not X"` deselect | Opt-in test categorization where the **developer chooses** whether to run them via CLI flag (e.g., HuggingFace `@slow`, pytest `@network`, `@gpu`) | ❌ Wrong fit. Corpus presence is a filesystem fact, not a developer choice. The CLI-flag-forgetting footgun is real (caught by the first CI run). |

**Chosen: `pytest.mark.skipif`.** Full design-evolution audit trail in `## Design evolution` below.

## Decision + integration thoughts

### Interaction with already-decided components

- **PR 1 / ADR-022** (`scripts/` package status, merged in `6a71724`): the `from scripts import …` migration + pytest `pythonpath = ["."]` config make the test imports work natively in CI without any per-file `sys.path` manipulation. CI was a forcing function for getting this right.
- **PR 2 / #62** (lint + typecheck restore, merged in `8b48723`): `make lint` + `make typecheck` are now green on `main`. CI keeps them green going forward.
- **`branch-and-pr-required` rule** (cascade-system): this ADR is the auto-enforcement layer. The agent-side discipline (refuse to push to `main`) + GitHub-side branch protection (require PR + review) + CI (require lint/typecheck/test green) together form the durable defense against the audit's failure modes.
- **`make-sure-it-works` rule** (cascade-system): "Evidence over claims. Run lint/build/test/demo before declaring done." CI is the automated evidence channel; the rule shifts from "Cascade-asserted-after-local-run" to "CI-asserted-on-every-PR".
- **`@release-manager` skill** (cascade-system ADR-018): step 4 ("artifact review gate") gains an automated counterpart in `/ci-watch`. Once this ADR lands + the first CI run goes green, `@release-manager` can route through `/ci-watch <pr-number>` as a hard-gate before `/branch-merge-and-cleanup`.

### Forward-compatibility

- **Future tests touching new corpora** (e.g., a non-ZUGFeRD invoice corpus, a CORD-v2 OCR corpus) inherit the skipif decorator pattern: add a new named decorator in `tests/_corpus.py` (or a sibling helper module), apply it at module-level (`pytestmark = skip_if_no_X`) or test-level (`@skip_if_no_X`), done. No marker registration; no CI-target rewiring.
- **Future CI steps** (e.g., `make coverage`, `make docs-build`, `make security-scan`) are additive — append after `make test`. The lint + typecheck + test ordering is non-load-bearing; rearrange as needed.
- **Future runners** (matrix over Python 3.14 / 3.15 / etc.) — `astral-sh/setup-uv` supports a matrix via `python-version: ${{ matrix.python-version }}`. Currently HORUS pins 3.14 only; matrix expansion is a future ADR.

### Mechanical changes (full enumeration)

1. **`tests/_corpus.py`** *(new)* — canonical helper module:
   - Path constants (`ZUGFERD_FX_DIR`, `TRANSCRIPTS_DIR`, etc.) as the single source of truth.
   - Content-aware predicates: `_HAS_CORPUS = ZUGFERD_FX_DIR.is_dir() and any(ZUGFERD_FX_DIR.glob("*.pdf"))`; `_HAS_TRANSCRIPTS`; `_HAS_FIXTURES = _HAS_CORPUS and _HAS_TRANSCRIPTS`.
   - Exported skipif decorators: `skip_if_no_corpus = pytest.mark.skipif(not _HAS_CORPUS, ...)`; `skip_if_no_fixtures = pytest.mark.skipif(not _HAS_FIXTURES, ...)`.
2. **`tests/conftest.py`** — re-exports path constants from `tests._corpus` (backward compat with `from tests.conftest import ZUGFERD_FX_DIR`); keeps the parametrized fixtures (`paired_invoice`, etc.); the original marker-design `pytest_collection_modifyitems` auto-mark hook is deleted (parametrize-empty-when-corpus-missing handles fixture-driven gating natively).
3. **5 test files** — add `from tests._corpus import skip_if_no_corpus` + `pytestmark = skip_if_no_corpus`:
   - `tests/test_extract_zugferd_xml.py`
   - `tests/test_ground_truth.py`
   - `tests/test_rasterize.py`
   - `tests/test_scorer_integration.py`
   - `tests/test_scorer_integration_multipage.py`
4. **`tests/test_harness.py`** — add `from tests._corpus import skip_if_no_corpus` + `@skip_if_no_corpus` on 15 tests (full list: `test_list_paired_invoices_matches_conftest_helper`, `test_run_cohort_single_model_single_invoice_e2e`, `test_run_cohort_resume_skips_finished_nested_runs`, `test_run_cohort_xrechnung_uses_facturx_not_sidecar`, `test_run_cohort_profile_aggregation`, `test_run_cohort_invoice_subset_from_yaml_applied`, `test_run_cohort_cli_invoice_subset_overrides_yaml`, `test_run_cohort_dev_only_tags_parent_and_nested_runs`, `test_run_cohort_logs_perf_metrics_in_nested_run_mlx_backend`, `test_run_cohort_logs_perf_metrics_in_nested_run_mps_backend`, `test_run_cohort_regex_adapter_mode_is_default_back_compat`, `test_run_cohort_json_adapter_mode_with_full_overrides`, `test_run_cohort_partial_prompt_override_falls_through_to_manifest`, `test_run_cohort_adapter_mode_tag_propagates_to_nested_runs`, `test_run_cohort_dev_only_false_tags_runs_as_false`).
5. **`tests/test_rescore.py`** — `from tests._corpus import skip_if_no_fixtures, TRANSCRIPTS_DIR, ZUGFERD_CORPUS_DIR as CORPUS_ROOT`; local duplicate definitions deleted.
6. **`tests/test_inference_smoke.py`** — `requires_macos = pytest.mark.skipif(sys.platform != "darwin", ...)` on 3 of 4 tests (`test_transformers_importable` stays unconditional — transformers is cross-platform).
7. **`pyproject.toml`** — no `[tool.pytest.ini_options] markers` registration needed (skipif requires no registration).
8. **`Makefile`** — single `test` target (`uv run pytest`). No `test-ci` variant.
9. **`.github/workflows/ci.yml`** — `make test` (not `make test-ci`).

### Known limitations (become risk items / future work)

- **macOS-only smoke targets not covered by CI** — `make inference-smoke` + `make cohort-smoke` require macOS + Metal + corpus. Currently covered by discipline + local execution evidence in `docs/sources/transcripts*` + MLflow runs. If a regression in these targets lands silently, only manual re-execution catches it. Mitigation: thesis-defense-window full re-run + the eventual ADR for self-hosted macOS CI.
- **Corpus tests not exercised by CI** — same rationale as above. Locally `make test` with corpus present exercises 462 tests; CI runs the same `make test` and the 71 corpus-dependent tests skip + the 49 parametrized-invoice tests don't collect. Mitigation: pre-merge local `make test` run via `@release-manager` step 4 (artifact + verification review gate).
- **CI as required status check NOT YET configured** — `gh api -X PATCH ... required_status_checks` requires the workflow to have run at least once on `main` (to register the check). Post-merge of this ADR, a follow-up step will add CI as a required check (separate small PR or in-place via the GitHub UI; not load-bearing for the ADR scope).
- **Cache key invalidation on every `pyproject.toml` change** — including doc-only changes to `[project]` metadata. Acceptable trade-off for explicit, predictable cache behavior.

## Design evolution (audit trail)

This ADR's test-gating design was refined twice during the first CI runs on PR #67. The trail is preserved here because the wrong-pattern → first-CI-amendment → user-challenge → research → right-pattern progression is itself a load-bearing lesson for future CI-introduction ADRs.

### Iteration 1 — `requires_corpus` marker + `make test-ci` (initial design)

Original Decision section proposed a `requires_corpus` pytest custom marker, registered in `pyproject.toml`, deselected via `pytest -m "not requires_corpus"` in a separate `make test-ci` Makefile target. Three application layers: module-level `pytestmark`, test-level `@pytest.mark.requires_corpus`, and a `pytest_collection_modifyitems` auto-marker hook for fixture-driven cases.

Local verification (initial commit `5d0074c`): `make test-ci` corpus-absent simulation showed 342 passed + 3 skipped + 68 deselected + 0 failed. Looked complete; PR opened.

### Iteration 2 — First-CI-run amendments (commit `8e57b7c`)

The first CI run on `ubuntu-latest` (PR #67 commit `5d0074c`) failed with **5 failures**: 3 in `tests/test_inference_smoke.py` (MLX + MPS Apple-Silicon-only imports) + 2 in `tests/test_rescore.py` (`_HAS_CORPUS = CORPUS_ROOT.is_dir()` predicate too weak; CI checkout has `MANIFEST.md` under the corpus dir per `.gitignore` allowlist, so the predicate evaluated True even though no PDFs were present).

The local CI-realism simulation (`mv data/raw/german/zugferd-corpus /tmp/...`) had been insufficient — it moved the entire dir, hiding the empty-MANIFEST-only state that CI's `git clone` actually produces. The corpus-absent state on Mac is NOT equivalent to the CI state on Linux for two reasons: (a) Mac has MLX + MPS, Linux doesn't, and (b) Mac with corpus moved has dir-absent, CI with corpus-gitignored has dir-present-content-absent.

Fix (commit `8e57b7c`):
- `tests/test_inference_smoke.py` — `requires_macos = pytest.mark.skipif(sys.platform != "darwin", ...)` on the 3 macOS-only tests.
- `tests/test_rescore.py` — strengthen `_HAS_CORPUS` to `CORPUS_ROOT.is_dir() and any((CORPUS_ROOT / "XML-Rechnung" / "FX").glob("*.pdf"))`.

CI re-ran on `8e57b7c` → all checks passed in 2m0s.

### Iteration 3 — Skipif-unification redesign (this ADR's final design)

User challenge after Iteration 2 went green: *"why do we have deselected at the first place. skipped and unselected look wrong to me."*

Deep research into pytest official + scientific Python ecosystem (scikit-learn, HuggingFace transformers, pandas, Django) revealed the marker-design was the wrong-pattern fit for HORUS's case:

- **Pytest's official recommendation** (API reference): *"It is better to use the pytest.mark.skipif marker when possible to declare a test to be skipped under certain conditions like mismatching platforms or dependencies."*
- **Pytest's official guidance on skip semantics** (skipping docs): *"A skip means... skipping tests that depend on an external resource which is not available at the moment."* — verbatim the corpus case.
- **scikit-learn's pattern** (`sklearn/utils/_testing.py`): named skipif decorators (`skip_if_array_api_compat_not_configured = pytest.mark.skipif(...)`). Identical mechanism to the existing `skip_if_no_fixtures` in `tests/test_rescore.py` predating this ADR.
- **HuggingFace's marker pattern** (`@slow`, `@require_torch`): used specifically for **opt-in** integration tests where the developer decides via `--run-slow` CLI flag whether to run them. Different category from "external resource availability".

Design flaws identified in Iteration-1+2 marker pattern:
1. **CLI-flag-forgetting footgun** — Iteration 2 itself exposed this. The fix-strengthen-rerun cycle was the diagnostic.
2. **Inconsistency** — the same repo already had `@skip_if_no_fixtures` (skipif pattern) in `test_rescore.py`. Adding `requires_corpus` (marker pattern) created two mechanisms for one semantic.
3. **Over-engineering** — required marker registration + separate `make test-ci` + `pytest_collection_modifyitems` hook. The skipif pattern needs none of these; fixture-driven tests auto-disappear via empty-parametrize.

Iteration 3 (this ADR's final state): single `tests/_corpus.py` helper module exports `skip_if_no_corpus` + `skip_if_no_fixtures`; all 5 module-level + 15 test-level applications migrated; `pytest_collection_modifyitems` hook deleted; `pyproject.toml` marker registration deleted; `make test-ci` deleted; CI runs `make test`. Net negative LoC.

### Process learnings for future CI-introduction ADRs

1. **Default to skipif over custom markers** for tests gated by environmental conditions (platform, dependency, data, hardware). Reserve custom markers for opt-in test categorization (slow, network, gpu).
2. **CI-realism local simulation must match the git-checkout-only state**, not the dir-absent state. Specifically: move content subdirs to /tmp, but keep all git-tracked files in place. For HORUS this means keeping `MANIFEST.md` + `LICENSE` + `README.md` + `sha256.txt` while moving `XML-Rechnung/` + `unstructured/` + `fatturaPA/` + etc.
3. **Cross-platform tests must consider hardware availability**, not just OS. MLX needs Apple Silicon Metal; MPS needs Apple Silicon. Linux CI runners have neither. Discover during author-time, not during first-CI-run.
4. **When in doubt, consult the project's existing patterns**. The `skip_if_no_fixtures` in `tests/test_rescore.py` was a working precedent that the author-time design should have noticed + extended, not parallel-mechanism-built.

## Source archival

- `docs/sources/tools/github-actions.md` — GitHub Actions documentation reference stub.
- `docs/sources/tools/astral-setup-uv.md` — `astral-sh/setup-uv` v8.1.0 reference stub.
- `docs/sources/tools/mypy-import-discovery.md` *(already exists from PR 1)* — referenced for the cache-cleared-mypy invariant.
- `docs/sources/tools/pytest-pythonpath.md` *(already exists from PR 1)* — referenced for pytest config in `pyproject.toml`.
- `docs/sources/tools/pytest-skipping.md` *(new in Iteration 3)* — pytest's official skip-vs-marker recommendation; scikit-learn precedent; HuggingFace contrast.

## Supersession trigger

This ADR is superseded if:

- **HORUS adopts self-hosted macOS CI** (e.g., for MPS-backed smoke coverage on every PR). The supersession ADR would document the runner setup, security model, and corpus-mount approach.
- **HORUS moves to a different CI provider** (e.g., GitLab CI for institutional reasons, Circle CI for matrix flexibility, GitHub-hosted larger runners with Metal). The supersession ADR would document the migration + cache pattern change.
- **A future test-gating need genuinely requires opt-in categorization** (slow tests where the developer chooses via CLI flag whether to run them). The supersession ADR would add a marker-based mechanism alongside the existing skipif decorators, NOT replace.
- **GitHub deprecates `actions/checkout@v5` or `astral-sh/setup-uv` versioning conventions** in ways that require workflow restructuring.

## Consequences

- **Positive**: lint + typecheck + non-corpus tests are auto-enforced on every PR + every push-to-`main`. The audit's failure modes are durably closed. CI run time is ~2–3 minutes (uv setup + sync from cache ~30s; lint ~5s; typecheck cache-cleared ~60s; test ~30s). Token-economy favorable — Cascade no longer needs to re-run `make lint && make typecheck && make test` in every session before declaring "done"; CI does it. **Single mechanism for test gating** (skipif decorators) reduces cognitive overhead vs the original mixed marker+skipif design.
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
- **Insight**: `/start-project` should bootstrap `.github/workflows/ci.yml` from the L3 template's `_shared/scaffold/.github/workflows/ci.yml` (and/or `<type>/scaffold/`) so every new project has CI from day 1. The audit-followups cluster demonstrated that retrofitting CI to a project that has been running on discipline alone produces a 3-PR cluster of cleanup (lint+typecheck restore + import structure ratification + the CI workflow itself). New projects should not pay this cost. Companion forcing-function: bootstrap `tests/_corpus.py` (or generic `tests/_resources.py`) with the named-skipif-decorator pattern so test gating is canonical from day 1.
- **Source**: ReebalSami/horus PR #65 (ADR-022), PR #66 (#62), PR #67 (ADR-023, this PR — final form per `## Design evolution` Iteration 3) + cascade-system audit-followups plan
- **Project**: cascade-system
- **Cascade**: D
- **Date observed**: 2026-05-23
- **Proposed L1 change**: extend `python-ml-uv` L3 template `scaffold/` (or `_shared/scaffold/`) with `.github/workflows/ci.yml` bootstrapped from the HORUS CI design + a `tests/_resources.py` scaffold demonstrating the named-skipif-decorator pattern. Also extend `@release-manager` step 4 (or add step 4.5) to detect "no CI configured" + surface a warning at the merge gate ("PR has no CI configured; relying on manual review only — confirm?"). Codify the "default to skipif over custom markers for environmental gating" lesson in a cross-project rule or `make-sure-it-works` extension.
- **Project-local action**: ADR-023 (this PR) ratifies the HORUS-specific CI; followup is whether to elevate to L3 default for python-ml-uv template.
```
