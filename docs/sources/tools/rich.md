---
title: "Rich — Python library for rich text and beautiful terminal formatting"
url: "https://rich.readthedocs.io/en/stable/"
repo: "https://github.com/Textualize/rich"
pypi: "https://pypi.org/project/rich/"
type: tool
tags: [terminal, python, progress-bar, table, panel, markup]
archived: 2026-05-26
cited_in: [ADR-026]
---

## Summary

Rich is a Python library for rich text and beautiful formatting in the terminal. It provides colored output, tables, progress bars, panels, markdown, syntax highlighting, and more.

Key features relevant to ADR-026:

- **`rich.Console`**: core output object. `Console(stderr=True)` writes to stderr; `Console(file=io.StringIO())` captures output for tests; auto-degrades on non-TTY.
- **`rich.Table`**: terminal table with configurable box style. `box=None` disables borders (preserves column-order + alignment with no box-drawing characters — used for `_print_perf_table` migration).
- **`rich.Progress`**: multi-task progress bars. `redirect_stdout=False, redirect_stderr=False` is required to prevent stdout/stderr capture that breaks HF tqdm.
- **`rich.Text`**: styled text object; accepts hex color codes (`#E8833A`).
- **`rich.Panel`**: bordered content box for section headers.
- **Terminal detection**: `Console.is_terminal` auto-detects TTY; `force_terminal=True/False` overrides. Strips ANSI escapes on non-TTY automatically.

## Version used

Declared in `pyproject.toml`. See `uv.lock` for the pinned version at integration time. Was already present as a transitive dep before ADR-026; this ADR promotes it to an explicit runtime dep.
