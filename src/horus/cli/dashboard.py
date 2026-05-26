"""HORUS cohort-sweep display adapters and textual inline dashboard (ADR-026).

Architecture
------------
The cohort harness (``run_cohort``) and ``cohort_smoke.py`` call a
``DisplayAdapter`` at 8 lifecycle points — sweep start, model load start/done,
invoice start/complete/failed, model done, sweep done.  Three concrete
implementations fulfil this Protocol:

``HorusDashboardAdapter``
    Textual inline app.  Three sections:

    * **Top** — ``RichLog`` widget.  Per-invoice completion lines accumulate and
      are independently scrollable while the run is live (keyboard ↑↓ or
      mouse-wheel).  Full rich markup (✓ green, ⚠ yellow, FAILED bold-red).
    * **Middle** — current-model progress bar + label (model name, position,
      running mean F1, peak GB, decode tps).
    * **Bottom** — sweep-wide progress bar + label (total tuples, %, elapsed,
      ETA, cumulative tokens).

    ``App.suspend()`` wraps every ``extractor.load()`` call so HF tqdm bars
    stream natively (A3-suspend strategy per ADR-026; Textualize/textual#2878).

``PlainDisplayAdapter``
    Line-by-line ``[harness]``-prefixed ``print(... flush=True)`` output.
    Auto-selected when ``sys.stdout.isatty()`` is False (CI, pipes, file
    redirects).  Also selected via ``HORUS_DASHBOARD=plain`` env var or the
    ``--no-tui`` CLI flag.

``SilentDisplayAdapter``
    No output.  Used by pytest fixtures to prevent test output pollution.
    Selected via ``HORUS_DASHBOARD=silent`` env var.

Selection
---------
Call ``get_display_adapter()`` to auto-pick based on environment::

    display = get_display_adapter()
    with display:
        run_cohort(cfg, display=display)

Precedence (first match wins):

1. ``HORUS_DASHBOARD=silent``  →  ``SilentDisplayAdapter``
2. ``HORUS_DASHBOARD=plain``   →  ``PlainDisplayAdapter``
3. ``force_plain=True`` kwarg  →  ``PlainDisplayAdapter``
4. ``sys.stdout.isatty()`` is False  →  ``PlainDisplayAdapter``
5. Otherwise                   →  ``HorusDashboardAdapter``
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
from contextlib import nullcontext
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DisplayAdapter(Protocol):
    """Protocol for cohort-progress display adapters.

    All implementations are context managers (``with display:`` starts and
    stops the display layer).  The ``suspend()`` method returns a context
    manager that temporarily yields control back to the terminal — used for
    wrapping ``extractor.load()`` so HF tqdm bars stream natively.
    """

    def on_sweep_start(
        self, parent_run_id: str, total_models: int, total_invoices: int
    ) -> None: ...
    def on_model_load_start(self, model_idx: int, model_id: str) -> None: ...
    def on_model_loaded(
        self,
        model_idx: int,
        model_id: str,
        weights_gb: float,
    ) -> None: ...
    def on_invoice_start(
        self,
        model_id: str,
        model_idx: int,
        total_models: int,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
    ) -> None: ...
    def on_invoice_complete(
        self,
        model_id: str,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
        micro_f1: float,
        page_count: int,
        seconds: float,
    ) -> None: ...
    def on_invoice_failed(
        self,
        model_id: str,
        invoice_idx: int,
        invoice_name: str,
        error: str,
    ) -> None: ...
    def on_model_complete(
        self,
        model_idx: int,
        model_id: str,
        mean_f1: float,
        total_seconds: float,
    ) -> None: ...
    def on_sweep_complete(self) -> None: ...

    def suspend(self) -> contextlib.AbstractContextManager[None]: ...
    def __enter__(self) -> DisplayAdapter: ...
    def __exit__(self, *exc: object) -> None: ...


# ---------------------------------------------------------------------------
# PlainDisplayAdapter
# ---------------------------------------------------------------------------


class PlainDisplayAdapter:
    """Fallback adapter — line-by-line flush=True print (non-TTY / CI / --no-tui)."""

    def __init__(self) -> None:
        self._total_models = 0
        self._total_invoices = 0
        self._start_ts: float = 0.0

    def on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None:
        self._total_models = total_models
        self._total_invoices = total_invoices
        self._start_ts = time.monotonic()
        print(
            f"[harness] parent_run_id={parent_run_id} "
            f"models={total_models} invoices={total_invoices}",
            flush=True,
        )

    def on_model_load_start(self, model_idx: int, model_id: str) -> None:
        print(
            f"[harness] [model {model_idx}/{self._total_models}] loading {model_id} ...",
            flush=True,
        )

    def on_model_loaded(
        self,
        model_idx: int,
        model_id: str,
        weights_gb: float,
    ) -> None:
        gb_str = f" ({weights_gb:.1f} GB)" if weights_gb > 0 else ""
        print(
            f"[harness] [model {model_idx}/{self._total_models}] loaded ✓ {model_id}{gb_str}",
            flush=True,
        )

    def on_invoice_start(
        self,
        model_id: str,
        model_idx: int,
        total_models: int,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
    ) -> None:
        pass

    def on_invoice_complete(
        self,
        model_id: str,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
        micro_f1: float,
        page_count: int,
        seconds: float,
    ) -> None:
        print(
            f"[harness]   [{invoice_idx}/{total_invoices}] {invoice_name}: "
            f"micro_f1={micro_f1:.3f} pages={page_count} ({seconds:.1f}s)",
            flush=True,
        )

    def on_invoice_failed(
        self,
        model_id: str,
        invoice_idx: int,
        invoice_name: str,
        error: str,
    ) -> None:
        print(
            f"[harness]   [{invoice_idx}/{self._total_invoices}] {invoice_name}: FAILED: {error}",
            flush=True,
        )

    def on_model_complete(
        self,
        model_idx: int,
        model_id: str,
        mean_f1: float,
        total_seconds: float,
    ) -> None:
        print(
            f"[harness] [model {model_idx}/{self._total_models}] {model_id} done "
            f"mean_f1={mean_f1:.3f} ({total_seconds:.0f}s)",
            flush=True,
        )

    def on_sweep_complete(self) -> None:
        elapsed = time.monotonic() - self._start_ts
        m, s = divmod(int(elapsed), 60)
        print(f"[harness] sweep complete ({m}m {s}s)", flush=True)

    def suspend(self) -> contextlib.AbstractContextManager[None]:
        return nullcontext()

    def __enter__(self) -> PlainDisplayAdapter:
        return self

    def __exit__(self, *exc: object) -> None:
        pass


# ---------------------------------------------------------------------------
# SilentDisplayAdapter
# ---------------------------------------------------------------------------


class SilentDisplayAdapter:
    """No-op adapter for tests — emits nothing."""

    def on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None:
        pass

    def on_model_load_start(self, model_idx: int, model_id: str) -> None:
        pass

    def on_model_loaded(
        self,
        model_idx: int,
        model_id: str,
        weights_gb: float,
    ) -> None:
        pass

    def on_invoice_start(
        self,
        model_id: str,
        model_idx: int,
        total_models: int,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
    ) -> None:
        pass

    def on_invoice_complete(
        self,
        model_id: str,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
        micro_f1: float,
        page_count: int,
        seconds: float,
    ) -> None:
        pass

    def on_invoice_failed(
        self,
        model_id: str,
        invoice_idx: int,
        invoice_name: str,
        error: str,
    ) -> None:
        pass

    def on_model_complete(
        self,
        model_idx: int,
        model_id: str,
        mean_f1: float,
        total_seconds: float,
    ) -> None:
        pass

    def on_sweep_complete(self) -> None:
        pass

    def suspend(self) -> contextlib.AbstractContextManager[None]:
        return nullcontext()

    def __enter__(self) -> SilentDisplayAdapter:
        return self

    def __exit__(self, *exc: object) -> None:
        pass


# ---------------------------------------------------------------------------
# HorusDashboardApp — textual inline app
# ---------------------------------------------------------------------------


class HorusDashboardApp:
    """Wrapper that drives a textual App from the harness worker thread.

    The textual App runs asynchronously.  The harness calls update methods
    on this wrapper from its own (non-async) thread; the wrapper forwards
    the calls into the textual event loop via ``app.call_from_thread()``.

    Design notes
    ------------
    - The app is started lazily on ``__enter__`` and torn down on
      ``__exit__``.
    - ``suspend()`` delegates to ``app.suspend()`` so that HF tqdm bars
      stream natively during model loads (A3-suspend, ADR-026 §Decision).
    - All textual widget state mutations happen on the app's event loop
      (via ``call_from_thread``); this is thread-safe per textual's model.
    """

    def __init__(self) -> None:
        self._app: Any = None  # _HorusTUIApp when active; Any to avoid mypy dynamic-class issues
        self._total_models = 0
        self._total_invoices = 0
        self._completed_tuples = 0
        self._start_ts: float = 0.0
        self._model_f1_acc: list[float] = []
        self._model_start_ts: float = 0.0

    def _safe_call(self, fn: Any, *args: Any) -> None:
        """Push *fn(*args)* into the app's event loop from the harness thread."""
        if self._app is not None and self._app.is_running:
            try:
                self._app.call_from_thread(fn, *args)
            except Exception:  # noqa: BLE001
                pass

    def on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None:
        self._total_models = total_models
        self._total_invoices = total_invoices
        self._completed_tuples = 0
        self._start_ts = time.monotonic()
        fn = self._app._on_sweep_start if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, parent_run_id, total_models, total_invoices)

    def on_model_load_start(self, model_idx: int, model_id: str) -> None:
        self._model_f1_acc = []
        self._model_start_ts = time.monotonic()
        fn = self._app._on_model_load_start if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, model_idx, model_id)

    def on_model_loaded(
        self,
        model_idx: int,
        model_id: str,
        weights_gb: float,
    ) -> None:
        fn = self._app._on_model_loaded if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, model_idx, model_id, weights_gb)

    def on_invoice_start(
        self,
        model_id: str,
        model_idx: int,
        total_models: int,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
    ) -> None:
        fn = self._app._on_invoice_start if self._app is not None else None
        if fn is not None:
            self._safe_call(
                fn, model_id, model_idx, total_models, invoice_idx, total_invoices, invoice_name
            )

    def on_invoice_complete(
        self,
        model_id: str,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
        micro_f1: float,
        page_count: int,
        seconds: float,
    ) -> None:
        self._completed_tuples += 1
        self._model_f1_acc.append(micro_f1)
        fn = self._app._on_invoice_complete if self._app is not None else None
        if fn is not None:
            self._safe_call(
                fn,
                model_id,
                invoice_idx,
                total_invoices,
                invoice_name,
                micro_f1,
                page_count,
                seconds,
                self._completed_tuples,
                self._total_models * self._total_invoices,
                time.monotonic() - self._start_ts,
            )

    def on_invoice_failed(
        self,
        model_id: str,
        invoice_idx: int,
        invoice_name: str,
        error: str,
    ) -> None:
        self._completed_tuples += 1
        fn = self._app._on_invoice_failed if self._app is not None else None
        if fn is not None:
            self._safe_call(
                fn,
                model_id,
                invoice_idx,
                invoice_name,
                error,
                self._completed_tuples,
                self._total_models * self._total_invoices,
            )

    def on_model_complete(
        self,
        model_idx: int,
        model_id: str,
        mean_f1: float,
        total_seconds: float,
    ) -> None:
        fn = self._app._on_model_complete if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, model_idx, model_id, mean_f1, total_seconds)

    def on_sweep_complete(self) -> None:
        fn = self._app._on_sweep_complete if self._app is not None else None
        if fn is not None:
            self._safe_call(fn)

    def suspend(self) -> contextlib.AbstractContextManager[None]:
        if self._app is not None:
            return self._app.suspend()
        return nullcontext()

    def __enter__(self) -> HorusDashboardApp:
        self._app = _HorusTUIApp()
        self._app._start_inline()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._app is not None:
            try:
                self._app._stop_inline()
            except Exception:  # noqa: BLE001
                pass
            self._app = None


