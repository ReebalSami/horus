.PHONY: help install test lint format typecheck experiment mustang-jar zugferd-smoke clean

# Default target — list available commands.
help:
	@echo "Available targets:"
	@echo "  install         uv sync (install all deps + dev group)"
	@echo "  test            uv run pytest"
	@echo "  lint            uv run ruff check (lint only; no fix)"
	@echo "  format          uv run ruff format (apply formatting)"
	@echo "  typecheck       uv run mypy src tests"
	@echo "  experiment      jupytext + papermill on NB=experiments/<name>.py CFG=configs/<name>.yaml"
	@echo "  mustang-jar     download + checksum-verify Mustang-CLI JAR (validator; ADR-005)"
	@echo "  zugferd-smoke   end-to-end smoke: factur-x generate + Mustang validate (ADR-005)"
	@echo "  clean           remove build artifacts and caches"

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts

format:
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts

typecheck:
	uv run mypy src tests scripts

# Jupytext-paired experiment runner (B2=A notebook discipline + horus-config-discipline).
# Usage: make experiment NB=experiments/<name>.py CFG=configs/<name>.yaml
# Converts .py -> .ipynb, runs via papermill (injects cfg_path=$(CFG)),
# converts result back to .py. Per ADR-004 + horus-config-discipline:
# every experiment receives ONE papermill parameter (cfg_path) and loads
# all knobs via ExperimentConfig.from_yaml(cfg_path).
experiment:
	@if [ -z "$(NB)" ] || [ -z "$(CFG)" ]; then \
		echo "Usage: make experiment NB=experiments/<name>.py CFG=configs/<name>.yaml"; \
		exit 1; \
	fi
	uv run jupytext --to ipynb $(NB) -o $(NB:.py=.ipynb)
	uv run papermill -p cfg_path "$(CFG)" $(NB:.py=.ipynb) $(NB:.py=.executed.ipynb)
	uv run jupytext --to py:percent $(NB:.py=.executed.ipynb) -o $(NB:.py=.executed.py)
	rm -f $(NB:.py=.ipynb)
	@echo "Executed: $(NB:.py=.executed.py) (and .executed.ipynb) [cfg=$(CFG)]"

# Mustang Project (Java) — ZUGFeRD validator (cross-tool check; ADR-005).
# Version + SHA-256 pinned for reproducibility. JAR is gitignored.
# Run `make mustang-jar` once; subsequent calls are no-ops if file exists.
MUSTANG_VERSION := 2.23.0
MUSTANG_JAR := tools/mustangproject/Mustang-CLI-$(MUSTANG_VERSION).jar
MUSTANG_URL := https://github.com/ZUGFeRD/mustangproject/releases/download/core-$(MUSTANG_VERSION)/Mustang-CLI-$(MUSTANG_VERSION).jar
MUSTANG_SHA256 := 344c88b8d9bddccae23899a87d1ef31c4d38532383faa6303c381ee489cabe07

mustang-jar:
	@mkdir -p tools/mustangproject
	@if [ -f "$(MUSTANG_JAR)" ]; then \
		echo "Mustang JAR already present: $(MUSTANG_JAR)"; \
	else \
		echo "Fetching Mustang-CLI-$(MUSTANG_VERSION).jar (~58 MB)..."; \
		curl -fsSL -o "$(MUSTANG_JAR)" "$(MUSTANG_URL)"; \
		echo "$(MUSTANG_SHA256)  $(MUSTANG_JAR)" | shasum -a 256 -c -; \
		echo "Verified Mustang $(MUSTANG_VERSION)."; \
	fi
	@java -jar "$(MUSTANG_JAR)" --help >/dev/null 2>&1 && echo "Mustang JAR is callable via 'java -jar $(MUSTANG_JAR)'." || (echo "ERROR: 'java -jar $(MUSTANG_JAR)' failed. Verify Java is installed and on PATH." && exit 1)

# End-to-end ADR-005 smoke: factur-x generates, Mustang validates.
# Depends on `make install` (factur-x) and `make mustang-jar` (validator JAR).
zugferd-smoke: mustang-jar
	@mkdir -p data/raw/smoke
	uv run python scripts/generate_zugferd_smoke.py
	uv run python scripts/validate_zugferd.py data/raw/smoke/invoice-001.pdf

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
