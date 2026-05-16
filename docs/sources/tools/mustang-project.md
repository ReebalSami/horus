---
source_url: "https://www.mustangproject.org/zugferd/"
source_title: "Mustang Project — open-source ZUGFeRD generator/validator (Java)"
source_author: "Jochen Stärk (jstaerk) et al."
source_date: ""
retrieved_date: "2026-05-16"
release_pinned: "core-2.23.0 (2026-04-24)"
release_sha256: "344c88b8d9bddccae23899a87d1ef31c4d38532383faa6303c381ee489cabe07"
extracted_concepts: []
tags: ["mustang-project", "zugferd", "java", "pdf-a-3", "validator", "extractor", "schematron", "xsd", "cross-tool-validation", "cross-tool-extraction", "data-unlock", "primary-tooling", "adr-005", "adr-010"]
archived_pdf: ""
status: stub
---

Mustang Project — Apache 2.0 Java toolset for generating, validating, parsing, visualizing, and converting ZUGFeRD / Factur-X invoices (PDF/A-3 with embedded CII XML). FeRD-affiliated; the de-facto reference implementation. CLI actions: `metrics`, `combine`, `extract`, `a3only`, `ubl`, `validate`, `validateExpectInvalid`, `validateExpectValid`, `visualize`, `upgrade`, `pdf`. Java 11 bytecode (runs on JDK 17+; HORUS uses local OpenJDK 25 via Homebrew). Release JAR ~58 MB; fetched + SHA-256-pinned via `make mustang-jar`; stored gitignored under `tools/mustangproject/`.

**Role in HORUS — two complementary cross-tool routes** (ADR-005 + ADR-010):

1. **Cross-tool validator** (ADR-005). `--action validate --source <pdf>` runs Mustang's Schematron + XSD checks (`xslt/ZF_240/FACTUR-X_*.xslt` for ZUGFeRD 2.4.0) against PDFs / XMLs produced by other tools (e.g., `factur-x`). Smoke evidence at ADR-005 decision time: 27 Schematron rules fired, 0 failures, on factur-x-emitted MINIMUM-profile invoices. Invoked via `scripts/validate_zugferd.py`.

2. **Cross-tool extractor** (ADR-010). `--action extract --source <pdf> --out <xml>` extracts the embedded factur-x XML attachment from a PDF/A-3, producing an independent-codebase verification route. Used by `scripts/extract_zugferd_xml.py --cross-check-mustang` (opt-in) to assert byte-equality with the `factur-x` Python extraction. Empirical: both routes are byte-identical on `EN16931_Einfach.pdf` (ADR-010 §"Empirical evidence" Probe 1).

**Behavioral hazard for subprocess wrappers** — `--action extract` refuses to overwrite an existing output file (`ensureFileNotExists` in `Main.performExtract`); wrappers must pass an output path that does NOT yet exist. HORUS uses `tempfile.TemporaryDirectory` for Mustang's output (placeholder file is never pre-created); same fix shape applies to any future action that writes a file. Documented in ADR-010 §"Empirical evidence" Probe 4.

**Why not generator in HORUS**: the brainstorm originally indicated Mustang as the primary tooling (the "data unlock"). ADR-005 ratified a finer-grained role split — generator-and-validator-same-codebase = closed-loop validation; dual-track gives independent cross-tool compliance evidence (scientific-correctness criterion, v2 §0 lock #9). Mustang's `--action combine` remains a fallback generator if `factur-x` lapses (ADR-005 supersession trigger 1+2).

**Cross-reference**: see `docs/sources/tools/factur-x-python.md` for the Python binder + canonical extractor. See ADR-005 for the dual-track validation decision; see ADR-010 for the cross-tool extraction decision + three-route ground-truth empirical evidence (factur-x ↔ Mustang byte-equal; both ↔ FeRD `.cii.xml` sidecar C14N2-equal).
