.PHONY: help install test lint format typecheck experiment clean

# Default target — list available commands.
help:
	@echo "Available targets:"
	@echo "  install     uv sync (install all deps + dev group)"
	@echo "  test        uv run pytest"
	@echo "  lint        uv run ruff check (lint only; no fix)"
	@echo "  format      uv run ruff format (apply formatting)"
	@echo "  typecheck   uv run mypy src tests"
	@echo "  experiment  jupytext + papermill on NB=experiments/<name>.py"
	@echo "  clean       remove build artifacts and caches"

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy src tests

# Jupytext-paired experiment runner (B2=A notebook discipline).
# Usage: make experiment NB=experiments/<name>.py
# Converts .py -> .ipynb, runs via papermill, converts result back to .py.
experiment:
	@if [ -z "$(NB)" ]; then \
		echo "Usage: make experiment NB=experiments/<name>.py"; \
		exit 1; \
	fi
	uv run jupytext --to ipynb $(NB) -o $(NB:.py=.ipynb)
	uv run papermill $(NB:.py=.ipynb) $(NB:.py=.executed.ipynb)
	uv run jupytext --to py:percent $(NB:.py=.executed.ipynb) -o $(NB:.py=.executed.py)
	rm -f $(NB:.py=.ipynb)
	@echo "Executed: $(NB:.py=.executed.py) (and .executed.ipynb)"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
