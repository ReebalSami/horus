# ADR-026 — Cohort dashboard TUI: textual inline-app three-section live display

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-26 |
| **Closes** | issue #47 (terminal-output refactor) |
| **Amends** | ADR-017 §"plain-text, no `rich` dep" deferral (dissolved — `rich` is now a declared dep) |

---

## Current-state survey

Date: 2026-05-26. Research performed via `mcp2_resolve-library-id` + `mcp2_query-docs` (context7 MCP) + four targeted web searches.

**`rich` 14.x** (Textualize, MIT): de-facto Python rich-text library. `rich.Progress` supports stacked tasks; `rich.Console` auto-degrades on non-TTY. Already present as a transitive dep; not yet declared as an explicit runtime dep. `rich.Progress.redirect_stdout=False, redirect_stderr=False` is the key flag for HF-tqdm coexistence.

**`textual` 6.x** (Textualize, MIT): full TUI framework layered on top of `rich`. `App.run(inline=True)` renders the app below the terminal prompt without taking over the screen (macOS/Linux only; not supported on Windows — Textualize/textual#4409). `App.suspend()` context manager: pauses the app, returns the terminal to normal mode, resumes on exit. `RichLog` widget: scrollable streaming log with full rich markup, auto-scrolls on append, user can scroll up manually with keyboard/mouse. `ProgressBar` widget: reactive, CSS-styleable. `Pilot` class: official testing driver for headless textual tests.

**Confirmed hard problem**: textual replaces `sys.stdout`/`sys.stderr` while running; `tqdm` (used by HF Transformers + huggingface_hub for model downloads) crashes with `AttributeError: 'NoneType' object has no attribute 'write'` (Textualize/textual#2878, filed Jul 2023, open as of this ADR date). The standard documented workaround is `App.suspend()`.

**`tqdm` 4.x** (MIT): universal Python progress bar; HF Transformers + huggingface_hub use it for model downloads. Already present as a transitive dep (declared transitive via `transformers` + `mlflow`). `tqdm.contrib.logging.logging_redirect_tqdm` enables clean coexistence with Python logging.

**`pyfiglet` 1.x** (MIT): Python port of FIGlet. `pyfiglet.figlet_format(text, font="slant")` returns ASCII-art string; `rich.Console.print(Text(banner, style="..."))` renders it with truecolor. Pure-Python, ARM-compatible, ~500 KB.

**Alternatives evaluated**: enlighten (A1), rich.Live+Layout (A2), textual (A3, chosen), alive-progress (A4), rich.Progress stacked (A5). Full mockup comparison in `~/.windsurf/plans/issue-47-cohort-dashboard-f347f3.md`.

---

## Options considered

| Option | Library stack | Why considered | Why not chosen |
|---|---|---|---|
| **A1 — enlighten + rich** | `enlighten` 1.14.x + `rich` | Built-for-purpose pinned-bottom-bars + scrolling top; no stdio redirection; honors `long-running-foreground` | Less interactive; "polished CLI" feel vs. app feel; top section is terminal scrollback (not a widget); future extendability limited |
| **A2 — rich.Live + Layout** | `rich` only | Most visually polished (panel borders, truecolor); single dep | Bounded top panel — older completion lines disappear and can't be retrieved; fights HF tqdm (must pause/resume); issue #47 anti-pattern guard explicitly flags this |
| **A3 — textual inline app** | `textual` + `rich` | ✓ **Chosen** — three-section layout per user spec; top panel independently scrollable; interactive (keyboard/mouse); future-extensible (could add MLflow widget, GPU monitor); `App.suspend()` handles HF tqdm cleanly | Highest implementation cost; `App.suspend()` causes ~30s panel disappearance per model load (7 loads × ~30s = ~3.5 min cumulative flicker per full sweep; accepted per user Q1 decision on 2026-05-26) |
| **A4 — alive-progress** | `alive-progress` + `rich` | Most animated; lowest cost | Single-bar architecture — compresses user's 3-section spec into 1; rotating label is a gimmick for a scientific harness; loses the sweep/model distinction |
| **A5 — rich.Progress stacked** | `rich` only | Single dep; honors all rules; 3 stacked bars; cheapest | Less data-density (model name as description string); mild HF tqdm flicker; less interactive (no scroll/search inside the log region) |

Sources archived: `docs/sources/tools/textual.md`, `docs/sources/tools/rich.md`, `docs/sources/tools/tqdm.md`, `docs/sources/tools/pyfiglet.md`.

---

## Decision + integration thoughts

**Adopt A3 (textual inline app) with A3-suspend strategy for HF tqdm.**

### Architecture: display-adapter pattern

`run_cohort` (ADR-014) and `cohort_smoke.py` (ADR-009) become display-agnostic via a `DisplayAdapter` Protocol. Three concrete adapters:

| Adapter | When | What |
|---|---|---|
| `HorusDashboardAdapter` | TTY + interactive (default dev path) | Textual inline app; 3-section layout |
| `PlainDisplayAdapter` | No TTY / pipe / CI / `--no-tui` flag | Line-by-line `[harness]`-prefixed print; `flush=True` |
| `SilentDisplayAdapter` | pytest | No output; context manager no-ops |

Selection (`get_display_adapter()` in `src/horus/cli/dashboard.py`):
1. `force_plain=True` kwarg → `PlainDisplayAdapter`
2. `HORUS_DASHBOARD=plain` env var → `PlainDisplayAdapter`
3. `HORUS_DASHBOARD=silent` env var → `SilentDisplayAdapter`
4. `sys.stdout.isatty()` is False → `PlainDisplayAdapter`
5. Otherwise → `HorusDashboardAdapter`

### Display callback surface (8 events)

```python
class DisplayAdapter(Protocol):
    def on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None: ...
    def on_model_load_start(self, model_idx: int, model_id: str) -> None: ...
    def on_model_loaded(self, model_idx: int, model_id: str, weights_gb: float) -> None: ...
    def on_invoice_start(self, model_id: str, invoice_idx: int, invoice_name: str) -> None: ...
    def on_invoice_complete(self, model_id: str, invoice_idx: int, invoice_name: str, micro_f1: float, page_count: int, seconds: float) -> None: ...
    def on_invoice_failed(self, model_id: str, invoice_idx: int, invoice_name: str, error: str) -> None: ...
    def on_model_complete(self, model_id: str, mean_f1: float) -> None: ...
    def on_sweep_complete(self) -> None: ...
    def suspend(self) -> contextlib.AbstractContextManager[None]: ...  # app.suspend() or nullcontext
    def __enter__(self) -> DisplayAdapter: ...
    def __exit__(self, *exc: object) -> None: ...
```

### HF tqdm / App.suspend() integration

Every `extractor.load()` call is wrapped in `with display.suspend():`. The `HorusDashboardAdapter` delegates `suspend()` to `textual.App.suspend()`:

```python
# In harness.py
with display.suspend():     # textual app pauses; tqdm bars stream natively
    extractor.load()
display.on_model_loaded(...)  # app resumes; updates the middle section
```

Trade-off accepted (user Q1, 2026-05-26): ~30s panel disappearance during each model load. HF tqdm download bars remain fully visible per `long-running-foreground` rule.

### Textual app layout (3 sections)

```
╭──── HORUS cohort sweep ─────────────────────────────────────╮
│ RichLog (scrollable, full rich markup) — per-invoice details │
│   ✓ model  invoice  f1=0.412  pages=2  (8.3s)               │
│   ⚠ model  invoice  FAILED: TimeoutError                     │
│   …                                                          │
│ ─── Current model ─────────────────────────────────────────  │
│ ModelBar (ProgressBar + Label)                               │
│   granite-docling-258M  17/26  f1=0.31  8.2 GB              │
│ ─── Sweep ──────────────────────────────────────────────     │
│ SweepBar (ProgressBar + Label)                               │
│   43/182 (24%)  0:23:47 elapsed  ETA 1:12  tok 124k         │
╰──────────────────────────────────────────────────────────────╯
[ Q quit · ↑↓ scroll log · SPACE pause ]
```

### Pyfiglet HORUS banner

Rendered once at sweep start via `src/horus/cli/banner.py`:

```python
from pyfiglet import figlet_format
from rich.console import Console
from rich.text import Text

EAGLE_ORANGE = "#E8833A"
HIEROGLYPH_CYAN = "#3AA8C8"

def print_banner(console: Console | None = None) -> None:
    c = console or Console()
    art = figlet_format("HORUS", font="slant")
    c.print(Text(art, style=f"bold {EAGLE_ORANGE}"))
    c.print(Text("  Hybrid OCR-free Reading & Understanding System", style=HIEROGLYPH_CYAN))
```

### Integration with existing ADRs

- **ADR-009** (cohort manifest): no change — dashboard renders any cohort configuration.
- **ADR-011** (MLflow tracker): no change — display callbacks are ADDITIVE; MLflow logging continues unchanged.
- **ADR-014** (cohort harness): `run_cohort` gains `display: DisplayAdapter | None = None` kwarg; existing call sites with no display arg → auto-pick (`get_display_adapter()`).
- **ADR-016** (adapter-iterate): `make adapter-iterate` calls `scripts/rescore.py` (not `run_cohort`) — out of scope for this ADR; captured as follow-up issue.
- **ADR-017** (perf instrumentation): `_print_perf_table` migrates to `rich.Table(box=None)` in this PR. The "plain-text, no `rich` dep" deferral from ADR-017 is dissolved because `rich` becomes an explicit dep here. Tests that assert `row.rstrip().endswith("—")` continue to pass — `rich.Table(box=None)` pads with spaces (stripped by `rstrip()`), leaving the em-dash as the last visible token.
- **ADR-023** (CI pipeline): CI runs in no-TTY → `get_display_adapter()` returns `PlainDisplayAdapter` → `make test` unchanged.
- `long-running-foreground` rule: honored — no stdio redirection inside `HorusDashboardAdapter` during inference; `App.suspend()` ensures HF tqdm streams live; `PlainDisplayAdapter` is line-by-line `flush=True`.
- `know-your-hardware` rule: all 4 new deps are pure-Python, ARM-compatible, no CUDA.

### New package: `src/horus/cli/`

- `src/horus/cli/__init__.py` — re-exports `get_display_adapter`, `print_banner`
- `src/horus/cli/dashboard.py` — `DisplayAdapter` Protocol + 3 adapters + `HorusDashboardApp`
- `src/horus/cli/banner.py` — pyfiglet + rich banner

### Amends ADR-017

ADR-017 §"Decision 3" deferred `_print_perf_table` to plain ASCII with explicit note "plain-text, no `rich` dep". This ADR dissolves that constraint (condition: `rich` not a declared dep; condition is now false). `_print_perf_table` migrates to `rich.Table(box=None)` for visual consistency with the other inspector tables.

---

## Source archival

- `docs/sources/tools/textual.md` — Textualize/textual GitHub + textual.textualize.io docs
- `docs/sources/tools/rich.md` — Textualize/rich GitHub + rich.readthedocs.io docs
- `docs/sources/tools/tqdm.md` — tqdm/tqdm GitHub + tqdm.github.io docs
- `docs/sources/tools/pyfiglet.md` — pwaller/pyfiglet GitHub + PyPI

---

## Supersession trigger

This ADR is superseded if any one of:

1. **Textualize/textual#2878 is fixed upstream**: `tqdm` + textual coexist without `App.suspend()`. The suspend/resume cycle becomes unnecessary; the panel stays continuously visible during model loads. Remove the `display.suspend()` wrapping in `harness.py`; update this ADR to note the simplification.
2. **HORUS pivots to API-only models**: no local model loads → no HF tqdm → no `App.suspend()` needed → the A3-suspend trade-off is moot. Consider migrating to A2 (rich.Live) for simpler code.
3. **Performance regression measured**: textual app overhead degrades inference throughput by >5% (measured: tokens/sec of `granite-docling-258M-mlx` on M1 Pro, with-vs-without `HorusDashboardAdapter`). Fall back to A5 (rich.Progress stacked) as the lower-overhead alternative.
4. **Inline mode lands on Windows**: the non-TTY fallback is the only Windows-compatible path until `textual` supports inline mode on Windows. If Windows support is ever required, evaluate Textualize/textual#4409 resolution.
