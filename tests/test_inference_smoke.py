"""Import-only smoke for the dual-track inference stack (ADR-007).

Asserts:
1. `mlx_vlm` imports cleanly and exposes a sane version string
2. `transformers` imports cleanly and exposes a sane version string
3. PyTorch's MPS backend is available on this M1 Pro machine

NO model weights are loaded by this test — it runs in `make test` and must
stay fast (< 1 s wall time). Real-model smoke evidence (loading
Granite-Docling 258M through both backends and feeding the ZUGFeRD smoke
invoice through them) lives in `scripts/inference_smoke.py` and runs via
`make inference-smoke`. Per ADR-007 §"Smoke evidence — methodology".
"""

from __future__ import annotations

import re
import sys

import pytest

# ADR-023 first-CI-run amendment: MLX core, mlx-vlm, and PyTorch MPS backend
# are macOS/Apple-Silicon-only (per ADR-007 dual-track hardware-fit). On
# ubuntu-latest CI runners these imports fail (`libmlx.so` not found; MPS
# not available). Platform skip preserves the ADR-007 hardware-wiring
# assertion on macOS while letting CI pass on Linux. The `transformers`
# import test is cross-platform and remains unconditional.
requires_macos = pytest.mark.skipif(
    sys.platform != "darwin",
    reason=(
        "MLX core + mlx-vlm + PyTorch MPS backend are macOS/Apple-Silicon-only "
        "(ADR-007 dual-track hardware-fit; per ADR-023 first-CI-run amendment)."
    ),
)


@requires_macos
def test_mlx_vlm_importable() -> None:
    """mlx-vlm imports without error and exposes a SemVer-shaped version."""
    import mlx_vlm

    version = mlx_vlm.__version__
    assert isinstance(version, str)
    assert re.match(r"^\d+\.\d+\.\d+", version), f"unexpected mlx_vlm version shape: {version!r}"


def test_transformers_importable() -> None:
    """transformers imports without error and exposes a SemVer-shaped version."""
    import transformers

    version = transformers.__version__
    assert isinstance(version, str)
    assert re.match(r"^\d+\.\d+\.\d+", version), (
        f"unexpected transformers version shape: {version!r}"
    )


@requires_macos
def test_torch_mps_backend_available() -> None:
    """PyTorch's MPS backend is available — confirms the Transformers + MPS
    fallback path is wired on this M1 Pro machine. If this fails, either the
    machine is not Apple Silicon or PyTorch was installed without Metal
    support; both invalidate ADR-007's hardware-fit reasoning.
    """
    import torch

    assert torch.backends.mps.is_available(), (
        "PyTorch MPS backend not available — ADR-007's Transformers + MPS "
        "fallback path is not wired. Verify Apple Silicon + a Metal-capable "
        "PyTorch build (`torch>=2.5` per pyproject.toml)."
    )
    assert torch.backends.mps.is_built(), (
        "PyTorch MPS backend reports available but not built — likely a "
        "non-Metal torch wheel was installed. Reinstall via `uv sync`."
    )


@requires_macos
def test_mlx_core_importable_via_mlx_vlm() -> None:
    """`mlx-vlm` pulls in `mlx>=0.31.2` transitively per its runtime deps;
    confirm the MLX core is importable and reports an MLX-Metal backend
    (the Apple-Silicon-native execution path).
    """
    import mlx.core as mx

    # mlx.default_device() returns Device(gpu, 0) on Apple Silicon Metal-capable boxes;
    # on any other path the smoke evidence in ADR-007 is invalidated.
    device = mx.default_device()
    assert device is not None
    # `repr(device)` is "Device(gpu, 0)" on M1 Pro Metal; the assertion is
    # forgiving (any GPU device suffices) to avoid coupling to a private repr.
    assert "gpu" in repr(device).lower(), f"mlx.default_device() reports non-GPU: {device!r}"
