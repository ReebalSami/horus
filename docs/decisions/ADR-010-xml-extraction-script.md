# ADR-010 — ZUGFeRD XML-extraction script: `factur-x` (canonical engine) + Mustang `--action extract` (opt-in cross-check)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-16 |
| **Milestone** | `experiments-validated` (pilot #13's XML-grounded F1 evaluation harness substrate) |
| **Authored by** | Cascade D (issue #15 implementation session; plan `~/.windsurf/plans/horus-issue-15-xml-extraction-31be03.md`) |
| **Issue** | `ReebalSami/horus#15` (sub of `#13`) |
| **Supersession trigger** | (1) `factur-x` Python library lapses maintenance (no release for ≥ 2 calendar years AND no responsive issue triage) → fallback to direct `pypdf` + hand-rolled namespace/filename validation; OR (2) Mustang's `--action extract` output diverges systematically from `factur-x`'s output AND from the FeRD-shipped `.cii.xml` sidecar on ≥ 3 distinct corpus fixtures → triage which route is wrong, supersede the wrong one; OR (3) the FeRD ZUGFeRD spec adds a new attachment-filename slot beyond `factur-x.xml` / `zugferd-invoice.xml` / `ZUGFeRD-invoice.xml` / `order-x.xml` AND `factur-x`'s `ALL_FILENAMES` list does not pick it up → upgrade `factur-x` or extend the wrapper to inspect the PDF's `/Names /EmbeddedFiles` directly; OR (4) pilot #13's evaluation harness demonstrates that XML-grounded F1 is not the right primary metric (e.g., requires structured-token F1 instead) → ADR-010 stays as ratification of XML *extraction*, the metric ADR supersedes the *use* of extracted XML downstream |

## Context

The HORUS thesis (`docs/prompts/stages/02-brainstorm.md` v2 §3 D8 + §5.1 + §5.5) evaluates whether **local vision-language models** (VLMs) can extract structured invoice fields from German B2B documents (`Steuerberater` / `Wirtschaftsprüfer` / `Anwälte` workflow) by looking only at the visual layer. To score a VLM's predictions, the experiment needs an authoritative ground-truth — and the ZUGFeRD / Factur-X invoice format provides exactly that, by design.

### What ZUGFeRD is, and why its design is methodologically privileged for this thesis

ZUGFeRD (*Zentraler User Guide des Forums elektronische Rechnung Deutschland*) is the German binding of the Franco-German **Factur-X** e-invoicing standard. Both names refer to the same artifact shape: a **PDF/A-3 file with an embedded XML attachment**. The PDF carries a human-readable visual invoice as A4 pages; the embedded XML attachment (typically named `factur-x.xml`, `zugferd-invoice.xml`, or `ZUGFeRD-invoice.xml`) carries the same invoice data in **UN/CEFACT Cross Industry Invoice (CII)** structured form — invoice ID, dates, line items, tax breakdown, totals, party identifiers. **The two layers carry the same data**: that is the spec's central property, codified by EN 16931, and the entire reason ZUGFeRD is the right substrate for HORUS's H1 / H2 experiment.

The thesis hypothesis is: a VLM, presented only with the visual layer (rasterized to pixels), can extract structured fields that match the embedded XML's content. The experiment closes only when the VLM's predictions are scored against the XML. Without extracted XML, there is no F1 score, no error heatmap, no answer to the research question. **This script is the ground-truth producer.**

### Why this evaluation framework is scientifically defensible (and why we picked ZUGFeRD over alternatives)

Five properties make ZUGFeRD uniquely well-grounded for thesis-grade VLM evaluation:

1. **The XML is an authoritative answer key, not a derivative one.** It is not LLM-generated, not human-annotated post-hoc, not crowdsourced. It is the *primary* representation of the invoice, signed off by the same business process that produced the PDF visual. There is no circularity risk in the form "the model that generated the ground truth scored the model we're evaluating."

2. **The XML is standards-body validated.** XSD + Schematron checks ship with `factur-x` (FNFE-MPE-aligned, Akretion-maintained) and an independent Java reference impl (Mustang Project, FeRD-affiliated) provides cross-tool validation. The thesis can claim "ground truth conforms to EN 16931" with two-tool independent evidence — not "ground truth is what we say it is." Same dual-track discipline ADR-005 established for synthetic-invoice generation.

3. **ZUGFeRD is the dominant German B2B e-invoice format.** Mandatory B2B e-invoicing in Germany has been in force since 2025-01-01 (federal `Wachstumschancengesetz`); ZUGFeRD + XRechnung are the two accepted formats. HORUS's target users handle these daily — relevance to the thesis's stated stakeholder (`AGENTS.md` §1) is direct, not derivative.

4. **FeRD ships a substantial pre-built corpus.** 22 EN16931 PDFs + 5 XRECHNUNG PDFs (each with a paired standalone `.cii.xml` sidecar) + dozens of ZUGFeRDv1 PDFs are already on disk under `data/raw/german/zugferd-corpus/` (acquired per issue #12 closure). Pilot #13 has n ≥ 27 without generating a single synthetic invoice. The standalone sidecars are particularly valuable: they constitute a **third independent ground-truth route** alongside `factur-x` and Mustang, since FeRD authored them separately from the embedded XML attachment.

5. **Cross-tool spec-validation is free.** Mustang is already installed (`tools/mustangproject/Mustang-CLI-*.jar` via `make mustang-jar` per ADR-005). It can validate that any extracted XML is itself spec-compliant via `--action validate`, and provide an independent extraction route via `--action extract`. No new tooling is needed for the cross-check.

### Pilot #13 dependency — this script is load-bearing infrastructure

ADR-009 Amendment 1 (2026-05-15, mid-sprint per cascade-system ADR-018 precedent) explicitly designates the embedded factur-x XML as the **authoritative ground truth** for pilot #13's evaluation:

> "1. **Authoritative ground truth is the embedded factur-x XML** of `EN16931_Einfach.pdf`. Two routes give identical content: (a) `facturx.get_xml_from_pdf(...)` — the canonical Python route for any factur-x PDF; (b) the parallel standalone sidecar `data/raw/german/zugferd-corpus/XML-Rechnung/CII/EN16931_Einfach.cii.xml` shipped by FeRD alongside the PDF."
> — `docs/decisions/ADR-009-pilot-vlm-cohort.md` §"Note on evidence limitations (Amendment 1)"

And §"Cross-Cat field-level comparison" §5 of the same amendment:

> "Pilot #13's first eval-harness design constraint should be uniform quantization + XML-grounded F1 + multi-substrate (full ZUGFeRD corpus, not just `EN16931_Einfach.pdf`)."

`scripts/extract_zugferd_xml.py` is the *XML-grounded* substrate of "XML-grounded F1." Without it, pilot #13 cannot proceed past the cohort-smoke stage to actual evaluation.

### The pipeline this script enables

```
   ZUGFeRD PDF        ── rasterize (sips) ─→   page-N PNG ─→  VLM extract  ─→  predicted fields
        │                                                                            │
        │                                                                            ▼
        └── extract_zugferd_xml.py ─→ embedded XML ─→ (parse fields)  ─→  ground-truth fields
                                                                                     │
                                                                                     ▼
                                                                            F1 / heatmap (pilot #13)
```

This ADR + script is the **upper-right corner** — the answer-key producer. The lower-right corner (parse CII XML into a flat field dict) and the right-hand merge (compute F1 / error heatmap from predicted vs ground-truth fields) live in pilot #13's evaluation-harness sub-issue, downstream of this work.

## Current-state survey (2026-05-16) — what HORUS already has installed for this work

This section exists specifically as a **discoverability artifact**: future readers of any ZUGFeRD-related ADR have one place to find the answer to "what's already in the project for this?" without chasing through ADR-005 + ADR-006 + ADR-009 amendments.

| Component | Where | Ratified by | Role for this issue |
|---|---|---|---|
| `factur-x>=4.2` (Python, PyPI) | `pyproject.toml:15`; usage at `scripts/generate_zugferd_smoke.py:175` | ADR-005 §"Decision" | **Primary engine for this ADR.** `facturx.get_xml_from_pdf(pdf_bytes) -> (filename, xml_bytes)`. Built-in XSD + Schematron validation. Profile + flavor autodetection. Wraps `pypdf` internally (`.venv/lib/python3.14/site-packages/facturx/facturx.py:34`). |
| `pypdf` (transitive of `factur-x`) | pulled in by `factur-x` | ADR-005 (transitive) | Low-level PDF I/O. Never called directly by HORUS code; `factur-x` is always the public-API surface. |
| `lxml` (transitive of `factur-x`) | pulled in by `factur-x` | ADR-005 (transitive) | XML parsing + canonicalization. Already used in `scripts/generate_zugferd_smoke.py` via `etree.fromstring`. This ADR adds `lxml.etree.tostring(..., method="c14n2")` for the cross-route equivalence assertion (see §"Decision" §"Empirical evidence"). |
| `saxonche` (transitive of `factur-x`) | pulled in by `factur-x` | ADR-005 (transitive) | Saxon XSLT engine used internally by `factur-x` for Schematron evaluation. ~32 MB; not invoked directly. |
| Mustang Project 2.23.0 CLI (Java) | `tools/mustangproject/Mustang-CLI-*.jar` (gitignored) via `make mustang-jar`; wrapper at `scripts/validate_zugferd.py` | ADR-005 §"Decision" | **Cross-check route for this ADR (opt-in).** `--action extract` gives an independent Java-side extraction; `--action validate` validates spec compliance (already wired in `validate_zugferd.py`). ~1–2 s JVM startup. |
| FeRD ZUGFeRD corpus | `data/raw/german/zugferd-corpus/XML-Rechnung/FX/*.pdf` (PDF with embedded XML attachment) + `data/raw/german/zugferd-corpus/XML-Rechnung/CII/*.cii.xml` (paired standalone sidecars from FeRD) | issue #12 acquisition; ADR-009 PR(a) smoke substrate | **Third independent ground-truth route for this ADR.** Sidecar XMLs are FeRD-shipped and byte-stable; tests assert content-equivalent extraction against them. |
| `EN16931_Einfach.pdf` smoke fixture | `data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf` (paired with `…/CII/EN16931_Einfach.cii.xml`) | ADR-009 PR(a) | Cohort-smoke substrate from ADR-009; this ADR's primary happy-path test fixture. |
| `RE-E-974-Hetzner_2016-01-19_R0005532486.pdf` non-ZUGFeRD fixture | `data/raw/german/zugferd-corpus/unstructured/RE-E-974-Hetzner_2016-01-19_R0005532486.pdf` | issue #12 acquisition; in `unstructured/` subdir (no embedded XML attachment) | This ADR's no-attachment test fixture; verified during implementation that `facturx.get_xml_from_pdf` returns `(False, False)` and logs a `WARNING` on it (does NOT raise). |

The decision in this ADR is therefore **substantially overdetermined** by what is already installed and working. The §"Options considered" walk below is preserved for the 5-section discipline mandate per `horus-decision-discipline`, but is honest about the post-hoc-ratification shape: the same library that ADR-005 ratified as the *generator* is also the canonical *extractor*; the same Mustang JAR that ADR-005 ratified as the cross-tool *validator* (`--action validate`) is also the cross-tool *extractor* (`--action extract`); the same FeRD corpus that issue #12 acquired provides a third independent extraction route via its standalone sidecars.

## Options considered

| Option | Stack | Role | Outcome |
|---|---|---|---|
| **`factur-x` (Akretion / Alexis de Lattre)** | Python (BSD) | Canonical extraction engine | **Chosen as primary engine — see Decision.** Already in `pyproject.toml`; already used at `scripts/generate_zugferd_smoke.py:175` for round-trip extraction in the synthetic-invoice smoke; FNFE-MPE-aligned (the body that co-publishes the Factur-X spec with FeRD); ships built-in XSD + Schematron checks; handles all factur-x / zugferd / order-x attachment-filename slots. Choosing anything else would require an ADR justifying *why* we abandoned a working installed library — and no such justification exists. |
| **Mustang Project `--action extract`** | Java (Apache 2.0) | Independent cross-check route | **Chosen as opt-in cross-check (not primary) — see Decision.** Already installed per ADR-005 (`tools/mustangproject/Mustang-CLI-*.jar`). Provides independent-codebase extraction proof for ADR-009 Amendment 1's "two routes give identical content" claim. JVM startup cost (~1–2 s) makes it inappropriate as the per-call hot path; reserved for opt-in verification (`--cross-check-mustang` flag) consistent with ADR-005's "Mustang validates once-per-batch at the edge" design. |
| **FeRD `.cii.xml` sidecar (third route)** | n/a — pre-shipped corpus data | Cross-corpus ground-truth verification | **Adopted for test assertions, not the script's runtime.** FeRD ships standalone `.cii.xml` files next to every EN16931 + XRECHNUNG PDF in `data/raw/german/zugferd-corpus/XML-Rechnung/CII/`. Tests assert C14N2-canonical equivalence between `facturx.get_xml_from_pdf` output and the FeRD sidecar on the `EN16931_Einfach.pdf` fixture, validating three-route agreement. Not runtime-consumed because the script accepts arbitrary PDFs; sidecars exist only for the EN16931 + XRECHNUNG corpus subdirs. |
| `pypdf` alone | Python (BSD) | DIY extractor | **Rejected — category error.** `factur-x` wraps `pypdf` internally for PDF I/O (`from pypdf import PdfWriter, PdfReader` at `.venv/lib/python3.14/site-packages/facturx/facturx.py:34`). Using `pypdf` directly drops factur-x's filename validation (`factur-x.xml` / `zugferd-invoice.xml` / `ZUGFeRD-invoice.xml` / `order-x.xml`), profile autodetection (MINIMUM / BASIC / EN16931 / EXTENDED / BASIC WL), embedded XSD validation, and Schematron checks. Reproducing those by hand is non-trivial work to fight a wrapper we already depend on transitively. |
| `pikepdf` | Python (MPL-2.0) — wraps QPDF (C++) | Alternative PDF library | **Rejected — strong-candidate status in issue #15 body is stale.** The issue body was authored before ADR-005 ratified `factur-x`. `pikepdf` is not in `pyproject.toml`; adopting it would add a ~10 MB QPDF C++ build dependency for zero factur-x-specific value. It does not handle the factur-x attachment-filename slot conventions, profile detection, or XSD/Schematron checks any better than `factur-x` (which sits one abstraction layer above it anyway). |
| `pdfplumber` | Python (MIT) | Layout extraction | **Eliminated by reference — wrong category.** Designed for visual layout extraction (table detection, bounding boxes, text positioning). Has no embedded-file extraction story. Mentioned in the issue body for completeness; not a serious candidate. |
| `qpdf` CLI | C++ binary, shell-out | Command-line PDF tool | **Eliminated by reference — coupling thesis to a system binary.** `qpdf --list-attachments` + `qpdf --extract-attachment` could extract embedded XML, but requires the binary to be on `PATH` everywhere the script runs. Mentioned in the issue body for completeness; rejected on the same grounds ADR-005 rejected non-Python tools. |
| Mustang `--action extract` as **sole** extractor (no Python primary) | Java | Single-tool extraction | **Rejected — JVM in the pilot-#13 hot path.** Pilot #13 will call this script 20–50 times (one per corpus PDF). Mustang's ~1–2 s JVM startup × 50 = ~75 s of overhead vs `factur-x`'s ~50 ms × 50 = ~3 s. ADR-005 explicitly designed Mustang as a once-per-batch validator — using it as the per-call extractor breaks that design discipline. |
| `pycheval` (zfutura) | Python | Newer entrant | **Eliminated by reference.** ADR-005 already rejected `pycheval` on track-record grounds ("Insufficient track record vs `factur-x`"); status unchanged here. |
| `factur-x-ng` / `invoice-x` forks (PhE / cnfilms / invoice-x) | Python | Akretion forks | **Eliminated by reference — stale.** Upstream akretion is the maintained line; forks have not seen activity in ≥ 2 years per their GitHub repos (verified during planning web search 2026-05-16). |
| `horstoeko/zugferd` | PHP/Composer | PHP library | **Eliminated by reference — stack mismatch.** HORUS toolchain is Python + Java only per ADR-005 §"Options considered". |
| `facturx-pdfextractxml` upstream CLI as-is (no HORUS wrapper) | Python | factur-x's bundled CLI | **Considered, rejected as the shipped artifact.** Upstream ships a 104-LOC argparse wrapper at `.venv/lib/python3.14/site-packages/facturx/scripts/pdfextractxml.py`. It is functionally adequate but exits **1** when no attachment is found — incompatible with issue #15's acceptance criterion ("PDF with no embedded XML → skip + log warning", which requires exit 0). Its default output path is also caller-mandatory rather than sidecar-conventional. HORUS wraps it (adds 4 behavioral deltas — see §"Decision" §"Why a wrapper, given the upstream CLI exists") rather than replacing it; the upstream CLI remains as a reference / fallback path. |

## Decision + integration thoughts

> **Honest light-ADR clause** (per `be-honest-direct-critical`): this ADR retroactively ratifies what is already in production rather than walking an open design space. The `factur-x` library was selected and installed by ADR-005 (2026-05-11), is already used at `scripts/generate_zugferd_smoke.py:175` for round-trip extraction in the synthetic-invoice smoke, and is the FNFE-MPE-aligned Python reference implementation. The 5-section discipline per `horus-decision-discipline` is preserved; the §"Options considered" walk above is documented for completeness and discoverability, not because the decision was genuinely contested. This mirrors ADR-005's "factur-x for generation" decision shape.

### Chosen

- **Primary extraction engine**: `factur-x` 4.2 (PyPI: `factur-x`; BSD; Akretion / Alexis de Lattre). API: `facturx.get_xml_from_pdf(pdf_bytes, check_xsd=True, check_schematron=True) -> (filename_or_False, xml_bytes_or_False)`.
- **Opt-in cross-check route**: Mustang Project 2.23.0 CLI, `--action extract` (with `--source <pdf>`). Invoked via subprocess from the script's `--cross-check-mustang` flag handler. Reuses the JAR-location pattern from `scripts/validate_zugferd.py` (`tools/mustangproject/Mustang-CLI-*.jar` glob).
- **Cross-corpus assertion in tests**: C14N2 canonical-XML equivalence between `facturx.get_xml_from_pdf` output and the FeRD-shipped `.cii.xml` sidecar on `EN16931_Einfach.pdf`. Validates the three-route ground-truth claim end-to-end.

### Script: `scripts/extract_zugferd_xml.py`

```text
usage: extract_zugferd_xml.py [-h] [--no-validate] [--cross-check-mustang]
                              [--log-level {debug,info,warn,error}]
                              input_pdf [output_xml]

Extract the embedded factur-x / ZUGFeRD XML attachment from a PDF/A-3 invoice.

positional arguments:
  input_pdf              Path to the input ZUGFeRD / Factur-X PDF.
  output_xml             Path to the output XML sidecar (default:
                         <input>.cii.xml next to the input PDF; matches
                         FeRD corpus convention).

optional flags:
  --no-validate          Skip factur-x's built-in XSD + Schematron checks
                         (default: validate).
  --cross-check-mustang  Also run Mustang --action extract and assert
                         C14N2-canonical equivalence with factur-x's
                         extraction. Requires the JAR (make mustang-jar).
  --log-level LEVEL      info | debug | warn | error (default: info).
```

Behavior contract — single source of truth for the test matrix:

| Input shape | Behavior | Exit code |
|---|---|---|
| Valid ZUGFeRD / Factur-X PDF with embedded XML | Extract via `facturx.get_xml_from_pdf`; write to sidecar; log profile + flavor + bytes-written | **0** |
| PDF with no embedded factur-x XML | `facturx.get_xml_from_pdf` returns `(False, False)` and logs an internal WARNING. The wrapper detects the falsy return, logs `"No factur-x XML attachment found in <path>; skipping (not an error)"`, does NOT write the output file. **Exit 0** — this is the issue #15 acceptance-criterion "skip + log warning" path. | **0** |
| Path is not a file / does not exist | Clear stderr error; no partial output written | **1** |
| Path exists but is not a valid PDF (factur-x raises) | Catch the exception, print a clear stderr message ("failed to parse PDF: <reason>"), no partial output written | **1** |
| `--cross-check-mustang` set but JAR absent | Clear stderr error pointing at `make mustang-jar`; no extraction attempted | **2** |
| `--cross-check-mustang` set and the two routes' XMLs C14N2-disagree | Print a diff summary to stderr; partial output (factur-x's extraction) IS still written to the sidecar (so debugging artefacts are preserved) | **3** |

### Sidecar-path convention

When `output_xml` is omitted, the wrapper writes to `<input>.cii.xml` next to the input PDF (e.g., `EN16931_Einfach.pdf` → `EN16931_Einfach.cii.xml`). Rationale:

- **Matches the FeRD corpus convention exactly.** The shipped sidecars at `data/raw/german/zugferd-corpus/XML-Rechnung/CII/*.cii.xml` use this naming. Pilot #13's eval harness can glob `*.cii.xml` and obtain both FeRD-shipped and HORUS-extracted ground-truth XMLs with identical discovery code.
- **Semantically accurate.** The XML's root element is `rsm:CrossIndustryInvoice` — CII is *literally what the XML is*, regardless of which PDF attachment-filename slot held it (`factur-x.xml` / `zugferd-invoice.xml` / `ZUGFeRD-invoice.xml` are all PDF/A-3 attachment slot conventions; CII is the content format).
- **Generalizes to ZUGFeRDv1.** Older v1 PDFs name their attachment `ZUGFeRD-invoice.xml`; the `.cii.xml` output convention works regardless.

### Why a wrapper, given the upstream CLI exists

`factur-x` ships `facturx-pdfextractxml` (104 LOC at `.venv/lib/python3.14/site-packages/facturx/scripts/pdfextractxml.py`). The HORUS wrapper adds four behavioral deltas, each tied to a specific HORUS need:

1. **No-attachment graceful skip (exit 0, not 1).** Upstream exits 1 on missing attachment; HORUS treats it as a skip case per issue #15's acceptance criterion. This is the key value-add.
2. **Sidecar-path default.** Upstream requires the output path; HORUS defaults to `<input>.cii.xml` for FeRD-corpus-glob compatibility.
3. **Opt-in three-route cross-check.** `--cross-check-mustang` adds the Mustang `--action extract` independent verification; not in upstream.
4. **HORUS code-style alignment.** Same shape as `scripts/validate_zugferd.py` (REPO_ROOT resolution via `__file__`, subprocess wrapper conventions, clear stderr error messages); future-Cascade-readable; consistent with the existing `scripts/` directory's idioms per `scripts/README.md`.

The upstream `facturx-pdfextractxml` remains available via the venv (`uv run facturx-pdfextractxml`) as a reference / fallback. Not removed, not shadowed.

### Empirical evidence captured at decision time

Probed during this PR's authoring session (2026-05-16, against the on-disk corpus). Documented here so the choice of canonical-XML comparison in tests is traceable to evidence, not preference.

**Probe 1 — Two-route extraction byte-agreement (factur-x vs Mustang) on `EN16931_Einfach.pdf`**:

```text
PDF                : data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf
PDF size           : 149,084 bytes
factur-x extraction : 13,396 bytes raw,  8,308 bytes after C14N2
Mustang  extraction : 13,396 bytes raw,  8,308 bytes after C14N2
Byte-equal raw?     : True   ← both extract the PDF attachment as-is
C14N2-equal?        : True   ← (trivially, since byte-equal)
```

**Finding**: factur-x and Mustang are **byte-identical** extractors when applied to the same PDF/A-3 attachment. Both produce the exact attachment bytes (CRLF line endings preserved, declarations preserved, ordering preserved). The two routes are functionally interchangeable for raw extraction; the cross-check exists as **independent-codebase verification of correctness**, not as a tie-breaker.

**Probe 2 — Three-route ground-truth agreement (factur-x vs FeRD `.cii.xml` sidecar) on `EN16931_Einfach.pdf`**:

```text
factur-x extraction : 13,396 bytes raw (CRLF line endings, as-attached)
FeRD sidecar        : 13,153 bytes raw (LF line endings, FeRD-normalized)
Byte-equal raw?     : False  ← line endings differ
factur-x C14N2      :  8,308 bytes
FeRD sidecar C14N2  :  8,308 bytes
C14N2-equal?        : True   ← canonical-XML byte-identical
First raw diff at byte 39: extracted has b'\\r\\n', sidecar has b'\\n'
```

**Finding**: the embedded XML attachment is authored with **CRLF line endings**; the standalone sidecar at `data/raw/german/zugferd-corpus/XML-Rechnung/CII/EN16931_Einfach.cii.xml` was normalized to **LF** during FeRD's corpus assembly. The two are content-identical after canonicalization (C14N2 method per W3C XML-C14N 2.0 specification), but **not** byte-identical at the file-system level.

**Implication for test design** — tests use **two granularities of agreement**:

1. **factur-x ↔ Mustang**: assert byte-equality (Probe 1 result). Any future divergence here is a **regression signal** (one of the two libraries changed its extraction behavior).
2. **(factur-x or Mustang) ↔ FeRD sidecar**: assert C14N2-canonical equivalence (Probe 2 result). The line-ending difference is a corpus-assembly artifact, not a content difference.

The choice of granularity is documented at each assertion site so future readers don't reach for the wrong default. ADR-009 Amendment 1's "two routes give identical content" claim is correct at both granularities (byte-equal for routes (a) and the embedded-XML reading of (b); C14N2-equal for the sidecar reading of (b)).

**Probe 3 — No-attachment graceful skip on Hetzner unstructured PDF**:

```text
PDF                : data/raw/german/zugferd-corpus/unstructured/RE-E-974-Hetzner_2016-01-19_R0005532486.pdf
PDF size           : 34,199 bytes
facturx behavior   : logs WARNING "No valid factur-x/order-x/zugferd/xrechnung XML file found in this PDF"
                     returns (False, False) — does NOT raise
```

**Finding**: `facturx.get_xml_from_pdf` is well-behaved on non-ZUGFeRD PDFs — no exception, just a falsy return + an internal warning log. The HORUS wrapper's no-attachment path detects `not filename or not xml_bytes` and treats it as a skip-not-error case. This is exactly what the issue acceptance criterion calls for ("skip + log warning") and is the wrapper's primary behavioral value-add over upstream `facturx-pdfextractxml` (which exits 1).

**Probe 4 — Mustang subprocess invocation hazard**:

```text
Failure mode       : Mustang's --action extract refuses to overwrite an existing
                     output file (`ensureFileNotExists` in `Main.performExtract`)
Symptom            : exit 255, stderr "File <out-path> already exists"
Implication        : Wrapper uses `tempfile.TemporaryDirectory` for Mustang's
                     output rather than `NamedTemporaryFile` (which creates the
                     placeholder); cleanup is by dir-removal, not file-removal.
```

**Finding**: a behavioral hazard in Mustang's CLI that's worth documenting since the script's `extract_via_mustang` helper has to thread around it. Same fix shape applies to any future Mustang subprocess action that writes a file.

### Integration with downstream pilot #13 evaluation harness

This script is the *first* artifact of pilot #13's eval-harness chain. Subsequent (downstream, separate sub-issues under #13):

1. **CII XML → flat field dict parser** — maps `rsm:CrossIndustryInvoice/.../ram:Name` etc. to a Python dict for F1 scoring. Out of scope here.
2. **Visual-layer PNG rasterizer** — already mechanized in ADR-009 cohort-smoke (`sips -s format png --resampleWidth 2480 …`). Reused by the harness.
3. **VLM extraction loop** — `scripts/cohort_smoke.py` per ADR-009; harness drives it per fixture, per model.
4. **F1 / heatmap computation** — pilot #13 step 5 + step 6 per `#13` body. Compares predicted-fields-from-VLM to ground-truth-fields-from-XML.
5. **MLflow / tracker integration** — pilot #13 sub-issue, separate ADR.

`scripts/extract_zugferd_xml.py` is invoked by the harness as a subprocess (`subprocess.run([sys.executable, "scripts/extract_zugferd_xml.py", pdf_path])`) or imported directly (`from horus.zugferd_extract import extract` — if/when the logic is hoisted into `src/horus/` later; not required for this PR).

### What this ADR does NOT decide

- **Field-level CII XML parsing**: lives in pilot #13's eval-harness sub-issue (downstream).
- **F1 / error-heatmap metric computation**: lives in pilot #13 step 5 + step 6 (downstream).
- **MLflow integration**: separate pilot #13 tracker sub-issue.
- **PDF/A-3 conformance validation**: already covered by ADR-005 / `scripts/validate_zugferd.py` (`--action validate`); orthogonal to XML extraction.
- **Synthetic invoice generation at pilot scale**: separate future issue per ADR-005 §"What this ADR does NOT decide".
- **Batch-mode CLI (`--batch <dir>`)**: deferred per Socratic Q1 lock in the plan. If pilot #13's eval harness wants it later, single-PR amendment to this script.

## Source archival

Per `horus-source-archival` rule + ADR-002, every option in `## Options considered` is archived under `docs/sources/`. For this ADR, no new sources are added because **the chosen primary engine and the cross-check tool are both already-archived from ADR-005**:

- **`docs/sources/tools/factur-x-python.md`** — exists from ADR-005 (M2D.5 step 2). **Updated this PR**: role description extended from "generator (binder)" to "generator (binder) + canonical XML extractor"; `get_xml_from_pdf` API documented as the canonical extraction route; reference to ADR-010 added.
- **`docs/sources/tools/mustang-project.md`** — exists from M2D.3 (`docs/prompts/stages/01-literature.md` import), refreshed in ADR-005. **Updated this PR**: `--action extract` documented alongside `--action validate` as the second cross-tool route; reference to ADR-010 added.
- `docs/sources/legal/zugferd-en16931.md` — exists from M2D.3; no update needed (spec reference is unchanged).
- `pikepdf`, `pypdf` (alone), `pdfplumber`, `pycheval`, `qpdf`, `factur-x-ng` forks, `horstoeko/zugferd` (PHP) — not archived; eliminated-by-reference alternatives per `horus-source-archival` §"When the rule does NOT fire" ("alternatives explicitly considered-and-rejected in the same ADR but not cited as positive evidence").

## Consequences

- **Positive**:
  - Pilot #13 has its ground-truth substrate: every PDF in the FeRD corpus can be turned into a `<basename>.cii.xml` sidecar with one CLI invocation. The eval-harness sub-issue starts from working infrastructure.
  - **Discoverability is restored**: §"Current-state survey" in this ADR is the single place a future reader can look to know "what's already installed for ZUGFeRD work in HORUS" — closes the user-reported pain ("it was difficult to find out what we already used").
  - **Three-route ground-truth claim is now empirically verified** (C14N2-canonical agreement between factur-x, FeRD sidecar — and, when the JAR is present, Mustang). ADR-009 Amendment 1's "two routes give identical content" assertion is now demonstrably correct at the content level, with the line-ending caveat documented.
  - **Honest light-ADR shape**: the 5-section discipline is preserved; the post-hoc-ratification nature is named directly (per `be-honest-direct-critical`). No false equivalences in the §"Options considered" walk.
  - **No new dependencies**: every component in §"Decision" is already installed. `make install` does not change. CI / `make test` baseline does not change beyond the new test file's additions.

- **Negative**:
  - **Coupling to `factur-x` semantics for filename detection**: if FeRD adds a new attachment-filename slot in a future ZUGFeRD spec revision (beyond the current `factur-x.xml` / `zugferd-invoice.xml` / `ZUGFeRD-invoice.xml` / `order-x.xml` set), HORUS waits on `factur-x` to update its `ALL_FILENAMES` list — or extends the wrapper to inspect `/Names /EmbeddedFiles` directly. Captured in §"Supersession trigger" (3).
  - **Cross-check is opt-in, not automatic**: it is conceivable a user runs the script across the full corpus without `--cross-check-mustang` and never validates the Java route. Mitigation: test #4 runs the cross-check on the canonical fixture in CI (when JAR is present); the test guarantees the routes agree on the substrate the rest of the pilot consumes.

- **Neutral**:
  - The wrapper is small (~120 LOC including docstring, type hints, and CLI plumbing). Cost-of-ownership is low; future Cascades will read it end-to-end in seconds.
  - `facturx-pdfextractxml` upstream CLI remains usable via the venv; the HORUS wrapper does not shadow or remove it.

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate; "Context" / "Current-state survey" / "Options considered" / "Decision + integration thoughts" / "Source archival" / "Supersession trigger" all present)
- **ADR-002** — source-archival convention (this ADR's `## Source archival` cites; no new stubs needed, two existing stubs updated)
- **ADR-005** — synthetic ZUGFeRD invoice generator: the upstream ADR that ratified `factur-x` as the *generator* and Mustang as the cross-tool *validator*. This ADR extends both roles: `factur-x` as the canonical *extractor*; Mustang `--action extract` as the opt-in cross-tool *extractor*. The two ADRs are complementary; this ADR is the natural sibling
- **ADR-009 Amendment 1** — the load-bearing forward-pointer that designates the embedded factur-x XML as pilot #13's authoritative ground truth; this ADR produces the artifact Amendment 1's "XML-grounded F1" eval-harness will consume
- **Cascade-system ADR-013** — `/commit` workflow (used for the commits in this PR; multi-line commit bodies routed through tempfile per `no-terminal-oneline-scripts`)
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager` per `branch-and-pr-required`)
- **Future pilot-#13 eval-harness ADR** — consumes this script's output; defines the CII XML → field-dict parser, the F1 metric, and the MLflow integration
