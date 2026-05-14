"""Unit tests for `horus.vlm_extractor` — ADR-009 dispatcher.

Asserts:
- Module imports cleanly (manifest validation at import time)
- `ExtractionResult` shape + `is_ok` semantics
- `VLMExtractor` Protocol — each concrete class satisfies it
- `COHORT_MANIFEST` has 10 entries; each has required keys + valid values
- Category distribution matches ADR-009 §3.1 (3 / 3 / 4 across Cat 1/2/3)
- `get_extractor()` returns the right concrete class per model_id
- `get_extractor()` raises KeyError on unknown model
- `validate_manifest()` raises on schema violations (synthetic bad entries)

NO model weights are loaded by this test — it runs in `make test` and must
stay fast (< 1 s wall time). Real-model smoke evidence lives in
`scripts/cohort_smoke.py` and runs via `make cohort-smoke` (per ADR-009 §3
plan, PR(a) Step 3).
"""

from __future__ import annotations

import pytest


def test_module_imports_and_manifest_validates() -> None:
    """Module imports cleanly => `validate_manifest()` passed at import time.

    If a future edit corrupts the manifest schema, the import itself will fail
    (per the `validate_manifest()` call at the bottom of `vlm_extractor.py`).
    """
    import horus.vlm_extractor  # noqa: F401


def test_extraction_result_default_and_is_ok() -> None:
    """`ExtractionResult` is frozen, has sensible defaults, `is_ok` mirrors `error`."""
    from horus.vlm_extractor import ExtractionResult

    ok_result = ExtractionResult(
        model_id="x",
        backend_name="mlx-vlm",
        text="hello",
        output_len_chars=5,
    )
    assert ok_result.is_ok is True
    assert ok_result.text == "hello"
    assert ok_result.error is None

    err_result = ExtractionResult(
        model_id="x",
        backend_name="mlx-vlm",
        error="oops",
        traceback_str="Traceback...",
    )
    assert err_result.is_ok is False
    assert err_result.text == ""  # default
    assert err_result.output_len_chars == 0  # default

    # Frozen — assignment raises.
    with pytest.raises(Exception):  # noqa: B017 — dataclasses raises FrozenInstanceError
        err_result.text = "mutated"  # type: ignore[misc]


def test_concrete_extractors_satisfy_protocol() -> None:
    """All 4 concrete extractor classes satisfy the `VLMExtractor` Protocol shape."""
    from horus.vlm_extractor import (
        GLMOCRExtractor,
        MLXVLMExtractor,
        PaddleOCRExtractor,
        TransformersMPSExtractor,
        VLMExtractor,
    )

    classes_to_check = [
        MLXVLMExtractor,
        TransformersMPSExtractor,
        PaddleOCRExtractor,
        GLMOCRExtractor,
    ]
    for cls in classes_to_check:
        instance = cls(model_id="test/model")  # cheap construction; no model load
        # Protocol membership via isinstance (runtime_checkable).
        assert isinstance(instance, VLMExtractor), (
            f"{cls.__name__} fails VLMExtractor Protocol check"
        )
        # Each concrete class declares a ClassVar `backend_name`; visible on instances.
        assert isinstance(instance.backend_name, str) and instance.backend_name
        # Required methods are present and callable.
        assert callable(instance.load)
        assert callable(instance.extract)
        assert callable(instance.unload)


def test_cohort_manifest_has_ten_entries() -> None:
    """`COHORT_MANIFEST` has exactly 10 entries per ADR-009 §3.1."""
    from horus.vlm_extractor import COHORT_MANIFEST

    assert len(COHORT_MANIFEST) == 10


def test_cohort_manifest_category_distribution() -> None:
    """3 models in Cat 1, 3 in Cat 2, 4 in Cat 3 per ADR-009 §3.1."""
    from horus.vlm_extractor import COHORT_MANIFEST

    categories = [entry["category"] for entry in COHORT_MANIFEST.values()]
    assert categories.count(1) == 3, "Cat 1 (End-to-end doc-VLMs) must have 3 models"
    assert categories.count(2) == 3, "Cat 2 (Architecturally innovative) must have 3 models"
    assert categories.count(3) == 4, "Cat 3 (General multimodal VLMs) must have 4 models"


