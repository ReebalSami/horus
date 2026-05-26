---
title: "pyfiglet — Python port of FIGlet for ASCII art banners"
url: "https://github.com/pwaller/pyfiglet"
pypi: "https://pypi.org/project/pyfiglet/"
type: tool
tags: [ascii-art, banner, python, terminal]
archived: 2026-05-26
cited_in: [ADR-026]
---

## Summary

pyfiglet is a full port of FIGlet (Frank, Ian and Glenn's Letters) into pure Python. It renders text as ASCII-art using a variety of fonts.

Key features relevant to ADR-026:

- `pyfiglet.figlet_format(text, font="slant")` returns the ASCII-art string.
- Ships 150+ FIGlet fonts; `"slant"` selected for the HORUS banner (angled look fits the Egyptian-eagle motif of the brand per ADR-003).
- Pure-Python, ARM-compatible, ~500 KB; no C extension deps.
- Used with `rich.Text` for truecolor coloring: `Text(art, style="bold #E8833A")`.

## Usage in HORUS

`src/horus/cli/banner.py::print_banner()` renders `figlet_format("HORUS", font="slant")` in eagle-orange (`#E8833A`) with a subtitle line in hieroglyph-cyan (`#3AA8C8`). Called once at sweep start by `scripts/cohort_smoke.py`.

## Version used

Declared in `pyproject.toml`. See `uv.lock` for the pinned version at integration time.
