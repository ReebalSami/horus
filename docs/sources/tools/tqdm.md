---
title: "tqdm — Fast, Extensible Progress Bar for Python"
url: "https://tqdm.github.io/"
repo: "https://github.com/tqdm/tqdm"
pypi: "https://pypi.org/project/tqdm/"
type: tool
tags: [progress-bar, python, cli, huggingface]
archived: 2026-05-26
cited_in: [ADR-026]
---

## Summary

tqdm (from Arabic taqaddum, "progress") is a fast, extensible progress bar for Python and CLI. It wraps any iterable with a real-time progress bar.

Key features relevant to ADR-026:

- **Default stderr output**: `tqdm.std.tqdm` writes bars to `sys.stderr` (not stdout). Keeps progress bars separate from stdout data streams; `script.py > out.txt` doesn't capture the bar.
- **`tqdm.auto`**: auto-selects `tqdm.notebook.tqdm` in Jupyter environments and `tqdm.std.tqdm` in terminals. Recommended default for library code.
- **`disable=None`**: automatically disables bars in non-TTY environments; `disable=True` always silences (BANNED by `long-running-foreground` rule); `disable=False` always shows (default).
- **`tqdm.contrib.logging.logging_redirect_tqdm`**: redirects Python `logging` output through `tqdm.write()` to prevent bar corruption.
- **HuggingFace integration**: `huggingface_hub` + `transformers` use tqdm for model downloads and shard loading. Controlled via `HF_HUB_DISABLE_PROGRESS_BARS` env var (DO NOT SET — banned by `long-running-foreground` rule).
- **textual + tqdm conflict**: see `docs/sources/tools/textual.md` §"Known issues". Workaround: `App.suspend()` (ADR-026 §A3-suspend strategy).

## Version used

Declared in `pyproject.toml`. See `uv.lock` for the pinned version at integration time. Was already present as a transitive dep before ADR-026; this ADR promotes it to an explicit runtime dep.
