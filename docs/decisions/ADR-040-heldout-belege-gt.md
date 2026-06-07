# ADR-040 — Held-out Belege test set: ground-truth methodology + loader + privacy + circularity guard

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-07 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (held-out test-set build session; plan `~/.windsurf/plans/horus-heldout-gt-belege-8fc513.md`) |
| **Issue** | [#78](https://github.com/ReebalSami/horus/issues/78) (HND-5 — Belege held-out test set) |
| **Relationship** | Sub-decision of **ADR-034** (held-out eval strategy); reproduces the **ADR-012/013** `GroundTruth`/scorer contract via a manual-JSON route; uses **ADR-035** `validate_and_repair`; the review page is a bounded WRITE exception like **ADR-039**. |

## Context

ADR-034 locked the held-out evaluation strategy and pre-registered that the final Layer-1 approach pick is decided on a **frozen, private set of real invoices (the "Belege")** — issue #78. That set did not yet exist. This ADR ratifies **how its ground truth is produced, stored, loaded, and kept private**, and builds the machinery.

The synthetic ZUGFeRD corpus gets its ground truth for free: every PDF embeds a factur-x CII XML that `parse_cii_xml` (ADR-012) turns into a `GroundTruth`. **Real invoices carry no embedded XML**, so their ground truth must be hand-authored. The user collected ~40 real invoices (German + English; native-digital email PDFs + phone-scans).

Four coupled questions, resolved in a Socratic walk (recorded in the plan file):

1. **What shape is the GT?** The user first floated a full transcription, then settled on: *"GT should be the same GT we get from ZUGFeRD."*
2. **Who drafts it?** The user asked Cascade to draft (more accurate than the local 258M/4B VLMs), with the user verifying.
3. **How is privacy guaranteed?** This is the heart of the thesis (a privacy-first local-VLM system); private invoices must never be committed, and the one-time cloud exposure during drafting must be disclosed.
4. **How is circularity avoided?** A model that is (or resembles) an evaluation contestant must not be the sole source of the GT it is later graded against.

This issue does **not** grade anything — it produces the answer key + the tooling to load it. Grading happens later (#80 cloud comparison; the local-arm held-out run).

## Current-state survey (2026-06-07)

| Fact | Evidence | Implication |
|---|---|---|
| GT for synthetic invoices is auto-extracted from embedded XML | `ground_truth.parse_cii_xml`; `harness._extract_groundtruth_via_facturx`; `transcripts.build_gt_cache` | No equivalent exists for real invoices — a manual route is needed |
| The scorer consumes a structured `GroundTruth(header={key: GroundTruthField})` | `scorer.score(predicted, gt, …)` (ADR-013) | The manual route must emit the *same* dataclass shape, unchanged scorer |
| The 19 scored fields + locale repair already have one home | `ground_truth.FIELDS`; `schema.validate_and_repair` + `normalizers` (ADR-035) | Reuse them; do not duplicate field-type dispatch or locale handling |
| Discovery + GT-cache are ZUGFeRD-shaped | `harness._list_paired_invoices` (looks for `XML-Rechnung/{FX,CII}/`) | Real invoices have a flat layout → a parallel discovery path is needed |
| `data/*` is git-ignored except a narrow `data/raw/<lang>/<slug>/MANIFEST.md` allowlist | `.gitignore` lines 67–97 | `data/self-collected/**` is already ignored; an explicit belt-and-braces rule makes intent unmissable |
| ~40 invoices collected; filenames contain real company/person names | `data/self-collected/{german,english}/{email,iphone-pdf-scan}/` | Even filenames are sensitive → tracked artifacts must use sanitized ids |
| The app has a read-only research surface + one live WRITE page | ADR-036 (read-only) + ADR-039 (live, bounded exception) | A GT-annotation page is a second bounded WRITE exception, precedented |

## Options considered

**A — GT shape:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Same 19 named fields as ZUGFeRD (chosen)** | grades with the exact same instrument as the synthetic set; zero scorer change; user-stated *"same GT we get from ZUGFeRD"* | the only shape that plugs into the existing scorer + keeps held-out and synthetic results commensurable |
| Full free-text transcription | captures *everything*; future-proof against schema growth | the per-field F1 the thesis already uses cannot run on free text; would need a separate, weaker text-overlap metric — diverges from the established evaluation |
| Extend the schema now (IBAN/`Skonto`/`Zahlungsziele`/paid-status/…) | the user wants these eventually | explicitly **out of scope** here (user: *"this is not what this issue is for"*); tracked as a separate issue so the held-out set ships against today's instrument |

**B — Who drafts the GT:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **Cascade drafts; author verifies every field (chosen)** | far more accurate than the local 258M/4B VLMs → least correction work; digital PDFs read as exact text | accepts a **one-time** cloud read of the private invoices for the DRAFT only (disclosed below); the author's field-by-field verification is the scientific anchor |
| Local VLM (Granite→Gemma) drafts | zero third-party exposure | weak drafts → heavy correction; and a local model is also an evaluation contestant (circularity, see E) |
| Author types from scratch | zero model involvement | maximal manual effort for 40 invoices; the user explicitly asked Cascade to draft |

**C — GT storage + loader:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **One JSON file per invoice (19 fields + metadata) + a JSON→`GroundTruth` builder (chosen)** | human-diffable; trivially editable in the IDE or the review page; mirrors `parse_cii_xml`'s output exactly | the clean parallel to the XML route; `build_groundtruth_from_mapping` reuses `validate_and_repair` so a hand-typed German value canonicalizes identically to a correct prediction |
| One big CSV / spreadsheet | compact overview | 19 columns × 40 rows is wide + fiddly for money/date locale; poor diffs; awkward per-field provenance |
| Re-encode as CII XML and reuse `parse_cii_xml` | zero new loader | absurd overhead (hand-authoring EN16931 XML); brittle; no upside |

**D — Discovery + freeze record:**

The set is defined by a single **local** `index.json` at the corpus root (id, source path, sha256, page count, GT path, verified). `load_heldout_index` returns `[]` when it is absent, so corpus-dependent tests + future eval runs auto-skip on machines without the private data (the ADR-023 pattern). Stable sanitized ids (`belege-<de|en>-<email|scan>-NNN`) are assigned once and preserved across re-index runs (read back from the existing `index.json`) so adding invoices never renumbers the frozen set. The **sha256 of each source PDF is the freeze proof**.

**E — Privacy boundary (what is tracked vs. git-ignored):**

| Artifact | Disposition |
|---|---|
| Invoices, per-invoice GT JSON, `index.json`, page-render cache | **git-ignored** (`data/self-collected/**`) — never committed |
| Loader (`heldout.py`), tests (synthetic fixtures only), scripts, review page, this ADR | tracked |
| **Sanitized datasheet** (`docs/architecture/belege-heldout-datasheet.md`) | tracked — counts + per-field presence rate + id↔sha256 freeze table; **no filenames, no field values** |

**F — Circularity guard:** the GT is Cascade-drafted but **100 % author-verified against the source document** — the human verification is the anchor, not any model output. Any contestant's raw extraction (the cloud H1 system #80; the local Arm A/B) is kept as a **separate artifact** and never feeds back into the GT. Cascade is not the H1 cloud contestant (that is a dedicated cloud OCR/VLM), so drafting is not self-grading; the verification step closes the residual gap for the local arms.

## Decision + integration thoughts

1. **GT shape = the existing 19-field `GroundTruth`.** No transcription, no schema change. The manual route is byte-compatible with the scorer.
2. **New module `src/horus/eval/heldout.py`** — the manual GT route, parallel to `ground_truth.parse_cii_xml`:
   - `build_groundtruth_from_mapping` / `build_groundtruth_from_json` — JSON → `GroundTruth`, reusing `schema.validate_and_repair` (locale repair) with honesty/presence semantics: `null` / missing / empty ⇒ `is_present=False` (the tax-domain guardrail — GT never invents a value the document lacks); present-but-unparseable keeps `is_present=True, normalized=None` (audit path).
   - `load_heldout_index` / `HeldoutItem` — flat-layout discovery from `index.json`; `[]` when absent.
   - `build_gt_cache(corpus_root, *, verified_only=False)` — id→`GroundTruth`, the parallel of `transcripts.build_gt_cache`; `verified_only=True` is the safe grading default (drops unverified drafts).
   - `gt_document` / `empty_gt_fields` — the canonical on-disk document builder shared by the drafting pass + the review page.
3. **New script `scripts/heldout_manifest.py`** (two modes): `index` regenerates the local `index.json` (stable sanitized ids + sha256 + page counts; extracts a PDF attachment from any `.eml`); `datasheet` writes the **sanitized** tracked datasheet. The `.eml` with no PDF attachment (an HTML-only receipt) is dropped, leaving **39 in-scope invoices** (18 German email, 11 English email, 10 German scans).
4. **GT drafting = Cascade**, one invoice at a time (digital PDFs read as exact text; scans read as images), emitting honest nulls for absent fields. The author verifies every field.
5. **Review page `app/views/heldout_review.py`** (+ `app/data/heldout.py`) — a bounded WRITE exception (cf. ADR-039): page image beside the 19 editable fields, **Verified** checkbox, **Save** writes the JSON answer key + refreshes the cached `verified` flag in `index.json`. Registered under a new "Held-out set" nav section. Files are plain JSON, so IDE editing remains equally valid.
6. **Privacy is enforced structurally**, not by discipline alone: `data/self-collected/**` is git-ignored (belt-and-braces rule added); only the sanitized datasheet is tracked; `git check-ignore` + `git status` confirm nothing private is staged.
7. **No grading in this issue.** `score` is reused only in a synthetic-fixture test that proves the manual GT plugs in (perfect prediction ⇒ micro-F1 1.0).

**Integration:** reuses `ground_truth.FIELDS` + `schema.validate_and_repair` + `normalizers` (no duplicated field logic), `rasterize_pdf` (page images), and the app's `theme`/`fields` components. No new dependency (`pypdfium2`, `streamlit`, stdlib `email` already present). 16 synthetic-fixture tests; `make lint` + `make typecheck` + `make test` (808 passed) green.

## Source archival

- Internal: ADR-034 (held-out strategy — parent), ADR-012/013 (`GroundTruth` + scorer contract reproduced), ADR-035 (`validate_and_repair` / 19-field schema), ADR-037 (19-field scoring scope), ADR-023 (corpus-absent auto-skip pattern), ADR-036/039 (app read-only doctrine + the WRITE-page precedent), ADR-030/032 (why the local arms are Granite+Gemma).
- External: no new third-party library introduced; the privacy rationale rests on the project's own AGENTS.md privacy posture + the §203 StGB / Berufsgeheimnisträger context recorded in the re-audit (`~/.windsurf/plans/horus-reaudit-review-d23373.md`). The cloud-exposure disclosure for GT drafting is recorded here as the canonical methodology note for the thesis.

## Supersession trigger

Superseded / amended if **any** of:

1. The **field schema is extended** (IBAN/bank, `Zahlungsziele`, paid-status, `Lastschrift` mandate, `Skonto`, line items, …) — a new ADR + issue ratifies the larger set; the held-out transcriptions are *not* required to re-annotate from scratch where the new fields are derivable.
2. The GT-drafting provenance changes (e.g., a local-only drafting policy is adopted, or a cloud contestant is later run on the private set for #80) → a new ADR records the change + its privacy/circularity handling.
3. The **storage format** changes (e.g., GT moves into a database, or a second annotator is added for inter-annotator agreement) → amend §Decision pt 2.
4. A **held-out grading run** is wired (the eval of the local arms / cloud H1 on this set) → that is a *new* decision (this ADR deliberately stops at the answer key + loader).

## Consequences

- HORUS gains a **private, frozen, real-invoice held-out test set** with author-verified ground truth in the exact shape the scorer consumes — the out-of-sample surface ADR-034 requires.
- The manual GT route + discovery + cache are reusable and tested; the held-out set grades with the *same* instrument as the synthetic corpus (commensurable results).
- The privacy posture is structurally enforced (git-ignored data tree + sanitized-only tracked artifacts) and the one-time cloud-drafting exposure is disclosed for the thesis methodology.
- The circularity guard is explicit: verification is the anchor; contestant raw output never feeds the GT.
- `#78` closes when the GT is drafted + verified + the datasheet is generated; the schema extension + the held-out grading runs remain separate, tracked work.
