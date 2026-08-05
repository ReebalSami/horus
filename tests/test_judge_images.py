"""Unit tests for judge image preparation (`horus.eval.judge_images`).

The resize is a faithful port of the API's own published algorithm, so the load-bearing
test is the documented check case: if that drifts, client-side and server-side sizing
disagree and the visual-token estimate silently stops matching what is billed.

The tiling tests pin the property that actually protects ground truth — a tall receipt
must be split rather than crushed to an unreadable width, and the slices must cover the
whole page with overlap so no printed row falls into a seam.
"""

from __future__ import annotations

import pytest

from horus.eval.judge_images import (
    HIGH_RES_MAX_EDGE,
    HIGH_RES_MAX_TOKENS,
    MANY_IMAGE_THRESHOLD,
    STANDARD_MAX_EDGE,
    STANDARD_MAX_TOKENS,
    count_image_tokens,
    describe_images,
    plan_tiles,
    prepare_judge_images,
    resized_size,
)

# --------------------------------------------------------------------------------------
# Token counting + resizing
# --------------------------------------------------------------------------------------


def test_count_image_tokens_is_one_per_28px_patch() -> None:
    assert count_image_tokens(28, 28) == 1
    assert count_image_tokens(29, 28) == 2  # partial patches count
    assert count_image_tokens(1120, 1120) == 1600


def test_resized_size_matches_the_documented_a4_case() -> None:
    """The published worked example. A mismatch here means the port has drifted."""
    assert resized_size(1075, 1520, max_edge=STANDARD_MAX_EDGE, max_tokens=STANDARD_MAX_TOKENS) == (
        924,
        1307,
    )


def test_resized_size_leaves_small_images_untouched() -> None:
    assert resized_size(800, 600) == (800, 600)


def test_resized_size_respects_both_limits() -> None:
    width, height = resized_size(4975, 6978)
    assert max(width, height) <= HIGH_RES_MAX_EDGE
    assert count_image_tokens(width, height) <= HIGH_RES_MAX_TOKENS


def test_resized_size_preserves_orientation() -> None:
    """A portrait page must stay portrait; the algorithm rotates internally."""
    width, height = resized_size(2306, 10325)
    assert height > width


def test_resized_size_preserves_aspect_ratio_closely() -> None:
    source_aspect = 4975 / 6978
    width, height = resized_size(4975, 6978)
    assert abs((width / height) - source_aspect) < 0.01


# --------------------------------------------------------------------------------------
# Tiling
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), [(2480, 3508), (4975, 6978), (1200, 1600)])
def test_ordinary_pages_are_not_tiled(width: int, height: int) -> None:
    """A4-proportioned pages (~1.41) must pass through as a single whole-page box."""
    assert plan_tiles(width, height) == [(0, 0, width, height)]


def test_wide_pages_are_not_tiled() -> None:
    """Only the tall axis is ever split; a landscape page is never divided left/right."""
    assert plan_tiles(3508, 2480) == [(0, 0, 3508, 2480)]


@pytest.mark.parametrize(
    ("width", "height", "min_tiles"),
    [(2306, 10325, 3), (2434, 6253, 2)],
)
def test_tall_receipts_are_tiled(width: int, height: int, min_tiles: int) -> None:
    boxes = plan_tiles(width, height)
    assert len(boxes) >= min_tiles


def test_tiles_cover_the_whole_page() -> None:
    """No printed row may fall outside every slice."""
    width, height = 2306, 10325
    boxes = plan_tiles(width, height)
    assert boxes[0][1] == 0
    assert boxes[-1][3] == height
    for box in boxes:
        assert box[0] == 0 and box[2] == width  # full width every time


def test_consecutive_tiles_overlap() -> None:
    """A line split by a cut must survive intact in a neighbouring slice."""
    boxes = plan_tiles(2306, 10325)
    for earlier, later in zip(boxes, boxes[1:], strict=False):
        assert later[1] < earlier[3], "expected the next tile to start before the previous ends"