def test_cohort_manifest_required_keys_all_present() -> None:
    """Every COHORT_MANIFEST entry has the 9 required keys."""
    from horus.vlm_extractor import COHORT_MANIFEST

    required_keys = {
        "extractor_class",
        "category",
        "prompt_template",
        "max_tokens",
        "quant_target",
        "alt_model_id",
        "license",
        "needs_trust_remote_code",
        "note",
    }
    for model_id, entry in COHORT_MANIFEST.items():
        missing = required_keys - set(entry.keys())
        assert not missing, f"COHORT_MANIFEST[{model_id!r}] missing keys: {missing}"


def test_get_extractor_returns_correct_class_per_model_id() -> None:
    """`get_extractor()` resolves each cohort model_id to the right extractor class."""
    from horus.vlm_extractor import (
        COHORT_MANIFEST,
        MLXVLMExtractor,
        TransformersMPSExtractor,
        get_extractor,
    )

    # Spot-check the PR(a) hot path: Granite-Docling-258M => MLXVLMExtractor.
    granite = get_extractor("ibm-granite/granite-docling-258M-mlx")
    assert isinstance(granite, MLXVLMExtractor)
    assert granite.model_id == "ibm-granite/granite-docling-258M-mlx"

    # DeepSeek-OCR-2 uses MLX with alt_model_id quant port.
    deepseek = get_extractor("deepseek-ai/DeepSeek-OCR-2")
    assert isinstance(deepseek, MLXVLMExtractor)
    assert deepseek.model_id == "deepseek-ai/DeepSeek-OCR-2"

    # Gemma-4-E4B-it uses MLX with lmstudio-community port.
    gemma = get_extractor("google/gemma-4-E4B-it")
    assert isinstance(gemma, MLXVLMExtractor)

    # MinerU-2.5-Pro VLM uses TransformersMPSExtractor (PR(b)).
    mineru = get_extractor("opendatalab/MinerU2.5-Pro-2604-1.2B")
    assert isinstance(mineru, TransformersMPSExtractor)

    # PaddleOCR-VL routes through MLXVLMExtractor (PR(b) Step 8 pivot —
    # mlx-community 4-bit port; mlx-vlm 0.5.0 has built-in paddleocr_vl support).
    paddle = get_extractor("PaddlePaddle/PaddleOCR-VL")
    assert isinstance(paddle, MLXVLMExtractor)

    # GLM-OCR routes through MLXVLMExtractor (PR(b) Step 9 pivot —
    # mlx-community 4-bit port; mlx-vlm 0.5.0 has built-in glm_ocr support,
    # sidesteps transformers<5.0.0 conflict).
    glm = get_extractor("zai-org/GLM-OCR")
    assert isinstance(glm, MLXVLMExtractor)

    # Every cohort model_id resolves without raising.
    for model_id in COHORT_MANIFEST:
        extractor = get_extractor(model_id)
        assert extractor.model_id == model_id


def test_get_extractor_unknown_model_raises_keyerror() -> None:
    """Unknown model_id raises `KeyError` with the known cohort listed."""
    from horus.vlm_extractor import get_extractor

    with pytest.raises(KeyError) as exc_info:
        get_extractor("not-a-cohort-model/fake")
    # Error message includes the known cohort for discoverability.
    assert "not-a-cohort-model/fake" in str(exc_info.value)
    assert "ibm-granite/granite-docling-258M-mlx" in str(exc_info.value)


def test_pr_a_models_route_to_mlxvlm_extractor() -> None:
    """The 3 PR(a) models all route through MLXVLMExtractor per ADR-009 §3.8."""
    from horus.vlm_extractor import COHORT_MANIFEST, MLXVLMExtractor

    pr_a_models = [
        "ibm-granite/granite-docling-258M-mlx",
        "deepseek-ai/DeepSeek-OCR-2",
        "google/gemma-4-E4B-it",
    ]
    for model_id in pr_a_models:
        assert COHORT_MANIFEST[model_id]["extractor_class"] is MLXVLMExtractor, (
            f"PR(a) model {model_id!r} must route through MLXVLMExtractor"
        )


