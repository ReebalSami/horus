#!/usr/bin/env python3
"""get_frozen_testset.py — download, decrypt, restore + verify the frozen test-set (ADR-075).

Examiner-side counterpart of `scripts/frozen_testset_bundle.py`. One command
restores the private held-out Belege corpus that the thesis' final numbers are
graded on, and PROVES it is byte-identical to the frozen set:

    make install
    make get-frozen-testset      # prompts for the password handed over separately

What it does, in order:

  1. Downloads the encrypted blob from the GitHub Release of this repository
     (public URL, no account needed) — or reads a local file via `--file`.
  2. Asks for the password and decrypts (AES-256-GCM: a wrong password or a
     corrupted download fails loudly instead of producing garbage).
  3. Extracts the corpus to `data/self-collected/` (refuses to overwrite an
     existing non-empty tree unless `--force` is given).
  4. Verifies every restored invoice PDF's sha256 + page count against the
     COMMITTED datasheet (`docs/architecture/belege-heldout-datasheet.md`) —
     the same freeze table reproduced in the thesis appendix — and prints a
     per-invoice verdict. Exits non-zero on any mismatch.

After a successful restore, the held-out targets run locally, e.g.:

    make audit-heldout-exclusions     # ADR-072 per-cell exclusion-cause audit
    make heldout-datasheet            # regenerate the datasheet from the restored tree

Privacy note (ADR-040/075): the restored tree contains real invoices and is
git-ignored in full; nothing you run against it can commit it. Please treat the
corpus as confidential examination material and delete it after grading.
"""

from __future__ import annotations

import argparse
import getpass
import io
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Direct-path invocation (`uv run python scripts/get_frozen_testset.py`) puts
# scripts/ on sys.path but not the repo root; insert it so the `scripts` package
# resolves (same prologue as scripts/compute_probe_verdict.py).
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.frozen_testset_common import (  # noqa: E402 — needs the prologue above
    BUNDLE_FILENAME,
    DATASHEET_RELPATH,
    RELEASE_TAG,
    FrozenTestsetError,
    decrypt_bytes,
    parse_freeze_table,
    verify_corpus_tree,
)

DEFAULT_DEST = PROJECT_ROOT / "data" / "self-collected"
DEFAULT_URL = (
    f"https://github.com/ReebalSami/horus/releases/download/{RELEASE_TAG}/{BUNDLE_FILENAME}"
)

_PROGRESS_EVERY = 8 * 1024 * 1024  # print a progress line every 8 MB


def _download(url: str) -> bytes:
    """Stream the blob with visible progress (per `long-running-foreground`)."""
    print(f"Downloading {url} ...", flush=True)
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310 — pinned https URL
            total_raw = response.headers.get("Content-Length")
            total = int(total_raw) if total_raw else None
            chunks: list[bytes] = []
            received = 0
            next_mark = _PROGRESS_EVERY
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)
                if received >= next_mark:
                    if total:
                        print(f"  {received / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)
                    else:
                        print(f"  {received / 1e6:.0f} MB", flush=True)
                    next_mark += _PROGRESS_EVERY
    except urllib.error.URLError as exc:
        raise FrozenTestsetError(
            f"Download failed ({exc}). Check the network, or pass a locally received "
            "blob via --file."
        ) from exc
    print(f"  downloaded {received / 1e6:.1f} MB.", flush=True)
    return b"".join(chunks)


def _read_password() -> str:
    """Password from HORUS_BUNDLE_PASSWORD, else one interactive prompt."""
    env = os.environ.get("HORUS_BUNDLE_PASSWORD", "")
    if env:
        return env
    return getpass.getpass("Password for the frozen test-set (handed over separately): ")


def _extract(plaintext_tar: bytes, dest: Path, *, force: bool) -> None:
    """Safely extract the decrypted tar.xz into `dest`."""
    if dest.exists() and any(dest.iterdir()) and not force:
        raise FrozenTestsetError(
            f"{dest} already exists and is not empty. Move it aside, or re-run with "
            "--force to extract over it."
        )
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Extracting to {dest} ...", flush=True)
    with tarfile.open(fileobj=io.BytesIO(plaintext_tar), mode="r:xz") as tar:
        # `filter="data"` = stdlib-sanctioned safe extraction: rejects absolute
        # paths, parent-directory traversal, and special files.
        tar.extractall(dest, filter="data")
    print("  extracted.", flush=True)


def _verify(dest: Path) -> int:
    """Verify the restored tree against the committed datasheet; return exit code."""
    datasheet = PROJECT_ROOT / DATASHEET_RELPATH
    if not datasheet.is_file():
        raise FrozenTestsetError(
            f"Committed datasheet not found at {datasheet} — run this from a full "
            "repository checkout."
        )
    freeze = parse_freeze_table(datasheet.read_text(encoding="utf-8"))
    print(
        f"Verifying the restored corpus against the frozen datasheet ({len(freeze)} invoices)...",
        flush=True,
    )
    ok, problems = verify_corpus_tree(dest, freeze)
    for line in ok:
        print(f"  {line}", flush=True)
    for line in problems:
        print(f"  {line}", flush=True)
    if problems:
        print(
            f"\nVERIFICATION FAILED: {len(problems)} problem(s), {len(ok)} OK. "
            "The restored corpus is NOT the frozen set.",
            flush=True,
        )
        return 1
    print(
        f"\nVERIFIED: all {len(ok)} invoices are byte-identical to the frozen set the "
        "thesis evaluated (sha256 + page counts match the committed datasheet).",
        flush=True,
    )
    print(
        "\nNext steps:\n"
        "  make audit-heldout-exclusions   # ADR-072 exclusion-cause audit\n"
        "  make heldout-datasheet          # regenerate the datasheet from this tree\n"
        "  make app                        # browse invoices + answer key in the dashboard",
        flush=True,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download + decrypt + restore + verify the frozen test-set (ADR-075).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="release-asset URL of the blob")
    parser.add_argument("--file", type=Path, default=None, help="local blob instead of a download")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--force", action="store_true", help="extract over a non-empty --dest")
    args = parser.parse_args()

    try:
        blob = args.file.read_bytes() if args.file else _download(args.url)
        password = _read_password()
        print("Decrypting (scrypt KDF takes a few seconds by design)...", flush=True)
        plaintext = decrypt_bytes(blob, password)
        del blob
        with tempfile.TemporaryDirectory(prefix="horus-frozen-restore-") as tmp:
            # Extract to a scratch dir first so a failed verification never leaves a
            # half-restored tree at the destination.
            scratch = Path(tmp) / "corpus"
            _extract(plaintext, scratch, force=True)
            del plaintext
            code = _verify(scratch)
            if code != 0:
                raise SystemExit(code)
            if args.dest.exists() and any(args.dest.iterdir()):
                if not args.force:
                    raise FrozenTestsetError(
                        f"{args.dest} already exists and is not empty. Move it aside, or "
                        "re-run with --force to replace its contents."
                    )
                shutil.rmtree(args.dest)
            args.dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(scratch), str(args.dest))
        print(f"\nRestored to {args.dest}.", flush=True)
    except FrozenTestsetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
