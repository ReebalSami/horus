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
  - `horus.tracking`  — `Tracker` Protocol + `DEFAULT_TRACKER` (stdout)
  - `horus.config`    — placeholder dataclass; replaced as design solidifies
"""

__version__ = "0.1.0"
