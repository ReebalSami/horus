"""Minimal `.env` loader for local credentials.

Cloud credentials (the ADR-060 vision judge's `ANTHROPIC_API_KEY`, and the Tier-B
second channel's Azure keys) deliberately do **not** travel through
:class:`horus.config.ExperimentConfig`: that model sets ``extra="forbid"`` and, more
importantly, everything reaching it is logged to MLflow as an experiment parameter. A
secret must never become a tracked run parameter.

So credentials are read from the process environment — but a developer keeping them in
the git-ignored `.env` (the documented workflow) had no way to get them there, because
nothing in this repo ever loaded that file. The judge CLI's own docstring promised
`.env` worked while the code only read `os.environ`, so a correctly-configured machine
still failed the pre-flight check.

Written against the stdlib rather than taking `python-dotenv`: the requirement is
"parse `KEY=VALUE` lines", `python-dotenv` is currently only a transitive dependency,
and `horus-decision-discipline` makes every new direct library an ADR. A dependency and
an architectural record are disproportionate to eight lines of parsing.

**The process environment always wins.** Values already present in ``os.environ`` are
never overwritten, so `HORUS_X=... uv run ...` and CI secrets keep priority over a
stale local file — the least surprising precedence, and the one that keeps CI immune to
a developer's `.env`.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


def parse_env_file(text: str) -> dict[str, str]:
    """Parse `.env` text into a mapping, tolerating the shapes editors produce.

    Handles ``export KEY=value`` prefixes, ``#`` comments, blank lines, surrounding
    single/double quotes, and a missing trailing newline. Lines without ``=`` are
    skipped rather than raising: a malformed line must not make credentials
    unreadable, and a raise here would break the caller's unrelated work.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_env_file(path: Path | None = None) -> list[str]:
    """Load `.env` into ``os.environ`` without overriding existing variables.

    Args:
        path: file to read; defaults to `.env` at the repository root.

    Returns:
        The names of the variables actually injected — never their values, so a caller
        may safely log the result to show *which* credentials were picked up. Empty
        when the file is absent (the normal CI case) or every key was already set.
    """
    env_path = path or DEFAULT_ENV_FILE
    if not env_path.is_file():
        return []
    injected: list[str] = []
    for key, value in parse_env_file(env_path.read_text(encoding="utf-8")).items():
        if key in os.environ:
            continue
        os.environ[key] = value
        injected.append(key)
    return injected
