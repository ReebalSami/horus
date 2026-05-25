"""Shared corpus-walk helpers (ADR-025 Phase A skeleton).

This module factors out the file-walking primitives every EDA chapter
needs: a deterministic recursive walk that filters out filesystem cruft
(`.gitkeep`, `.gitignore`, `.DS_Store`) and corpus-metadata files
(`MANIFEST.md`, `sha256.txt`, `README.md`, `LICENSE`) so that downstream
analysis sees only data content.

Per the forensic audit on 2026-05-25 (in the conversation that produced
ADR-025): without filtering dotfiles, the walk reported a fake "Other: 6"
extension class (5 `.gitkeep` files in symtrax empty subdirs + 1
`.gitignore` in XML-Rechnung) AND inflated duplicate-filename counts
from 4 (real fatturaPA mirrors) to 9. Centralizing the filter here
prevents per-chapter rediscovery of the same gotcha.

Refs: ADR-025 §"Decision + integration thoughts" §`src/horus/eda/`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

# Files Cascade or external tools deposit alongside data that are NOT data.
# Centralized here so every chapter walks the same set; per-chapter
# subclassing can extend (not narrow) this list.
DEFAULT_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "MANIFEST.md",
        "sha256.txt",
        "README.md",
        "README_ZH.md",
        "LICENSE",
        "LICENSE.txt",
        "CODEOWNERS",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        ".gitattributes",
    }
)


def walk(
    root: Path,
    *,
    extra_skip_names: Iterable[str] = (),
    skip_dotfiles: bool = True,
) -> pd.DataFrame:
    """Walk `root` recursively, filter out metadata + dotfiles, return DataFrame.

    Args:
        root: corpus directory to walk (must exist).
        extra_skip_names: per-dataset filenames to also skip (extends DEFAULT_SKIP_NAMES).
        skip_dotfiles: if True (default), files whose name starts with "."
            are skipped — `.gitkeep`, `.gitignore`, `.DS_Store`, etc.

    Returns:
        DataFrame with one row per file. Columns:
            - `path`: absolute Path
            - `relative_path`: Path relative to `root`
            - `flavor`: top-level subdirectory (e.g., "ZUGFeRDv2"); "(root)" if file is at root
            - `subdir`: second-level subdirectory or "(none)"
            - `nested`: deeper-level path joined by "/", "" if depth ≤ 3
            - `filename`: bare file name
            - `extension`: lowercased file extension (".pdf", ".xml", ".json", ...) or "(none)"
            - `size_bytes`: stat() size

    Raises:
        FileNotFoundError: if `root` does not exist.
        RuntimeError: if walk produces zero files (probable misconfiguration).
    """
    if not root.exists():
        raise FileNotFoundError(f"Corpus root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Corpus root is not a directory: {root}")

    skip_names = DEFAULT_SKIP_NAMES | frozenset(extra_skip_names)
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in skip_names:
            continue
        if skip_dotfiles and path.name.startswith("."):
            continue
        rel = path.relative_to(root)
        parts = rel.parts
        flavor = parts[0] if len(parts) >= 1 else "(root)"
        subdir = parts[1] if len(parts) >= 2 else "(none)"
        nested = "/".join(parts[2:-1]) if len(parts) > 3 else ""
        ext = path.suffix.lower() or "(none)"
        rows.append(
            {
                "path": path,
                "relative_path": rel,
                "flavor": flavor,
                "subdir": subdir,
                "nested": nested,
                "filename": path.name,
                "extension": ext,
                "size_bytes": path.stat().st_size,
            }
        )
    if not rows:
        raise RuntimeError(
            f"Corpus walk produced zero files under {root}. "
            "Verify the corpus is fully fetched + per-dataset MANIFEST.md exists."
        )
    return pd.DataFrame(rows)
