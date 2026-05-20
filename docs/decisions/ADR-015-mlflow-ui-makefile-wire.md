# ADR-015 — MLflow UI Makefile target: `make mlflow-ui` wired into the project substrate (post-pilot-13 Seq 1)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-20 |
| **Milestone** | `experiments-validated` (pilot #13 closed via PR #42; this is Seq 1 of post-pilot-13 follow-ups) |
| **Authored by** | Cascade D (issue #45 implementation session; plan `~/.windsurf/plans/horus-issue-45-mlflow-ui-9f6841.md`) |
| **Issue** | `ReebalSami/horus#45` |
| **Supersession trigger** | (1) Port 8080 conflicts on a future user environment (the override flag `MLFLOW_UI_PORT` is the first response; new ADR only if a class of environments breaks the default systematically). OR (2) MLflow 4.x ships a breaking change — `mlflow ui` removed as an alias for `mlflow server`, OR the `--backend-store-uri sqlite:///mlflow.db` flag semantics change, OR the `--host`/`--port`/`--workers` surface diverges from MLflow 3.12.0 — re-evaluate the invocation against the new surface. OR (3) Tracking migrates to a remote backend (Postgres + S3 / GCS / Azure Blob per ADR-011 supersession trigger 2) — the local-launch instructions become stale; new ADR documents the remote-backend launch surface. OR (4) Multi-user / multi-machine usage emerges (currently solo-dev) — `--host 127.0.0.1` becomes load-bearing for the privacy-frame; new ADR ratifies an authentication strategy (basic-auth / OIDC / Tailscale-fronted) before relaxing the host binding. OR (5) The `make pilot-13` runner adopts a different artifact-store layout (e.g., MLflow `--serve-artifacts` proxy mode populating `./mlartifacts/`) — the path-claims documentation has to be re-aligned with empirical filesystem state. |

## Context

Pilot #13 closed via PR #42 (issue #13), producing 182 nested MLflow runs across 3 experiments (`pilot-13-full`, `pilot-13-eval`, `cohort-smoke`) with the full per-(model, invoice) F1 grid + 7-model `cohort_heatmap.png` + per-field `per_field_scores.json` artifacts. The substrate now contains thesis-defense-quality empirical evidence — 200+ runs total, ~3.8 MB SQLite metadata at `mlflow.db`, ~ tens of MB of artifacts at `mlruns/<experiment_id>/<run_id>/artifacts/`.

[ADR-011](ADR-011-experiment-tracker-integration.md) line 306, in the section *"What this ADR does NOT decide"*, explicitly deferred the question of how the analyst actually browses these runs:

> *"`mlflow ui` deployment posture: invoking `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db` is documented in `docs/sources/tools/mlflow.md`; not wired into the Makefile (single-user local-dev affordance, not a thesis-substrate deliverable)."*

The post-pilot-13 retrospective (`docs/retros/m2d.5-pilot-13-cohort-harness.md` §"What got committed") + the post-pilot-13 rethink plan (`~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5) surfaced the deferral as Seq 1 friction: the analyst keeps typing the long invocation from memory across sessions, which is exactly the kind of operational rough edge the `make`-target convention exists to smooth.

Issue [`ReebalSami/horus#45`](https://github.com/ReebalSami/horus/issues/45) is the supersession of that deferral. This ADR ratifies the operational decision per `horus-decision-discipline` even though it is NOT a tool/model/library/dataset/framework/hosting choice (MLflow already locked by ADR-011) — the user explicitly elected ADR ratification at planning time to ensure the `mlflow ui ≡ mlflow server` empirical equivalence + the macOS port-5000 caveat + the project-wide `./mlartifacts/` documentation drift are all surfaced in a durable, reviewable artifact.

## Current-state survey (2026-05-20)

Authoritative-source verification per `context7-and-docs-first` rule. All evidence is dated; nothing relies on training-data memory.

| Source | Finding | Where verified |
|---|---|---|
| MLflow self-hosting overview | *"The simplest way to start an MLflow server is by running the `mlflow server --port 5000` command after installing MLflow via pip. This method is suitable for personal use or small teams and defaults to using SQLite as the backend store. The UI will be accessible at `http://localhost:5000`."* | `https://mlflow.org/docs/latest/self-hosting/` (read in full via `read_url_content` 2026-05-20) |
| MLflow CLI reference | `mlflow server` documented as the canonical command. Default `--host 127.0.0.1`. Default `--port 5000`. Default `--backend-store-uri` = `./mlruns` per help text (NOTE: stale; MLflow 3.7+ default is SQLite per release notes). Default `--serve-artifacts True` → `./mlartifacts/` proxy directory. | `https://mlflow.org/docs/latest/api_reference/cli.html` (full read of `server` chunks via `view_content_chunk`) |
| MLflow CONTRIBUTING.md | *"On some versions of MacOS, the 'Airplay Receiver' process runs on port 5000 by default, which can cause network request failures."* | `context7` MCP query against `/mlflow/mlflow` v3.1.4 |
| MLflow CLI empirical (HORUS local) | `uv run mlflow ui --help` and `uv run mlflow server --help` produce **byte-identical option surfaces** in MLflow 3.12.0. Both run "the MLflow tracking server with built-in security middleware". `mlflow ui` is a non-deprecated alias of `mlflow server`; the modern preferred name is `mlflow server`. | `uv run mlflow ui --help` + `uv run mlflow server --help` byte-comparison, 2026-05-20 |
| HORUS filesystem state | `mlruns/` exists with 3 experiments + 200+ runs (pilot-13 = 182 nested + parent, cohort-smoke = ~12, pilot-13-eval ad-hoc). `mlflow.db` exists at 3.8 MB. `mlartifacts/` does **NOT** exist on disk. | `ls -la mlruns/` + `find mlruns -maxdepth 2 -type d` + `du -sh mlflow.db`, 2026-05-20 |
| `.gitignore` posture | All four MLflow paths gitignored: `mlruns/`, `mlartifacts/` (defensive — empty on disk), `mlflow.db`, `mlflow.db-journal`. | `cat .gitignore`, 2026-05-20 |
| `./mlartifacts/` doc drift | Five files claim `./mlartifacts/` as the artifact root: `AGENTS.md:62`, `configs/cohort-smoke.yaml:9`, `configs/pilot-13.yaml:11`, `configs/pilot-13-eval.yaml:15`, `src/horus/tracking.py:215`. Empirically false; ADR-011 §Decision line 90 + `docs/sources/tools/mlflow.md` line 24 both correctly cite `mlruns/<experiment_id>/<run_id>/artifacts/`. | `grep -rn 'mlartifacts' docs configs src AGENTS.md`, 2026-05-20 |

The drift's origin is now understood: MLflow's `--artifacts-destination` flag defaults to `./mlartifacts/` for the **server-side proxy** when `--serve-artifacts True` (which is the server CLI's default). When the **Python client** writes runs (HORUS's harness pattern via `mlflow.start_run()` from `src/horus/tracking.py::MLflowTracker`), artifacts go to `mlruns/<experiment_id>/<run_id>/artifacts/` directly — no proxy involved. The five drift sites confused these two execution modes; this ADR + its PR fix all five in the same atomic commit.

## Options considered

| Option | What | Why rejected / chosen |
|---|---|---|
| **α** — Documentation-only (status quo per ADR-011 line 306) | Keep `docs/sources/tools/mlflow.md` line 22 as the only invocation reference. Analyst types the long command from memory. | Rejected. Post-pilot-13 retro identified this as Seq 1 friction; the `make`-target convention is precisely the affordance that closes this kind of operational rough edge. Persisting the deferral is a `anti-laziness-core-principles` violation ("repair, don't defer"). |
| **β** — `make mlflow-ui` invoking `mlflow ui --port 5000` (MLflow's documented default) | Pin to MLflow's default port. | Rejected. MLflow's own CONTRIBUTING.md documents the macOS AirPlay Receiver port-5000 conflict on M1/M2 macOS. HORUS hardware = M1 Pro per `know-your-hardware` — the conflict surfaces on the actual target environment. Pinning to a known-broken default is a `make-sure-it-works` violation. |
| **γ** — `make mlflow-ui` invoking `mlflow ui --port 8080` | Use the no-conflict port without explicit host binding. | Rejected (close call vs δ). `mlflow ui` and `mlflow server` are byte-equivalent in MLflow 3.12.0 (verified empirically), but MLflow's modern docs uniformly use `mlflow server` as the canonical name. Implicit `--host` default leaves the privacy posture invisible in the artifact. |
| **δ (chosen)** — `make mlflow-ui` invoking `mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 8080` | Use the modern canonical command with explicit host (privacy-posture VISIBLE) + explicit backend-store-uri (no reliance on the help-text-stale `./mlruns` default) + no-conflict port. Override via `MLFLOW_UI_PORT` Makefile variable. Pre-flight guard against empty `mlflow.db` + empty `mlruns/`. | **Chosen.** All three explicit flags appear in the artifact for reviewer auditability. Privacy frame (`AGENTS.md` §1) is visible at the invocation site. Port 8080 matches MLflow's own tutorial convention. Foreground-streaming per `long-running-foreground` rule (no background-and-poll). The Makefile target name stays `mlflow-ui` to match the user's mental model + issue #45 wording. |
| **ε** — Streamlit / Gradio dashboard atop MLflow's REST API | Custom dashboard wrapping `mlflow.search_runs()` + custom heatmap renderer. | Rejected. Out of scope for issue #45. MLflow's native UI already covers the run-comparison + artifact-browsing + filter-by-tag use cases. Building a custom layer is a `no-quantity-over-shape` violation ("instances emerge from need" — current need is "browse runs", which the native UI satisfies). Reserved as a future ADR if a thesis-defense-grade visualization need surfaces. |
| **ζ** — Auto-launch the UI on `make pilot-13` completion | Spawn the server as a background process at the end of every experiment run. | Rejected. Surprising side-effect (port-binding on the user's machine without explicit invocation). Conflicts with `long-running-foreground` rule (the experiment runner exits cleanly; the UI server should be invoked deliberately). Conflicts with `make-sure-it-works` ("evidence over claims" — the user controls when to inspect the evidence). |

The minimum-2-options requirement of `horus-decision-discipline` is satisfied (4 closely-considered options + 2 rejected-by-reference). No new tool dependency introduced; MLflow already locked by ADR-011.

## Decision + integration thoughts

**Wire `make mlflow-ui` into the project Makefile** (Option δ) with the following shape:

```makefile
MLFLOW_UI_PORT ?= 8080

mlflow-ui:
	@if [ ! -f mlflow.db ] && [ ! -d mlruns ]; then \
		echo "ERROR: No MLflow data found at mlflow.db / mlruns/."; \
		echo "Run 'make pilot-13 CFG=configs/pilot-13.yaml' or 'make cohort-smoke ...' first."; \
		exit 1; \
	fi
	@echo "MLflow UI: http://127.0.0.1:$(MLFLOW_UI_PORT) (local-only; press Ctrl+C to stop)"
	uv run mlflow server \
		--backend-store-uri sqlite:///mlflow.db \
		--host 127.0.0.1 \
		--port $(MLFLOW_UI_PORT)
```

The pre-flight check honors `make-sure-it-works` (no silent confusion on a fresh clone). The explicit `--host 127.0.0.1` makes the privacy posture VISIBLE in the artifact (matches `AGENTS.md` §1 stakeholder contract). The `MLFLOW_UI_PORT ?= 8080` pattern matches existing Makefile conventions (e.g., `MUSTANG_VERSION ?= 2.23.0`). The foreground-streaming behavior honors `long-running-foreground` rule — no background-and-poll anti-pattern.

### How this fits the bigger HORUS puzzle

- **Pilot #13 (ADR-014)**: parent-run `df6bce67369c47948d10dfa0d2624490` + 182 nested runs are the immediate consumers of the new affordance. The README section authored alongside this ADR documents the parent/nested hierarchy + the tag-filter conventions for cross-config comparison.
- **`Tracker` Protocol (ADR-011)**: unchanged. `MLflowTracker` writes to `mlruns/` via the Python client; the new server invocation reads the same SQLite metadata + filesystem artifacts. No code changes to `src/horus/tracking.py`'s class surface (only a docstring path correction in the same PR per the doc-drift fix below).
- **`horus-config-discipline` (ADR-004)**: unchanged. Configs continue to drive experiment runs; the UI is purely read-side.
- **`horus-decision-discipline` (ADR-001)**: this ADR's authoring honors the rule even though the operational nature of the change does not strictly require it. The user explicitly elected the formal ratification path at planning time to lock in the `mlflow ui ≡ mlflow server` finding + the macOS port caveat + the documentation-drift resolution as a durable record.
- **Forward-compat to `implement` + `writeup` phases**: the same `make mlflow-ui` target serves the implementation phase's TDD harness runs + the writeup phase's thesis-figure regeneration step. No phase-specific UI variant needed.
- **`make-sure-it-works` artifact-review-before-push gate**: the implementation PR ships with browser-side verification of the UI rendering against the actual 182 pilot-13 runs (per `@release-manager` step 4 enforcement of the human-eye review on tangible artifacts).

### Documentation-drift resolution (same PR)

In the same PR that wires the Makefile target, fix the five `./mlartifacts/` claim sites identified in the Current-state survey:

1. `AGENTS.md` §Toolchain bullet — replace `artifact root './mlartifacts/'` with `artifact root 'mlruns/<experiment_id>/<run_id>/artifacts/'`.
2. `configs/cohort-smoke.yaml` header comment line 9 — same correction.
3. `configs/pilot-13.yaml` header comment line 11 — same correction.
4. `configs/pilot-13-eval.yaml` header comment line 15 — same correction.
5. `src/horus/tracking.py` `MLflowTracker` class docstring line 215 — same correction.

Plus: amend `docs/sources/tools/mlflow.md` (per `horus-source-archival` rule — the canonical MLflow source stub) with the `mlflow ui ≡ mlflow server` byte-equivalence finding + the macOS AirPlay caveat. Plus: add a 1-line supersession marker on `README.md` `### Experiment tracker (B4=C)` subsection per `document-as-you-go` supersession-over-deletion (the L3-template-leftover text remains as substrate documentation; the marker resolves the contradiction for HORUS readers).

Plus: sync `AGENTS.md` §Toolchain Make-targets list to include `make mlflow-ui` alongside `make zugferd-smoke` / `make cohort-smoke` / `make pilot-13` — future Cascade kickoff sessions reading AGENTS.md first see the new affordance immediately.

### Known limitations (deferred to future ADRs)

- **Authentication / multi-user**: out of scope per supersession trigger 4. Solo-dev only. Reserved.
- **CORS / `--allowed-hosts` tuning**: defaults are correct for `127.0.0.1`-only.
- **`mlflow.db` archival / rotation / `mlflow gc`**: not addressed. Run cleanup is manual; revisit if substrate grows beyond ~10⁵ runs (also ADR-011 supersession trigger 2).
- **`mlflow doctor` invocation**: useful diagnostic but separate concern. Out of scope.
- **Auto-open browser**: Unix philosophy applies — print URL, let the user click. Avoids OS-specific `open` / `xdg-open` branching.

## Source archival

Per `horus-source-archival` rule. All MLflow-project sources cited in this ADR (`https://mlflow.org/docs/latest/self-hosting/`, `https://mlflow.org/docs/latest/api_reference/cli.html`, `https://github.com/mlflow/mlflow/blob/master/CONTRIBUTING.md`) are covered by the canonical `docs/sources/tools/mlflow.md` stub created at ADR-011's authoring time.

The stub is being amended in this PR (alongside this ADR's authoring) to add:

- The `mlflow ui ≡ mlflow server` empirical-equivalence finding (verified 2026-05-20 against MLflow 3.12.0 via `--help` byte-comparison).
- The macOS AirPlay Receiver port-5000 caveat (cited from MLflow's CONTRIBUTING.md).

No new `docs/sources/<type>/<slug>.md` stubs are required: this ADR introduces no new tool, library, dataset, or framework dependency.

## Cross-references

- **ADR being superseded (partial — operational deferral only, not the underlying tracker decision)**: [ADR-011 §"What this ADR does NOT decide" line 306](ADR-011-experiment-tracker-integration.md). ADR-011 itself remains `Accepted` and load-bearing.
- **Sibling ADR (immediate context)**: [ADR-014 — Cohort harness + multi-page rasterizer](ADR-014-cohort-harness-multipage.md) (the artifact this UI primarily browses).
- **Predecessor ADRs (background)**: [ADR-009 — Pilot-loop VLM cohort selection](ADR-009-pilot-vlm-cohort.md), [ADR-013 — VLM prediction scorer](ADR-013-vlm-prediction-scorer.md), [ADR-012 — CII XML → ground-truth field dict](ADR-012-cii-ground-truth-parser.md).
- **Plan**: `~/.windsurf/plans/horus-issue-45-mlflow-ui-9f6841.md` (this ADR's authoring substrate; Option D scope).
- **Parent plan**: `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5 Seq 1.
- **Retro that surfaced the friction**: `docs/retros/m2d.5-pilot-13-cohort-harness.md`.
- **Issue**: [`ReebalSami/horus#45`](https://github.com/ReebalSami/horus/issues/45).
- **Source archival stub (canonical for MLflow)**: `docs/sources/tools/mlflow.md`.
- **Rules consulted**: `horus-decision-discipline` (5-section discipline), `horus-source-archival` (single MLflow stub covers all citations), `context7-and-docs-first` (authoritative-doc verification), `make-sure-it-works` (pre-flight check + browser verification), `long-running-foreground` (foreground-streaming for the server process), `know-your-hardware` (M1 Pro AirPlay caveat), `be-honest-direct-critical` (correct path claims throughout the documentation surface), `anti-laziness-core-principles` (resolve doc drift in same PR).