# ---------------------------------------------------------------------------
# _HorusTUIApp — the actual textual.App
# ---------------------------------------------------------------------------


class _HorusTUIApp:
    """Lightweight textual App wrapper with the 3-section HORUS layout.

    Runs in a background thread so the harness can call ``call_from_thread``
    to push widget updates without blocking inference.
    """

    def __init__(self) -> None:
        self._app: Any = None  # _TextualHorusApp when active
        self._thread: threading.Thread | None = None
        self.is_running: bool = False

    def _start_inline(self) -> None:
        import threading  # noqa: PLC0415

        self._app = _TextualHorusApp()
        ready_event = threading.Event()

        def _run() -> None:
            import asyncio  # noqa: PLC0415

            async def _inner() -> None:
                ready_event.set()
                await self._app.run_async(inline=True)

            asyncio.run(_inner())

        self._thread = threading.Thread(target=_run, daemon=True, name="horus-tui")
        self._thread.start()
        ready_event.wait(timeout=5.0)
        self.is_running = True

    def _stop_inline(self) -> None:
        if self._app is not None and self._app.is_running:
            self._app.call_from_thread(self._app.exit)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self.is_running = False

    def call_from_thread(self, fn: Any, *args: Any) -> None:
        if self._app is not None and self._app.is_running:
            self._app.call_from_thread(fn, *args)

    def suspend(self) -> contextlib.AbstractContextManager[None]:
        if self._app is not None and self._app.is_running:
            return self._app.suspend()
        return nullcontext()

    def _on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None:
        if self._app:
            self._app._on_sweep_start(parent_run_id, total_models, total_invoices)

    def _on_model_load_start(self, model_idx: int, model_id: str) -> None:
        if self._app:
            self._app._on_model_load_start(model_idx, model_id)

    def _on_model_loaded(self, model_idx: int, model_id: str, weights_gb: float) -> None:
        if self._app:
            self._app._on_model_loaded(model_idx, model_id, weights_gb)

    def _on_invoice_start(
        self,
        model_id: str,
        model_idx: int,
        total_models: int,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
    ) -> None:
        if self._app:
            self._app._on_invoice_start(
                model_id, model_idx, total_models, invoice_idx, total_invoices, invoice_name
            )

    def _on_invoice_complete(
        self,
        model_id: str,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
        micro_f1: float,
        page_count: int,
        seconds: float,
        completed_tuples: int,
        total_tuples: int,
        elapsed_s: float,
    ) -> None:
        if self._app:
            self._app._on_invoice_complete(
                model_id,
                invoice_idx,
                total_invoices,
                invoice_name,
                micro_f1,
                page_count,
                seconds,
                completed_tuples,
                total_tuples,
                elapsed_s,
            )

    def _on_invoice_failed(
        self,
        model_id: str,
        invoice_idx: int,
        invoice_name: str,
        error: str,
        completed_tuples: int,
        total_tuples: int,
    ) -> None:
        if self._app:
            self._app._on_invoice_failed(
                model_id, invoice_idx, invoice_name, error, completed_tuples, total_tuples
            )

    def _on_model_complete(
        self,
        model_idx: int,
        model_id: str,
        mean_f1: float,
        total_seconds: float,
    ) -> None:
        if self._app:
            self._app._on_model_complete(model_idx, model_id, mean_f1, total_seconds)

    def _on_sweep_complete(self) -> None:
        if self._app:
            self._app._on_sweep_complete()