def test_pr_a_models_are_one_per_category() -> None:
    """The 3 PR(a) models are one per category (1/2/3) per ADR-009 §3.8."""
    from horus.vlm_extractor import COHORT_MANIFEST

    pr_a_categories = {
        COHORT_MANIFEST["ibm-granite/granite-docling-258M-mlx"]["category"],
        COHORT_MANIFEST["deepseek-ai/DeepSeek-OCR-2"]["category"],
        COHORT_MANIFEST["google/gemma-4-E4B-it"]["category"],
    }
    assert pr_a_categories == {1, 2, 3}, (
        f"PR(a) models must span Cat 1+2+3, got {sorted(pr_a_categories)}"
    )


def test_trust_remote_code_flags_documented() -> None:
    """Models with `custom_code` correctly flag `needs_trust_remote_code=True`.

    Per ADR-009 §3.7 honest disclosure: DeepSeek-OCR-2, PaddleOCR-VL, Molmo-7B
    all require trust_remote_code=True at load time. The manifest flag is
    the security-disclosure surface.
    """
    from horus.vlm_extractor import COHORT_MANIFEST

    expected_trust_remote_code = {
        "deepseek-ai/DeepSeek-OCR-2": True,
        "PaddlePaddle/PaddleOCR-VL": True,
        "allenai/Molmo-7B-D-0924": True,
        # All others should be False (apache-2.0 / gemma-licensed standard paths).
    }
    for model_id, expected in expected_trust_remote_code.items():
        actual = COHORT_MANIFEST[model_id]["needs_trust_remote_code"]
        assert actual is expected, (
            f"COHORT_MANIFEST[{model_id!r}] needs_trust_remote_code expected "
            f"{expected!r}, got {actual!r}"
        )


def test_paddleocr_extractor_load_raises_not_implemented() -> None:
    """PaddleOCRExtractor.load() is a skeleton — raises NotImplementedError per PR(b) scope."""
    from horus.vlm_extractor import PaddleOCRExtractor

    extractor = PaddleOCRExtractor(model_id="PaddlePaddle/PaddleOCR-VL")
    with pytest.raises(NotImplementedError) as exc_info:
        extractor.load()
    assert "PR(b)" in str(exc_info.value)
    assert "paddlepaddle" in str(exc_info.value)


def test_glmocr_extractor_load_raises_not_implemented() -> None:
    """GLMOCRExtractor.load() is a skeleton — raises NotImplementedError per PR(b) scope."""
    from horus.vlm_extractor import GLMOCRExtractor

    extractor = GLMOCRExtractor(model_id="zai-org/GLM-OCR")
    with pytest.raises(NotImplementedError) as exc_info:
        extractor.load()
    assert "PR(b)" in str(exc_info.value)
    assert "transformers<5.0.0" in str(exc_info.value)


def test_skeleton_extractors_extract_returns_error_result_not_raise() -> None:
    """Skeleton extractors return an error ExtractionResult from extract() (no raise)."""
    from pathlib import Path

    from horus.vlm_extractor import GLMOCRExtractor, PaddleOCRExtractor

    paddle = PaddleOCRExtractor(model_id="PaddlePaddle/PaddleOCR-VL")
    result = paddle.extract(image_path=Path("/nonexistent.png"), prompt="test")
    assert result.is_ok is False
    assert result.error is not None
    assert "PR(b)" in result.error

    glm = GLMOCRExtractor(model_id="zai-org/GLM-OCR")
    result = glm.extract(image_path=Path("/nonexistent.png"), prompt="test")
    assert result.is_ok is False
    assert result.error is not None


def test_validate_manifest_rejects_missing_key() -> None:
    """`validate_manifest()` raises ValueError when a manifest entry is missing a required key."""
    from horus.vlm_extractor import (
        COHORT_MANIFEST,
        MLXVLMExtractor,
        validate_manifest,
    )

    # Inject a bad entry into a copy + monkey-patch.
    original = dict(COHORT_MANIFEST)
    try:
        # Missing `prompt_template`.
        COHORT_MANIFEST["bad/missing-prompt"] = {
            "extractor_class": MLXVLMExtractor,
            "category": 1,
            "max_tokens": 1024,
            "quant_target": "bf16",
            "alt_model_id": None,
            "license": "apache-2.0",
            "needs_trust_remote_code": False,
            "note": "synthetic bad entry for test",
        }
        with pytest.raises(ValueError) as exc_info:
            validate_manifest()
        assert "bad/missing-prompt" in str(exc_info.value)
        assert "prompt_template" in str(exc_info.value)
    finally:
        # Restore original manifest so other tests + module re-validation work.
        COHORT_MANIFEST.clear()
        COHORT_MANIFEST.update(original)


