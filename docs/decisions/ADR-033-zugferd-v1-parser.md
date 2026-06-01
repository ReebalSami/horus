# ADR-033 — ZUGFeRD v1 (`CrossIndustryDocument`) CII ground-truth parser support

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-01 |
| **Milestone** | `experiments-validated` (HND-18 per re-audit plan `~/.windsurf/plans/horus-reaudit-review-d23373.md`; ∥ data-infra; resolves Decision-Register DR-1) |
| **Authored by** | Cascade (issue #75 implementation session; plan `~/.windsurf/plans/horus-issues-77-75-79-522413.md`) |
| **Issue** | [`ReebalSami/horus#75`](https://github.com/ReebalSami/horus/issues/75) |

## Context

The CII → 16-field ground-truth parser (`src/horus/eval/ground_truth.py`, ADR-012) was hardcoded to the ZUGFeRD/Factur-X **v2** schema: `CII_NAMESPACES` pinned `rsm` to `urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100` and every `FieldSpec.xpath` was anchored at `/rsm:CrossIndustryInvoice/...`. The 24 PDFs in `data/raw/german/zugferd-corpus/ZUGFeRDv1/` use the older ZUGFeRD **1.0** (FeRD 2014) schema, whose root is `CrossIndustryDocument` in the `urn:ferd:CrossIndustryDocument:invoice:1p0` namespace. Fed a v1 XML, every v2 XPath matched 0 elements → all 16 fields read as absent → the embedded, authoritative ground truth was silently unread. This is **Decision-Register DR-1** (surfaced in `experiments/08-cross-corpus.py` §6) and issue #75. The v1 PDFs were thus excluded from the evaluation substrate + the fine-tuning pool despite carrying valid EN16931 ground truth.

The DR-1 entry hypothesized the fix would be "non-trivial because v1's schema differs from v2 in field *semantics*, not just namespace." This ADR records that this worry was **disproven empirically**.

## Current-state survey (2026-06-01)

Verified empirically by extracting the embedded XML from a real FeRD v1 reference invoice (`ZUGFeRDv1/correct/Intarsys/ZUGFeRD_1p0_COMFORT_Einfach.pdf`) via the already-ratified `factur-x` route (ADR-005/010) and diffing its structure against the v2 `EN16931_Einfach` fixture (the two are the same canonical FeRD example invoice in different schema versions):

| Aspect | v2 (`CrossIndustryInvoice`) | v1 (`CrossIndustryDocument`) | Delta |
|---|---|---|---|
| Embedded attachment name | `factur-x.xml` | `ZUGFeRD-invoice.xml` | `factur-x.get_xml_from_pdf` extracts BOTH transparently (auto-detects; returned `flavor=zugferd, level=comfort`) — no extraction-side change needed |
| Root namespace (`rsm`) | `…:CrossIndustryInvoice:100` | `urn:ferd:CrossIndustryDocument:invoice:1p0` | namespace URN + root local-name |
| `ram` / `udt` namespaces | `…:100` / `…:100` | `…:12` / `…:15` | URN revision suffix only |
| Document header | `rsm:ExchangedDocument` | `rsm:HeaderExchangedDocument` | container name |
| Transaction | `rsm:SupplyChainTradeTransaction` | `rsm:SpecifiedSupplyChainTradeTransaction` | container name |
| Agreement / Delivery / Settlement | `ram:ApplicableHeader*` | `ram:ApplicableSupplyChain*` | container name (×3) |
| Monetary summation | `…HeaderMonetarySummation` | `…MonetarySummation` | container name |
| **16 EN16931 leaf paths + `schemeID` predicates** | — | — | **byte-IDENTICAL** (`ram:SellerTradeParty/ram:Name`, `…/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']`, `…/ram:LineTotalAmount`, etc.) |

So the v1↔v2 difference is **exactly** 4 namespace URNs + 7 container element names. The 16 in-scope EN16931 business-term leaf elements are structurally identical. Parsing the v1 fixture with the new code reproduced all 16 expected values (invoice 471102, seller "Lieferant GmbH", totals 473.00 / 56.87 / 529.87, `buyer_vat_id` correctly absent) — matching the v2 fixture except the date (2013 vs 2018, the 2014-era v1.0 sample). `factur-x`'s own flavor/level auto-detection corroborates the v1 namespace as the canonical ZUGFeRD 1.0 schema (not a per-sample quirk).

## Options considered

| Option | Why considered | Why not chosen |
|---|---|---|
| **DRY-derive `FIELDS_V1` from `FIELDS` via container substitution** (chosen) | Single field-definition source; impossible for v1/v2 registries to drift; the 7 deltas are explicit + auditable in one dict | — |
| Hand-written parallel `FIELDS_V1` literal (16 rows) | Maximally explicit (every v1 XPath readable inline) | Duplicates the 16-row registry → drift risk between v1/v2 on any future field addition; ~170 redundant lines |
| Refactor `FIELDS` into a `_build_fields(prefixes)` factory called twice | Both registries built from one body, fully parameterized | Larger, riskier diff to a core parser; restructures the working v2 registry with no functional gain over substitution |
| Lenient fallback (unknown root → parse with v2 XPaths → empty GT, no raise) | Smallest blast radius; preserves the pre-existing "non-CII → empty GT" contract the EDA loader relied on | Silently returns a misleading all-absent `GroundTruth` for genuinely-non-invoice XML — the opposite of fail-fast; rejected on scientific-correctness grounds |

## Decision + integration thoughts

Extend the **shared** `parse_cii_xml` (single source of truth for CII → GT) to auto-detect the schema and parse both versions:

- **`CII_NAMESPACES_V1`** — the v1 namespace map (verified URNs).
- **`FIELDS_V1`** — derived from `FIELDS` via `_to_v1_xpath`, applying the 7 mutually-disjoint container substitutions in `_V2_TO_V1_XPATH_SUBSTITUTIONS` (leaf paths + `schemeID` predicates pass through unchanged; the namespace-URN difference is resolved by binding the unchanged `rsm/ram/udt` prefixes to `CII_NAMESPACES_V1` at parse time).
- **`_select_schema(tree)`** — detects the root local-name: `CrossIndustryInvoice` → (`FIELDS`, v2 ns); `CrossIndustryDocument` → (`FIELDS_V1`, v1 ns); anything else → `ValueError` (**fail-fast** — a GT parser fed non-invoice XML must error loudly, not fabricate an all-absent record).

**Integration with already-decided components:**
- **ADR-014 harness** (`_extract_groundtruth_via_facturx` → `parse_cii_xml`): auto-benefits with zero harness change — `factur-x` already extracts the v1 attachment, and the parser now handles it. The 24 v1 PDFs become usable cohort ground truth.
- **ADR-010 / ADR-005 factur-x**: unchanged; its v1 extraction was already capable (verified).
- **ADR-024/025 EDA loader** (`horus.eda.zugferd_loader`): the strict-raise contract changed non-CII input from "empty GT" to "ValueError → `parse_one_gt` catches → None". Functionally identical for the EDA's corpus-scan (both → "not meaningful" via `gt_has_any_field`), but the loader's docstrings (which documented "v1 = empty GT, presence rates capped at ~84%") were now factually wrong and have been corrected: v1 now parses, so on next `make eda-book` the v1 PDFs will count as GT-meaningful and the ~84% cap lifts. `line_item_count` still uses a local v2-only namespace (v1 line-items return 0) — left as a documented, separate, out-of-scope limitation (a version-aware counter is a follow-up).

**Forward-compat:** the `experiment`/`implement` phases gain 24 additional German invoices with authoritative GT (baselines + LoRA pool); `writeup` can report v1+v2 corpus coverage honestly.

## Source archival

No new `docs/sources/` stubs required: this ADR adopts no new library, dataset, or paper. The extraction tool (`factur-x`) is already archived under ADR-005 + ADR-010; the v1 schema facts were verified **empirically** from a FeRD-published reference invoice already present in the gitignored corpus (the most authoritative source — the data itself), cross-corroborated by `factur-x`'s own v1 flavor/level auto-detection.

## Supersession trigger

This ADR is superseded if **either**: (a) a v1 invoice is found whose in-scope EN16931 **leaf** path (not just container) differs from v2 — the disjoint-substitution model would then be insufficient and a parallel `FIELDS_V1` literal (or per-field version override) would be required; **or** (b) line-item-level (BG-25) or v1 line-item counting is brought into scope — `line_item_count` + any line-item GT would need version-aware namespace handling, ratified by a new ADR.

## Consequences

- **24 `ZUGFeRDv1/` PDFs unlocked** as GT-parseable (≈21 in `correct/` + 3 deliberately-invalid in `fail/`), enriching the evaluation substrate + fine-tuning pool. **Resolves DR-1.**
- v2 behaviour is **byte-unchanged** (auto-detect routes v2 docs through the identical `FIELDS`/`CII_NAMESPACES` path) — all pre-existing parser tests pass unmodified.
- New tests: real-v1-fixture end-to-end smoke (corpus-gated) + corpus-independent v1-XPath-executable + non-CII-root `ValueError` checks (`tests/test_ground_truth.py`); one EDA-loader test updated to the new strict-raise contract.
- **Downstream EDA re-render** (`make eda-book`): the §5 mandatory-field presence-rate "~84% cap" lifts (v1 now contributes). `line_item_count` v1-awareness is a noted follow-up.
- Verified: `make lint` + `make typecheck` + `make test` (705 passed) all green at authoring time.
