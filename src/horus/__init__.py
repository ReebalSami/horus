"""HORUS — Hybrid OCR-free Reading & Understanding System.

Master's thesis project (FH Wedel, SS 2026): privacy-first document
intelligence for German tax/accounting professionals via local
vision-language models. The Egyptian falcon-headed god of vision lends
his name (and the Eye-of-Horus glyph) to the central methodological
commitment — VLMs that *see* documents holistically, no OCR pipeline.

Bootstrapped from the `python-ml-uv` L3 template (cascade-system meta-repo,
Vertical B output). See `README.md` §"Why HORUS?" + `docs/decisions/` for
naming + architectural ratification.

Public surface (lazy-imported by callers):
  - `horus.seeding`   — `set_global_seed` (deterministic experiments)
  - `horus.tracking`  — `Tracker` Protocol + `Run` dataclass + `StdoutTracker` (default,
                        zero-dep) + `MLflowTracker` (MLflow-backed, per ADR-011) +
                        `get_tracker(cfg)` factory + `DEFAULT_TRACKER`
  - `horus.config`    — `ExperimentConfig` schema (Pydantic Settings + YAML; see ADR-004)
"""

__version__ = "0.1.0"
