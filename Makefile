.PHONY: help install test lint format typecheck experiment mustang-jar zugferd-smoke inference-smoke orchestrated-smoke cohort-smoke data-manifest pilot-13 mlflow-ui clean

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
	@echo "  orchestrated-smoke  Docling StandardPdfPipeline smoke on the ZUGFeRD invoice (ADR-008)"
	@echo "  cohort-smoke    cohort-VLM smoke runner (ADR-009; MODEL=ID or MODELS=A,B for subset; OUT=path for transcript file; CFG=configs/<slug>.yaml for ADR-011 MLflow tracking)"
	@echo "  data-manifest   generate MANIFEST.md + sha256.txt for a downloaded dataset corpus"
	@echo "  pilot-13        full (cohort × ZUGFeRD-corpus) sweep with parent/nested MLflow runs (ADR-014; CFG=configs/pilot-13.yaml required)"
	@echo "  mlflow-ui       browse pilot-13 + cohort-smoke runs in MLflow's local UI (ADR-015; MLFLOW_UI_PORT=<n> to override default 8080)"
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

# Cohort smoke (ADR-009). Loads each cohort model in turn (via
# `horus.vlm_extractor.get_extractor()`), runs page-1 of the real corpus PDF
# `EN16931_Einfach.pdf` through it, and emits ADR-007-style transcript blocks
# suitable for embedding in ADR-009 §Decision. Per-model invocation supported:
#   make cohort-smoke MODEL=ibm-granite/granite-docling-258M-mlx
# Subset via comma-separated list:
#   make cohort-smoke MODELS=ibm-granite/granite-docling-258M-mlx,deepseek-ai/DeepSeek-OCR-2
# Redirect transcript to a file (for ADR §Decision embedding):
#   make cohort-smoke OUT=/tmp/granite.txt MODEL=ibm-granite/granite-docling-258M-mlx
# ADR-011 MLflow tracking (opt-in; CFG= triggers the parent/nested run wire):
#   make cohort-smoke MODEL=ibm-granite/granite-docling-258M-mlx CFG=configs/cohort-smoke.yaml
#
# Uses macOS `sips` for PDF->PNG rasterization (same as inference-smoke). The
# resampleWidth=2480 is ~300 DPI for A4; model processors (per ADR-007) resize
# to a longest_edge cap internally so further resolution is wasted.
COHORT_SMOKE_PDF := data/raw/german/zugferd-corpus/XML-Rechnung/FX/EN16931_Einfach.pdf
COHORT_SMOKE_PNG := data/raw/smoke/EN16931_Einfach.page1.png

cohort-smoke:
	@command -v sips >/dev/null 2>&1 || (echo "ERROR: macOS 'sips' not found. cohort-smoke requires macOS." && exit 1)
	@mkdir -p data/raw/smoke
	@if [ ! -f "$(COHORT_SMOKE_PDF)" ]; then \
		echo "ERROR: $(COHORT_SMOKE_PDF) not found."; \
		echo "Acquire the zugferd-corpus first (see data/raw/german/zugferd-corpus/README.md)."; \
		exit 1; \
	fi
	@if [ ! -f "$(COHORT_SMOKE_PNG)" ]; then \
		echo "Rasterizing $(COHORT_SMOKE_PDF) page 1 -> $(COHORT_SMOKE_PNG) ..."; \
		sips -s format png --resampleWidth 2480 $(COHORT_SMOKE_PDF) --out $(COHORT_SMOKE_PNG) >/dev/null; \
	else \
		echo "Reusing existing $(COHORT_SMOKE_PNG)."; \
	fi
	uv run python scripts/cohort_smoke.py $(COHORT_SMOKE_PNG) \
		$(if $(MODEL),--model "$(MODEL)") \
		$(if $(MODELS),--models "$(MODELS)") \
		$(if $(OUT),--out "$(OUT)") \
		$(if $(MAX_TOKENS),--max-tokens $(MAX_TOKENS)) \
		$(if $(CFG),--cfg "$(CFG)")

# Orchestrated-baseline smoke (ADR-008). Loads Docling's default
# StandardPdfPipeline (orchestrated specialists: layout + OCR + table
# recognition) and runs it on the ZUGFeRD smoke invoice. Captures load /
# convert wall-times, output char count, structural counts (pages, tables,
# pictures), and a markdown snippet for ADR §"Captured transcript". Single-
# backend by design (plan Q4 = A: Docling-only smoke); MinerU pipeline
# backend smoke is deferred to pilot #13. First-run downloads docling-ibm-
# models layout + table-structure weights (~hundreds of MB; cached in
# ~/.cache/ via huggingface hub default).
orchestrated-smoke: zugferd-smoke
	uv run python scripts/orchestrated_smoke.py data/raw/smoke/invoice-001.pdf

