---
source_url: "https://omegaconf.readthedocs.io/"
source_title: "OmegaConf — flexible Python configuration library"
source_author: "Omry Yadan"
source_date: ""
retrieved_date: "2026-05-10"
extracted_concepts: []
tags: ["omegaconf", "structured-configs", "yaml", "alternative-considered"]
archived_pdf: ""
status: stub
---

OmegaConf — hierarchical configuration system (the layer Hydra builds on). Provides `OmegaConf.structured(MyDataclass)` for dataclass-backed schemas, `OmegaConf.load("file.yaml")` for YAML loading, `OmegaConf.merge(schema, conf)` for schema-validated merge, and a "struct mode" that fails on extra fields. Considered as ADR-004 alternative; **rejected** because: (1) validation is runtime-only — no static-type-checker integration on par with Pydantic v2 + the Pydantic mypy plugin; (2) uses Python dataclasses, not Pydantic models — the `horus-config-discipline` rule body explicitly references `BaseModel` / `Field`, so OmegaConf would force a rule rewrite for no functional gain; (3) lacks the env-var override / dotenv / secrets-loading machinery `pydantic-settings` provides natively, which HORUS will need for cloud-baseline API keys (Mistral OCR / Gemini / GPT-5 per brainstorm §8.2) and MLflow tracking URI. License: BSD-3-Clause.
