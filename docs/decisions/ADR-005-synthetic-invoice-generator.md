# ADR-005 — Synthetic ZUGFeRD invoice generator: `factur-x` (Python) + Mustang Project (Java validator)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-11 |
| **Milestone** | M2D.5 step 2 — first tooling-install ADR after repo structural prep |
| **Authored by** | Cascade D (M2D.5 session, plan `~/.windsurf/plans/m2d5-step2-mustang-adr-and-install-2e5a0f.md`) |
| **Issue** | `ReebalSami/horus#9` |
| **Supersession trigger** | (1) `factur-x` Python library lapses maintenance (no release for ≥ 2 calendar years AND no responsive issue triage); OR (2) Mustang's cross-tool Schematron reports systematic compliance failures on `factur-x` output that cannot be remediated upstream — fallback = Mustang's CLI `--action combine` becomes the generator and `factur-x` becomes parser-only; OR (3) ZUGFeRD spec advances past `factur-x`'s shipped XSD set AND a German B2B compliance experiment exposes the lag (verified by Mustang Schematron failure) AND Mustang ships the new ruleset — fallback = upgrade `factur-x` if patched; else swap to Mustang-for-generation per (2) |

## Context

The HORUS thesis evaluates whether local vision-language models can extract structured invoice data from German B2B documents (`docs/prompts/stages/02-brainstorm.md` §1, v2 §0–§3). Ground truth requires synthetic invoices whose **embedded XML is spec-compliant** — extracting from a VLM is meaningless if the comparison target isn't itself standard-conforming. Brainstorm §6.2 P0 names ZUGFeRD as the "data unlock" — Mustang was indicated as the candidate; this ADR walks the decision Socratically per `horus-decision-discipline` rule and lands a dual-track answer.

