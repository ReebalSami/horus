"""Hermetic tests for the corrected-findability ruler script (ADR-056/ADR-057).

Two behaviours are pinned here:

1. **The 8B stays in `CANDIDATES`.** ADR-057's pre-registered sibling test is adjudicated
   against this table; dropping the row would make the record unreproducible.
2. **`--detail` rejects an unknown reader.** The flag selects which reader's individual
   misses to print, and ADR-057 clause (b) is argued from that list — a silent typo that
   printed nothing would look identical to "this reader has no misses".

The corpus-dependent scoring path is deliberately not exercised here (it needs the
ZUGFeRD corpus + every bake-off transcript); `eval/reader-findability-audit.md` records
the measured table, and the script raises rather than reporting a subset (see the
`n_scored != len(records)` guard) if any transcript is missing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "findability_corrected.py"


def _candidates() -> list[str]:
    """Read `CANDIDATES` without importing the module (it imports heavy deps at module scope)."""
    src = SCRIPT.read_text(encoding="utf-8")
    block = src.split("CANDIDATES = [", 1)[1].split("]", 1)[0]
    return [
        line.split('"')[1]
        for line in block.splitlines()
        if line.strip().startswith('"') or line.strip().startswith("'")
    ]


def test_pre_registered_8b_sibling_is_wired() -> None:
    """ADR-057 Decision 2's sibling candidate must remain in the table."""
    assert "Qwen/Qwen3-VL-8B-Instruct" in _candidates()


def test_confirmed_reader_is_wired() -> None:
    """The confirmed reader (ADR-057) is the comparison baseline for clause (a)."""
    assert "Qwen/Qwen3-VL-4B-Instruct" in _candidates()


def test_detail_rejects_unknown_reader() -> None:
    """A mistyped --detail must fail loudly, not print an empty (and thus flattering) list."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--detail", "Qwen/Qwen3-VL-9B-Instruct"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "is not in CANDIDATES" in (proc.stderr + proc.stdout)


@pytest.mark.parametrize("flag", ["--detail"])
def test_detail_flag_is_documented(flag: str) -> None:
    """The flag ADR-057's evidence is reproduced with stays discoverable via --help."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0
    assert flag in proc.stdout