def test_validate_manifest_rejects_invalid_category() -> None:
    """`validate_manifest()` raises ValueError on category not in {1,2,3}."""
    from horus.vlm_extractor import (
        COHORT_MANIFEST,
        MLXVLMExtractor,
        validate_manifest,
    )

    original = dict(COHORT_MANIFEST)
    try:
        COHORT_MANIFEST["bad/bad-category"] = {
            "extractor_class": MLXVLMExtractor,
            "category": 5,  # invalid — not in {1, 2, 3}
            "prompt_template": "test",
            "max_tokens": 1024,
            "quant_target": "bf16",
            "alt_model_id": None,
            "license": "apache-2.0",
            "needs_trust_remote_code": False,
            "note": "synthetic bad entry for test",
        }
        with pytest.raises(ValueError) as exc_info:
            validate_manifest()
        assert "bad/bad-category" in str(exc_info.value)
        assert "category" in str(exc_info.value)
    finally:
        COHORT_MANIFEST.clear()
        COHORT_MANIFEST.update(original)


def test_validate_manifest_rejects_invalid_extractor_class() -> None:
    """`validate_manifest()` raises ValueError when extractor_class is not a recognised class."""
    from horus.vlm_extractor import COHORT_MANIFEST, validate_manifest

    class _NotAnExtractor:
        """Some random class that's not in the valid_classes tuple."""

    original = dict(COHORT_MANIFEST)
    try:
        COHORT_MANIFEST["bad/wrong-class"] = {
            "extractor_class": _NotAnExtractor,
            "category": 1,
            "prompt_template": "test",
            "max_tokens": 1024,
            "quant_target": "bf16",
            "alt_model_id": None,
            "license": "apache-2.0",
            "needs_trust_remote_code": False,
            "note": "synthetic bad entry for test",
        }
        with pytest.raises(ValueError) as exc_info:
            validate_manifest()
        assert "bad/wrong-class" in str(exc_info.value)
        assert "extractor_class" in str(exc_info.value)
    finally:
        COHORT_MANIFEST.clear()
        COHORT_MANIFEST.update(original)


def test_default_max_tokens_is_positive_int() -> None:
    """`DEFAULT_MAX_TOKENS` is a positive int."""
    from horus.vlm_extractor import DEFAULT_MAX_TOKENS

    assert isinstance(DEFAULT_MAX_TOKENS, int)
    assert DEFAULT_MAX_TOKENS > 0


def test_pr_a_alt_model_ids_point_to_quantised_ports() -> None:
    """PR(a) DeepSeek-OCR-2 + Gemma-4-E4B-it have MLX 4-bit alt_model_id ports."""
    from horus.vlm_extractor import COHORT_MANIFEST

    deepseek_alt = COHORT_MANIFEST["deepseek-ai/DeepSeek-OCR-2"]["alt_model_id"]
    assert deepseek_alt == "mlx-community/DeepSeek-OCR-2-4bit", (
        f"DeepSeek-OCR-2 alt_model_id should be mlx-community 4bit port, got {deepseek_alt!r}"
    )

    gemma_alt = COHORT_MANIFEST["google/gemma-4-E4B-it"]["alt_model_id"]
    assert gemma_alt == "lmstudio-community/gemma-4-E4B-it-MLX-4bit", (
        f"Gemma-4-E4B-it alt_model_id should be lmstudio-community MLX 4bit port, got {gemma_alt!r}"
    )

    # Granite-Docling-258M is already MLX-ported as the canonical model_id, so no alt needed.
    granite_alt = COHORT_MANIFEST["ibm-granite/granite-docling-258M-mlx"]["alt_model_id"]
    assert granite_alt is None
