---
title: "Textual — TUI framework for Python"
url: "https://textual.textualize.io/"
repo: "https://github.com/Textualize/textual"
pypi: "https://pypi.org/project/textual/"
type: tool
tags: [tui, terminal, python, rich, inline-app]
archived: 2026-05-26
cited_in: [ADR-026]
---

## Summary

Textual is a rapid application development (RAD) framework for Python, built on top of `rich`. It enables building sophisticated terminal user interfaces (TUIs) with a simple Python API, running in the terminal or a web browser.

Key features relevant to ADR-026:

- **Inline mode** (`App.run(inline=True)`): renders the app below the terminal prompt without full-screen takeover. macOS/Linux only (not Windows — Textualize/textual#4409).
- **`App.suspend()`** context manager: temporarily pauses the app, returning the terminal to normal mode. Used to resolve the textual+tqdm incompatibility (Textualize/textual#2878).
- **`RichLog` widget**: scrollable streaming log with full rich markup. Auto-scrolls on append; user can scroll up manually with keyboard or mouse during a live run.
- **`ProgressBar` widget**: reactive, CSS-styleable, supports gradient via `Gradient` class.
- **`Pilot` class**: official headless testing driver for textual apps.

## Known issues

- **textual + tqdm incompatibility** (Textualize/textual#2878, open as of 2026-05-26): textual replaces `sys.stdout`/`sys.stderr` while running; `tqdm` crashes with `AttributeError: 'NoneType' object has no attribute 'write'`. Workaround: `App.suspend()` before any tqdm-driven code.
- **`RichLog` scroll behavior** (Textualize/textual#6311): auto-scroll on append jumps to bottom; user manual scroll is preserved by `Log` widget but not `RichLog`. Monitor for fix; workaround if needed: swap `RichLog` → `Log` + manual render formatting.
- **Inline mode not available on Windows** (Textualize/textual#4409).

## Version used

Declared in `pyproject.toml`. See `uv.lock` for the pinned version at integration time.
