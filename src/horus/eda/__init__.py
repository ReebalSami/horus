"""HORUS EDA helpers — multi-dataset Quarto Book substrate (ADR-025).

This package factors out the shared infrastructure that every EDA chapter
needs (corpus walking, figure styling, Datasheet rendering) plus the
per-dataset loaders. Each chapter notebook in `experiments/0X-<slug>.py`
imports from here; chapter notebooks contain narrative + cells that call
into this package, NOT inline library code.

Public surface (lazy-imported by callers):
  - `horus.eda.corpus_walk` — `walk(root, ...)` shared file-walking helpers
  - `horus.eda.figures`     — palette + matplotlib/seaborn/Plotly setup
  - `horus.eda.datasheet`   — Pydantic Datasheet model + qmd renderer
                              (Gebru et al. 2018, arxiv:1803.09010)

Per-dataset loaders are added in Phase B (ZUGFeRD) and Phase C (the
remaining 6 datasets) per the EDA expansion plan
(`~/.windsurf/plans/eda-full-corpus-ed5d97.md`).

Refs: ADR-024 (visualization stack), ADR-025 (multi-dataset Book + Datasheets).
"""

__all__ = ["corpus_walk", "figures", "datasheet"]
