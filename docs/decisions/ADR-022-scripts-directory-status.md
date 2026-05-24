# ADR-022 — `scripts/` directory status

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-23 |
| **Milestone** | Evidence-base audit follow-ups (PR 1 of 3-PR cluster: #63 → #62 → #64) |
| **Authored by** | Cascade D evidence-base audit follow-ups (`~/.windsurf/plans/audit-followups-7e4a25.md` §2) |
| **Supersession trigger** | See `## Supersession trigger` below |

## Context

The HORUS repository has been internally inconsistent about whether `scripts/` is a Python package or a flat directory of standalone scripts.

- **`scripts/__init__.py` exists** — empty, but present. Added in commit `8d1c44d` (2026-05-11, ADR-006 fpdf2 PR).
- **Three files contain comments asserting the opposite**: `# scripts/ is not a package — load … via sys.path injection.`
  - `scripts/compute_probe_verdict.py:50`
  - `tests/test_rescore.py:41`
  - `tests/test_inspect_pilot_13.py:25` (with the contradiction repeated in the module docstring line 14)
- **Runtime behavior** relies on `sys.path` injection patterns (each file inserts `scripts/` into `sys.path[0]` then `import rescore` / `import inspect_pilot_13` as bare module names). This works at runtime but is invisible to static analysis — producing 3 of the 5 mypy errors tracked in issue #62:
  - `scripts/compute_probe_verdict.py:55: error: Cannot find implementation or library stub for module named "rescore"  [import-not-found]`
  - `tests/test_rescore.py:45: error: Cannot find implementation or library stub for module named "rescore"  [import-not-found]`
  - `tests/test_inspect_pilot_13.py:29: error: Cannot find implementation or library stub for module named "inspect_pilot_13"  [import-not-found]`

The evidence-base audit (`~/.windsurf/plans/audit-branch-disposition-14db9b.md`) surfaced that the deleted branch `fix/evidence-base-verification-gates` had silently resolved this contradiction in favor of "is a package" — with no ADR, no comment cleanup, no deliberation. Per `horus-decision-discipline`, structural project choices like this require explicit 5-section ADR adjudication. This ADR is that adjudication.

This ADR is the prerequisite for issue #62 (PR 2 of the cluster): the `import-not-found` failures cannot be closed without first deciding what `scripts/` is.

## Decision

**`scripts/` IS a Python package.** Keep `scripts/__init__.py`. Migrate all sibling/cross-script imports to `from scripts import <name>`. Remove the three contradicting comments. Add `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml` so the repo root is on `sys.path` during pytest sessions. Standalone-invocable scripts that import siblings (currently only `scripts/compute_probe_verdict.py`) get a small `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` at module top, documented as a known Python invocation-discovery idiom.

## Current-state survey

Dated 2026-05-23. Sources consulted via web search + `context7` MCP (`mcp2_resolve-library-id` + `mcp2_query-docs` for both pytest and mypy).

- **Python's import system** (`https://docs.python.org/3/reference/import.html`): a directory containing `__init__.py` is a *regular package* — importable via `import <pkg>` once its parent is on `sys.path`. PEP 420 *implicit namespace packages* (directories without `__init__.py`) exist but are intended for split-package distribution, not as the default for first-party project code. PEP 8 + the Python tutorial both recommend explicit `__init__.py` for project-internal packages.

- **Python's script-invocation semantics**: when a script is invoked via direct path (`python scripts/foo.py`), Python prepends the script's *own* directory to `sys.path[0]` — NOT the repo root. Sibling imports via `from scripts import bar` therefore require the repo root to be added to `sys.path` manually. When the same script is invoked as a module (`python -m scripts.foo` from the repo root), Python adds the CWD to `sys.path[0]`; `from scripts import bar` then works without manipulation. This asymmetry is well-documented; many production Python CLIs ship a small `sys.path.insert(0, repo_root)` block at module top to make direct-path invocation work alongside `-m` invocation.

- **mypy import discovery** (`https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports`, also `mypy/docs/source/error_code_list.md`): the `import-not-found` error code fires when mypy "cannot find the source code or a stub file for an imported module." For **first-party project code**, the standard resolution is to make the module discoverable via a package layout (`__init__.py` + parent on `sys.path` / `mypy_path`). `# type: ignore[import-not-found]` and `ignore_missing_imports = True` overrides are appropriate **only for third-party untyped libraries**, not for owned source. **An override on first-party code is a code smell, not a fix.**

- **mypy incremental-cache nondeterminism**: `mypy/.mypy_cache/` warm cache can silently mask `import-not-found` errors after configuration changes. The audit-discovered reliable verification command is `rm -rf .mypy_cache && uv run mypy ... --no-incremental` (also captured in ADR-023 forthcoming for CI).

- **pytest `pythonpath`** (`https://docs.pytest.org/en/stable/reference/reference.html#confval-pythonpath`, also `https://docs.pytest.org/en/stable/explanation/goodpractices.html`): list-of-strings ini option (supported in `pyproject.toml` under `[tool.pytest.ini_options]`). Paths are relative to the `rootdir` (the directory containing the pytest config file — for HORUS, the repo root). pytest inserts them at `sys.path[0]` at session start and cleans up at session end (`_pytest/config.py:_configure_python_path`). Canonical use: `pythonpath = ["src"]` for src-layout projects. For HORUS's scripts/ + src/horus/ layout, `pythonpath = ["."]` makes the repo root discoverable, enabling `from scripts import X` in tests without per-file `sys.path` manipulation. pytest 9.0.0 docs confirm this is current behavior.

- **uv build-backend interaction**: HORUS uses `[build-system] requires = ["uv_build>=0.5"]` (per `pyproject.toml`). `uv sync` installs HORUS itself in editable mode via `src/horus/` (src-layout), making `from horus import …` work in tests + scripts. The `scripts/` directory is NOT under `src/` and is NOT part of the installable distribution — so `from scripts import X` cannot piggyback on the editable-install mechanism. Hence `pythonpath = ["."]` for pytest + manual `sys.path.insert(0, repo_root)` for direct-path script invocation are necessary.

## Options considered

| # | Option | Pros | Cons |
|---|---|---|---|
| 1 | **`scripts/` IS a package** (chosen) | `__init__.py` already exists; mypy resolves imports natively; modern Python convention; cleaner test imports (`from scripts import X`); supports both direct-path and `-m` invocation; pytest `pythonpath` is a one-line config | Standalone-invocable scripts that import siblings need a small `sys.path.insert(0, repo_root)` at module top — visible idiom, not a hack but cosmetically slightly noisy |
| 2 | **`scripts/` is NOT a package** | Honest about scripts/ being loose CLI entry points; no `sys.path.insert` idiom in standalone scripts | Requires deleting `__init__.py` (active change); requires per-file `# type: ignore[import-not-found]` or pyproject `[[tool.mypy.overrides]] module = ["rescore", "inspect_pilot_13"]` blocks — both are "suppress error in first-party code" which is a code smell per mypy docs; keeps the `sys.path.insert(scripts/)` injection pattern (more invisible to readers than a package import); future contributors are surprised by `import rescore` (no namespace) more than by `from scripts import rescore` |
| 3 | **Move scripts to a `tools/` top-level + namespace package (PEP 420)** | Cleaner separation of CLI tools from library code | Adds churn: rename every Makefile target, every test import, every doc reference; loses naming continuity with existing ADRs (ADR-016 → `scripts/rescore.py`, ADR-017 → `scripts/inspect_pilot_13.py`); no clear gain over Option 1 |
| 4 | **Install `scripts/` as part of the published distribution via `[project.scripts]` (PEP 621)** | Standard packaging idiom; scripts become installable entry points (`uv run rescore` instead of `uv run python scripts/rescore.py`) | scripts/ contains ad-hoc thesis tooling, not a published API; co-installation would expose ad-hoc tooling as part of the `horus` package surface (`horus.rescore` namespace pollution); over-engineered for the current scope; revisit possible at thesis-completion milestone |

**Chosen: Option 1.** Reasons (in priority order):

1. `__init__.py` already exists — Option 1 is the path of least churn.
2. Modern Python convention favors explicit packages for any importable code; PEP 420 namespace packages are intended for distributed split packages, not for first-party project code.
3. mypy resolves `from scripts import X` natively without overrides — Option 2's `# type: ignore[import-not-found]` on first-party code is documented as a code smell.
4. `from scripts import rescore` is more discoverable than `sys.path` injection: IDEs, linters, import-graph tools all see it; readers grok the dependency at a glance.
5. The `sys.path.insert(0, repo_root)` idiom in Option 1 is visible scaffolding, not hidden state — preferable to Option 2's hidden runtime path mutation.

## Decision + integration thoughts

### Interaction with already-decided components

- **ADR-006 (fpdf2 visual PDF renderer)**: introduced `scripts/__init__.py` accidentally during that PR. ADR-022 ratifies the implicit choice retroactively.
- **ADR-016 (fast dev config + adapter-iterate)**: `scripts/rescore.py` is the public surface for `make adapter-iterate`. `tests/test_rescore.py` imports it; the migration to `from scripts import rescore` confirms continued testability with no change to the public callable surface (`load_adapter_pair`, `parse_transcript`, `rescore_transcripts`, `main`).
- **ADR-017 (perf instrumentation)**: `scripts/inspect_pilot_13.py` ships `_print_perf_table`; `tests/test_inspect_pilot_13.py` imports it via the same pattern.
- **ADR-019 + ADR-021 (probe verdict matrix)**: `scripts/compute_probe_verdict.py` is the only script with a sibling import (`from scripts import rescore` — depends on rescore's public callable surface for re-scoring transcripts at τ=0.5).
- **horus-config-discipline rule**: orthogonal — no change to config-loading semantics; `cfg_path` papermill parameter unchanged.

### Forward-compatibility with `experiment` / `implement` / `writeup` phases

- Future scripts that import nothing from `scripts/` need no `sys.path` manipulation — they work via direct invocation (`python scripts/new_thing.py`) or `-m` invocation (`python -m scripts.new_thing`) with zero ceremony.
- Future scripts that import siblings follow the same idiom as `compute_probe_verdict.py`: small `sys.path.insert(0, repo_root)` at module top, then `from scripts import X`. Documented as a convention in `scripts/README.md` (forthcoming sub-step of PR 1 if the existing README doesn't already cover it).
- Test files import `from scripts import X` natively (pytest `pythonpath = ["."]`).
- ADR-023 (forthcoming, PR 3) CI workflow runs `make typecheck` with `.mypy_cache` cleared — guarantees this ADR's resolution doesn't quietly drift back to red.

### Mechanical changes (full enumeration)

1. **`pyproject.toml`** — add `pythonpath = ["."]` to `[tool.pytest.ini_options]`.
2. **`scripts/compute_probe_verdict.py`** lines 50–55:
   - Replace `# scripts/ is not a package — load sibling modules via sys.path injection.` with a brief comment explaining the repo-root insert idiom.
   - Replace `SCRIPTS_DIR = Path(__file__).resolve().parent` + `sys.path.insert(0, str(SCRIPTS_DIR))` with `REPO_ROOT = Path(__file__).resolve().parent.parent` + `sys.path.insert(0, str(REPO_ROOT))`.
   - Replace `import rescore  # noqa: E402 …` with `from scripts import rescore  # noqa: E402`.
3. **`tests/test_rescore.py`** lines 41–45:
   - Remove the `# scripts/ is not a package …` comment line.
   - Remove `SCRIPTS_DIR = …` + `sys.path.insert(0, str(SCRIPTS_DIR))`.
   - Replace `import rescore  # noqa: E402` with `from scripts import rescore  # noqa: E402`.
4. **`tests/test_inspect_pilot_13.py`** lines 14 + 25–29:
   - Remove the `scripts/ is not a package — ...` line from the module docstring (line 14).
   - Remove the `# scripts/ is not a package …` comment line (25).
   - Remove `SCRIPTS_DIR = …` + `sys.path.insert(0, str(SCRIPTS_DIR))` (26–27).
   - Replace `import inspect_pilot_13  # noqa: E402` with `from scripts import inspect_pilot_13  # noqa: E402`.

### Known limitations (become risk items / future work)

- The `sys.path.insert(0, repo_root)` idiom at top of `compute_probe_verdict.py` is invocation-discovery scaffolding, not a runtime correctness concern. A future Cascade or contributor might mistake it for legacy cruft and try to remove it — the in-file comment + this ADR are the durable explanation.
- `# noqa: E402` ("module-level import not at top of file") remains required because the `sys.path.insert` precedes the `from scripts import X` line. This is the well-known accepted exception for invocation-discovery prologues.
- Co-existing with `python -m scripts.X` invocation is supported but not documented as an alternative invocation path in the Makefile. If a future ADR adopts `-m` invocation as canonical, the `sys.path.insert` becomes unnecessary and can be removed (with a superseding ADR).

## Source archival

- `docs/sources/tools/python-import-system.md` — Python 3.14 import system reference (`docs.python.org/3/reference/import.html`).
- `docs/sources/tools/mypy-import-discovery.md` — mypy `Running mypy — Missing imports` docs + `error_code_list.md` `import-not-found` entry.
- `docs/sources/tools/pytest-pythonpath.md` — pytest configuration reference `pythonpath` ini option + good-practices src layout guidance.

## Supersession trigger

This ADR is superseded if:

- **HORUS grows a second top-level scripts directory** (e.g., `bin/`, `tools/`) — would force a re-evaluation of namespace package layout vs single-package layout. The supersession ADR would document the chosen reorganization.
- **HORUS adopts `uv run <entry>` / `[project.scripts]` (PEP 621) for all CLI invocations** — would obviate the `scripts/` directory entirely (entry points installed into the user's PATH at `uv sync` time). The supersession ADR would document the entry-point migration.
- **mypy ships a config option that makes `import-not-found` on first-party `sys.path`-injected modules cleanly resolvable without `__init__.py`** — would re-open Option 2 as a viable path. Tracked indirectly via mypy issue tracker; no current candidate.

## Consequences

- **Positive**: mypy gets 3 of 5 errors cleared (just the 2 `union-attr` remain for PR 2 to fix); test imports become standard `from scripts import …` (mypy + IDEs + readers all see them clearly); no `# type: ignore` overrides on first-party code; pytest `pythonpath = ["."]` is a one-line idempotent config that benefits any future test importing from `scripts/`.
- **Negative**: the `sys.path.insert(0, repo_root)` idiom in `compute_probe_verdict.py` is visible scaffolding that future readers must understand (mitigation: in-file comment + this ADR).
- **Neutral**: no runtime behavior change for end users (`uv run python scripts/X.py --help` still works identically); no Makefile target changes; no new dependencies; no CI changes (CI lands in PR 3).

## Related ADRs

- **ADR-001** — tool-decision discipline (mandates this ADR's 5-section shape).
- **ADR-006** — accidentally introduced `scripts/__init__.py`; ADR-022 retroactively ratifies.
- **ADR-009** — ADR numbering protocol (reserve in INDEX.md first; this ADR reserved ADR-022 before file authoring).
- **ADR-016** — `scripts/rescore.py` public surface unchanged by this migration.
- **ADR-017** — `scripts/inspect_pilot_13.py` public surface unchanged by this migration.
- **ADR-019** — `scripts/compute_probe_verdict.py` consumes `scripts/rescore.py` via the now-canonical `from scripts import rescore`.
- **ADR-023** (forthcoming, PR 3) — GitHub Actions CI workflow guarantees this ADR's resolution stays green via cache-cleared `make typecheck` on every push/PR.