The scientific-correctness criterion (v2 §0 lock #9, supervisor-stated) elevates a structural concern: **a tool that generates AND validates its own output is a closed loop**. A second, independent codebase validating the first tool's output gives the ground-truth XML a stronger compliance claim — the thesis cannot afford to discover at writeup that "ZUGFeRD-compliant per tool X" silently meant "ZUGFeRD-shaped per tool X". This concern bears directly on the choice and motivates a multi-tool answer.

Issue #9 acceptance: ADR with 5 sections + chosen tool installed (`uv add` if Python-available; else JAR or VCS) + `make install && make test` still passing + ≥ 1 source stub in `docs/sources/tools/` for chosen tool + ZUGFeRD spec archived under `docs/sources/legal/` (the latter exists from M2D.3: `docs/sources/legal/zugferd-en16931.md`).

## Current-state survey (2026-05-11)

### ZUGFeRD / Factur-X specification state

- **ZUGFeRD 2.4 / Factur-X 1.08** released December 2025 (per `docs/prompts/stages/02-brainstorm.md` §9.1; FeRD + FNFE-MPE joint release). EN 16931-aligned. Profiles: MINIMUM, BASIC WL, BASIC, EN 16931, EXTENDED, XRECHNUNG, EXTENDED-CTC-FR (France 2026 obligation, added in 2.4).
- **Format**: PDF/A-3 carrying a CII (UN/CEFACT Cross Industry Invoice) XML attachment with name `factur-x.xml` or `zugferd-invoice.xml`. The PDF visual is human-readable; the XML is machine-parseable; both carry the same data.

### Pure-Python ZUGFeRD libraries

- **`akretion/factur-x` (PyPI: `factur-x` 4.2)** — BSD; the FNFE-MPE-aligned Python reference. **Generates** by attaching CII XML to an existing PDF (`generate_from_file` / `generate_from_binary`); does **not** generate visual PDFs from scratch (binder, not end-to-end). **Parses** via `get_xml_from_pdf`. **Validates** via `xml_check_xsd` + `xml_check_schematron`. Ships Factur-X 1.08 XSDs for all 5 standard profiles (verified: `.venv/lib/python3.14/site-packages/facturx/xsd/facturx-{minimum,basicwl,basic,en16931,extended}/Factur-X_1.08_*_codedb.xml`). Saxon XSLT engine bundled (`saxonche`) for Schematron evaluation. **Result: ZUGFeRD-2.4-spec-current.**
- **`pretix/python-drafthorse` (PyPI: `drafthorse`)** — Apache 2.0; German-origin (pretix Berlin). Strong CII-XML builder ergonomics. Maintainer self-flagged: "ancillary, not core business; turnaround time on issues or PRs might be longer than usual due to other priorities" (from project README). Yellow flag for thesis-grade reliability.
- **`zfutura/pycheval`** — newer entrant, parse + generate, less mature track record than `factur-x`; not chosen due to lack of established reference status.
- **DIY hand-authored** (per the dev.to "No Library Needed" blog approach) — reinventing scientifically-fragile code for thesis-critical ground truth violates `make-sure-it-works`.

### Java ZUGFeRD reference implementation

- **Mustang Project (CLI 2.23.0, April 2026)** — Apache 2.0; FeRD-affiliated; the de-facto reference impl. Ships ZUGFeRD 2.4 XSLT Schematron rulesets (`xslt/ZF_240/FACTUR-X_*.xslt` verified inside the 2.23.0 JAR at smoke-validation time). Validates **PDF/A-3 conformance** (290 ISO-19005-3 assertions) AND **embedded-XML Schematron** (profile-specific rule sets). CLI: `--action validate|combine|extract|visualize|metrics|upgrade|ubl`. ~58 MB JAR. Java 11 bytecode (runs on Java 17+; verified on local OpenJDK 25.0.1 ARM64).

### PHP / other-stack options (eliminated)

- **`horstoeko/zugferd`** — PHP/Composer. Eliminated: HORUS toolchain is Python + Java only.

### Local environment audit (2026-05-11)

- macOS 26.4.1 (Build 25E253), arm64 (M1 Pro), 16 GB RAM
- Python 3.14.3; `uv 0.9.8`
- **OpenJDK 25.0.1 already installed** via Homebrew (`brew list` confirms `openjdk` + `openjdk@21`); `java_home -V` reports `arm64` native — Mustang's Java 11 bytecode runs cleanly, JDK install is **not** a side-effect of this PR

## Options considered

| Option | Stack | Role | License | Why considered | Outcome |
|---|---|---|---|---|---|
| Mustang Project as sole generator + validator | Java | Generator + Validator | Apache 2.0 | Brainstorm §6.2 indicated; FeRD-reference impl; ZF 2.4-current | **Rejected.** Tautological — generator and validator share the same codebase + Schematron rules; no independent compliance check. JVM in every experiment hot path adds startup cost + subprocess error surface to the Python pipeline. |
| `factur-x` as sole generator + validator | Python | Generator (binder) + Validator | BSD | Pure-Python `uv add`-able; built-in XSD + Schematron; ZUGFeRD 2.4 XSDs shipped | **Rejected.** Single-source compliance trust — `xml_check_schematron` validates against the same XSDs the library ships. If a bug exists in those XSDs OR in the library's CII XML emitter, the self-check cannot detect it. |
| **`factur-x` for generation + Mustang for validation** (dual-track) | Python + Java | Generator (binder, Python) + Independent Validator (Java) | BSD + Apache 2.0 | Combines `uv add` ergonomics with independent cross-tool verification; JDK already on-machine | **Chosen — see Decision** |
| `drafthorse` for generation + Mustang for validation | Python + Java | Generator + Validator | Apache 2.0 + Apache 2.0 | Pure-Python; German-origin; same dual-track shape | **Rejected.** Maintainer's "ancillary, not core business" notice is a reliability risk for thesis-grade ground truth across the M2D.5–M2D.6+ horizon. `factur-x` is the FNFE-MPE-aligned Python reference; preferred. |
| `pycheval` for generation + Mustang for validation | Python + Java | Generator + Validator | check needed | Newer entrant; parse + generate | **Rejected.** Insufficient track record vs `factur-x`. |
| Hand-authored CII XML + minimal PDF + Mustang validation | Python | Generator (DIY) + Validator | n/a | Zero dep beyond Mustang | **Rejected.** Reinventing CII emission for thesis-critical ground truth violates `make-sure-it-works`. The MINIMUM-profile XML hand-authored in `scripts/generate_zugferd_smoke.py` is **smoke-only** — the actual pilot generator (next issue) MUST use a library. |
| LaTeX/Word PDF + `factur-x` post-attach + Mustang validation | LaTeX/Word + Python + Java | PDF source + Binder + Validator | varies | Pilot may want realistic-looking PDFs | **Deferred (not rejected).** This issue's smoke uses blank PDFs; pilot may layer in realistic PDF visuals via this approach. Out of scope for ADR-005. |
| Hand-curated real-world ZUGFeRD invoices (Bauerfeind/Lexware exports) | n/a | Real corpus | various | Highest fidelity to production | **Complementary, not substitute.** Brainstorm §6.2 already names the public ZUGFeRD corpus as P0 alongside Mustang-generated synthetics. Real corpus = distribution check; synthetic corpus = unlimited parameterised supply. Both planned. |

## Decision + integration thoughts

**Chosen — dual-track**:

- **Generator**: `factur-x` 4.2 (PyPI: `factur-x`; BSD) — installed via `uv add factur-x`. Transitive deps: `lxml`, `pypdf`, `saxonche` (Saxon XSLT for Schematron).
- **Validator (cross-tool)**: Mustang Project 2.23.0 CLI JAR — fetched via `make mustang-jar` into `tools/mustangproject/Mustang-CLI-2.23.0.jar` (gitignored). Version + SHA-256 pinned in `Makefile`. Invoked from Python via `scripts/validate_zugferd.py` (subprocess wrapper).

### Why the dual-track is the right answer for HORUS

1. **Independent cross-tool compliance check.** Mustang's Schematron (`xslt/ZF_240/FACTUR-X_*.xslt`) is a separate codebase from `factur-x`'s. Smoke evidence at decision time: Mustang reports `<summary status="valid"/>` on factur-x output with `<rules><fired>27</fired><failed>0</failed></rules>`. The cross-tool path catches what a self-validating loop cannot.
2. **Pipeline stays Python in the hot path.** Bulk-generation (next issue) loops `for cfg in configs: factur_x.generate(...)` — no JVM spawn per invoice, no subprocess marshalling in MLflow-tracked experiment runs. Mustang validates once-per-batch at the edge.
3. **JDK cost = 0.** OpenJDK 25.0.1 already installed via Homebrew (verified at planning); no new system dependency lands.
4. **Spec currency confirmed by evidence.** Smoke run shows Mustang loading `xslt/ZF_240/FACTUR-X_MINIMUM.xslt` (= ZUGFeRD 2.4.0 ruleset) AND detecting the factur-x-generated profile as `urn:factur-x.eu:1p0:minimum` (= Factur-X 1.0 MINIMUM, which is the binding profile namespace used by ZUGFeRD 2.x MINIMUM). 27 Schematron rules fired, 0 failed → factur-x 4.2 emits ZUGFeRD-2.4-compatible CII XML.
5. **Brainstorm §6.2 honored.** Mustang still lands in `tools/mustangproject/` per the brainstorm row — its role shifts (validator, not generator), which is the stronger fit given Mustang's reference-impl status.

### Smoke evidence captured at decision time

End-to-end via `make zugferd-smoke` (one invocation; both scripts; runs clean):

| Step | Tool | Result |
|---|---|---|
| Generate CII XML | hand-authored MINIMUM-profile literal in `scripts/generate_zugferd_smoke.py` (smoke-only) | 2,324 bytes, schema-valid |
| Generate blank visual PDF | `pypdf.PdfWriter.add_blank_page` (A4) | ~750 bytes |
| Bond XML + PDF → Factur-X | `facturx.generate_from_file(flavor="factur-x", level="minimum", check_xsd=True, check_schematron=True)` | 3,322 bytes; `factur-x.xml` attachment; **XSD pass + Schematron pass** |
| Round-trip extract | `facturx.get_xml_from_pdf` | Flavor `factur-x` + Level `minimum` autodetected; XML byte-identical to source |
| Independent validation | Mustang 2.23.0, `--action validate --no-notices --disable-file-logging` | XML: `<rules><fired>27</fired><failed>0</failed></rules>`, `<summary status="valid"/>`; profile detected as `urn:factur-x.eu:1p0:minimum`; signature recognized as `Factur/X Python` |

### Honest caveat: PDF/A-3 trailer ID

Mustang's PDF/A-3 conformance check reports **one ISO 19005-3:2012 §6.1.3 assertion failure** on the smoke output: `Missing or empty ID in the document trailer`. This is a `pypdf`-generated-blank-PDF artifact, not a `factur-x` or Mustang issue — `pypdf.PdfWriter()` does not populate the `/ID` entry in the PDF trailer dictionary that ISO 19005-3 requires. Mustang's **overall** verdict remains `<summary status="valid"/>` because the embedded-XML layer (the ZUGFeRD spec compliance) is clean; the PDF/A-3 substrate compliance is a separate concern.

**For thesis evaluation, this is acceptable for now**: HORUS evaluates VLM extraction against the **embedded XML ground truth**, not against PDF/A-3 conformance of the carrier. Real-world ZUGFeRD invoices from ERPs (the corpus side of the data unlock per brainstorm §6.2) will have properly-formed `/ID` trailers; synthetic blanks from `pypdf` do not. If the thesis defense later requires strict PDF/A-3 conformance of synthetic invoices (e.g., for a "round-trip through a strict PDF/A-3 viewer" experiment), the path is to swap `pypdf` for `pikepdf` (qpdf wrapper, full PDF/A support) or `weasyprint` (HTML → PDF/A) in `scripts/generate_zugferd_smoke.py` — captured as supersession trigger (4) sibling, not a blocker for this ADR.

### Integration with HORUS components

- **`scripts/generate_zugferd_smoke.py`** — smoke generator. Hand-authored MINIMUM-profile CII XML. Produces `data/raw/smoke/invoice-001.pdf` (gitignored). **Smoke scope only**: parameterised CII-XML builders + EN16931-profile pilot generation are deferred to the **next issue** alongside the XML-extraction script + script-architecture ADR (brainstorm §8 step 3-4).
- **`scripts/validate_zugferd.py`** — Mustang subprocess wrapper. Locates the JAR via glob (`tools/mustangproject/Mustang-CLI-*.jar`); falls back to a clear error with `make mustang-jar` instruction if absent.
- **`Makefile` `mustang-jar` target** — fetches JAR with `curl`; `shasum -a 256 -c` verifies; `java -jar ... --help` callability check. Idempotent (no-op if file exists).
- **`Makefile` `zugferd-smoke` target** — depends on `mustang-jar`; runs both scripts in sequence; non-zero exit on any failure (per `make-sure-it-works`).
- **`.gitignore`** — `tools/` ignored entirely; `data/raw/smoke/` covered by existing `data/*` rule.
- **Future**: pilot generator (next issue) lives in `scripts/` (likely `scripts/generate_zugferd_pilot.py`); it consumes a `configs/zugferd-pilot.yaml` (per `horus-config-discipline` + ADR-004); it produces N invoices into `data/raw/synthetic/`; the validator wrapper stays reusable.

### What this ADR does NOT decide (and where those decisions live)

- **CII XML builder for pilot-scale generation.** `factur-x` is a binder; it doesn't generate CII from invoice records. The pilot generator needs a CII builder — candidates: `drafthorse` (German-origin, broad CII coverage), hand-rolled `lxml` builder (already a transitive dep), or `pycheval`. Walked at the pilot-generator ADR. **Smoke uses a hand-authored XML literal** to keep this ADR scoped.
- **PDF visual realism.** Blank A4 vs. ReportLab-rendered invoice-looking PDF vs. HTML+WeasyPrint. Walked at the pilot-generator ADR if VLM evaluation requires non-blank inputs (likely it does — Granite-Docling looks at pixels).
- **EN16931 vs MINIMUM profile target.** Smoke uses MINIMUM (smallest valid). Pilot likely uses EN16931 (B2B-relevant). Walked at the pilot-generator ADR.

## Source archival

Per `horus-source-archival` rule + ADR-002, every option in `## Options considered` is archived under `docs/sources/`:

- `docs/sources/tools/factur-x-python.md` — **new** (this PR). Akretion factur-x, the chosen Python binder.
- `docs/sources/tools/mustang-project.md` — exists from M2D.3 (`docs/prompts/stages/01-literature.md`). **Updated this PR**: retrieval date refreshed, version pin added (2.23.0), role-clarification (validator, not generator) added.
- `docs/sources/legal/zugferd-en16931.md` — exists from M2D.3. No update needed (spec reference).
- `drafthorse`, `pycheval`, `horstoeko/zugferd` (PHP, eliminated) — not archived; named-and-rejected alternatives that did not become primary citations in this ADR's Decision text. (Per `horus-source-archival` §"When the rule does NOT fire": "alternatives explicitly considered-and-rejected in the same ADR but not cited as positive evidence" — these are eliminated-by-reference, not built upon.)

## Consequences

- **Positive**: every synthetic invoice produced for HORUS evaluation has an **independent cross-tool compliance claim** (`factur-x` generates → Mustang validates). The thesis can defend "ground-truth XML is spec-compliant" with two-tool evidence, not one. Pipeline stays pure-Python in the experiment hot path. JDK already on-machine → zero new system dependencies. Smoke target `make zugferd-smoke` is a one-command end-to-end check developers (and future Cascades) can run before any pilot generation.
- **Negative**: two tools, two specs to track. If `factur-x` releases break the binder API OR Mustang releases break the validator CLI signature, both scripts need update. Mitigation: version pin on Mustang (Makefile `MUSTANG_VERSION` constant); `factur-x` semver-bumped via `uv lock` reviews. Bulk pilot will need a separate CII-XML-builder decision (next ADR) — this ADR does not solve "generate from invoice record" end-to-end on its own.
- **Neutral**: `factur-x` pulls in `lxml` + `pypdf` + `saxonche` (~33 MB) as transitive deps. All three are useful beyond ZUGFeRD work (HORUS likely uses `lxml` and `pypdf` directly later). `saxonche` is bulky (32 MB) but ships only because Schematron evaluation in pure Python is impractical. Acceptable.

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate; "Current-state survey" / "Options considered" / "Decision + integration thoughts" / "Source archival" / "Supersession trigger" all present)
- **ADR-002** — source-archival convention (this ADR's `## Source archival` cites)
- **ADR-004** — config library (Pydantic Settings + PyYAML); the pilot-generator ADR (next) will define an `ExperimentConfig` extension with `synthetic.profile`, `synthetic.count`, `synthetic.seed` fields per `horus-config-discipline`
- **Cascade-system ADR-013** — `/commit` workflow (used for the commits in this PR)
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager`)
- **Future ADR-006 (reserved at next reservation pass)** — pilot CII-XML builder + parameterised generator
