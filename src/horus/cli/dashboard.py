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
from collections.abc import Callable
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

    def run_with_harness(self, fn: Callable[[], None]) -> None: ...


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

    def run_with_harness(self, fn: Callable[[], None]) -> None:
        with self:
            fn()


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

    def run_with_harness(self, fn: Callable[[], None]) -> None:
        fn()


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

    LOG_PATH = "/tmp/horus-last-run.log"

    def __init__(self) -> None:
        self._app: Any = None  # _HorusTUIApp when active; Any to avoid mypy dynamic-class issues
        self._total_models = 0
        self._total_invoices = 0
        self._completed_tuples = 0
        self._start_ts: float = 0.0
        self._model_f1_acc: list[float] = []
        self._model_start_ts: float = 0.0
        self._parent_run_id: str = ""
        self._weights_gb: float = 0.0
        # Visibility: TUI clears its inline area on exit, so the dashboard's
        # log content disappears. Mirror every lifecycle event to (a) an in-
        # memory list printed to stderr after the TUI exits and (b) a tail-able
        # log file at /tmp/horus-last-run.log. This guarantees the user sees
        # what happened even if the TUI rendering itself has issues.
        self._event_log: list[str] = []
        self._failures: list[tuple[str, str, str]] = []  # (model_id, inv, err)
        self._log_file: Any = None

    def _safe_call(self, fn: Any, *args: Any) -> None:
        """Push *fn(*args)* into the app's event loop from the harness thread."""
        if self._app is not None and self._app.is_running:
            try:
                self._app.call_from_thread(fn, *args)
            except Exception:  # noqa: BLE001
                pass

    def _emit(self, line: str) -> None:
        """Record a lifecycle event to memory + tail-able log file."""
        self._event_log.append(line)
        if self._log_file is not None:
            try:
                self._log_file.write(line + "\n")
                self._log_file.flush()
            except Exception:  # noqa: BLE001
                pass

    def on_sweep_start(self, parent_run_id: str, total_models: int, total_invoices: int) -> None:
        self._total_models = total_models
        self._total_invoices = total_invoices
        self._completed_tuples = 0
        self._start_ts = time.monotonic()
        self._parent_run_id = parent_run_id
        self._weights_gb = 0.0
        short_id = parent_run_id[:8] if len(parent_run_id) >= 8 else parent_run_id
        self._emit(
            f"[sweep] start parent={short_id} models={total_models} invoices={total_invoices}"
        )
        fn = self._app._on_sweep_start if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, parent_run_id, total_models, total_invoices)

    def on_model_load_start(self, model_idx: int, model_id: str) -> None:
        self._model_f1_acc = []
        self._model_start_ts = time.monotonic()
        self._emit(f"[model {model_idx}/{self._total_models}] loading {model_id}")
        fn = self._app._on_model_load_start if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, model_idx, model_id)

    def on_model_loaded(
        self,
        model_idx: int,
        model_id: str,
        weights_gb: float,
    ) -> None:
        self._weights_gb = max(self._weights_gb, weights_gb)
        gb_str = f" ({weights_gb:.1f} GB)" if weights_gb > 0 else ""
        self._emit(f"[model {model_idx}/{self._total_models}] loaded \u2713 {model_id}{gb_str}")
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
        self._emit(f"  [{invoice_idx}/{total_invoices}] {invoice_name}: extracting")
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
        self._emit(
            f"  [{invoice_idx}/{total_invoices}] {invoice_name}: "
            f"\u2713 f1={micro_f1:.3f} pages={page_count} ({seconds:.1f}s)"
        )
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
        self._failures.append((model_id, invoice_name, error))
        self._emit(f"  [{invoice_idx}] {invoice_name}: \u26a0 FAILED ({model_id}): {error}")
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
        self._emit(
            f"[model {model_idx}/{self._total_models}] {model_id} done "
            f"mean_f1={mean_f1:.3f} ({total_seconds:.1f}s)"
        )
        fn = self._app._on_model_complete if self._app is not None else None
        if fn is not None:
            self._safe_call(fn, model_idx, model_id, mean_f1, total_seconds)

    def on_sweep_complete(self) -> None:
        elapsed = time.monotonic() - self._start_ts
        m, s = divmod(int(elapsed), 60)
        self._emit(f"[sweep] complete ({m}m {s}s)")
        fn = self._app._on_sweep_complete if self._app is not None else None
        if fn is not None:
            self._safe_call(fn)

    def suspend(self) -> contextlib.AbstractContextManager[None]:
        # Cross-thread textual ``app.suspend()`` invokes ``signal.signal()`` from
        # the calling thread inside the driver's pause/resume — which Python
        # forbids outside the main thread (same restriction that motivated the
        # threading inversion in `run_with_harness`). Returning ``nullcontext``
        # from a worker thread means HF tqdm bars during ``extractor.load()``
        # are NOT shown live (the dashboard's ``loading…`` line + the post-TUI
        # event log are the surfaced signals). Trade-off documented in ADR-026.
        return nullcontext()

    def __enter__(self) -> HorusDashboardApp:
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def run_with_harness(self, fn: Callable[[], None]) -> None:
        """Run *fn* in a background thread while the textual TUI blocks the main thread.

        Textual's ``LinuxInlineDriver.start_application_mode()`` calls
        ``signal.signal(SIGWINCH, ...)`` which Python forbids outside the main
        thread.  The previous ``_start_inline()`` design ran the TUI in a
        daemon thread — raising ``ValueError`` on every real run.  This method
        inverts the model: TUI owns the main thread; harness runs in a daemon
        thread.  When *fn* completes (or raises), the TUI is signalled to exit.

        After the TUI exits, the in-memory event log is printed to stderr so the
        user sees what happened (the inline TUI clears its render area on exit).
        The same lines are mirrored to ``LOG_PATH`` for durable inspection.
        """
        import asyncio  # noqa: PLC0415

        # Open the durable log file (best-effort — falls back to memory only).
        try:
            self._log_file = open(self.LOG_PATH, "w", encoding="utf-8")  # noqa: SIM115
        except Exception:  # noqa: BLE001
            self._log_file = None

        self._app = _HorusTUIApp()
        exc_holder: list[BaseException | None] = [None]

        def _worker() -> None:
            self._app.wait_ready()  # wait for on_mount to fire
            try:
                fn()
            except BaseException as exc:  # noqa: BLE001
                exc_holder[0] = exc
                self._emit(f"[harness] WORKER EXCEPTION: {type(exc).__name__}: {exc}")
            finally:
                if self._app is not None and self._app.is_running:
                    try:
                        self._app.call_from_thread(self._app.exit)
                    except Exception:  # noqa: BLE001
                        pass

        t = threading.Thread(target=_worker, daemon=True, name="horus-harness")
        t.start()

        try:
            asyncio.run(self._app.run_async(inline=True))
        finally:
            t.join(timeout=60.0)
            self._app = None
            if self._log_file is not None:
                try:
                    self._log_file.close()
                except Exception:  # noqa: BLE001
                    pass
                self._log_file = None

        # TUI inline area is cleared on exit. Replay the event log to stderr
        # so the user sees a permanent record in the terminal scrollback.
        if self._event_log:
            print("", file=sys.stderr, flush=True)
            print(
                f"[harness] event log (full record at {self.LOG_PATH}):",
                file=sys.stderr,
                flush=True,
            )
            for line in self._event_log:
                print(line, file=sys.stderr, flush=True)

        if self._failures:
            print("", file=sys.stderr, flush=True)
            print("[harness] FAILURES:", file=sys.stderr, flush=True)
            for model_id, invoice_name, error in self._failures:
                print(f"  - {model_id} / {invoice_name}: {error}", file=sys.stderr, flush=True)

        if exc_holder[0] is not None:
            raise exc_holder[0]


