---
source_url: "https://www.mustangproject.org/zugferd/"
source_title: "Mustang Project — open-source ZUGFeRD generator/validator (Java)"
source_author: "Jochen Stärk (jstaerk) et al."
source_date: ""
retrieved_date: "2026-05-11"
release_pinned: "core-2.23.0 (2026-04-24)"
release_sha256: "344c88b8d9bddccae23899a87d1ef31c4d38532383faa6303c381ee489cabe07"
extracted_concepts: []
tags: ["mustang-project", "zugferd", "java", "pdf-a-3", "validator", "schematron", "xsd", "cross-tool-validation", "data-unlock", "primary-tooling", "adr-005"]
archived_pdf: ""
status: stub
---

Mustang Project — Apache 2.0 Java toolset for generating, validating, parsing, visualizing, and converting ZUGFeRD / Factur-X invoices (PDF/A-3 with embedded CII XML). FeRD-affiliated; the de-facto reference implementation. CLI actions: `metrics`, `combine`, `extract`, `a3only`, `ubl`, `validate`, `validateExpectInvalid`, `validateExpectValid`, `visualize`. Java 11 bytecode (runs on JDK 17+; HORUS uses local OpenJDK 25 via Homebrew). Release JAR ~58 MB; fetched + SHA-256-pinned via `make mustang-jar`; stored gitignored under `tools/mustangproject/`.

**Role in HORUS (per ADR-005)**: the **independent cross-tool validator** in the dual-track synthetic-invoice toolchain. `factur-x` (Python) generates; Mustang (Java) validates. Smoke evidence at ADR-005 decision time: Mustang Schematron `xslt/ZF_240/FACTUR-X_MINIMUM.xslt` (ZUGFeRD 2.4.0 ruleset) fires 27 rules, 0 failures, on factur-x-emitted MINIMUM-profile invoices.

**Why not generator in HORUS**: the brainstorm originally indicated Mustang as the primary tooling (the "data unlock"). ADR-005 ratified a finer-grained role split — generator-and-validator-same-codebase = closed-loop validation; dual-track gives independent cross-tool compliance evidence (scientific-correctness criterion, v2 §0 lock #9). Mustang's `--action combine` remains a fallback generator if `factur-x` lapses (ADR-005 supersession trigger 1+2).

**Cross-reference**: see `docs/sources/tools/factur-x-python.md` for the Python binder. See ADR-005 for the dual-track decision rationale + full smoke evidence captured at decision time.
