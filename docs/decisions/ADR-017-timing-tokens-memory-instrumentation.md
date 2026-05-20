# ADR-017 — Timing + tokens/sec + GPU-memory instrumentation for the cohort harness

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-05-20 |
| **Milestone** | `experiments-validated` (post-pilot-13 follow-ups; Seq 3 per `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5) |
| **Authored by** | Cascade D (issue #52 implementation session; plan `~/.windsurf/plans/horus-issue-52-timing-inspector-3fe7c5.md`) |
| **Issue** | [`ReebalSami/horus#52`](https://github.com/ReebalSami/horus/issues/52) |
| **Supersession trigger** | (1) PyTorch lands `torch.mps.max_memory_allocated()` (or equivalent transient-peak tracker on MPS) — pytorch/pytorch#104188 closes — replace the pre/post snapshot with the native API and supersede this ADR. OR (2) MLX-VLM removes / renames `GenerationResult.peak_memory` / `generation_tokens` / `generation_tps` (e.g., 1.0 release breaking changes) — author a supersession ADR with the migration path. OR (3) The thesis adopts a tiktoken-standardised tokens/sec metric for cross-model H4 comparison — supersession ADR ratifies the metric + its computation point in the harness. OR (4) The inspector outgrows plain-text rendering (e.g., > 15 models, multiple parent-run comparison) and switches to `rich` / `tabulate` / a separate dashboard — supersession ADR ratifies the new dependency + rendering substrate. OR (5) The `perf.*` MLflow namespace conflicts with a future MLflow built-in (e.g., MLflow 4.x reserves `perf.*` for a system-metrics integration) — supersession ADR migrates to a different prefix (`hardware.*` / `latency.*`). |

## Context

Pilot #13 ([`ReebalSami/horus#13`](https://github.com/ReebalSami/horus/issues/13), closed via PR #42, ratified by ADR-014) produced **182 saved transcripts** and the canonical thesis-defense F1 evidence base. The cohort harness logs per-tuple accuracy metrics (`micro_f1`, `extract_seconds_total`, per-field outcomes) but does **NOT** log:

- per-tuple **generation token counts** — needed to derive native tokens/sec
- per-tuple **tokens/sec** — needed for the H4 latency-efficiency comparison (brainstorm v2 §6 H4)
- per-tuple **peak GPU memory** — needed for the H4 efficiency claim ("does the model fit on a 16 GB MacBook?") and for the `%_max` of-host-ceiling diagnostic

The retro (`docs/retros/m2d.5-pilot-13-cohort-harness.md` §"Out of scope") and the post-pilot-13 rethink plan (`~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5 Seq 3) identified this gap as a Seq-3 follow-up. Issue #52 captures it.

The substrate for filling this gap is **already** present:

- MLX-VLM's `mlx_vlm.generate(...)` returns a `GenerationResult` dataclass with `generation_tokens`, `generation_tps`, and `peak_memory` fields populated by the library itself (verified at `mlx_vlm/generate.py:375-385`). MLX-path extractors get all three for free.
- MLX exposes `mx.get_peak_memory()` / `mx.reset_peak_memory()` as a true peak-memory tracker (per `mlx-apple-silicon.md` source stub).
- For the Transformers-MPS backend: `torch.mps.driver_allocated_memory()` returns driver-managed memory in bytes; `torch.mps.recommended_max_memory()` returns the per-host MPS memory ceiling. Both exist in PyTorch 2.x.

What's missing is **wiring**:

1. Per-page perf fields on `ExtractionResult` (Chunk 1).
2. Harness aggregation of those fields into per-tuple `perf.*` MLflow metrics (Chunk 2).
3. Pre/post `driver_allocated_memory()` snapshots around the Transformers-MPS extract call (Chunk 3 — workaround for the `torch.mps` peak-memory gap).
4. Inspector rendering of a per-model perf summary table (Chunk 4).
5. Tests pinning the rendering + logging contracts (Chunk 5).
6. Make target + README (Chunk 6).

This ADR ratifies the design across all 6 chunks. Authored alongside the implementation across a 7-commit branch (`feat/issue-52-timing-inspector`); the chunks are dependency-ordered: schema → harness aggregation → MPS workaround → inspector → tests → docs → this ADR.

**Critical scope boundary**: this ADR ships the **substrate** for hypothesis H4 (latency-efficiency comparison; brainstorm v2 §6). It does **NOT** run the H4 test. H4 requires a sweep across the full 7-working-model cohort with the perf instrumentation enabled, statistical comparison of the perf-vs-F1 trade-off, and write-up against the pre-registered hypothesis. That work is filed separately.

## Current-state survey (2026-05-20)

Authoritative-source verification per `context7-and-docs-first` rule.

| Source | Finding | Where verified |
|---|---|---|
| **MLX-VLM `GenerationResult` dataclass** | The dataclass returned by `mlx_vlm.generate(...)` has fields `text: str`, `prompt_tokens: int`, `generation_tokens: int`, `prompt_tps: float`, `generation_tps: float`, `peak_memory: float` (GB). `peak_memory` is populated via `mx.get_peak_memory()` at the end of the generate loop. The repository file `mlx_vlm/generate.py` lines 375-385 is the canonical definition. | Direct source-code read at `~/.cache/uv/...` post `uv sync`; cross-checked at `https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/generate.py` |
| **MLX `mx.get_peak_memory()` / `mx.reset_peak_memory()`** | True peak-memory tracker on MLX. Returns bytes (cast to GB in `GenerationResult.peak_memory`). Reset between extract calls is required for per-tuple isolation; otherwise the value is the running maximum across all calls in a process. | `mlx-apple-silicon.md` source stub + MLX docs at `https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.metal.get_peak_memory.html` |
| **PyTorch `torch.mps` API** | `torch.mps.driver_allocated_memory()` returns bytes of driver-managed memory; `torch.mps.recommended_max_memory()` returns the per-host MPS ceiling (typically ~75% of unified memory). `torch.mps.max_memory_allocated()` does NOT exist (CUDA-only API). | PyTorch 2.5 docs at `https://pytorch.org/docs/stable/mps.html` |
| **pytorch/pytorch#104188** | "Add `torch.mps.max_memory_allocated()` for MPS" — issue OPEN since 2023; no PR landed. Confirms the API gap. The community workaround documented in the issue thread is exactly the pre/post snapshot pattern this ADR adopts. | `https://github.com/pytorch/pytorch/issues/104188` (read at `retrieved_date: 2026-05-20`) |
| **Artificial Analysis tokens/sec methodology** | "Output Tokens per Second (TPS) is the rate at which the model generates output tokens. We measure end-to-end at the API boundary (input sent → final output token received) divided by output token count." Time-weighted throughput (`total_tokens / total_seconds`), NOT arithmetic mean of per-step TPS. The methodology page is the de-facto industry standard for cross-model TPS comparison. | `https://artificialanalysis.ai/methodology/intelligence-benchmarking-methodology` |
| **Tiktoken** (deferred — D5) | OpenAI's BPE tokenizer; provides a fixed reference vocabulary for cross-model token-count standardisation. Cross-model TPS comparison rigorously requires a single tokenizer (e.g., `cl100k_base`) — different model tokenizers produce different token counts for the same text, so per-model `generation_tps` is NOT cross-model comparable. | `https://github.com/openai/tiktoken` + Hugging Face cookbook tokens-per-second post |
| **`rich` library** (deferred — D6) | Mature TUI library with table rendering, ANSI colors, progress bars. ~2 MB install. Used by countless Python CLIs (`pip`, `pdm`, `uv`'s status output). The standard choice for "make terminal output pretty". | `https://github.com/Textualize/rich` |
| **`mlflow.log_metric` semantics** | Each call records a single value at a step (default step=0) with timestamp. Querying via `run.data.metrics[key]` returns the LAST value logged for that key. Suitable for per-tuple aggregates that don't change after the run completes. | MLflow 3.12 docs at `https://mlflow.org/docs/latest/python_api/mlflow.html#mlflow.log_metric` |
| **`time.perf_counter()`** | High-resolution monotonic clock; the Python stdlib choice for measuring elapsed wall-clock with sub-microsecond resolution. Already used in `vlm_extractor.py` and `harness.py` for `extract_seconds_total`. No new measurement primitive needed. | Python 3.14 stdlib docs at `https://docs.python.org/3/library/time.html#time.perf_counter` |

The decision is **substantially overdetermined** by the available APIs (MLX gives us peak memory for free; MPS forces a workaround; the `time` module is the obvious clock). The §"Options considered" walk below documents the 6 axes per `horus-decision-discipline`.

## Options considered

The plan (`~/.windsurf/plans/horus-issue-52-timing-inspector-3fe7c5.md` §5) walked 6 orthogonal forks. Each fork is recorded below per `horus-decision-discipline` minimum-2-options requirement.

### Axis 1 — Timing measurement primitive

| Option | Outcome |
|---|---|
| **A1** — `time.perf_counter()` per page, pre/post-extract; ExtractionResult carries `extract_seconds` already | **Accepted.** Already in use; sub-microsecond resolution; monotonic; immune to wall-clock NTP adjustments. Zero new code in extractors. |
| **A2** — `time.process_time()` (CPU-only) | **Rejected.** Excludes GPU compute time on MLX/MPS; for VLM inference this is the dominant cost. Useless for our purpose. |
| **A3** — Wrap each generate call in `cProfile` / `pyinstrument` | **Rejected.** Profiler overhead skews the measurement we're trying to capture (5-15% slowdown on fast paths). Use case is "measure production latency", not "find hot loops". |

### Axis 2 — Peak GPU memory tracking on MPS

| Option | Outcome |
|---|---|
| **B1** — Wait for `torch.mps.max_memory_allocated()` to land upstream (pytorch/pytorch#104188) | **Rejected.** Issue open since 2023 with no PR. Blocking on upstream is incompatible with the M-thesis timeline. |
| **B2.A** — Pre/post snapshot of `torch.mps.driver_allocated_memory()` around the extract call; report `delta_mb` + post-`mb` | **Accepted.** Documented in pytorch/pytorch#104188 as the community workaround. Captures steady-state memory after generation completes. **Limitation** (must disclose): misses transient peak DURING generation (e.g., a Qwen3-VL forward pass that briefly spikes 2× the post-call number is invisible). The thesis writeup must call this out for any MPS-routed model claim. For MLX-routed models, the limitation does not apply — MLX has true peak tracking. |
| **B2.B** — Background thread sampling `driver_allocated_memory()` every 50 ms during the extract call; record max | **Rejected for #52, deferred for future ADR.** Captures transient peaks B2.A misses. **Cost**: thread synchronisation, sampling-rate vs accuracy trade-off, GIL contention with the generate loop, overhead on fast-extracting models, complexity in error paths. The marginal accuracy gain is not justified at the current scope (substrate for H4, not H4 itself). If H4's findings prove the post-snapshot is materially misleading for a class of models, supersession ADR adopts B2.B. |
| **B3** — `psutil.Process().memory_info()` for total process RSS | **Rejected.** Includes all process memory (Python heap, transformers/MLX library state, page cache); not GPU-specific. Useful for OOM debugging, useless for the H4 claim "this VLM fits in X GB of GPU memory". |

### Axis 3 — Tokens/sec computation point

| Option | Outcome |
|---|---|
| **C1** — Compute in the extractor, store in `ExtractionResult.generation_tps` | **Accepted.** MLX-VLM populates `generation_tps` natively from the library; for Transformers-MPS, derive from `generated_only.shape[-1] / extract_seconds`. Per-page granularity enables the harness to aggregate any way. |
| **C2** — Compute only in the harness from raw token counts + extract seconds | **Rejected.** Loses per-page diagnostic granularity. Future "page-level latency variance" analysis becomes impossible without re-running. |
| **C3** — Don't compute; store only token count + seconds, derive in inspector | **Rejected.** Pushes computation downstream to every consumer. Storing the derivation is cheap (1 float per page); recomputing it everywhere is fragile. |

### Axis 4 — Tokens/sec aggregation across pages (the `mean_tps` formula)

| Option | Outcome |
|---|---|
| **D1.A** — `mean_tps = total_tokens / total_seconds` (time-weighted throughput) | **Accepted.** Matches Artificial Analysis methodology + MLX-VLM's own internal formula (sum tokens, sum time, divide). Robust against page-size variance. **This is what the harness logs as `perf.generation_tps_mean`.** |
| **D1.B** — `mean_tps = arithmetic mean of per-page generation_tps` | **Rejected as primary.** Biases the result toward fast pages: a 100-token page at 50 tps + a 200-token page at 25 tps gives arithmetic-mean = 37.5 tps, but the actual end-to-end throughput is 300 / (100/50 + 200/25) = 300/10 = 30 tps. **Retained as fallback** when `total_tokens == 0` but per-page tps is non-zero (defensive — for a future extractor that estimates tps without exposing token count). |
| **D1.C** — Median per-page tps (robust to outliers) | **Rejected.** Robust outlier-handling is a virtue when the noise is unwanted; for VLM inference the page-size variance IS the signal we want preserved. Median throws it away. |

### Axis 5 — Tokens/sec cross-model standardisation

| Option | Outcome |
|---|---|
| **E1** — Native tokens/sec only (per-model tokenizer; non-comparable across models) + chars/sec as tokenizer-agnostic sanity check | **Accepted for #52.** Within-model comparison is valid (same tokenizer, same metric); chars/sec is the cross-model proxy. Honest disclosure in the inspector header that `tps` is NOT cross-model comparable. |
| **E2** — Tiktoken-standardised tokens/sec — re-tokenize every model's output with `cl100k_base` and compute `standardised_tps = retokenized_count / extract_seconds` | **Rejected for #52, deferred to H4.** Adds `tiktoken` dep + retokenization overhead per page. Cross-model rigor is needed for the H4 hypothesis test, not the substrate. When H4 runs, supersession ADR adopts E2 (or Hugging Face's standardised methodology if it stabilises in the meantime). |
| **E3** — Words/sec (tokenizer-free, language-agnostic) | **Rejected.** German invoices have long compound words; English / Korean have entirely different word boundaries; "word" isn't well-defined cross-language. Chars/sec (E1's proxy) is more robust for our multilingual corpus. |

### Axis 6 — Inspector output format

| Option | Outcome |
|---|---|
| **F1** — Plain-text `print(...)` table with right-aligned columns; no new dependency | **Accepted.** Matches existing inspector convention (`_print_per_run_grid`, `_print_per_model_aggregate` are all plain `print` with f-string padding). Zero dep. Renders identically in any terminal, CI log, file redirect. Honest "boring works" choice. |
| **F2** — `rich.Table` with colors / styling / box-drawing | **Rejected for #52, deferred.** Adds 2 MB dep. Visual polish is real but premature — the table's information content is fully expressible in plain text. If the thesis writeup needs publication-quality tables, generate them via matplotlib or a separate `make` target rather than coupling the inspector to `rich`. |
| **F3** — JSON output for machine consumption + plain-text for human consumption (two outputs) | **Rejected for #52.** Premature. The inspector currently has 1 consumer (the analyst). When a second consumer materialises (e.g., a CI gate that reads the table), revisit. |
| **F4** — Embed the table in `mlflow.log_text` artifact attached to the parent run | **Considered, partial-accept.** Worth doing as a future enhancement (the parent run becomes self-contained — MLflow UI shows the table without re-running the inspector). Out of scope for #52 to keep the chunk minimal; flag as a follow-up enhancement. |

### Axis 7 — Per-tuple metric naming convention

| Option | Outcome |
|---|---|
| **G1** — `perf.*` prefix (`perf.generation_tokens_total`, `perf.generation_tps_mean`, `perf.peak_memory_gb`, …) | **Accepted.** Mirrors the existing `tags.adr.*` namespacing pattern. MLflow-friendly (UI groups metrics by prefix). Disambiguates from accuracy metrics (`micro_f1`, `extract_seconds_total`) which are top-level. |
| **G2** — Top-level (`generation_tokens_total`, `peak_memory_gb`, …) | **Rejected.** Pollutes the metric grid in the MLflow UI; mixes accuracy + perf in a single sort/filter pass. |
| **G3** — `latency.*` / `throughput.*` / `memory.*` (3 separate prefixes) | **Rejected.** Granular but awkward — the 6 logged metrics span all three categories. One prefix is simpler. |

## Decision

The 6 axes resolve to:

### D1 — Timing primitive: `time.perf_counter()` (Axis A1)

Reuse the existing per-page measurement already populating `ExtractionResult.extract_seconds`. No code change to extractors beyond what Chunk 1 added (per-page token counts + per-page tps).

### D2 — Peak GPU memory: dual-track per backend (Axis B2.A + MLX native)

- **MLX-routed extractors** (`MLXVLMExtractor`): use `GenerationResult.peak_memory` (true peak via `mx.get_peak_memory()`). Reset between extracts via `mx.reset_peak_memory()` in `MLXVLMExtractor.unload()` (Chunk 1). Stored as `ExtractionResult.peak_memory_gb`.
- **Transformers-MPS-routed extractors** (`TransformersMPSExtractor`): the harness calls `_snapshot_mps_driver_alloc_mb_or_none(extractor)` BEFORE and AFTER each `_score_single_invoice` call (Chunk 3). The post-snapshot is logged as `perf.mps_post_alloc_mb`; the delta as `perf.mps_delta_mb`; the post value (in GB) **overrides** `perf.peak_memory_gb` in the metric for this tuple (since `ExtractionResult.peak_memory_gb=0.0` for MPS extractors).

**Limitation (disclose in thesis writeup)**: MPS snapshot misses transient peak during `model.generate()`. For models where the transient peak materially exceeds the post-call steady state (uncommon for autoregressive LM decode but possible for any model that allocates large intermediate KV-cache tensors), the reported `peak_memory_gb` understates true memory usage. MLX-routed models do NOT suffer this limitation.

**Parent-level metric**: at the start of `run_cohort`, the harness logs `perf.mps_recommended_max_gb` (the host's `torch.mps.recommended_max_memory()` ceiling, in GB) on the parent MLflow run as a host-constant. The inspector uses this for the `%_max` column.

### D3 — Inspector graceful degradation (`_print_perf_table`)

Pre-#52 parent runs (no `perf.*` metrics on any nested run) get a single-line note ("`no perf.* metrics found on any nested run — this parent run predates issue #52 instrumentation`") instead of an empty table. Mixed runs (some tuples have `perf.*`, some don't) report the table over the perf-equipped subset and a footer note with the un-equipped count. This makes the inspector usable for archived parent runs from before #52 without a separate code path.

### D4 — Tokens/sec semantics: native + chars/sec proxy (Axis E1)

The inspector reports:

- `tps` = `perf.generation_tps_mean` (native, per-model tokenizer; **NOT cross-model comparable** — caveat in the section header).
- `chars/s` = `perf.chars_per_sec` (tokenizer-agnostic; pairs with `tps` as a sanity check; cross-model comparable for languages with similar character distributions).

Cross-model standardised tokens/sec (via tiktoken or HF benchmark methodology) is **deferred to the H4 hypothesis test**, where the cross-model rigor is required.

### D5 — Tokens/sec aggregation: time-weighted throughput (Axis D1.A)

`perf.generation_tps_mean = total_tokens / total_seconds` (matches Artificial Analysis methodology + MLX-VLM's internal formula). Fallback to arithmetic mean of per-page tps **only when** `total_tokens == 0` AND per-page tps is non-zero (defensive — handles a hypothetical future extractor that estimates tps without exposing token counts).

### D6 — Inspector rendering: plain-text, no new dependency (Axis F1)

`_print_perf_table` uses plain `print(...)` with f-string column alignment. Sorts by mean wall-clock ascending (fastest model row top — matches H4 latency narrative reading order). 8 columns: `model`, `n` (count), `wall_s`, `tps`, `chars/s`, `gen_tok`, `peak_GB`, `%_max`. The `_mean_str` helper renders per-column means or `—` for empty lists.

`%_max` shows `(max(per_model_peak) / mps_ceiling_gb) * 100` when both values exist; `—` otherwise (non-MPS hosts; pre-#52 parents without the ceiling logged).

## Source archival

Per `horus-source-archival.md`, every cited source archived under `docs/sources/<type>/<slug>.md`. New stubs landed in this ADR's commit:

- `docs/sources/tools/pytorch-issue-104188.md` — pytorch/pytorch#104188 (`torch.mps` peak-memory tracking gap; community workaround = pre/post snapshot)
- `docs/sources/tools/artificial-analysis-methodology.md` — Artificial Analysis tokens/sec methodology page (time-weighted throughput as canonical)
- `docs/sources/tools/mlx-vlm-generation-result.md` — MLX-VLM `GenerationResult` dataclass field shape (extends the existing `mlx-vlm.md` stub with the per-call return contract used in Chunk 1)

Existing source stubs reused (no new content needed — already archived):

- `docs/sources/tools/mlx-vlm.md` — MLX-VLM library overview (ADR-007 citation)
- `docs/sources/tools/pytorch-mps.md` — PyTorch MPS backend overview (ADR-007 citation)
- `docs/sources/tools/mlx-apple-silicon.md` — MLX `mx.get_peak_memory()` reference (ADR-007 citation)
- `docs/sources/tools/mlflow.md` — MLflow tracking + `log_metric` semantics (ADR-011 citation)

## Implementation map

The 7-commit branch `feat/issue-52-timing-inspector` lands the work in dependency order:

| Chunk | Commit | Files | Tested |
|---|---|---|---|
| 1 — `ExtractionResult` perf fields + extractor population | `feat(extractor): per-page perf fields ...` | `src/horus/vlm_extractor.py` | Ch.5 (3 tests in `test_vlm_extractor.py`) |
| 2 — Harness perf.* per-tuple metrics + parent ceiling | `feat(harness): per-tuple perf.* metrics ...` | `src/horus/eval/harness.py` | Ch.5 (`test_run_cohort_logs_perf_metrics_in_nested_run`) |
| 3 — MPS pre/post snapshot helper + override | `feat(harness): MPS pre/post memory snapshots ...` | `src/horus/eval/harness.py` | Ch.5 (`test_snapshot_mps_driver_alloc_returns_none_*` × 2) |
| 4 — Inspector `_print_perf_table` | `feat(inspector): per-model perf summary table ...` | `scripts/inspect_pilot_13.py` | Ch.5 (4 tests in `test_inspect_pilot_13.py`) |
| 5 — Tests | `test(perf): tests for ...` | `tests/test_{vlm_extractor,harness,inspect_pilot_13}.py` | self-pinning (10 new tests; full suite 379 → 389 passed) |
| 6 — Make target + README | `docs(perf): inspect-pilot-13 Make target ...` | `Makefile`, `README.md` | `make help \| grep inspect`, `make -n inspect-pilot-13` |
| 7 — This ADR + INDEX row + 3 source stubs | `docs(adr): ADR-017 ratifies #52 ...` | `docs/decisions/ADR-017-...md`, `docs/decisions/INDEX.md`, `docs/sources/tools/{pytorch-issue-104188,artificial-analysis-methodology,mlx-vlm-generation-result}.md` | (this commit) |

## What this ADR does NOT decide

- **The H4 hypothesis test itself.** This ADR ratifies the substrate (instrumentation + inspector). H4 (latency-efficiency comparison across the 7-working-model cohort) requires its own sweep, statistical analysis, and pre-registered-claim verification. Filed separately.
- **Cross-model standardised tokens/sec via tiktoken.** Deferred to H4 (Axis E2). When H4 runs, a follow-up ADR ratifies the standardisation.
- **Background-thread MPS peak sampler (Axis B2.B).** Deferred. Adopt only if H4's findings prove B2.A's snapshot misses transient peaks materially for a class of models in the cohort.
- **`rich`/`tabulate` inspector output.** Deferred (Axis F2). Plain-text is sufficient for current cohort size.
- **JSON output for machine consumption (Axis F3).** Deferred until a second consumer (CI gate / dashboard) materialises.
- **`mlflow.log_text` of the perf table on the parent run (Axis F4).** Worthwhile follow-up enhancement; out of scope for #52 to keep chunks minimal.
- **Mid-extract memory peak via background thread (Axis B2.B).** See above.
- **The `%_max` column when no MPS ceiling is logged.** Renders as `—` per row — see Axis F1's `_mean_str` helper. The ADR does not prescribe an alternative computation (would require a non-MPS ceiling source, e.g., `psutil.virtual_memory().total`, which conflates GPU and CPU memory).

## Refs

- Plan: `~/.windsurf/plans/horus-issue-52-timing-inspector-3fe7c5.md`
- Issue: [`ReebalSami/horus#52`](https://github.com/ReebalSami/horus/issues/52)
- Predecessor ADRs: ADR-007 (dual-track local VLM), ADR-009 (cohort), ADR-011 (MLflow), ADR-014 (cohort harness), ADR-016 (fast dev config — same Seq pattern)
- Sister rule: `long-running-foreground` — inspector output streams unbuffered; harness logging streams unbuffered.
- Pre-registered hypothesis: brainstorm v2 §6 H4 — "MLX-routed VLMs achieve ≥3× tokens/sec compared to Transformers-MPS-routed VLMs at comparable F1 on the ZUGFeRD corpus." This ADR's substrate makes the test possible; the test itself is a separate work item.
