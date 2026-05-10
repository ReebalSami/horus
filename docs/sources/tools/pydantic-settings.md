---
source_url: "https://docs.pydantic.dev/latest/concepts/pydantic_settings/"
source_title: "Pydantic Settings — Settings management"
source_author: "Pydantic team"
source_date: ""
retrieved_date: "2026-05-10"
extracted_concepts: []
tags: ["pydantic-settings", "config-management", "yaml-loading", "env-vars", "primary-tooling"]
archived_pdf: ""
status: stub
---

Pydantic Settings — Pydantic-team-maintained extension to Pydantic v2 that adds source-aware settings loading (env vars, dotenv files, secrets directories, YAML / JSON / TOML files) with a unified `BaseSettings` model. HORUS uses `BaseSettings` + `SettingsConfigDict(env_prefix="HORUS_", env_nested_delimiter="__", extra="forbid")` as the `ExperimentConfig` base: YAML is the primary source (loaded explicitly via `from_yaml(cfg_path)` classmethod that hands data to `cls(**data)`), env vars layer on top for secret-style overrides (e.g., `HORUS_MLFLOW__TRACKING_URI`). Chosen over Hydra (heavy CLI-decorator pattern incompatible with papermill `cfg_path` contract), OmegaConf alone (runtime-only validation, no Pydantic ergonomics, dataclass-not-BaseModel-based), and stdlib + PyYAML (no fail-fast schema enforcement). Cited in ADR-004 as the chosen config library. License: MIT.
