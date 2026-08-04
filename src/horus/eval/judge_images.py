"""Page rasters → images the vision judge can actually read (ADR-060 support module).

The 300 DPI rasters that feed the local cohort are the wrong shape for a cloud vision
API, in two distinct ways that both silently damage ground truth:

**Hard rejection.** The Messages API refuses any image whose long edge exceeds 8000 px.
One held-out page — a photographed till receipt at 2306 × 10325 — trips this, and the
whole invoice fails with a 400 rather than degrading.

**Silent crushing, which is worse.** Images above the model's resolution tier are
downscaled *server-side*, so a 4975 × 6978 A4 scan is quietly reduced and the judge reads
whatever survives. For an instrument that authors an answer key, "whatever survives" is
not an acceptable input contract: what the judge saw must be knowable and reproducible.

So resizing happens HERE, deterministically, with a recorded result — a faithful port of
the resize the API documents (`resized_size`), which also makes visual-token cost
predictable instead of discovered on the invoice.

Tiling, and why it is not gold-plating: fitting a 1:4.5 receipt into a 2576 px box leaves
it ~575 px wide, which destroys the small print that IS the ground truth. Splitting a
tall page into overlapping, page-shaped tiles gives each tile its own resolution budget
and recovers roughly 3× the linear detail. Both tall pages in the held-out set are
phone-scanned receipts — precisely the Tier B documents where no text layer exists to
cross-check against, so judge fidelity is the only line of defence.

Source archival: `docs/sources/tools/claude-vision-image-limits.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

#: Visual tokens are one per 28 × 28 px patch; every limit below is expressed against it.
PATCH_PX = 28

#: Standard resolution tier (older models).
STANDARD_MAX_EDGE = 1568
STANDARD_MAX_TOKENS = 1568

#: High-resolution tier. Enabled automatically for supported models with no request-side
#: configuration, so the client's only job is to not exceed it.
HIGH_RES_MAX_EDGE = 2576
HIGH_RES_MAX_TOKENS = 4784

#: Above this many images in one request the API applies a stricter per-side limit.
MANY_IMAGE_THRESHOLD = 20
MANY_IMAGE_MAX_EDGE = 2000

#: Long-edge : short-edge ratio above which a page is treated as a receipt strip and
#: tiled. A4 is ~1.41 and the held-out median is 1.41, so 2.2 sits far from normal
#: pages while catching both genuine strips (2.57 and 4.48).
TALL_ASPECT_THRESHOLD = 2.2

#: Tiles are cut to roughly page proportions — the shape these models see most.
TILE_TARGET_ASPECT = 1.4

#: Fraction of tile height repeated across the seam, so a line of text split by a cut is
#: still intact in one of the two neighbouring tiles.
TILE_OVERLAP = 0.12


def count_image_tokens(width: int, height: int) -> int:
    """Visual tokens an image consumes: one per 28 × 28 px patch."""
    return math.ceil(width / PATCH_PX) * math.ceil(height / PATCH_PX)


def _fits(width: int, height: int, max_edge: int, max_tokens: int) -> bool:
    """Whether a size satisfies both the padded-edge and the visual-token limit."""
    return (
        math.ceil(width / PATCH_PX) * PATCH_PX <= max_edge
        and math.ceil(height / PATCH_PX) * PATCH_PX <= max_edge
        and count_image_tokens(width, height) <= max_tokens
    )


def _short_edge(long_edge: int, aspect_ratio: float) -> int:
    """Aspect-preserving short edge. `round()` is half-to-even, matching the API's rint."""
    return max(round(long_edge / aspect_ratio), 1)


def resized_size(
    width: int,
    height: int,
    *,
    max_edge: int = HIGH_RES_MAX_EDGE,
    max_tokens: int = HIGH_RES_MAX_TOKENS,
) -> tuple[int, int]:
    """The size the API would resize an image to — computed locally, ahead of the call.

    Faithful port of the published algorithm, including the binary search along the long
    edge and half-to-even rounding of the short edge, so client-side and server-side
    resizing agree and the visual-token count is known before spending anything. Sizes
    already within both limits are returned unchanged.

    The documented A4 check case: ``resized_size(1075, 1520, max_edge=1568,
    max_tokens=1568)`` returns ``(924, 1307)``.
    """
    if _fits(width, height, max_edge, max_tokens):
        return width, height
    if height > width:
        rotated_w, rotated_h = resized_size(height, width, max_edge=max_edge, max_tokens=max_tokens)
        return rotated_h, rotated_w

    aspect_ratio = width / height
    low, high = 1, width  # low always fits; high never does
    while low + 1 < high:
        mid = (low + high) // 2
        if _fits(mid, _short_edge(mid, aspect_ratio), max_edge, max_tokens):
            low = mid
        else:
            high = mid
    return low, _short_edge(low, aspect_ratio)


