# ADR-012 — CII XML → ground-truth field dict: 16-field English-keyed parser substrate for pilot #13

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-17 |
| **Milestone** | `experiments-validated` (pilot #13's ground-truth-parser sub-issue; PR(a) of the locked 3-PR split) |
| **Authored by** | Cascade D (issue #13 implementation session; plan `~/.windsurf/plans/horus-issue-13-pra-cii-parser-c482cf.md`) |
| **Issue** | `ReebalSami/horus#13` (parent: pilot #13 first data loop) |
| **Supersession trigger** | (1) EN 16931 itself is superseded (e.g., a forthcoming EN 16931-2 revision with renumbered BT codes) — the schema lockup at the type level (BT codes as `FieldSpec.bt_code` strings) requires an update + a migration `FIELDS` registry; OR (2) CII XML schema (UN/CEFACT CrossIndustryInvoice) versions beyond `:100` (the current namespace URN) — XPaths + namespace map need a migration ADR; OR (3) the 16-field scope becomes inadequate for the thesis (e.g., compliance evaluation requires line items, BG-23 per-VAT-rate breakdown, or address fields) — additive: extend `GroundTruth` with the forward-compat-reserved optional fields, extend `FIELDS` registry; OR (4) HORUS pivots from CII to UBL (OASIS) syntax — keep `GroundTruth` shape, add `parse_ubl_xml(...) -> GroundTruth` sibling function with a parallel `UBL_FIELDS` registry; OR (5) a downstream consumer (PR(b) scorer, PR(c) harness) discovers that the tristate value semantics leak `None == ""` edge cases despite the explicit contract — re-evaluate the dataclass shape with concrete evidence. |

## Context

The HORUS thesis (`docs/prompts/stages/02-brainstorm.md` v2 §5.5 + §10) evaluates **local vision-language models** for German B2B invoice extraction. Pilot #13 ([ReebalSami/horus#13](https://github.com/ReebalSami/horus/issues/13)) builds the first data loop: 10 VLM cohort members × 26 paired ZUGFeRD PDFs → field extraction → **XML-grounded per-field F1** (per ADR-009 Amendment 1) → error heatmap.

ADR-010 ratified the XML-**extraction** layer (`factur-x` Python library as canonical engine + Mustang Project CLI as opt-in cross-check route + three-route C14N2-canonical equivalence proven on the smoke fixture). ADR-010 §"What this ADR does NOT decide" explicitly forward-points to two follow-on deliverables: (a) "the CII → dict parser (PR(a))" — **this ADR** — and (b) "the VLM output parser + F1 scorer (PR(b))" — a future ADR.

This ADR ships PR(a): a typed `GroundTruth` dataclass produced from any CII XML byte string, keyed by 16 EN16931-anchored English field names, with each record carrying raw + normalized values + provenance + presence flag. PR(b) will consume `GroundTruth` instances as the comparison target for VLM predictions.

### What is already half-built

- **ADR-010 (2026-05-16)** ratified the extraction route (factur-x). The extracted XML is the **input** to this PR(a)'s parser; the three-route C14N2-byte-equivalence proven there is now extended to **dict-equivalence** post-parse (see §"Empirical evidence" Probe 2 below).
- **ADR-009 Amendment 1 (2026-05-15)** designated the embedded factur-x XML as pilot #13's authoritative ground truth and identified BT-29 (seller GLN) + BT-72 (delivery date) as members of the evidence base — both are in the 16-field scope of this ADR per the Socratic-walk decision documented in the plan.
- **`data/raw/german/zugferd-corpus/XML-Rechnung/`** — the FeRD-shipped corpus of 26 paired ZUGFeRD PDFs (in `FX/`) + standalone CII sidecars (in `CII/`).

### What is novel in this ADR

Five additions that no prior decision covered:

1. **The 16-field schema selection** — picked the EN16931-mandatory core (11 fields) + 3 VAT-compliance fields + 2 ADR-009-continuity fields (`seller_gln` BT-29 and `delivery_date` BT-72). Load-bearing scope decision: pilot #13's F1 numbers will be reported against exactly these 16 fields.
2. **The `GroundTruth` / `GroundTruthField` / `FieldSpec` / `FIELDS` shape** — concrete dataclasses + registry that PR(b)'s scorer and PR(c)'s harness will consume. Frozen dataclasses for hashable-free equality; separate static `FIELDS` registry so per-invoice records stay lean.
3. **The English-keyed-with-BT-attribute design** — readable English keys at the lookup site; BT code preserved as record attribute (`gt["invoice_number"].bt_code == "BT-1"`).
4. **The tristate value semantics + per-field normalizer dispatch** — explicit contract distinguishing absent (`raw=None, normalized=None`) from present-but-empty (`raw="", normalized=""`). Each `FieldSpec` carries its own `normalize: Callable[[str], str]` — no central dispatch cascade.
5. **The XRECHNUNG corpus-divergence finding** — captured at authoring (see §"Empirical evidence" Probe 5): the 4 XRECHNUNG-profile fixtures show a 2018-era-PDF / 2024-era-sidecar date drift.

## Current-state survey (2026-05-17)

| Component | Where | Ratified by | Role |
|---|---|---|---|
| `lxml` (PyPI) | transitive dep of `factur-x` | — | XPath engine. mypy override already in place (ADR-005). |
| `unicodedata` (stdlib) | always present | — | NFC normalization for German diacritics. |
| `decimal.Decimal` (stdlib) | always present | — | Canonical 2-decimal money strings; sign preservation. |
| `dataclasses.dataclass(frozen=True)` (stdlib) | always present | — | Value-object shape for `FieldSpec`, `GroundTruthField`, `GroundTruth`. |
| `CII_NAMESPACES` constant | `src/horus/eval/ground_truth.py` (new) | This ADR | Single source of truth for XPath namespace resolution. |
| `FieldSpec` + `FIELDS` registry | same file (new) | This ADR | Static 16-row catalog: per-field BT code, German label, XPath, normalize callable. |
| `GroundTruthField` | same file (new) | This ADR | Per-extraction record (raw + normalized + xpath + is_present). Tristate semantics documented. |
| `GroundTruth` | same file (new) | This ADR | Top-level wrapper with `header` field; future `line_items` reserved. |
| `parse_cii_xml(xml_bytes) -> GroundTruth` | same file (new) | This ADR | Main entry point. |
| `tests/conftest.py` (new) | `tests/conftest.py` | This ADR | Centralizes corpus paths + parametrized fixtures (`en16931_paired_invoice`, `xrechnung_paired_invoice`, `paired_invoice`). |
| `e-invoice.be EN16931 mapper` | https://e-invoice.be/en16931-mapper | consulted | BT ↔ CII XPath canonical lookup. |
| B2BRouter `BT ↔ CII XPath` doc | https://developer.b2brouter.net/docs/mapping_json_invoice_to_cii | consulted | Independent vendor's mapping (second-opinion source). |
| arXiv:2510.15727 §3.4 | "Invoice Information Extraction: Methods and Performance Evaluation" | consulted | DocILE-aligned field-vs-line-item separation; methodological precedent for header-only scope. |

The decision is **substantially overdetermined** by what was locked in the Socratic walk (`~/.windsurf/plans/horus-issue-13-pra-cii-parser-c482cf.md`). The §"Options considered" walk below is documented for the 5-section discipline mandate; same retroactive-ratification shape as ADR-010 + ADR-011.

## Options considered

The Socratic walk explored **four orthogonal axes**.

### Axis 1 — Scope

| Option | Outcome |
|---|---|
| **Header + totals only (16 fields)** | **Chosen.** DocILE-aligned (arXiv 2510.15727 §3.4 separates field-level from line-item F1 — methodologically distinct research questions). Vorsteuerabzug compliance hinges on header BTs; clean baseline F1 across the cohort. |
| Header + totals + line items (BG-25) | Rejected — doubles parser+test complexity; line-item F1 requires row-wise assignment (set-matching). Worth a future ADR amendment once header baseline established. |
| Full BG-22 + BG-23 + BG-25 | Rejected — premature for first pilot; test matrix explodes. |
| Configurable via YAML | Rejected — over-engineered for PR(a); the closed `FieldSpec` registry shape makes future conversion trivial. |

### Axis 2 — Key vocabulary

| Option | Outcome |
|---|---|
| **English snake_case (`gt["invoice_number"]`) — BT code as record attribute** | **Chosen.** Self-documenting in tests + MLflow charts; codebase consistency (HORUS is English throughout per AGENTS.md). BT code preserved on every record. |
| BT-* codes as keys (`gt["BT-1"]`) | Rejected — opaque at the lookup site. |
| German snake_case | Rejected — codebase consistency. German labels live in `FieldSpec.german_label` for thesis writeup tables. |
| Three-identifier dataclass on every record | Rejected — data-vs-metadata confusion; duplicates static label strings 26×16 times. |

### Axis 3 — Value shape

| Option | Outcome |
|---|---|
| **Frozen `GroundTruthField` dataclass** with bt_code + raw + normalized + xpath + is_present | **Chosen.** DocILE-aligned: needs both `raw_value` (exact-match) and `normalized_value` (relaxed-match). Provenance survives into MLflow `log_dict` artifacts. |
| Flat scalar value | Rejected — loses per-extraction audit trail. |
| Pydantic model | Rejected — overkill (no runtime validation needed; HORUS precedent: Pydantic for boot-time config, dataclass for value objects). |

### Axis 4 — Top-level container

| Option | Outcome |
|---|---|
| **`GroundTruth(header=...)` wrapper dataclass; future `line_items` reserved** | **Chosen.** Forward-compatible: future amendment adding `line_items: list[LineItemGT] \| None = None` is non-breaking. |
| Bare `dict[str, GroundTruthField]` return | Rejected — future-amendment hostile (signature change → caller refactor). |
| Two separate functions | Rejected — split-API hostile to atomic dict-equivalence comparisons. |

## Decision + integration thoughts

> **Honest light-ADR clause** (mirrors ADR-010 + ADR-011): this ADR retroactively ratifies the Socratic-walk outcome documented in the plan file rather than walking an open design space. The §"Options considered" walk above is for the 5-section discipline mandate; the post-walk decision was settled.

### Chosen

- **Module placement**: `src/horus/eval/ground_truth.py` (new `eval/` subpackage); re-exported from `src/horus/eval/__init__.py`.
- **Public surface**: `CII_NAMESPACES`, `FieldSpec`, `FIELDS`, `GroundTruthField`, `GroundTruth`, `parse_cii_xml`.
- **Scope**: 16 EN16931-anchored header + totals fields (see table below).
- **Dict key vocabulary**: English snake_case; BT code preserved as `GroundTruthField.bt_code` attribute.
- **Per-record shape**: frozen `GroundTruthField(bt_code, raw_value, normalized_value, xpath, is_present)`. Tristate: absent → `(None, None, False)`; present-empty → `("", "", True)`; present-content → `(<raw>, <normalized>, True)`; present-normalizer-rejects → `(<raw>, None, True)` with WARNING.
- **Top-level wrapper**: frozen `GroundTruth(header: dict[str, GroundTruthField])`. Forward-compat reserved for `line_items`.
- **Static catalog**: `FIELDS: dict[str, FieldSpec]`; `FieldSpec` is frozen with `(english_key, bt_code, german_label, xpath, normalize)`. Per-field `normalize` callable — no central dispatch.
- **Normalization rules**: dates → ISO 8601 (`YYYY-MM-DD`); money → 2-decimal Decimal string with sign preservation; strings → outer-strip + Unicode NFC; codes → pass-through. Pure, deterministic, no I/O.
- **Namespace map**: single module-level `CII_NAMESPACES` constant (rsm/ram/udt/qdt/xs).
- **Multi-match XPath behavior**: take first in document order; log WARNING.
- **Test substrate**: `tests/conftest.py` centralizes corpus paths + parametrized fixtures.

### The 16 fields

| # | English key | BT code | German label | Normalizer |
|---|---|---|---|---|
| 1 | `invoice_number` | BT-1 | Rechnungsnummer | string |
| 2 | `issue_date` | BT-2 | Rechnungsdatum | date |
| 3 | `invoice_currency_code` | BT-5 | Währung | passthrough |
| 4 | `delivery_date` | BT-72 | Liefer-/Leistungsdatum | date |
| 5 | `seller_name` | BT-27 | Verkäufer | string |
| 6 | `seller_vat_id` | BT-31 | USt-IdNr. (Verkäufer) | string |
| 7 | `seller_tax_id` | BT-32 | Steuernummer | string |
| 8 | `seller_gln` | BT-29 (scheme 0088) | GLN (Verkäufer) | string |
| 9 | `buyer_name` | BT-44 | Käufer | string |
| 10 | `buyer_reference` | BT-46 | Kundennummer | string |
| 11 | `buyer_vat_id` | BT-48 | USt-IdNr. (Käufer) | string |
| 12 | `line_total_amount` | BT-106 | Summe Nettobeträge | money |
| 13 | `tax_basis_total_amount` | BT-109 | Steuerlicher Bemessungsbetrag | money |
| 14 | `tax_total_amount` | BT-110 | Umsatzsteuer gesamt | money |
| 15 | `grand_total_amount` | BT-112 | Bruttobetrag | money |
| 16 | `due_payable_amount` | BT-115 | Zahlbetrag | money |

11 EN16931-mandatory + 3 VAT-compliance + 2 ADR-009-continuity (BT-29, BT-72).

**Note on BT-3 invoice type code exclusion**: BT-3 carries values like "380" (commercial invoice) uniformly across the German B2B corpus → no F1 signal. ADR-009 cohort smoke transcripts confirm multiple models DO extract `Handelsrechnung (380)` cleanly; the exclusion rationale is **"low information value across a uniform-typed corpus"**, not "VLM-unreadable" (an earlier planning-draft framing corrected during the Socratic walk).

### Empirical evidence captured at decision time

Probed during this PR(a)'s authoring session (2026-05-17) against the on-disk corpus.

#### Probe 1 — End-to-end on `EN16931_Einfach.pdf`

```text
================================================================================
Probe 1 — End-to-end on EN16931_Einfach.pdf
================================================================================
  factur-x attachment name: 'factur-x.xml'
  factur-x XML size:        13396 bytes

  Parsed dict size:         16 keys (expected: 16)
  Present fields:           15/16
  Absent fields:            1/16

  Per-field summary:
  ----------------------------------------------------------------------------
    [+] invoice_number                 BT-1                      norm=471102
    [+] issue_date                     BT-2                      norm=2018-03-05
    [+] invoice_currency_code          BT-5                      norm=EUR
    [+] delivery_date                  BT-72                     norm=2018-03-05
    [+] seller_name                    BT-27                     norm=Lieferant GmbH
    [+] seller_vat_id                  BT-31                     norm=DE123456789
    [+] seller_tax_id                  BT-32                     norm=201/113/40209
    [+] seller_gln                     BT-29 (scheme 0088)       norm=4000001123452
    [+] buyer_name                     BT-44                     norm=Kunden AG Mitte
    [+] buyer_reference                BT-46                     norm=GE2020211
    [-] buyer_vat_id                   BT-48                     norm=(absent)
    [+] line_total_amount              BT-106                    norm=473.00
    [+] tax_basis_total_amount         BT-109                    norm=473.00
    [+] tax_total_amount               BT-110                    norm=56.87
    [+] grand_total_amount             BT-112                    norm=529.87
    [+] due_payable_amount             BT-115                    norm=529.87
  ----------------------------------------------------------------------------

  Verdict: 15/16 present, 1/16 absent — matches expected
           (BT-48 buyer_vat_id absent in domestic B2B Einfach)
```

All 16 normalized values were cross-referenced against the visible PDF content (manual eye-check). The single absent field (`buyer_vat_id`) is **deliberately** missing — Einfach is a domestic German B2B invoice; BT-48 is only conditionally-mandatory for cross-border EU transactions. This validates the tristate "absent" path of the contract.

#### Probe 2 — Three-route dict-equivalence on `EN16931_Einfach.pdf`

```text
================================================================================
Probe 2 — Three-route dict-equivalence on EN16931_Einfach.pdf
================================================================================
  Route 1 — factur-x extracted: 13396 bytes
  Route 2 — FeRD CII sidecar:   13153 bytes
  Route 3 — Mustang extracted:  13396 bytes

  parse(factur-x)  == parse(FeRD)     : True
  parse(factur-x)  == parse(Mustang)  : True
  parse(FeRD)      == parse(Mustang)  : True

  Verdict: PASS — all routes produce identical GroundTruth
```

**Stronger evidence than ADR-010 Probe 2's C14N2 byte-equivalence claim**: ADR-010 proved the three routes produce semantically-equivalent **raw XML**; this ADR proves the three routes produce **identical `GroundTruth` instances** post-parse — the parser introduces no route-dependent state. The byte-size diff (FeRD sidecar 243 bytes smaller) is a CRLF→LF corpus-assembly artifact documented in ADR-010; dict equality persists across this cosmetic byte diff because the parser operates on lxml tree nodes, not raw bytes.

#### Probe 3 — Cross-corpus dict-shape stability

```text
================================================================================
Probe 3 — Cross-corpus dict-shape stability (5 diverse fixtures)
================================================================================
  Fixture                                       present    absent     shape     
  ----------------------------------------------------------------------------
  EN16931_Einfach                               15/16      1/16      [OK]
  EN16931_Reisekostenabrechnung                 14/16      2/16      [OK]
  EN16931_Innergemeinschaftliche_Lieferungen    13/16      3/16      [OK]
  EN16931_Gutschrift                            16/16      0/16      [OK]
  EN16931_Rabatte                               15/16      1/16      [OK]
  ----------------------------------------------------------------------------

  Verdict: All 5 fixtures produce identical 16-key shape
           (presence varies sensibly per invoice content): PASS
```

5 fixtures spanning corpus diversity: minimal Einfach, multi-page Reisekostenabrechnung, cross-border `Innergemeinschaftliche_Lieferungen` (BT-48 buyer VAT mandatory — tests conditional-presence), negative-direction `Gutschrift` (credit note), and `Rabatte` (BG-20 discount/allowance lines active). All 5 produce **identical 16-key dict shapes** — the only variation is `is_present` flags. PR(b)'s scorer iterates the same 16 keys for every invoice, regardless of corpus diversity.

#### Probe 4 — Negative test on Hetzner no-attachment PDF

```text
================================================================================
Probe 4 — Negative test on Hetzner PDF (no embedded factur-x XML)
================================================================================
  extract_via_facturx(RE-E-974-Hetzner_2016-01-19_R0005532486.pdf) → None

  Verdict: PASS — negative path correctly handled upstream
```

The Hetzner PDF is the canonical no-attachment fixture from ADR-010 Probe 3. **Contract documented**: `parse_cii_xml` requires non-None XML bytes input; the upstream layer (`scripts/extract_zugferd_xml.py::extract_via_facturx`) returns `None` for PDFs without embedded factur-x attachments; downstream consumers MUST check before invoking `parse_cii_xml`. The parser itself never sees a no-attachment PDF.

#### Probe 5 — Negative finding: XRECHNUNG corpus date drift

Discovered during PR(a) authoring (was NOT in the plan's risk table at this level of detail).

For all 4 XRECHNUNG-profile fixtures, the factur-x-extracted XML and the FeRD-shipped CII sidecar agree on **14 of the 16 fields** but **differ on `issue_date` and `delivery_date`**:

```text
XRECHNUNG_Einfach.pdf:
    issue_date:    factur-x='2018-03-05'  FeRD='2024-11-15'
    delivery_date: factur-x='2018-03-05'  FeRD='2024-11-14'

XRECHNUNG_Elektron.pdf:
    issue_date:    factur-x='2018-04-25'  FeRD='2024-11-15'
    delivery_date: factur-x='2018-03-06'  FeRD='2024-11-01'

XRECHNUNG_Betriebskostenabrechnung.pdf:
    issue_date:    factur-x='2018-03-05'  FeRD='2024-11-15'
    delivery_date: factur-x=is_present=False  FeRD='2023-12-31'

XRECHNUNG_Reisekostenabrechnung.pdf:
    issue_date:    factur-x='2018-07-13'  FeRD='2024-11-15'
    delivery_date: factur-x=is_present=False  FeRD='2024-11-05'
```

**Forensic interpretation**: all 4 FeRD-shipped CII sidecars uniformly carry `issue_date = 2024-11-15` (suspicious uniformity), while the PDF-embedded XMLs carry **original 2018-era authoring dates**. The 14 non-date fields agree perfectly; divergence is **scoped to dates and to XRECHNUNG fixtures only**. The 22 EN16931 fixtures are route-equal across all 16 fields.

**Likely cause**: a corpus-revision pass on the standalone `.cii.xml` files updated the dates, but the PDFs in `FX/` were not re-bonded with the updated XMLs. The corpus README does not document this offset.

**Mitigation in code**:

- `test_two_route_dict_equivalence_en16931_corpus` (parametrized over 22 EN16931 fixtures) asserts **strict equality** — passes today.
- `test_xrechnung_documented_divergence` (parametrized over 4 XRECHNUNG fixtures) asserts **structural equality + non-date-field equality + the specific drift pattern** (`FeRD issue_date == "2024-11-15"`). If FeRD updates the corpus to re-align, the latter assertion fires.

**Implications for pilot #13**:

- The **PDF is what the VLM sees**. VLM predictions on `XRECHNUNG_*.pdf` will produce 2018-era dates.
- Pilot #13's eval harness (PR(c)) MUST use the **extracted-XML route** for XRECHNUNG fixtures, NOT the sidecar route, or the date mismatches will be misreported as VLM errors.
- For the 22 EN16931 fixtures, both routes are equivalent — PR(c) can use either.

### Test matrix

40 tests in `tests/test_ground_truth.py`, all passing. Full project test count post-PR(a): **106 tests passing** (66 pre-existing + 40 new).

| Test category | Count | Asserts |
|---|---|---|
| End-to-end smoke (Einfach) | 1 | 16-key dict; spot-check 15 present field values |
| Tristate "absent" path | 1 | `buyer_vat_id` is_present=False, raw_value=None, normalized_value=None |
| Three-route equivalence (Einfach) | 1 | factur-x ↔ FeRD ↔ Mustang all parse to equal GroundTruth |
| Two-route equivalence (22 EN16931, parametrized) | 22 | For each fixture: factur-x ↔ FeRD sidecar produce equal GroundTruth |
| XRECHNUNG documented divergence (4 fixtures, parametrized) | 4 | Structural shape + 14 non-date fields equal; date pattern pinned |
| Date normalization | 1 | Format codes 102 / 203 / 204; ValueError on bad input |
| Money normalization | 1 | 2-decimal canonical; sign preservation; banker's rounding |
| Money sign preservation E2E | 1 | `EN16931_Einfach_negativePaymentDue` fixture parses with negative `due_payable_amount` |
| String normalization | 1 | NFC + outer-strip + internal-preserve |
| Passthrough normalization | 1 | Currency code; outer-strip only; case preserved |
| FIELDS registry consistency | 1 | All 16 rows: unique BT codes, callable normalizers, XPath shape |
| FIELDS registry XPath executable | 1 | Every FIELDS XPath compiles against CII_NAMESPACES |
| `GroundTruth` forward-compat | 1 | Frozen dataclass; `header` field; future `line_items` extension path proven |
| Tristate semantics | 3 | Absent / present-empty / present-content paths each asserted |

### What this ADR does NOT decide

- **Real per-field F1 computation**: PR(b) sub-issue. `GroundTruthField.raw_value` + `normalized_value` are the comparison targets; the exact-vs-relaxed match + tolerance-window logic is PR(b)'s scope.
- **VLM output parsing**: PR(b) builds the `VlmPrediction → dict[english_key, str]` adapter. The 16 english_keys defined here are the stable target vocabulary.
- **Per-field error heatmap content**: PR(c) (pilot harness) consumes `GroundTruth` + VLM predictions, computes per-field F1, logs via `Tracker.log_dict(...)` per ADR-011.
- **Line items (BG-25)**: deferred. `GroundTruth` wrapper reserves the forward-compat extension path (`line_items: list[LineItemGT] | None = None`). Line-item F1 is methodologically distinct from header F1 (row-wise assignment + set-matching per arXiv 2510.15727 §3.4); a separate ADR will own it.
- **Per-VAT-rate breakdown (BG-23)**: same deferral.
- **Charge / allowance / prepaid totals (BT-107 / BT-108 / BT-113)**: almost always "0.00" → no F1 signal. Trivial to add via amendment.
- **Address fields (BT-37/38/40, BT-52/53/55)**: easy add via amendment if pilot writeup demands them.
- **Compliance-weighted F1**: §14 UStG categorization needs a domain-expert meeting (per brainstorm v2 §5.5). Raw per-field F1 can be re-weighted post-hoc.
- **UBL syntax parsing**: HORUS corpus is CII; UBL would require parallel `parse_ubl_xml(...)` with parallel `UBL_FIELDS` registry. Same `GroundTruth` shape. Not needed for pilot #13.
- **XRECHNUNG corpus drift remediation**: documented in Probe 5 + pinned by `test_xrechnung_documented_divergence`.
- **`defusedxml` hardening for untrusted XML input**: FX corpus is trusted; PR(b)/PR(c) will receive VLM-output XML from arbitrary PDFs in production deployments. Captured as a `cascade-system/queue/pending-review.md` item for a future sprint.

## Source archival

Per `horus-source-archival` rule + ADR-002:

- **`docs/sources/tools/factur-x-python.md`** — already archived (ADR-005, ADR-010). Re-cited here as the extraction-route engine whose output this ADR's parser consumes.
- **`docs/sources/tools/mustang-project.md`** — already archived (ADR-005, ADR-010). Re-cited as the independent JVM cross-check route used in Probe 2.
- **`docs/sources/tools/e-invoice-be-en16931-mapper.md`** — **new this PR.** Web-based BT ↔ CII XPath lookup reference; consulted during XPath authoring.
- **`docs/sources/tools/b2brouter-cii-xpath.md`** — **new this PR.** Independent vendor's published mapping table; consulted as a second-opinion source.
- **`docs/sources/papers/raman-2025-invoice-extraction-arxiv-2510-15727.md`** — **new this PR.** arXiv 2510.15727 §3.4 cited as the methodological precedent for separating field-level F1 (header) from line-item F1 (row-wise assignment).
- **Alternatives considered + rejected in §"Options considered"** — not archived per `horus-source-archival` §"When the rule does NOT fire" (alternatives explicitly considered-and-rejected in the same ADR but not cited as positive evidence).

## Consequences

- **Positive**:
  - Pilot #13 has its **ground-truth parser substrate**: PR(b)'s scorer + PR(c)'s harness can be built directly against the `GroundTruth` / `GroundTruthField` / `FIELDS` API without further parser work.
  - **EN16931 standards anchor preserved at the type level**: every `GroundTruthField` carries the BT code; the `FIELDS` registry catalogs BT → English-key → German-label in one place. Thesis writeup renders German-labelled tables via `FIELDS["<key>"].german_label`; future Säring-meeting compliance discussions reference BT-* directly.
  - **Three-route dict-equivalence proven empirically** (Probe 2). Stronger than ADR-010's byte-level claim; this ADR proves the parser is route-invariant at the semantic level.
  - **Tristate value semantics + per-field normalizer dispatch + centralized namespace map** — three coding-debt-mitigation patterns called out during the Socratic walk; all three implemented + tested.
  - **Forward-compat for line items reserved**: future amendments adding BG-25 evaluation don't break existing pilot-#13 call sites.
  - **XRECHNUNG corpus drift surfaced + characterized**: pilot #13's eval harness has explicit guidance; future Cascades won't be confused by silent 2018-vs-2024 date mismatches.
  - **40 new tests, all passing, full corpus exercised**: parametrized over 22 EN16931 + 4 XRECHNUNG fixtures; PR(b) + PR(c) inherit a strong regression-test substrate.
  - **`tests/conftest.py` centralizes corpus paths**: future test modules reuse `EINFACH_PDF` / `EINFACH_CII` / `ZUGFERD_CORPUS_DIR` constants; corpus path drift is now a one-file change.
- **Negative**:
  - **16-field-only scope** means line-item extraction quality is unmeasured in pilot #13. The plan locked this scope deliberately (test matrix tractability + DocILE-aligned methodology); a future ADR amendment will lift it if the thesis writeup demands.
  - **English-keyed dict requires PR(b) to maintain a German-label / variant-name → english_key resolver**: small adapter layer downstream, but real work. Mitigation: the `FIELDS` registry exposes `german_label` per row so the resolver has a canonical mapping table to seed from.
  - **XRECHNUNG corpus drift requires PR(c) awareness**: not a code-level fix, but documentation discipline. The pinned test asserts the drift pattern; if FeRD re-aligns, the assertion fires and PR(c)'s guidance can be relaxed.
  - **No address fields, no per-VAT-rate, no charge/allowance/prepaid** — F1 heatmap will not cover those dimensions in pilot #13. Same lifting path as line items (additive amendment).
- **Neutral**:
  - The 5-section ADR discipline (per `horus-decision-discipline`) was followed; this ADR retroactively ratifies the Socratic-walk outcome with the same honest light-ADR clause used in ADR-010 + ADR-011.
  - **`make test` runtime impact**: +40 tests, full project test runtime stayed at ~17s (negligible — most new tests are XPath ops on small XML byte strings; the parametrized corpus sweep dominates and is still <2s).
  - **New `eval/` subpackage**: HORUS now has `horus.eval.*` namespace; PR(b) + PR(c) will populate it with `scorer.py` and `harness.py` modules.

## Related ADRs

- **`docs/decisions/ADR-001-tool-decision-discipline.md`** — Mandates the 5-section ADR shape this document follows.
- **`docs/decisions/ADR-002-source-archival.md`** — Requires every cited source archived under `docs/sources/`; this ADR adds 3 new stubs (e-invoice.be mapper, B2BRouter docs, arXiv 2510.15727).
- **`docs/decisions/ADR-005-zugferd-tooling.md`** — Ratified `factur-x` (binder) + `fpdf2` (renderer) + Mustang (validator). `factur-x` extraction is this ADR's parser input.
- **`docs/decisions/ADR-009-vlm-cohort-smoke.md`** — Amendment 1 designated the embedded factur-x XML as pilot #13's ground truth; BT-29 + BT-72 are in this ADR's 16-field scope for continuity with the cohort smoke evidence base.
- **`docs/decisions/ADR-010-xml-extraction-script.md`** — Ratified the extraction route + 3-route C14N2 byte-equivalence. This ADR's Probe 2 strengthens the equivalence claim from byte-level to dict-level.
- **`docs/decisions/ADR-011-experiment-tracking.md`** — `Tracker.log_dict(...)` is how PR(c) will persist `GroundTruth` instances + per-field F1 results as MLflow artifacts.
- **Future ADR (PR(b))** — VLM output → predicted-dict scorer with per-field F1 computation. Will cite this ADR as the ground-truth substrate.
- **Future ADR (PR(c))** — Pilot #13 harness orchestrating cohort × corpus × scorer; will cite this ADR + the PR(b) ADR.

---

**End of ADR-012.**