# Dataset manifest generator (M2D.5 issue #12).
# Generates data/raw/<lang>/<slug>/MANIFEST.md (git-tracked) + sha256.txt (gitignored).
# Usage: make data-manifest SLUG=<slug> LANG=<lang> [SOURCE_URL=...] [SOURCE_TYPE=...]
#                            [LICENSE_SPDX=...] [LICENSE_URL=...] [SKIP_SHA256=1]
data-manifest:
	@if [ -z "$(SLUG)" ] || [ -z "$(LANG)" ]; then \
		echo "Usage: make data-manifest SLUG=<slug> LANG=<lang> [SOURCE_URL=...] [SOURCE_TYPE=...] [LICENSE_SPDX=...] [LICENSE_URL=...] [SKIP_SHA256=1]"; \
		exit 1; \
	fi
	uv run python scripts/data_manifest.py \
		--slug "$(SLUG)" --lang "$(LANG)" \
		$(if $(SOURCE_URL),--source-url "$(SOURCE_URL)") \
		$(if $(SOURCE_TYPE),--source-type "$(SOURCE_TYPE)") \
		$(if $(LICENSE_SPDX),--license-spdx "$(LICENSE_SPDX)") \
		$(if $(LICENSE_URL),--license-url "$(LICENSE_URL)") \
		$(if $(SKIP_SHA256),--skip-sha256) \
		$(if $(COMMIT_SHA),--commit-sha "$(COMMIT_SHA)") \
		$(if $(COMMIT_DATE),--commit-date "$(COMMIT_DATE)")

# Pilot #13 runner (ADR-014 PR(c)). Full (cohort × ZUGFeRD-corpus) sweep
# under one parent MLflow run, with (model, invoice) nested runs, multi-page
# rasterization via pypdfium2, per-page extract + concat (Strategy α), and
# factur-x-extracted GT (NOT sidecar — per ADR-012 Probe 5).
#
# Replaces the page-1-only sips loop of `make cohort-smoke` for full-corpus
# evaluation. (`make cohort-smoke` is preserved as ADR-009 §Decision evidence.)
#
# Required:
#   CFG=configs/pilot-13.yaml
# Optional subsets:
#   INVOICES=EN16931_Einfach,XRECHNUNG_Einfach
#   MODELS=ibm-granite/granite-docling-258M-mlx
# Optional flags:
#   NO_RESUME=1  (re-run every nested run, even FINISHED ones)
#
# Example smallest-possible smoke:
#   make pilot-13 CFG=configs/pilot-13.yaml \
#     INVOICES=EN16931_Einfach \
#     MODELS=ibm-granite/granite-docling-258M-mlx
#
# Example full sweep (~3-5h on M1 Pro):
#   make pilot-13 CFG=configs/pilot-13.yaml
#
# Resume-safe: ctrl-c → re-run picks up where it left off via mlflow.search_runs.
pilot-13:
	@if [ -z "$(CFG)" ]; then \
		echo "Usage: make pilot-13 CFG=configs/pilot-13.yaml [INVOICES=<csv>] [MODELS=<csv>] [NO_RESUME=1]"; \
		exit 1; \
	fi
	uv run python scripts/run_pilot_13.py --cfg "$(CFG)" \
		$(if $(INVOICES),--invoices "$(INVOICES)") \
		$(if $(MODELS),--models "$(MODELS)") \
		$(if $(NO_RESUME),--no-resume)

# MLflow UI for browsing pilot-13 + cohort-smoke runs (ADR-015).
# Wraps `mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1
# --port 8080` — the modern canonical MLflow CLI invocation (`mlflow ui` and
# `mlflow server` are byte-identical commands in MLflow 3.12.0; verified at
# ADR-015 authoring time via `--help` byte-comparison).
#
# Bound to 127.0.0.1 by default for local-only access (matches MLflow's
# default; explicit here to make the privacy posture VISIBLE per AGENTS.md
# §1: "documents stay inside the firm"). Port 8080 avoids the documented
# macOS AirPlay Receiver conflict at MLflow's port-5000 default (cited in
# MLflow's CONTRIBUTING.md). Override via MLFLOW_UI_PORT=<n>.
#
# Reads SQLite metadata from `mlflow.db` + filesystem artifacts from
# `mlruns/<experiment_id>/<run_id>/artifacts/` — both gitignored. Pre-flight
# guard refuses to launch against an empty repo (no mlflow.db AND no mlruns/).
#
# Per ADR-015 §"Decision + integration thoughts" — supersedes ADR-011's
# original deferral ("not Makefile-wired"; line 306 of ADR-011).
MLFLOW_UI_PORT ?= 8080

mlflow-ui:
	@if [ ! -f mlflow.db ] && [ ! -d mlruns ]; then \
		echo "ERROR: No MLflow data found at mlflow.db / mlruns/."; \
		echo "Run 'make pilot-13 CFG=configs/pilot-13.yaml' or 'make cohort-smoke ... CFG=configs/cohort-smoke.yaml' first."; \
		exit 1; \
	fi
	@echo "MLflow UI: http://127.0.0.1:$(MLFLOW_UI_PORT) (local-only; press Ctrl+C to stop)"
	uv run mlflow server \
		--backend-store-uri sqlite:///mlflow.db \
		--host 127.0.0.1 \
		--port $(MLFLOW_UI_PORT)

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
