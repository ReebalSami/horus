"""Tests for the frozen test-set distribution machinery (ADR-075).

All fixtures here are SYNTHETIC (fake "PDF" bytes + hand-written index/datasheet)
— never real invoice content — so the suite runs in CI without the private
corpus and without any network access. Covered end-to-end:

  * the encrypted container round-trip (AES-256-GCM + scrypt), including the
    loud-failure paths: wrong password, corrupted blob, foreign file, future
    format version;
  * the datasheet freeze-table parser;
  * `verify_corpus_tree` verdicts: match, sha mismatch, missing PDF, invoice
    missing from the restored index, invoice unknown to the freeze table;
  * the author-side staging pass: id-based renames, `index.json` rewrite with
    `source_filename` scrubbed, `.eml` + `_pagecache/` exclusion, aux trees
    copied verbatim — and the packed bundle restoring byte-identically.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from scripts import frozen_testset_bundle
from scripts.frozen_testset_common import (
    FORMAT_VERSION,
    MAGIC,
    FreezeRow,
    FrozenTestsetError,
    decrypt_bytes,
    encrypt_bytes,
    parse_freeze_table,
    sha256_file,
    verify_corpus_tree,
)

PASSWORD = "korrekt-pferd-batterie-klammer"


# ---------------------------------------------------------------------------
# Container round-trip
# ---------------------------------------------------------------------------


def test_container_roundtrip() -> None:
    plaintext = b"belege bytes " * 1000
    blob = encrypt_bytes(plaintext, PASSWORD)
    assert blob.startswith(MAGIC)
    assert blob[len(MAGIC)] == FORMAT_VERSION
    assert decrypt_bytes(blob, PASSWORD) == plaintext


def test_container_is_nondeterministic_but_stable() -> None:
    """Fresh salt + nonce per bundle: two blobs differ, both open."""
    plaintext = b"same plaintext"
    blob_a = encrypt_bytes(plaintext, PASSWORD)
    blob_b = encrypt_bytes(plaintext, PASSWORD)
    assert blob_a != blob_b
    assert decrypt_bytes(blob_a, PASSWORD) == decrypt_bytes(blob_b, PASSWORD) == plaintext


def test_wrong_password_fails_loudly() -> None:
    blob = encrypt_bytes(b"secret", PASSWORD)
    with pytest.raises(FrozenTestsetError, match="wrong password"):
        decrypt_bytes(blob, "not-the-password")


def test_corrupted_blob_fails_loudly() -> None:
    blob = bytearray(encrypt_bytes(b"secret", PASSWORD))
    blob[-1] ^= 0xFF  # flip a ciphertext bit
    with pytest.raises(FrozenTestsetError, match="wrong password|corrupted"):
        decrypt_bytes(bytes(blob), PASSWORD)


def test_foreign_file_rejected() -> None:
    with pytest.raises(FrozenTestsetError, match="not a HORUS"):
        decrypt_bytes(b"PK\x03\x04 definitely a zip not our container", PASSWORD)


def test_future_format_version_rejected() -> None:
    blob = bytearray(encrypt_bytes(b"secret", PASSWORD))
    blob[len(MAGIC)] = FORMAT_VERSION + 1
    with pytest.raises(FrozenTestsetError, match="newer than this script"):
        decrypt_bytes(bytes(blob), PASSWORD)


# ---------------------------------------------------------------------------
# Freeze-table parsing + corpus verification
# ---------------------------------------------------------------------------

_SHA_A = "a" * 64
_SHA_B = "b" * 64

_DATASHEET = f"""# Belege Held-Out Test Set — Datasheet (sanitized)

## Freeze table (id ↔ sha256)