def test_tiling_recovers_resolution_that_whole_page_fitting_would_lose() -> None:
    """The reason tiling exists: a 1:4.5 strip fitted whole becomes unreadably narrow."""
    width, height = 2306, 10325
    whole_w, _ = resized_size(width, height)
    boxes = plan_tiles(width, height)
    tile_w, _ = resized_size(boxes[0][2] - boxes[0][0], boxes[0][3] - boxes[0][1])
    assert tile_w > 2 * whole_w


def test_plan_tiles_rejects_degenerate_pages() -> None:
    with pytest.raises(ValueError, match="non-positive"):
        plan_tiles(0, 100)


# --------------------------------------------------------------------------------------
# End-to-end preparation
# --------------------------------------------------------------------------------------


def _write_png(path, width: int, height: int) -> None:
    from PIL import Image

    Image.new("RGB", (width, height), color=(255, 255, 255)).save(path)


def test_prepare_judge_images_downscales_an_oversized_page(tmp_path) -> None:
    page = tmp_path / "page-1.png"
    _write_png(page, 4000, 5600)
    prepared = prepare_judge_images([page], out_dir=tmp_path / "out")

    assert len(prepared) == 1
    image = prepared[0]
    assert image.path.is_file()
    assert max(image.width, image.height) <= HIGH_RES_MAX_EDGE
    assert image.tokens <= HIGH_RES_MAX_TOKENS
    assert image.is_tile is False


def test_prepare_judge_images_tiles_a_tall_page(tmp_path) -> None:
    page = tmp_path / "page-1.png"
    _write_png(page, 600, 3000)
    prepared = prepare_judge_images([page], out_dir=tmp_path / "out")

    assert len(prepared) > 1
    assert all(image.is_tile for image in prepared)
    assert all(image.page_index == 0 for image in prepared)
    assert [image.tile_index for image in prepared] == list(range(len(prepared)))
    assert all(image.path.is_file() for image in prepared)


def test_prepare_judge_images_never_exceeds_the_hard_api_dimension_limit(tmp_path) -> None:
    """The 400 that motivated this module: no output may exceed the API's 8000 px cap."""
    page = tmp_path / "page-1.png"
    _write_png(page, 2306, 10325)
    prepared = prepare_judge_images([page], out_dir=tmp_path / "out")
    assert all(max(image.width, image.height) <= 8000 for image in prepared)


def test_many_images_trigger_the_stricter_dimension_limit(tmp_path) -> None:
    pages = []
    for index in range(MANY_IMAGE_THRESHOLD + 1):
        page = tmp_path / f"page-{index}.png"
        _write_png(page, 4000, 5600)
        pages.append(page)
    prepared = prepare_judge_images(pages, out_dir=tmp_path / "out")
    assert len(prepared) == MANY_IMAGE_THRESHOLD + 1
    assert all(max(image.width, image.height) <= 2000 for image in prepared)


def test_preserves_page_order_across_pages_and_tiles(tmp_path) -> None:
    short_page = tmp_path / "a.png"
    tall_page = tmp_path / "b.png"
    _write_png(short_page, 1000, 1400)
    _write_png(tall_page, 600, 3000)
    prepared = prepare_judge_images([short_page, tall_page], out_dir=tmp_path / "out")

    assert prepared[0].page_index == 0
    assert prepared[0].is_tile is False
    assert all(image.page_index == 1 for image in prepared[1:])


# --------------------------------------------------------------------------------------
# The layout note sent to the judge
# --------------------------------------------------------------------------------------


def test_describe_images_is_silent_when_nothing_was_tiled(tmp_path) -> None:
    """Ordinary pages need no explanation; a spurious note is just prompt noise."""
    page = tmp_path / "page-1.png"
    _write_png(page, 1000, 1400)
    prepared = prepare_judge_images([page], out_dir=tmp_path / "out")
    assert describe_images(prepared) == ""


def test_describe_images_warns_against_double_counting_when_tiled(tmp_path) -> None:
    """Overlapping slices otherwise read as extra pages with duplicated rows."""
    page = tmp_path / "page-1.png"
    _write_png(page, 600, 3000)
    prepared = prepare_judge_images([page], out_dir=tmp_path / "out")
    note = describe_images(prepared)

    assert "ONE page" in note
    assert "never count it twice" in note.lower()
    for image in prepared:
        assert image.path.name in note