def plan_tiles(
    width: int,
    height: int,
    *,
    aspect_threshold: float = TALL_ASPECT_THRESHOLD,
    target_aspect: float = TILE_TARGET_ASPECT,
    overlap: float = TILE_OVERLAP,
) -> list[tuple[int, int, int, int]]:
    """Crop boxes covering a page, splitting only strips too tall to read whole.

    Returns one full-page box for ordinary pages, so callers need no special case. For a
    tall strip, returns overlapping top-to-bottom boxes of roughly ``target_aspect``
    proportions; the overlap means a text line crossing a cut survives intact in a
    neighbour. Only the tall axis is ever split — a page is never divided left/right,
    which would break reading order.
    """
    if height <= 0 or width <= 0:
        raise ValueError(f"page has a non-positive dimension: {width}x{height}")
    if height / width <= aspect_threshold:
        return [(0, 0, width, height)]

    n_tiles = max(2, math.ceil((height / width) / target_aspect))
    step = height / n_tiles
    pad = step * overlap
    boxes: list[tuple[int, int, int, int]] = []
    for index in range(n_tiles):
        top = max(0, int(round(index * step - pad)))
        bottom = min(height, int(round((index + 1) * step + pad)))
        boxes.append((0, top, width, bottom))
    return boxes


@dataclass(frozen=True)
class PreparedImage:
    """One image as the judge will receive it, with the provenance to reproduce it."""

    path: Path
    source_page: Path
    page_index: int
    tile_index: int
    tile_count: int
    width: int
    height: int
    tokens: int

    @property
    def is_tile(self) -> bool:
        """Whether this image is a slice of a taller page rather than a whole page."""
        return self.tile_count > 1


def prepare_judge_images(
    page_paths: list[Path],
    *,
    out_dir: Path,
    max_edge: int = HIGH_RES_MAX_EDGE,
    max_tokens: int = HIGH_RES_MAX_TOKENS,
) -> list[PreparedImage]:
    """Render every page to a judge-ready image, tiling strips and downscaling the rest.

    Writes PNGs into ``out_dir`` and returns them in reading order (page, then tile top
    to bottom). Lanczos resampling is used because the payload is small text, where
    nearest/bilinear visibly damages digit strokes — and a misread digit in an answer key
    is permanent.

    When the plan would exceed the request's image count threshold, the per-side limit
    drops to the API's stricter ceiling for many-image requests; that is applied to every
    image so one request never mixes two contracts.
    """
    from PIL import Image

    plans: list[tuple[int, Path, list[tuple[int, int, int, int]]]] = []
    for page_index, page_path in enumerate(page_paths):
        with Image.open(page_path) as img:
            width, height = img.size
        plans.append((page_index, page_path, plan_tiles(width, height)))

    total_images = sum(len(boxes) for _, _, boxes in plans)
    if total_images > MANY_IMAGE_THRESHOLD:
        max_edge = min(max_edge, MANY_IMAGE_MAX_EDGE)

    out_dir.mkdir(parents=True, exist_ok=True)
    prepared: list[PreparedImage] = []
    for page_index, page_path, boxes in plans:
        with Image.open(page_path) as img:
            source = img.convert("RGB")
            for tile_index, box in enumerate(boxes):
                tile = source.crop(box) if len(boxes) > 1 else source
                target = resized_size(*tile.size, max_edge=max_edge, max_tokens=max_tokens)
                if target != tile.size:
                    tile = tile.resize(target, Image.Resampling.LANCZOS)
                suffix = f"-tile{tile_index + 1}of{len(boxes)}" if len(boxes) > 1 else ""
                out_path = out_dir / f"page-{page_index + 1:02d}{suffix}.png"
                tile.save(out_path, format="PNG", optimize=True)
                prepared.append(
                    PreparedImage(
                        path=out_path,
                        source_page=page_path,
                        page_index=page_index,
                        tile_index=tile_index,
                        tile_count=len(boxes),
                        width=target[0],
                        height=target[1],
                        tokens=count_image_tokens(*target),
                    )
                )
    return prepared


def describe_images(prepared: list[PreparedImage]) -> str:
    """Explain the attached images to the judge, so tiles are not read as extra pages.

    Without this, overlapping tiles look like additional pages and the overlap invites
    double-counting — a repeated line item or a total transcribed twice. Returns an empty
    string when nothing was tiled, since ordinary pages need no explanation.
    """
    if not any(image.is_tile for image in prepared):
        return ""
    lines = [
        "IMAGE LAYOUT: some pages were too tall to send whole and were split into "
        "OVERLAPPING top-to-bottom slices. Slices of the same page are ONE page, not "
        "several. Because neighbouring slices deliberately repeat a band of content, a "
        "row visible in two slices is the SAME row — never count it twice.",
        "",
    ]
    for image in prepared:
        if image.is_tile:
            lines.append(
                f"- {image.path.name}: page {image.page_index + 1}, "
                f"slice {image.tile_index + 1} of {image.tile_count}"
            )
        else:
            lines.append(f"- {image.path.name}: page {image.page_index + 1}, whole page")
    return "\n".join(lines)
