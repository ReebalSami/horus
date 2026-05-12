.PHONY: help install test lint format typecheck experiment mustang-jar zugferd-smoke inference-smoke clean

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
	@echo "  inference-smoke real-model smoke: load Granite-Docling-258M via mlx-vlm + Transformers+MPS (ADR-007)"
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

# Real-model inference smoke (ADR-007). Loads Granite-Docling-258M through
# BOTH backends (mlx-vlm + Transformers+MPS), runs DocTags extraction on
# the rasterized ZUGFeRD smoke invoice, captures transcripts. One-off:
# produces ADR-007 §"Decision" evidence. Depends on `zugferd-smoke` for the
# input PDF; uses macOS `sips` for PDF->PNG rasterization (no extra dep).
# ~500 MB of model weights cached on first run; subsequent runs fast.
#
# Rasterization: --resampleWidth 2480 ≈ 300 DPI for A4 (210mm × 297mm =
# 8.27" × 11.69"; 8.27 × 300 = 2481 px). Granite-Docling-258M's processor
# resizes to longest_edge=2048 internally, so 300 DPI feeds it the highest
# pre-resize resolution it will actually use; 150 DPI (resampleWidth=1240)
# rendered the invoice body unreadable in the first smoke pass. Cohort ADR
# #14 will replace sips with pypdfium2 + parameterized DPI.
INFERENCE_SMOKE_PNG := data/raw/smoke/invoice-001.page1.png

inference-smoke: zugferd-smoke
	@command -v sips >/dev/null 2>&1 || (echo "ERROR: macOS 'sips' not found. inference-smoke requires macOS." && exit 1)
	sips -s format png --resampleWidth 2480 data/raw/smoke/invoice-001.pdf --out $(INFERENCE_SMOKE_PNG)
	uv run python scripts/inference_smoke.py $(INFERENCE_SMOKE_PNG)

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