# ---------------------------------------------------------------------------
# _HorusTUIApp — the actual textual.App
# ---------------------------------------------------------------------------


class _HorusTUIApp:
    """Lightweight textual App wrapper with the 3-section HORUS layout.

    Runs in a background thread so the harness can call ``call_from_thread``
    to push widget updates without blocking inference.
    """

    def __init__(self) -> None:
        self._ready: threading.Event = threading.Event()
        self._app: Any = _TextualHorusApp(ready=self._ready)
        self._thread: threading.Thread | None = None
        self.is_running: bool = False

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Block until HorusApp.on_mount has fired — app is mounted and safe to call."""
        return self._ready.wait(timeout=timeout)

    async def run_async(self, *, inline: bool = False) -> None:
        """Run the textual app on the calling thread until exit() is called."""
        self.is_running = True
        try:
            await self._app.run_async(inline=inline)
        finally:
            self.is_running = False

    def exit(self, *args: Any) -> None:
        if self._app is not None:
            self._app.exit()

    def _start_inline(self) -> None:
        """Deprecated — superseded by HorusDashboardApp.run_with_harness()."""

    def _stop_inline(self) -> None:
        """Deprecated — superseded by HorusDashboardApp.run_with_harness()."""
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

    def __init__(self, ready: threading.Event | None = None) -> None:
        self._built_app: Any = None  # HorusApp(App) instance; typed as Any (defined inside _build)
        self._ready = ready
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
        EAGLE_ORANGE = eagle_orange  # noqa: N806
        HIEROGLYPH_CYAN = hieroglyph_cyan  # noqa: N806
        _ready = self._ready  # closure for on_mount

        def _model_dots(current: int, total: int) -> str:
            """● ● ○ ○ ○  N/M — filled-cyan done, bold-orange current, dim empty."""
            parts = []
            for i in range(1, total + 1):
                if i < current:
                    parts.append(f"[{HIEROGLYPH_CYAN}]●[/]")
                elif i == current:
                    parts.append(f"[bold {EAGLE_ORANGE}]●[/]")
                else:
                    parts.append("[dim]○[/]")
            return " ".join(parts) + f"  [dim]{current}/{total}[/]"

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
            #log-summary {{
                color: $text-muted;
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
            #sweep-stats {{
                color: $text-muted;
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
                ("d", "toggle_dark", "Dark"),
            ]

            _n_ok: int = 0
            _n_failed: int = 0
            _inflight: int = 0
            _parent_run_id: str = ""
            _total_tuples: int = 0

            def compose(self) -> ComposeResult:
                yield Static(
                    f"[bold {EAGLE_ORANGE}]🦅 HORUS cohort sweep[/] — starting…",
                    id="title-bar",
                )
                yield Static(
                    "[dim]▼ Completed  — —  starting…[/]",
                    id="log-summary",
                )
                yield RichLog(id="log-section", markup=True, auto_scroll=True)
                yield Rule(id="section-rule")
                yield Label("Current model: (loading…)", id="model-label")
                yield ProgressBar(total=100, show_eta=False, id="model-bar")
                yield Rule()
                yield Label("Sweep: (starting…)", id="sweep-label")
                yield ProgressBar(total=100, show_eta=False, id="sweep-bar")
                yield Static("", id="sweep-stats")
                yield Static(
                    "[dim][ Q quit  ·  ↑↓ scroll log  ·  SPACE pause  ·  D dark ][/]",
                    id="footer-hint",
                )

            def on_mount(self) -> None:
                if _ready is not None:
                    _ready.set()

            def action_toggle_pause(self) -> None:
                pass

            def _refresh_summary(self) -> None:
                self.query_one("#log-summary", Static).update(
                    f"[dim]▼ Completed  "
                    f"[green]{self._n_ok} ✓[/]  "
                    f"[{'red' if self._n_failed else 'dim'}]{self._n_failed} ⚠[/]"
                    f"  {'[bold ' + HIEROGLYPH_CYAN + ']' if self._inflight else '[dim]'}"
                    f"{self._inflight} in flight"
                    f"{'[/]' if self._inflight else '[/]'}[/]"
                )

            def _on_sweep_start(
                self, parent_run_id: str, total_models: int, total_invoices: int
            ) -> None:
                self._parent_run_id = (
                    parent_run_id[:8] if len(parent_run_id) >= 8 else parent_run_id
                )
                self._total_tuples = total_models * total_invoices
                short_id = self._parent_run_id
                self.query_one("#title-bar", Static).update(
                    f"[bold {EAGLE_ORANGE}]🦅 HORUS cohort sweep[/]  "
                    f"[dim]parent={short_id}  "
                    f"{total_models}×{total_invoices}={self._total_tuples} tuples[/]"
                )
                self.query_one("#sweep-bar", ProgressBar).update(total=float(self._total_tuples))
                self.query_one("#sweep-label", Label).update(
                    f"[{EAGLE_ORANGE}]Sweep:[/] 0/{self._total_tuples}  (0%)"
                )
                self.query_one("#sweep-stats", Static).update(f"[dim]parent {short_id}[/]")
                self._refresh_summary()

            def _on_model_load_start(self, model_idx: int, model_id: str) -> None:
                log = self.query_one("#log-section", RichLog)
                log.write(
                    f"[{HIEROGLYPH_CYAN}]⏵[/] [{HIEROGLYPH_CYAN}]{_short_model(model_id)}[/]"
                    f"  [{EAGLE_ORANGE}]loading …[/]"
                )
                self.query_one("#model-label", Label).update(
                    f"[{HIEROGLYPH_CYAN}]Model {model_idx}:[/]"
                    f" {_short_model(model_id)} — [{EAGLE_ORANGE}]loading …[/]"
                )
                self.query_one("#model-bar", ProgressBar).update(progress=0.0)

            def _on_model_loaded(self, model_idx: int, model_id: str, weights_gb: float) -> None:
                gb_str = f"  [{EAGLE_ORANGE}]{weights_gb:.1f} GB[/]" if weights_gb > 0 else ""
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
                self._inflight = max(0, self._inflight) + 1
                self._refresh_summary()
                short_inv = invoice_name[:30]
                dots = _model_dots(model_idx, total_models)
                self.query_one("#model-label", Label).update(
                    f"[{HIEROGLYPH_CYAN}]{_short_model(model_id):<28}[/]  "
                    f"{dots}  [{EAGLE_ORANGE}]⏵[/] {short_inv}"
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
                self._n_ok += 1
                self._inflight = max(0, self._inflight - 1)
                self._refresh_summary()
                log = self.query_one("#log-section", RichLog)
                if micro_f1 >= 0.5:
                    f1_color = "green"
                elif micro_f1 >= 0.3:
                    f1_color = "yellow"
                else:
                    f1_color = "red"
                log.write(
                    f"[green]✓[/] [{HIEROGLYPH_CYAN}]{_short_model(model_id):<28}[/]  "
                    f"{invoice_name:<38}  "
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
                self.query_one("#sweep-stats", Static).update(
                    f"[dim]parent {self._parent_run_id}[/]"
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
                self._n_failed += 1
                self._inflight = max(0, self._inflight - 1)
                self._refresh_summary()
                log = self.query_one("#log-section", RichLog)
                log.write(
                    f"[bold red]⚠[/] [{HIEROGLYPH_CYAN}]{_short_model(model_id):<28}[/]  "
                    f"{invoice_name:<38}  [bold red]FAILED[/]: {error[:55]}"
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
                    f"  done  mean_f1=[{'green' if mean_f1 >= 0.5 else 'yellow'}]"
                    f"{mean_f1:.3f}[/]  ({m}m {s:02d}s)"
                )

            def _on_sweep_complete(self) -> None:
                log = self.query_one("#log-section", RichLog)
                log.write(f"[bold {EAGLE_ORANGE}]🦅 HORUS sweep complete.[/]")
                self.query_one("#sweep-label", Label).update(
                    f"[bold {EAGLE_ORANGE}]Sweep complete ✔[/]"
                )
                self._refresh_summary()

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
