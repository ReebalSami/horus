"""Tests for horus.cli dashboard adapters (ADR-026).

Strategy:
  - PlainDisplayAdapter: capsys-based; all 8 callbacks produce expected output.
  - SilentDisplayAdapter: capsys captures empty.
  - get_display_adapter: monkeypatch sys.stdout.isatty() + env vars.
  - HorusDashboardApp: smoke-instantiate + context-manager round-trip; no
    full textual app started (avoids threading/TTY overhead in CI).

No tests start the real textual inline app in CI — that requires a TTY and is
verified manually via `make cohort-smoke MODEL=ibm-granite/granite-docling-258M-mlx`.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from horus.cli.dashboard import (
    DisplayAdapter,
    HorusDashboardApp,
    PlainDisplayAdapter,
    SilentDisplayAdapter,
    get_display_adapter,
)


class TestSilentDisplayAdapter:
    def test_all_callbacks_no_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        with SilentDisplayAdapter() as d:
            d.on_sweep_start("abc123", 7, 26)
            d.on_model_load_start(1, "ibm-granite/granite-docling-258M-mlx")
            d.on_model_loaded(1, "ibm-granite/granite-docling-258M-mlx", 4.2)
            d.on_invoice_start(
                "ibm-granite/granite-docling-258M-mlx", 1, 7, 1, 26, "EN16931_Einfach"
            )
            d.on_invoice_complete(
                "ibm-granite/granite-docling-258M-mlx", 1, 26, "EN16931_Einfach", 0.412, 2, 8.3
            )
            d.on_invoice_failed(
                "ibm-granite/granite-docling-258M-mlx", 2, "EN16931_Stadtwerke", "TimeoutError"
            )
            d.on_model_complete(1, "ibm-granite/granite-docling-258M-mlx", 0.62, 120.0)
            d.on_sweep_complete()
        out, err = capsys.readouterr()
        assert out == ""
        assert err == ""

    def test_suspend_returns_nullcontext(self) -> None:
        d = SilentDisplayAdapter()
        ctx = d.suspend()
        with ctx:
            pass

    def test_implements_protocol(self) -> None:
        d = SilentDisplayAdapter()
        assert isinstance(d, DisplayAdapter)


class TestPlainDisplayAdapter:
    def _run_all(self, d: PlainDisplayAdapter) -> None:
        with d:
            d.on_sweep_start("abc12345", 2, 3)
            d.on_model_load_start(1, "ibm-granite/granite-docling-258M-mlx")
            d.on_model_loaded(1, "ibm-granite/granite-docling-258M-mlx", 1.5)
            d.on_invoice_start(
                "ibm-granite/granite-docling-258M-mlx", 1, 2, 1, 3, "EN16931_Einfach"
            )
            d.on_invoice_complete(
                "ibm-granite/granite-docling-258M-mlx", 1, 3, "EN16931_Einfach", 0.5, 2, 5.0
            )
            d.on_invoice_failed(
                "ibm-granite/granite-docling-258M-mlx", 2, "EN16931_Stadtwerke", "OOMError"
            )
            d.on_model_complete(1, "ibm-granite/granite-docling-258M-mlx", 0.5, 30.0)
            d.on_sweep_complete()

    def test_sweep_start_emits_parent_run_id(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        assert "abc12345" in out
        assert "models=2" in out
        assert "invoices=3" in out

    def test_model_load_start_emits_model_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        assert "granite-docling-258M-mlx" in out
        assert "loading" in out

    def test_model_loaded_emits_loaded_marker(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        assert "loaded" in out.lower() or "✓" in out

    def test_invoice_complete_emits_f1_and_pages(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        assert "EN16931_Einfach" in out
        assert "micro_f1=0.500" in out
        assert "pages=2" in out

    def test_invoice_failed_emits_failed_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        assert "FAILED" in out
        assert "OOMError" in out

    def test_sweep_complete_emits_elapsed(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        assert "sweep complete" in out.lower()

    def test_prefix_all_lines_with_harness(self, capsys: pytest.CaptureFixture[str]) -> None:
        d = PlainDisplayAdapter()
        self._run_all(d)
        out = capsys.readouterr().out
        harness_lines = [ln for ln in out.splitlines() if ln.strip()]
        assert all("[harness]" in ln for ln in harness_lines), (
            f"Expected all output lines to start with [harness]; got:\n{out}"
        )

    def test_suspend_returns_nullcontext(self) -> None:
        d = PlainDisplayAdapter()
        ctx = d.suspend()
        assert ctx is not None
        with ctx:
            pass

    def test_implements_protocol(self) -> None:
        d = PlainDisplayAdapter()
        assert isinstance(d, DisplayAdapter)


class TestGetDisplayAdapter:
    def test_returns_plain_when_force_plain(self) -> None:
        result = get_display_adapter(force_plain=True)
        assert isinstance(result, PlainDisplayAdapter)

    def test_returns_plain_when_not_tty(self) -> None:
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            result = get_display_adapter()
        assert isinstance(result, PlainDisplayAdapter)

    def test_returns_silent_when_env_silent(self) -> None:
        with patch.dict(os.environ, {"HORUS_DASHBOARD": "silent"}):
            result = get_display_adapter()
        assert isinstance(result, SilentDisplayAdapter)

    def test_returns_plain_when_env_plain(self) -> None:
        with patch.dict(os.environ, {"HORUS_DASHBOARD": "plain"}):
            result = get_display_adapter()
        assert isinstance(result, PlainDisplayAdapter)

    def test_env_silent_takes_precedence_over_force_plain(self) -> None:
        with patch.dict(os.environ, {"HORUS_DASHBOARD": "silent"}):
            result = get_display_adapter(force_plain=True)
        assert isinstance(result, SilentDisplayAdapter)

    def test_returns_dashboard_when_is_tty(self) -> None:
        with patch.dict(os.environ, {"HORUS_DASHBOARD": ""}):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                result = get_display_adapter()
        assert isinstance(result, HorusDashboardApp)

    def test_plain_takes_precedence_over_tty_when_env_set(self) -> None:
        with patch.dict(os.environ, {"HORUS_DASHBOARD": "plain"}):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                result = get_display_adapter()
        assert isinstance(result, PlainDisplayAdapter)


class TestHorusDashboardApp:
    def test_instantiates_without_ttyl(self) -> None:
        d = HorusDashboardApp()
        assert d is not None

    def test_suspend_returns_nullcontext_before_enter(self) -> None:
        d = HorusDashboardApp()
        ctx = d.suspend()
        with ctx:
            pass

    def test_all_callbacks_callable_before_enter(self) -> None:
        d = HorusDashboardApp()
        d.on_sweep_start("abc", 2, 3)
        d.on_model_load_start(1, "m1")
        d.on_model_loaded(1, "m1", 1.0)
        d.on_invoice_start("m1", 1, 2, 1, 3, "inv1")
        d.on_invoice_complete("m1", 1, 3, "inv1", 0.5, 2, 5.0)
        d.on_invoice_failed("m1", 2, "inv2", "err")
        d.on_model_complete(1, "m1", 0.5, 10.0)
        d.on_sweep_complete()

    def test_implements_protocol(self) -> None:
        d = HorusDashboardApp()
        assert isinstance(d, DisplayAdapter)
