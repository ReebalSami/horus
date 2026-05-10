---
source_url: "https://hydra.cc/"
source_title: "Hydra — A framework for elegantly configuring complex applications"
source_author: "Omry Yadan / Meta AI Research"
source_date: ""
retrieved_date: "2026-05-10"
extracted_concepts: []
tags: ["hydra", "config-framework", "ml-tooling", "alternative-considered"]
archived_pdf: ""
status: stub
---

Hydra — Meta-maintained config framework for ML applications, built on OmegaConf. Uses dataclass-based `ConfigStore` + `@hydra.main(config_path=..., config_name=...)` decorator on the entry-point function + opinionated `conf/` directory layout + composition via CLI overrides (`+db=mysql`, `db.timeout=30`) + multirun support (`-m` for parameter sweeps). Considered as ADR-004 alternative; **rejected** because: (1) the `@hydra.main` decorator wants to OWN the entry point — wrapping inside papermill's parameterised notebook execution requires manual `hydra.compose()` invocation and forfeits CLI/multirun ergonomics (the only differentiating features); (2) the `conf/` directory + structured-config opinion adds layout overhead the HORUS one-YAML-per-experiment pattern doesn't need; (3) heavier dep tree (`hydra-core` → `omegaconf` → `antlr4-python3-runtime`) for capabilities unused in the M2D.5–M2D.6 pilot scope. License: MIT.
