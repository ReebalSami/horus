#!/usr/bin/env python3
"""frozen_testset_bundle.py — build the encrypted examiner bundle of the held-out set (ADR-075).

Author-side counterpart of `scripts/get_frozen_testset.py`. Stages the private
`data/self-collected/` tree into a sanitized layout, packs it as `tar.xz`, seals
it with AES-256-GCM under an scrypt-derived password key, and writes ONE blob
that can be attached to a GitHub Release on the (public) repository.

What the staging pass does — and why (ADR-075 §Decision pt 1):

  * Source PDFs are renamed to their sanitized ids
    (`german/email/belege-de-email-001.pdf`, …). The original filenames carry
    real third-party company names (ADR-040); the ids are what the thesis, the
    datasheet, and the answer key cite, so the rename makes cross-referencing
    easier while keeping those names off the examiner's screen.
  * `index.json` is rewritten to the new paths with `source_filename` scrubbed —
    ids, hashes, page counts, and `verified` flags are preserved byte-for-byte,
    so a later `make heldout-index` on the restored tree keeps ids stable (the
    id map is path-keyed; the rewritten index IS the map).
  * `_pagecache/` is excluded (regenerable rasters), `*.eml` is excluded
    everywhere (full mail headers = sender identities), OS litter is dropped.
  * Every other tree (`gt/`, `_promoted/`, `_judge/`, `_azure/`, `_transcripts/`,
    `_eval/`, `_review/`, `_audit/`, `_drafts/`, `_text/`) travels verbatim —
    that is the ADR-060/062 adjudication provenance.
  * Before packing, every staged PDF is verified against the COMMITTED datasheet
    freeze table: the script refuses to build a bundle that contradicts
    `docs/architecture/belege-heldout-datasheet.md`.

Usage:
    make frozen-testset-bundle
    # or directly:
    uv run python scripts/frozen_testset_bundle.py [--out dist/horus-frozen-testset-v1.enc]

Password: interactive double prompt, or the HORUS_BUNDLE_PASSWORD environment
variable for non-interactive builds. Hand it to the examiner out-of-band only.
The blob itself is safe to publish (AES-256-GCM); it must still never be
committed — `dist/` is git-ignored.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Direct-path invocation (`uv run python scripts/frozen_testset_bundle.py`) puts
# scripts/ on sys.path but not the repo root; insert it so the `scripts` package
# resolves (same prologue as scripts/compute_probe_verdict.py).
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.frozen_testset_common import (  # noqa: E402 — needs the prologue above
    BUNDLE_FILENAME,
    DATASHEET_RELPATH,
    RELEASE_TAG,
    FrozenTestsetError,
    encrypt_bytes,
    parse_freeze_table,
    sha256_file,
    verify_corpus_tree,
)

DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "data" / "self-collected"
DEFAULT_OUT = PROJECT_ROOT / "dist" / BUNDLE_FILENAME

#: Top-level entries of the corpus root that never enter the bundle.
_EXCLUDED_TOP_LEVEL = {"_pagecache"}
#: File names / suffixes dropped wherever they appear.
_EXCLUDED_SUFFIXES = {".eml"}
_EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
#: The invoice source trees — only INDEXED PDFs leave these, renamed to their ids.
_SOURCE_TREES = {"german", "english"}

_MIN_PASSWORD_LEN = 12


def _read_password() -> str:
    """Password from HORUS_BUNDLE_PASSWORD, else a confirmed interactive prompt."""
    env = os.environ.get("HORUS_BUNDLE_PASSWORD", "")
    if env:
        if len(env) < _MIN_PASSWORD_LEN:
            raise FrozenTestsetError(
                f"HORUS_BUNDLE_PASSWORD is shorter than {_MIN_PASSWORD_LEN} characters — "
                "the blob will be public; use a strong passphrase."
            )
        return env
    first = getpass.getpass("Bundle password (will be handed to the examiner out-of-band): ")
    if len(first) < _MIN_PASSWORD_LEN:
        raise FrozenTestsetError(
            f"Password shorter than {_MIN_PASSWORD_LEN} characters — the blob will be "
            "public; use a strong passphrase."
        )
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise FrozenTestsetError("Passwords do not match.")
    return first


def _stage_tree(corpus_root: Path, staging: Path) -> int:
    """Copy the sanitized bundle layout into `staging`; return the invoice count."""
    index_path = corpus_root / "index.json"
    if not index_path.is_file():
        raise FrozenTestsetError(f"No index.json at {index_path}. Run 'make heldout-index' first.")
    index: dict[str, Any] = json.loads(index_path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = list(index.get("items", []))
    if not items:
        raise FrozenTestsetError("index.json contains no invoices — nothing to bundle.")

    print(f"Staging {len(items)} invoices (renamed to sanitized ids)...", flush=True)
    staged_sources: set[Path] = set()
    for entry in items:
        invoice_id = str(entry["id"])
        src = corpus_root / str(entry["pdf"])
        if not src.is_file():
            raise FrozenTestsetError(f"{invoice_id}: source PDF missing at {src}.")
        new_rel = f"{entry['language']}/{entry['channel']}/{invoice_id}.pdf"
        dst = staging / new_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        staged_sources.add(src.resolve())
        entry["pdf"] = new_rel
        entry["source_filename"] = f"{invoice_id}.pdf"
        print(f"  {invoice_id}  <- staged", flush=True)

    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Copying provenance + answer-key trees verbatim...", flush=True)
    for top in sorted(corpus_root.iterdir()):
        if top.name in _EXCLUDED_TOP_LEVEL or top.name == "index.json":
            continue
        if top.name in _SOURCE_TREES:
            # Only indexed PDFs leave the source trees; anything else would carry
            # an original (name-bearing) filename into the bundle.
            for stray in top.rglob("*"):
                if not stray.is_file():
                    continue
                if stray.suffix in _EXCLUDED_SUFFIXES or stray.name in _EXCLUDED_NAMES:
                    continue
                if stray.resolve() not in staged_sources:
                    print(f"  WARN: skipping un-indexed file {stray.relative_to(corpus_root)}")
            continue
        if top.is_file():
            if top.suffix in _EXCLUDED_SUFFIXES or top.name in _EXCLUDED_NAMES:
                continue
            shutil.copy2(top, staging / top.name)
            continue
        n_files = 0
        for src_file in top.rglob("*"):
            if not src_file.is_file():
                continue
            if src_file.suffix in _EXCLUDED_SUFFIXES or src_file.name in _EXCLUDED_NAMES:
                continue
            rel = src_file.relative_to(corpus_root)
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
            n_files += 1
        print(f"  {top.name}/  ({n_files} files)", flush=True)
    return len(items)


def _verify_staging(staging: Path) -> None:
    """Refuse to pack a bundle that contradicts the committed datasheet."""
    datasheet = PROJECT_ROOT / DATASHEET_RELPATH
    if not datasheet.is_file():
        raise FrozenTestsetError(f"Committed datasheet not found at {datasheet}.")
    freeze = parse_freeze_table(datasheet.read_text(encoding="utf-8"))
    print(f"Verifying staged tree against the freeze table ({len(freeze)} rows)...", flush=True)
    ok, problems = verify_corpus_tree(staging, freeze)
    for line in problems:
        print(f"  {line}", flush=True)
    if problems:
        raise FrozenTestsetError(
            f"Staged tree contradicts the datasheet ({len(problems)} problem(s)). "
            "Regenerate the datasheet ('make heldout-datasheet') or fix the corpus first."
        )
    print(f"  all {len(ok)} invoices match the frozen datasheet.", flush=True)


def build_bundle(corpus_root: Path, out_path: Path, password: str) -> Path:
    """Stage, verify, pack, and encrypt; returns the written blob path."""
    with tempfile.TemporaryDirectory(prefix="horus-frozen-testset-") as tmp:
        staging = Path(tmp) / "staging"
        staging.mkdir()
        n_items = _stage_tree(corpus_root, staging)
        _verify_staging(staging)

        tar_path = Path(tmp) / "bundle.tar.xz"
        print("Packing tar.xz (this can take a minute on the JSON trees)...", flush=True)
        with tarfile.open(tar_path, "w:xz") as tar:
            for member in sorted(staging.rglob("*")):
                # rglob enumerates every path itself; without recursive=False each
                # directory add would re-pack its whole subtree (duplicate members).
                tar.add(member, arcname=str(member.relative_to(staging)), recursive=False)
        raw_size = tar_path.stat().st_size
        print(f"  packed: {raw_size / 1e6:.1f} MB", flush=True)

        print("Encrypting (AES-256-GCM, scrypt KDF)...", flush=True)
        blob = encrypt_bytes(tar_path.read_bytes(), password)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    digest = sha256_file(out_path)
    print(
        f"\nBundle written: {out_path}  ({out_path.stat().st_size / 1e6:.1f} MB, "
        f"{n_items} invoices)",
        flush=True,
    )
    print(f"Blob sha256:    {digest}", flush=True)
    print(
        "\nNext steps:\n"
        f"  1. gh release create {RELEASE_TAG} --title 'Frozen held-out test set (encrypted)' "
        "--notes 'AES-256-GCM sealed private test set; see README + ADR-075.'\n"
        f"  2. gh release upload {RELEASE_TAG} {out_path}\n"
        "  3. Hand the password to the examiner out-of-band (in person / phone) — never in\n"
        "     the same channel as the link. Quote the blob sha256 in the covering email.",
        flush=True,
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the encrypted frozen test-set bundle (ADR-075).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        password = _read_password()
        build_bundle(args.corpus_root, args.out, password)
    except FrozenTestsetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
