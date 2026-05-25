"""Tests for `horus.eda.corpus_walk` (ADR-025 Phase A skeleton).

Verifies the shared file-walking helpers behave deterministically and
filter out filesystem cruft (`.gitkeep`, `.gitignore`, `.DS_Store`) +
corpus-metadata files (`MANIFEST.md`, `sha256.txt`, `README.md`,
`LICENSE`) by default, per the forensic audit recorded in ADR-025
§"Context".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus.eda.corpus_walk import DEFAULT_SKIP_NAMES, walk


def _seed(root: Path) -> None:
    """Populate `root` with a representative mix of content + cruft files."""
    (root / "ZUGFeRDv2" / "correct").mkdir(parents=True)
    (root / "ZUGFeRDv2" / "correct" / "invoice-1.pdf").write_bytes(b"%PDF-1.4\n")
    (root / "ZUGFeRDv2" / "correct" / "invoice-1.cii.xml").write_text("<root/>")
    (root / "ZUGFeRDv2" / "correct" / ".gitkeep").write_text("")
    (root / "MANIFEST.md").write_text("# manifest")
    (root / "sha256.txt").write_text("deadbeef  invoice-1.pdf\n")
    (root / "LICENSE").write_text("Apache-2.0")
    (root / ".DS_Store").write_bytes(b"\x00\x00\x00")


def test_walk_returns_dataframe_with_expected_columns(tmp_path: Path) -> None:
    _seed(tmp_path)
    df = walk(tmp_path)
    expected = {
        "path",
        "relative_path",
        "flavor",
        "subdir",
        "nested",
        "filename",
        "extension",
        "size_bytes",
    }
    assert expected.issubset(df.columns)


def test_walk_skips_metadata_and_dotfiles_by_default(tmp_path: Path) -> None:
    _seed(tmp_path)
    df = walk(tmp_path)
    names = set(df["filename"])
    # Content survives.
    assert "invoice-1.pdf" in names
    assert "invoice-1.cii.xml" in names
    # Metadata + dotfiles filtered.
    assert ".gitkeep" not in names
    assert ".DS_Store" not in names
    assert "MANIFEST.md" not in names
    assert "sha256.txt" not in names
    assert "LICENSE" not in names


def test_walk_with_skip_dotfiles_false_includes_gitkeep(tmp_path: Path) -> None:
    _seed(tmp_path)
    df = walk(tmp_path, skip_dotfiles=False)
    assert ".gitkeep" in set(df["filename"])
    # MANIFEST.md still filtered (it's in DEFAULT_SKIP_NAMES, not dotfiles).
    assert "MANIFEST.md" not in set(df["filename"])


def test_walk_extra_skip_names_extends_defaults(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "ZUGFeRDv2" / "correct" / "extra.skip").write_text("skip me")
    df = walk(tmp_path, extra_skip_names={"extra.skip"})
    assert "extra.skip" not in set(df["filename"])
    # Defaults still applied.
    assert "MANIFEST.md" not in set(df["filename"])


def test_walk_flavor_subdir_nested_columns(tmp_path: Path) -> None:
    (tmp_path / "ZUGFeRDv2" / "correct" / "Mustang").mkdir(parents=True)
    (tmp_path / "ZUGFeRDv2" / "correct" / "Mustang" / "deep.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "top-level.pdf").write_bytes(b"%PDF-1.4\n")
    df = walk(tmp_path)
    deep = df[df["filename"] == "deep.pdf"].iloc[0]
    assert deep["flavor"] == "ZUGFeRDv2"
    assert deep["subdir"] == "correct"
    assert deep["nested"] == "Mustang"
    top = df[df["filename"] == "top-level.pdf"].iloc[0]
    assert top["flavor"] == "top-level.pdf"  # only-1-component path → flavor is filename
    assert top["subdir"] == "(none)"
    assert top["nested"] == ""


def test_walk_extension_lowercased(tmp_path: Path) -> None:
    (tmp_path / "MIXED.PDF").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "no-ext").write_text("no ext")
    df = walk(tmp_path)
    assert df.loc[df["filename"] == "MIXED.PDF", "extension"].iloc[0] == ".pdf"
    assert df.loc[df["filename"] == "no-ext", "extension"].iloc[0] == "(none)"


def test_walk_raises_on_missing_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        walk(tmp_path / "does-not-exist")


def test_walk_raises_on_root_being_a_file(tmp_path: Path) -> None:
    f = tmp_path / "i-am-a-file.txt"
    f.write_text("not a directory")
    with pytest.raises(NotADirectoryError):
        walk(f)


def test_walk_raises_on_empty_corpus(tmp_path: Path) -> None:
    (tmp_path / "MANIFEST.md").write_text("only metadata, no content")
    with pytest.raises(RuntimeError, match="zero files"):
        walk(tmp_path)


def test_default_skip_names_is_immutable() -> None:
    """Guard against accidental in-place mutation of the shared frozen set."""
    assert isinstance(DEFAULT_SKIP_NAMES, frozenset)
    assert "MANIFEST.md" in DEFAULT_SKIP_NAMES
    assert "sha256.txt" in DEFAULT_SKIP_NAMES
