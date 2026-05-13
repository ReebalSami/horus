"""Import-only smoke for ADR-008 orchestrated-baseline dependencies.

Mirrors the ADR-007 ``test_inference_smoke.py`` pattern: assert the chosen
libraries are importable and expose their canonical entrypoints. Does NOT
load any models or run any conversions — full hands-on smoke runs via
``make orchestrated-smoke`` (one-off; not in ``make test``).
"""

from __future__ import annotations

import shutil
from importlib.metadata import version


def test_docling_importable() -> None:
    """Docling is importable and exposes ``DocumentConverter``."""
    from docling.document_converter import DocumentConverter

    assert callable(DocumentConverter)
    docling_version = version("docling")
    # Pinned floor in pyproject.toml is 2.93.0 — assert at least major version 2.
    major = int(docling_version.split(".")[0])
    assert major >= 2, f"docling {docling_version} below ADR-008 floor 2.93.0"


def test_docling_pipeline_options_importable() -> None:
    """Docling's pipeline-options module exposes ``PdfPipelineOptions``.

    ADR-008's Decision section references the option as the orchestrated-stage
    knob surface. Failing this import = upstream API drift requiring an ADR
    revision.
    """
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    options = PdfPipelineOptions()
    assert hasattr(options, "do_ocr")
    assert hasattr(options, "do_table_structure")


def test_mineru_importable() -> None:
    """MinerU is importable; ``mineru`` CLI is on PATH after ``uv sync``."""
    import mineru  # noqa: F401  (importability check)

    mineru_version = version("mineru")
    major = int(mineru_version.split(".")[0])
    assert major >= 3, f"mineru {mineru_version} below ADR-008 floor 3.1.11"


def test_mineru_cli_callable() -> None:
    """The ``mineru`` CLI is callable after ``uv sync`` install.

    ADR-008's MinerU integration is CLI-driven (`mineru -p <pdf> -o <out> -b
    pipeline`); confirm the entry point exists. ``shutil.which`` returns the
    resolved absolute path or ``None``.
    """
    cli_path = shutil.which("mineru")
    assert cli_path is not None, "mineru CLI not found on PATH after uv sync"