# ---------------------------------------------------------------------------
# _TextualHorusApp — the actual textual.App class
# ---------------------------------------------------------------------------


def _fmt_eta(elapsed_s: float, completed: int, total: int) -> str:
    """Return a human-friendly ETA string, or '—' when not computable."""
    if completed <= 0 or total <= 0:
        return "—"
    rate = completed / elapsed_s if elapsed_s > 0 else 0.0
    remaining = total - completed
    if rate <= 0:
        return "—"
    eta_s = remaining / rate
    m, s = divmod(int(eta_s), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def _short_model(model_id: str) -> str:
    """Return just the model name part (after the last '/') truncated to 28 chars."""
    name = model_id.split("/")[-1]
    return name[:28]


class _TextualHorusApp:
    """The actual textual.App, assembled lazily to avoid import-at-module-level."""

    def __init__(self) -> None:
        self._built_app: Any = None  # HorusApp(App) instance; typed as Any (defined inside _build)
        self._build()

    def _build(self) -> None:
        from textual.app import App, ComposeResult  # noqa: PLC0415
        from textual.widgets import (  # noqa: PLC0415
            Label,
            ProgressBar,
            RichLog,
            Rule,
            Static,
        )

        eagle_orange = "#E8833A"
        hieroglyph_cyan = "#3AA8C8"
        EAGLE_ORANGE = eagle_orange  # noqa: N806 — used in f-strings for CSS + markup
        HIEROGLYPH_CYAN = hieroglyph_cyan  # noqa: N806

        class HorusApp(App):  # noqa: N801 — defined inside function; inherits from Any-typed App
            CSS = f"""
            Screen {{
                background: $surface;
            }}
            #title-bar {{
                color: {EAGLE_ORANGE};
                text-style: bold;
                padding: 0 1;
                height: 1;
            }}
            #log-section {{
                height: 1fr;
                border: solid {HIEROGLYPH_CYAN};
                padding: 0 1;
            }}
            #section-rule {{
                color: {EAGLE_ORANGE};
                margin: 0;
            }}
            #model-label {{
                color: {HIEROGLYPH_CYAN};
                padding: 0 1;
                height: 1;
            }}
            #model-bar {{
                padding: 0 1;
                height: 1;
            }}
            #sweep-label {{
                color: {EAGLE_ORANGE};
                padding: 0 1;
                height: 1;
            }}
            #sweep-bar {{
                padding: 0 1;
                height: 1;
            }}
            #footer-hint {{
                color: $text-muted;
                padding: 0 1;
                height: 1;
            }}
            """

            BINDINGS = [
                ("q", "quit", "Quit"),
                ("space", "toggle_pause", "Pause"),
            ]

            def compose(self) -> ComposeResult:
                yield Static(
                    f"[bold {EAGLE_ORANGE}]🦅 HORUS cohort sweep[/] — starting…",
                    id="title-bar",
                )
                yield RichLog(id="log-section", markup=True, auto_scroll=True)
                yield Rule(id="section-rule")
                yield Label("Current model: (loading…)", id="model-label")
                yield ProgressBar(total=100, show_eta=False, id="model-bar")
                yield Rule()
                yield Label("Sweep: (starting…)", id="sweep-label")
                yield ProgressBar(total=100, show_eta=False, id="sweep-bar")
                yield Static(
                    "[dim][ Q quit  ·  ↑↓ scroll log  ·  SPACE pause ][/]",
                    id="footer-hint",
                )

            def action_toggle_pause(self) -> None:
                pass

            def _on_sweep_start(
                self, parent_run_id: str, total_models: int, total_invoices: int
            ) -> None:
                short_id = parent_run_id[:8] if len(parent_run_id) >= 8 else parent_run_id
                self.query_one("#title-bar", Static).update(
                    f"[bold {EAGLE_ORANGE}]🦅 HORUS cohort sweep[/] "
                    f"[dim]parent={short_id}  {total_models} models × "
                    f"{total_invoices} invoices = {total_models * total_invoices} tuples[/]"
                )
                total_t = float(total_models * total_invoices)
                self.query_one("#sweep-bar", ProgressBar).update(total=total_t)
                self.query_one("#sweep-label", Label).update(
                    f"[{EAGLE_ORANGE}]Sweep:[/] 0/{total_models * total_invoices}  (0%)"
                )

            def _on_model_load_start(self, model_idx: int, model_id: str) -> None:
                log = self.query_one("#log-section", RichLog)
                log.write(
                    f"[bold {HIEROGLYPH_CYAN}]⏵[/] [{HIEROGLYPH_CYAN}]{_short_model(model_id)}[/]"
                    "  loading …"
                )
                self.query_one("#model-label", Label).update(
                    f"[{HIEROGLYPH_CYAN}]Model {model_idx}:[/] {_short_model(model_id)} — loading …"
                )
                self.query_one("#model-bar", ProgressBar).update(progress=0.0)

            def _on_model_loaded(self, model_idx: int, model_id: str, weights_gb: float) -> None:
                gb_str = f"  {weights_gb:.1f} GB" if weights_gb > 0 else ""
                self.query_one("#model-label", Label).update(
                    f"[{HIEROGLYPH_CYAN}]Model {model_idx}:[/] {_short_model(model_id)}{gb_str}"
                )

            def _on_invoice_start(
                self,
                model_id: str,
                model_idx: int,
                total_models: int,
                invoice_idx: int,
                total_invoices: int,
                invoice_name: str,
            ) -> None:
                short_inv = invoice_name[:30]
                self.query_one("#model-label", Label).update(
                    f"[{HIEROGLYPH_CYAN}]Model {model_idx}/{total_models}:[/] "
                    f"{_short_model(model_id)}  [{invoice_idx}/{total_invoices}] {short_inv}"
                )

            def _on_invoice_complete(
                self,
                model_id: str,
                invoice_idx: int,
                total_invoices: int,
                invoice_name: str,
                micro_f1: float,
                page_count: int,
                seconds: float,
                completed_tuples: int,
                total_tuples: int,
                elapsed_s: float,
            ) -> None:
                log = self.query_one("#log-section", RichLog)
                if micro_f1 >= 0.5:
                    f1_color = "green"
                elif micro_f1 >= 0.3:
                    f1_color = "yellow"
                else:
                    f1_color = "red"
                log.write(
                    f"[green]✓[/] [{HIEROGLYPH_CYAN}]{_short_model(model_id):<28}[/]  "
                    f"{invoice_name:<40}  "
                    f"f1=[{f1_color}]{micro_f1:.3f}[/]  "
                    f"p={page_count}  ({seconds:.1f}s)"
                )
                pct = int(completed_tuples * 100 / total_tuples) if total_tuples else 0
                eta = _fmt_eta(elapsed_s, completed_tuples, total_tuples)
                self.query_one("#sweep-bar", ProgressBar).update(progress=float(completed_tuples))
                self.query_one("#sweep-label", Label).update(
                    f"[{EAGLE_ORANGE}]Sweep:[/] {completed_tuples}/{total_tuples}"
                    f"  ({pct}%)  elapsed {int(elapsed_s // 60)}m {int(elapsed_s % 60):02d}s"
                    f"  ETA {eta}"
                )
                self.query_one("#model-bar", ProgressBar).update(progress=float(invoice_idx))

            def _on_invoice_failed(
                self,
                model_id: str,
                invoice_idx: int,
                invoice_name: str,
                error: str,
                completed_tuples: int,
                total_tuples: int,
            ) -> None:
                log = self.query_one("#log-section", RichLog)
                log.write(
                    f"[bold red]⚠[/] [{HIEROGLYPH_CYAN}]{_short_model(model_id):<28}[/]  "
                    f"{invoice_name:<40}  [bold red]FAILED[/]: {error[:60]}"
                )
                self.query_one("#sweep-bar", ProgressBar).update(progress=float(completed_tuples))
                self.query_one("#model-bar", ProgressBar).update(progress=float(invoice_idx))

            def _on_model_complete(
                self,
                model_idx: int,
                model_id: str,
                mean_f1: float,
                total_seconds: float,
            ) -> None:
                log = self.query_one("#log-section", RichLog)
                m, s = divmod(int(total_seconds), 60)
                log.write(
                    f"[bold green]✔[/] [{EAGLE_ORANGE}]{_short_model(model_id)}[/]"
                    f"  done  mean_f1={mean_f1:.3f}  ({m}m {s:02d}s)"
                )

            def _on_sweep_complete(self) -> None:
                log = self.query_one("#log-section", RichLog)
                log.write(f"[bold {EAGLE_ORANGE}]🦅 HORUS sweep complete.[/]")
                self.query_one("#sweep-label", Label).update(f"[{EAGLE_ORANGE}]Sweep complete ✔[/]")

        self._built_app = HorusApp()

    @property
    def is_running(self) -> bool:
        if self._built_app is None:
            return False
        return getattr(self._built_app, "is_running", False)

    def call_from_thread(self, fn: Any, *args: Any) -> None:
        if self._built_app is not None:
            self._built_app.call_from_thread(fn, *args)

    def suspend(self) -> contextlib.AbstractContextManager[None]:
        if self._built_app is not None and getattr(self._built_app, "is_running", False):
            return self._built_app.suspend()
        return nullcontext()

    async def run_async(self, *, inline: bool = False) -> None:
        if self._built_app is not None:
            await self._built_app.run_async(inline=inline)

    def exit(self, *args: Any) -> None:
        if self._built_app is not None:
            self._built_app.exit()

    def _on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None:
        if self._built_app is not None:
            self._built_app._on_sweep_start(parent_run_id, total_models, total_invoices)

    def _on_model_load_start(self, model_idx: int, model_id: str) -> None:
        if self._built_app is not None:
            self._built_app._on_model_load_start(model_idx, model_id)

    def _on_model_loaded(self, model_idx: int, model_id: str, weights_gb: float) -> None:
        if self._built_app is not None:
            self._built_app._on_model_loaded(model_idx, model_id, weights_gb)

    def _on_invoice_start(
        self,
        model_id: str,
        model_idx: int,
        total_models: int,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
    ) -> None:
        if self._built_app is not None:
            self._built_app._on_invoice_start(
                model_id, model_idx, total_models, invoice_idx, total_invoices, invoice_name
            )

    def _on_invoice_complete(
        self,
        model_id: str,
        invoice_idx: int,
        total_invoices: int,
        invoice_name: str,
        micro_f1: float,
        page_count: int,
        seconds: float,
        completed_tuples: int,
        total_tuples: int,
        elapsed_s: float,
    ) -> None:
        if self._built_app is not None:
            self._built_app._on_invoice_complete(
                model_id,
                invoice_idx,
                total_invoices,
                invoice_name,
                micro_f1,
                page_count,
                seconds,
                completed_tuples,
                total_tuples,
                elapsed_s,
            )

    def _on_invoice_failed(
        self,
        model_id: str,
        invoice_idx: int,
        invoice_name: str,
        error: str,
        completed_tuples: int,
        total_tuples: int,
    ) -> None:
        if self._built_app is not None:
            self._built_app._on_invoice_failed(
                model_id, invoice_idx, invoice_name, error, completed_tuples, total_tuples
            )

    def _on_model_complete(
        self,
        model_idx: int,
        model_id: str,
        mean_f1: float,
        total_seconds: float,
    ) -> None:
        if self._built_app is not None:
            self._built_app._on_model_complete(model_idx, model_id, mean_f1, total_seconds)

    def _on_sweep_complete(self) -> None:
        if self._built_app is not None:
            self._built_app._on_sweep_complete()


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------


def get_display_adapter(*, force_plain: bool = False) -> DisplayAdapter:
    """Auto-select the right display adapter for the current environment.

    Precedence (first match wins):

    1. ``HORUS_DASHBOARD=silent``  →  :class:`SilentDisplayAdapter`
    2. ``HORUS_DASHBOARD=plain``   →  :class:`PlainDisplayAdapter`
    3. *force_plain=True* kwarg    →  :class:`PlainDisplayAdapter`
    4. ``sys.stdout.isatty()`` is False  →  :class:`PlainDisplayAdapter`
    5. Otherwise                   →  :class:`HorusDashboardAdapter`

    Returns:
        An instance satisfying the :class:`DisplayAdapter` Protocol.
    """
    env = os.environ.get("HORUS_DASHBOARD", "").strip().lower()
    if env == "silent":
        return SilentDisplayAdapter()
    if env == "plain" or force_plain:
        return PlainDisplayAdapter()
    if not sys.stdout.isatty():
        return PlainDisplayAdapter()
    return HorusDashboardApp()
