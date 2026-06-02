"""Read-only data-access layer for the observability dashboard.

Pure, dependency-light, and unit-tested (see `tests/test_app_data.py`). Wraps the
local MLflow run store (`mlflow_store`), reconstructs per-field scores from the
saved artifacts and recomputes the headline metrics with the project's OWN scorer
(`results` + `metrics`) so the dashboard's numbers are produced by the same code
as the research pipeline, and resolves invoice page images + raw transcripts
(`invoices`). The three extraction approaches are described in `approaches`.

Nothing here imports Streamlit — the layer is independently importable + testable.
"""
