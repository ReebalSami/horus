---
source_url: "https://pyyaml.org/"
source_title: "PyYAML — YAML parser and emitter for Python"
source_author: "Kirill Simonov; Ingy döt Net"
source_date: ""
retrieved_date: "2026-05-10"
extracted_concepts: []
tags: ["pyyaml", "yaml-parser", "transitive-dep"]
archived_pdf: ""
status: stub
---

PyYAML — canonical Python YAML 1.1 parser. Required transitive dependency of `pydantic-settings`'s `YamlConfigSettingsSource`, also used directly by HORUS's `ExperimentConfig.from_yaml()` classmethod via `yaml.safe_load`. `safe_load` is mandatory (never `yaml.load`) — `safe_load` rejects arbitrary Python tag execution, the documented YAML deserialization vulnerability surface. Mypy stubs ship as the separate `types-PyYAML` dev dependency. Cited in ADR-004's `## Source archival` as the YAML-parsing layer underneath the Pydantic Settings choice. License: MIT.
