# ADR-075 — Frozen test-set distribution: encrypted public release asset + one-command examiner restore

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-25 |
| **Milestone** | submission (Phase 7 — writeup / delivery) |
| **Authored by** | Cascade (supervisor-delivery audit session; plan `~/.windsurf/plans/horus-supervisor-delivery-audit-62fe0e.md`) |
| **Relationship** | Amends **ADR-040** §E (privacy boundary) — the "never leaves the machine" posture gains one sealed, deliberate egress channel. Consumes the ADR-040 freeze table as its verification anchor. Sub-decision of the submission-delivery plan. |

## Context

The thesis' final Layer-1 numbers are graded on the private held-out Belege set (ADR-034/040): 39 real invoices whose only tracked representations are the sanitized datasheet (`docs/architecture/belege-heldout-datasheet.md`) and aggregate scores (`eval/heldout-breakdown.json`). The examiners must be able to **inspect the original invoices and re-run the held-out evaluation** — otherwise the headline result rests on artifacts they cannot audit. The repository is **public**, so any distribution mechanism that touches GitHub is world-visible.

Three constraints collide:

1. **Auditability** — the examiner needs the exact frozen corpus, provably unmodified.
2. **Privacy** — the invoices are the author's own incoming business correspondence (not client material, per ADR-040), but they carry real third-party company names; the original *filenames* alone are sensitive (ADR-040 §Current-state survey).
3. **Friction** — the examiner should not need a GitHub account, tokens, special tooling, or a USB handover ceremony.

## Current-state survey (2026-08-25)