| id | pages | sha256 (source PDF) | verified |
| --- | --- | --- | --- |
| `belege-de-email-001` | 2 | `{_SHA_A}` | yes |
| `belege-en-email-001` | 1 | `{_SHA_B}` | yes |
"""


def test_parse_freeze_table() -> None:
    rows = parse_freeze_table(_DATASHEET)
    assert set(rows) == {"belege-de-email-001", "belege-en-email-001"}
    assert rows["belege-de-email-001"] == FreezeRow(
        id="belege-de-email-001", pages=2, sha256=_SHA_A
    )


def test_parse_freeze_table_empty_raises() -> None:
    with pytest.raises(FrozenTestsetError, match="No freeze table"):
        parse_freeze_table("# a datasheet with no table\n")


def _write_corpus(root: Path, *, pdf_bytes: dict[str, bytes], pages: dict[str, int]) -> None:
    """Write a minimal bundle-layout corpus: renamed PDFs + rewritten index."""
    items = []
    for invoice_id, payload in pdf_bytes.items():
        lang = "german" if "-de-" in invoice_id else "english"
        rel = f"{lang}/email/{invoice_id}.pdf"
        pdf_path = root / rel
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(payload)
        items.append(
            {
                "id": invoice_id,
                "pdf": rel,
                "source_filename": f"{invoice_id}.pdf",
                "language": lang,
                "channel": "email",
                "pages": pages[invoice_id],
                "sha256": sha256_file(pdf_path),
                "gt": f"gt/{invoice_id}.gt.json",
                "verified": True,
            }
        )
    index = {"name": "belege-heldout-v1", "schema_version": 1, "items": items}
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")


def _freeze_for(root: Path) -> dict[str, FreezeRow]:
    """Freeze table matching whatever `_write_corpus` produced."""
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    return {
        e["id"]: FreezeRow(id=e["id"], pages=e["pages"], sha256=e["sha256"]) for e in index["items"]
    }


def test_verify_corpus_tree_all_ok(tmp_path: Path) -> None:
    _write_corpus(
        tmp_path,
        pdf_bytes={"belege-de-email-001": b"%PDF-1.4 de", "belege-en-email-001": b"%PDF-1.4 en"},
        pages={"belege-de-email-001": 2, "belege-en-email-001": 1},
    )
    ok, problems = verify_corpus_tree(tmp_path, _freeze_for(tmp_path))
    assert problems == []
    assert len(ok) == 2


def test_verify_corpus_tree_detects_content_change(tmp_path: Path) -> None:
    _write_corpus(
        tmp_path,
        pdf_bytes={"belege-de-email-001": b"%PDF-1.4 de"},
        pages={"belege-de-email-001": 2},
    )
    freeze = _freeze_for(tmp_path)
    (tmp_path / "german/email/belege-de-email-001.pdf").write_bytes(b"%PDF-1.4 TAMPERED")
    ok, problems = verify_corpus_tree(tmp_path, freeze)
    assert ok == []
    assert len(problems) == 1
    assert "MISMATCH" in problems[0]


def test_verify_corpus_tree_detects_missing_pdf_and_missing_index_entry(tmp_path: Path) -> None:
    _write_corpus(
        tmp_path,
        pdf_bytes={"belege-de-email-001": b"%PDF-1.4 de"},
        pages={"belege-de-email-001": 2},
    )
    freeze = _freeze_for(tmp_path)
    freeze["belege-en-email-099"] = FreezeRow(id="belege-en-email-099", pages=1, sha256=_SHA_B)
    (tmp_path / "german/email/belege-de-email-001.pdf").unlink()
    ok, problems = verify_corpus_tree(tmp_path, freeze)
    assert ok == []
    assert any(p.startswith("MISSING") and "belege-de-email-001" in p for p in problems)
    assert any(p.startswith("MISSING") and "belege-en-email-099" in p for p in problems)


def test_verify_corpus_tree_flags_unknown_invoice(tmp_path: Path) -> None:
    _write_corpus(
        tmp_path,
        pdf_bytes={"belege-de-email-001": b"%PDF-1.4 de"},
        pages={"belege-de-email-001": 2},
    )
    ok, problems = verify_corpus_tree(tmp_path, {})  # empty freeze table
    assert any("UNKNOWN" in p for p in problems)


# ---------------------------------------------------------------------------
# Author-side staging + full bundle round-trip (synthetic corpus)
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_corpus(tmp_path: Path) -> tuple[Path, Path]:
    """A source-layout corpus with name-bearing files + a fake repo root.

    Returns `(corpus_root, fake_repo_root)`; the fake repo root carries a
    datasheet whose freeze table matches the corpus, so `_verify_staging`
    exercises the real verification path.
    """
    corpus = tmp_path / "self-collected"
    (corpus / "german/email").mkdir(parents=True)
    (corpus / "gt").mkdir()
    (corpus / "_promoted").mkdir()
    (corpus / "_pagecache").mkdir()

    # Original, name-bearing source files (the .eml must never leave the machine).
    pdf = corpus / "german/email/2024-03 Acme GmbH Rechnung 4711.pdf"
    pdf.write_bytes(b"%PDF-1.4 synthetic invoice bytes")
    (corpus / "german/email/2024-03 Acme GmbH Rechnung 4711.eml").write_bytes(
        b"From: buchhaltung@acme.example\r\nSubject: Rechnung 4711\r\n"
    )
    (corpus / "_pagecache/belege-de-email-001-p1.png").write_bytes(b"raster")
    (corpus / "gt/belege-de-email-001.gt.json").write_text('{"verified": true}')
    (corpus / "_promoted/belege-de-email-001.gt.json").write_text('{"schema_version": 2}')

    index = {
        "name": "belege-heldout-v1",
        "schema_version": 1,
        "corpus_root": "data/self-collected",
        "items": [
            {
                "id": "belege-de-email-001",
                "pdf": "german/email/2024-03 Acme GmbH Rechnung 4711.pdf",
                "source_filename": "2024-03 Acme GmbH Rechnung 4711.pdf",
                "language": "german",
                "channel": "email",
                "pages": 1,
                "sha256": sha256_file(pdf),
                "gt": "gt/belege-de-email-001.gt.json",
                "verified": True,
            }
        ],
    }
    (corpus / "index.json").write_text(json.dumps(index), encoding="utf-8")

    fake_repo = tmp_path / "repo"
    datasheet = fake_repo / "docs/architecture/belege-heldout-datasheet.md"
    datasheet.parent.mkdir(parents=True)
    datasheet.write_text(
        "| id | pages | sha256 (source PDF) | verified |\n"
        "| --- | --- | --- | --- |\n"
        f"| `belege-de-email-001` | 1 | `{sha256_file(pdf)}` | yes |\n",
        encoding="utf-8",
    )
    return corpus, fake_repo


def test_bundle_roundtrip_sanitizes_and_restores(
    synthetic_corpus: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus, fake_repo = synthetic_corpus
    monkeypatch.setattr(frozen_testset_bundle, "PROJECT_ROOT", fake_repo)
    out = tmp_path / "out" / "bundle.enc"

    frozen_testset_bundle.build_bundle(corpus, out, PASSWORD)

    plaintext = decrypt_bytes(out.read_bytes(), PASSWORD)
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:xz") as tar:
        names = set(tar.getnames())
    # Renamed to the sanitized id; original filename + .eml + page cache absent.
    assert "german/email/belege-de-email-001.pdf" in names
    assert "gt/belege-de-email-001.gt.json" in names
    assert "_promoted/belege-de-email-001.gt.json" in names
    assert "index.json" in names
    assert not any("Acme" in n for n in names)
    assert not any(n.endswith(".eml") for n in names)
    assert not any(n.startswith("_pagecache") for n in names)

    # Restore and verify byte-identity through the examiner-side machinery.
    restored = tmp_path / "restored"
    restored.mkdir()
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:xz") as tar:
        tar.extractall(restored, filter="data")
    index = json.loads((restored / "index.json").read_text(encoding="utf-8"))
    entry = index["items"][0]
    assert entry["pdf"] == "german/email/belege-de-email-001.pdf"
    assert entry["source_filename"] == "belege-de-email-001.pdf"
    datasheet_text = (fake_repo / "docs/architecture/belege-heldout-datasheet.md").read_text(
        encoding="utf-8"
    )
    ok, problems = verify_corpus_tree(restored, parse_freeze_table(datasheet_text))
    assert problems == []
    assert len(ok) == 1


def test_bundle_refuses_datasheet_contradiction(
    synthetic_corpus: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corpus whose bytes drifted from the frozen datasheet must not ship."""
    corpus, fake_repo = synthetic_corpus
    monkeypatch.setattr(frozen_testset_bundle, "PROJECT_ROOT", fake_repo)
    pdf = corpus / "german/email/2024-03 Acme GmbH Rechnung 4711.pdf"
    pdf.write_bytes(b"%PDF-1.4 DRIFTED bytes")  # index + datasheet now stale
    with pytest.raises(FrozenTestsetError, match="contradicts the datasheet"):
        frozen_testset_bundle.build_bundle(corpus, tmp_path / "bundle.enc", PASSWORD)


def test_bundle_requires_index(tmp_path: Path) -> None:
    empty = tmp_path / "empty-corpus"
    empty.mkdir()
    with pytest.raises(FrozenTestsetError, match="No index.json"):
        frozen_testset_bundle.build_bundle(empty, tmp_path / "bundle.enc", PASSWORD)
