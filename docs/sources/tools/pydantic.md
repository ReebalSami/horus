---
source_url: "https://docs.pydantic.dev/latest/"
source_title: "Pydantic — Data validation using Python type hints"
source_author: "Samuel Colvin and contributors"
source_date: ""
retrieved_date: "2026-05-10"
extracted_concepts: []
tags: ["pydantic", "schema-validation", "type-safety", "fail-fast", "primary-tooling"]
archived_pdf: ""
status: stub
---

Pydantic v2 — data validation library powered by Python type hints, with a Rust core (`pydantic-core`) for high-performance schema validation. The HORUS `ExperimentConfig` schema is built on `pydantic.BaseModel` (nested submodels) + `pydantic.Field` (per-field metadata + defaults) + `ConfigDict(extra="forbid")` (fail-fast on unrecognised YAML keys). `pydantic.ValidationError` is the canonical raise-at-boot signal that satisfies the `horus-config-discipline` rule's "Pydantic-validates-at-boot" forcing function: any malformed YAML / missing required field / type mismatch / extra field → `ValidationError` BEFORE any model loads, dataset downloads, or compute is spent. Cited in ADR-004 as the foundational dependency under `pydantic-settings`. License: MIT.