| Fact | Evidence | Implication |
|---|---|---|
| The freeze proof already exists | datasheet freeze table: id ↔ sha256 for all 39 source PDFs, reproduced in the thesis appendix | delivered bytes can be verified against a committed, thesis-cited record — no trust in transport needed |
| `index.json` is path-keyed for id stability | `heldout_manifest._load_existing_id_map` returns `{source_relpath: id}` | renaming PDFs requires shipping a rewritten `index.json` (same ids, new paths); regeneration then stays stable |
| The loader resolves paths relative to `corpus_root` | `heldout.load_heldout_index`: `pdf_path = corpus_root / entry["pdf"]` | a bundle-relative index restores cleanly on any machine |
| `_promoted/` GT is id-keyed, no source filenames | `belege-*.gt.json` keys: schema_version, id, fields, provenance, … | the answer key travels without filename scrubbing |
| The source tree still holds one `.eml` | the HTML-only receipt dropped per ADR-040 §Decision pt 3 | `.eml` files carry full mail headers (sender identities, author's address) — must never enter the bundle |
| `_pagecache/` is 125 MB and regenerable | `rasterize_pdf` rebuilds it on demand | exclude from the bundle |
| The repo is public | `gh repo view` | any release asset is world-downloadable → confidentiality must come from cryptography, not access control |

## Options considered

**A — Hosting:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Encrypted asset on a GitHub Release of this repo (chosen)** | zero auth friction (`urllib` download, no account); versioned; survives as long as the repo; the same release's auto-generated source archive doubles as the frozen submission snapshot | blob is public — mitigated by AES-256-GCM with a strong out-of-band password; user explicitly approved the posture change |
| Separate private repo + collaborator invite | blob never public | examiner needs a GitHub account + accepted invite + a token wired into the download script — friction defeats the one-command goal |
| Offline handover (USB / cloud drive) | zero exposure | link-rot / ceremony; no in-repo audit trail; the restore script would still be needed — strictly worse |
| `git-crypt` / DVC with encrypted remote | established tools | puts (encrypted) private data into the repo/history permanently, against ADR-040's "never committed"; adds tool dependencies for one delivery |

**B — Cryptography:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **AES-256-GCM, key = scrypt(password) — `cryptography` package (chosen)** | authenticated encryption: wrong password or bit-rot fails loudly; scrypt is memory-hard against brute force; `cryptography` (pyca) is the boring, audited, ubiquitous choice; pure-Python flow via `uv run` = identical cross-platform behavior | adds one dev dependency — acceptable; recorded here per `horus-decision-discipline` |
| 7z AES-256 / `age` / OpenSSL CLI | no Python dependency | requires the examiner to install a tool (7z, age) or fight OpenSSL CLI portability (no AEAD in `openssl enc`); breaks the make-target-only flow |
| Fernet (cryptography recipes) | simpler API | base64 inflates a ~100 MB payload ~33 %; AESGCM primitive is equally simple here |

**C — Filename handling:** source PDFs are **renamed to their sanitized ids** (`belege-de-email-001.pdf`, …) inside the bundle; `index.json` is rewritten (`pdf` → `<language>/<channel>/<id>.pdf`, `source_filename` → `<id>.pdf`). The ids are what the thesis, datasheet, and answer key cite — cross-referencing gets *easier* while third-party names stay off the examiner's screen. Content bytes are untouched, so the freeze-table sha256s still match. Aux adjudication trees (`_judge/`, `_azure/`, …) are included verbatim (id-keyed JSONs); they are the ADR-060/062 provenance evidence.

## Decision + integration thoughts

1. **Author side — `scripts/frozen_testset_bundle.py` (`make frozen-testset-bundle`)**: stage `data/self-collected/` excluding `_pagecache/`, `*.eml`, and OS litter; rename PDFs to id-based names; rewrite `index.json` (same ids/sha256s, bundle-relative paths, scrubbed `source_filename`); pack `tar.xz` (stdlib); encrypt AES-256-GCM (key = scrypt(password, salt, n=2^17, r=8, p=1); container = magic `HORUSFTS` + version + 16-byte salt + 12-byte nonce + ciphertext, header bytes as AAD); print the blob's sha256 + the `gh release upload` command. Password read via `getpass` twice or `HORUS_BUNDLE_PASSWORD` env for non-interactive use.
2. **Examiner side — `scripts/get_frozen_testset.py` (`make get-frozen-testset`)**: download the asset from the pinned release URL (stdlib `urllib`; also accepts a local `--file`), prompt for the password, decrypt + verify GCM tag, extract to `data/self-collected/` (refuses a non-empty target without `--force`), then verify every restored PDF's sha256 + page count against the **committed datasheet's freeze table** and print a per-invoice ✓/✗ report. Exit non-zero on any mismatch.
3. **Dependency**: `cryptography` joins the `dev` dependency group (both scripts run under `uv run` after `make install`).
4. **Tests**: hermetic round-trip suite (`tests/test_frozen_testset.py`) over synthetic fixtures — stage/rename/index-rewrite, encrypt→decrypt→extract→verify, wrong-password failure, freeze-table mismatch detection. No network, no real corpus.
5. **Delivery flow**: tag the submission state → `gh release create` (the auto source archive = the frozen repo snapshot) → upload the blob → hand the password to the first examiner in person or by phone — never in the same channel as the link.

**Integration:** reuses the datasheet as the verification contract (no second freeze record); `heldout_manifest.py index` on a restored tree preserves ids (the rewritten index is the id map). No change to any evaluation path.

## Source archival

- Internal: ADR-040 (privacy boundary + freeze table — the amended parent), ADR-034 (held-out strategy), ADR-060/062 (adjudication provenance included in the bundle), `docs/architecture/belege-heldout-datasheet.md` (verification anchor).
- External: `pyca/cryptography` — archived at `docs/sources/tools/python-cryptography.md` (AESGCM AEAD + Scrypt KDF APIs verified against current docs at decision time).

## Supersession trigger

Superseded / amended if **any** of:

1. The **corpus changes** (invoice added/removed/re-scanned) → regenerate index + datasheet, build a `v2` blob, upload as a new release asset; the datasheet remains the single verification contract.
2. The **repo becomes private** or moves — the hosting trade-off (Option A) re-opens.
3. A **second examiner-facing dataset** needs distribution → generalize the container format before duplicating it.
4. The password-based scheme is replaced (e.g., per-examiner keys, `age` recipients) → new ADR; the container version byte exists for this.

## Consequences

- Examiners audit the original frozen invoices and re-run every held-out target with three commands; the sha256 verification makes "this is exactly the evaluated corpus" a checkable claim instead of an assertion.
- The privacy posture stays structural: the plaintext tree remains git-ignored and machine-local; the only public artifact carrying invoice bytes is AES-256-GCM-sealed.
- One new dev dependency (`cryptography`), one new container format (versioned), two new scripts + make targets, one hermetic test module.
- The delivered thesis gains a reproducibility property most theses lack: the *private* test set is as verifiable as the public one.
