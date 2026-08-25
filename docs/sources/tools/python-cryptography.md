---
source_url: "https://cryptography.io/"
source_title: "pyca/cryptography — cryptographic primitives and recipes for Python"
source_author: "Python Cryptographic Authority (pyca) contributors"
source_date: ""
retrieved_date: "2026-08-25"
extracted_concepts: ["aes-gcm", "aead", "scrypt-kdf", "password-based-encryption"]
tags: ["cryptography", "python-library", "aes-256-gcm", "scrypt", "frozen-testset", "adr-075"]
archived_pdf: ""
status: stub
---

The de-facto standard Python cryptography package (Apache-2.0/BSD dual-licensed), maintained by the Python Cryptographic Authority. Exposes both high-level recipes (Fernet) and audited low-level primitives (`hazmat` layer) backed by OpenSSL.

**Role in HORUS (per ADR-075)** — dev-dependency powering the frozen test-set distribution scripts:

- `cryptography.hazmat.primitives.ciphers.aead.AESGCM` — authenticated encryption of the held-out bundle (`AESGCM(key).encrypt(nonce, data, aad)` / `.decrypt(...)`; 12-byte nonce, 16-byte tag appended to the ciphertext). Wrong password or a corrupted blob raises `InvalidTag` instead of yielding garbage — the property that makes the examiner flow fail loudly.
- `cryptography.hazmat.primitives.kdf.scrypt.Scrypt` — memory-hard password KDF (`salt` 16 B, `length=32` → AES-256 key, `n=2**17, r=8, p=1` per current OWASP interactive guidance). Verified against the library's own docs (retrieved via context7 at decision time): both APIs stable in the current release line.

**Why not alternatives** (recorded in ADR-075 §Options B): Fernet inflates a ~100 MB payload ~33 % via base64; external CLI tools (7z, age, OpenSSL enc) add install friction or lack AEAD; hand-rolled crypto is disqualified by definition.

**Consumed by**: `scripts/frozen_testset_bundle.py` (encrypt) + `scripts/get_frozen_testset.py` (decrypt) + `tests/test_frozen_testset.py` (hermetic round-trip).
