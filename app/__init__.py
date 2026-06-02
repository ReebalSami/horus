"""HORUS observability dashboard — a read-only Streamlit research/eval surface (ADR-036, #103).

Top-level application package. The entry point is `app/Home.py`
(`streamlit run app/Home.py`, or `make app`); pages live in `app/views/`,
reusable widgets in `app/components/`, and the read-only data-access layer in
`app/data/`. The app never runs a model or re-scores — it reads results that
already exist locally (MLflow runs + saved transcripts + the CII ground truth)
and arranges them.
"""
