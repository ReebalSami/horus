#!/usr/bin/env python3
"""frozen_testset_common.py — shared container format for the frozen test-set (ADR-075).

Single source of truth for everything BOTH distribution scripts need so the
author-side bundler (`scripts/frozen_testset_bundle.py`) and the examiner-side
restorer (`scripts/get_frozen_testset.py`) can never drift apart:

  * the encrypted container format (magic + version + salt + nonce + AES-256-GCM
    ciphertext, header bytes authenticated as AAD),
  * the scrypt password KDF parameters,
  * the parser for the committed datasheet's id ↔ sha256 freeze table
    (`docs/architecture/belege-heldout-datasheet.md`), and
  * the verification walk that proves a corpus tree on disk is byte-identical
    to the frozen set the thesis evaluated.

Container layout (bytes):

    offset  size  field
    0       8     magic  b"HORUSFTS"
    8       1     format version (currently 0x01)
    9       16    scrypt salt (random per bundle)
    25      12    AES-GCM nonce (random per bundle)
    37      -     ciphertext (AES-256-GCM; 16-byte tag appended by the primitive)

Design rationale, options considered, and the privacy posture amendment are in
`docs/decisions/ADR-075-frozen-testset-distribution.md`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"HORUSFTS"
FORMAT_VERSION = 1
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32  # AES-256

# Scrypt cost parameters (OWASP interactive guidance at decision time; ADR-075 §Options B).
_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1

#: Where the sanitized datasheet (the verification contract) lives, repo-relative.
DATASHEET_RELPATH = Path("docs/architecture/belege-heldout-datasheet.md")

#: Default blob filename; the `v1` tracks the corpus freeze, not the code.
BUNDLE_FILENAME = "horus-frozen-testset-v1.enc"

#: Release tag the examiner-side default URL points at (ADR-075 §Decision pt 5).
RELEASE_TAG = "frozen-testset-v1"

_FREEZE_ROW = re.compile(
    r"^\|\s*`(?P<id>belege-[a-z]{2}-[a-z]+-\d{3})`\s*\|\s*(?P<pages>\d+|\?)\s*\|"
    r"\s*`(?P<sha>[0-9a-f]{64})`\s*\|"
)


class FrozenTestsetError(RuntimeError):
    """Any container / verification failure the CLIs should print, not traceback."""


def sha256_file(path: Path) -> str:
    """Return the hex sha256 of a file (streamed in 64 KiB chunks)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive the AES-256 key from the password via scrypt (parameters above)."""
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt  # noqa: PLC0415 — heavy; defer

    kdf = Scrypt(salt=salt, length=_KEY_LEN, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, password: str) -> bytes:
    """Seal `plaintext` into the versioned container with a fresh salt + nonce."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: PLC0415

    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    header = MAGIC + bytes([FORMAT_VERSION]) + salt + nonce
    key = derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, MAGIC + bytes([FORMAT_VERSION]))
    return header + ciphertext


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    """Open a container produced by `encrypt_bytes`.

    Raises `FrozenTestsetError` with an examiner-readable message on a foreign
    file, an unknown format version, or GCM authentication failure (wrong
    password / corrupted download) — never a bare traceback.
    """
    from cryptography.exceptions import InvalidTag  # noqa: PLC0415
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: PLC0415

    min_len = len(MAGIC) + 1 + _SALT_LEN + _NONCE_LEN + 16
    if len(blob) < min_len or not blob.startswith(MAGIC):
        raise FrozenTestsetError(
            "This is not a HORUS frozen test-set container (bad magic bytes). "
            "Did the download complete?"
        )
    version = blob[len(MAGIC)]
    if version != FORMAT_VERSION:
        raise FrozenTestsetError(
            f"Container format version {version} is newer than this script understands "
            f"({FORMAT_VERSION}). Update the repository checkout and retry."
        )
    offset = len(MAGIC) + 1
    salt = blob[offset : offset + _SALT_LEN]
    offset += _SALT_LEN
    nonce = blob[offset : offset + _NONCE_LEN]
    offset += _NONCE_LEN
    key = derive_key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, blob[offset:], MAGIC + bytes([FORMAT_VERSION]))
    except InvalidTag as exc:
        raise FrozenTestsetError(
            "Decryption failed: wrong password, or the blob is corrupted. "
            "Re-check the password (case-sensitive) and re-download if it persists."
        ) from exc


@dataclass(frozen=True)
class FreezeRow:
    """One row of the datasheet's freeze table."""

    id: str
    pages: int | None
    sha256: str


def parse_freeze_table(datasheet_text: str) -> dict[str, FreezeRow]:
    """Parse the id ↔ sha256 freeze table out of the committed datasheet."""
    rows: dict[str, FreezeRow] = {}
    for line in datasheet_text.splitlines():
        match = _FREEZE_ROW.match(line.strip())
        if match is None:
            continue
        pages_raw = match.group("pages")
        rows[match.group("id")] = FreezeRow(
            id=match.group("id"),
            pages=None if pages_raw == "?" else int(pages_raw),
            sha256=match.group("sha"),
        )
    if not rows:
        raise FrozenTestsetError(
            "No freeze table found in the datasheet — cannot verify the corpus. "
            "Expected rows like '| `belege-de-email-001` | 1 | `<sha256>` | yes |'."
        )
    return rows


def verify_corpus_tree(
    corpus_root: Path, freeze: dict[str, FreezeRow]
) -> tuple[list[str], list[str]]:
    """Verify every restored invoice PDF against the freeze table.

    Expects the ADR-075 bundle layout: `<corpus_root>/<language>/<channel>/<id>.pdf`
    resolved through the bundle's rewritten `index.json`. Returns
    `(ok_lines, problem_lines)` — human-readable per-invoice verdicts; the corpus
    verifies iff `problem_lines` is empty.
    """
    ok: list[str] = []
    problems: list[str] = []
    index_path = corpus_root / "index.json"
    if not index_path.is_file():
        return [], [f"MISSING  index.json not found at {index_path}"]
    items = json.loads(index_path.read_text(encoding="utf-8")).get("items", [])
    seen: set[str] = set()
    for entry in items:
        invoice_id = str(entry.get("id", "?"))
        seen.add(invoice_id)
        row = freeze.get(invoice_id)
        pdf_path = corpus_root / str(entry.get("pdf", ""))
        if row is None:
            problems.append(f"UNKNOWN  {invoice_id}: not in the datasheet freeze table")
            continue
        if not pdf_path.is_file():
            problems.append(f"MISSING  {invoice_id}: no PDF at {pdf_path}")
            continue
        digest = sha256_file(pdf_path)
        if digest != row.sha256:
            problems.append(
                f"MISMATCH {invoice_id}: sha256 {digest[:12]}… != frozen {row.sha256[:12]}…"
            )
            continue
        pages = entry.get("pages")
        if row.pages is not None and pages is not None and int(pages) != row.pages:
            problems.append(f"MISMATCH {invoice_id}: {pages} pages != frozen {row.pages}")
            continue
        ok.append(f"OK       {invoice_id}: sha256 + pages match the frozen datasheet")
    for missing_id in sorted(set(freeze) - seen):
        problems.append(f"MISSING  {missing_id}: in the freeze table but not in the restored index")
    return ok, problems
