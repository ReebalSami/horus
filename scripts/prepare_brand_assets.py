"""One-time brand-asset preparation for the Streamlit observability app (ADR-036, #103).

Produces the background-removed PNG brand assets the dashboard loads at runtime
from the raw logo source JPEGs the user provided. Run once:

    uv run python scripts/prepare_brand_assets.py

The OUTPUTS (``app/assets/brand/*.png``) are git-tracked (the running app loads
them); the SOURCES (``app/assets/brand/sources/*.jpeg``) are git-ignored. On a
fresh clone without the sources this script is a no-op-with-error — the tracked
PNGs are the artifacts of record.

Two assets are produced:

  - ``eye-of-horus.png``  — the Eye-of-Horus mark (gold + teal) with its dark
    textured background keyed out. Colourful, so it reads on both light and dark
    app backgrounds. Used as the favicon, sidebar logo icon, and hero mark.
  - ``horus-wordmark.png`` — the "HORUS" wordmark lifted from the falcon logo,
    its flat sand background keyed out and cropped to the lettering. Used in the
    Home hero.

Background removal is done locally with Pillow + NumPy (no external service, no
extra runtime dependency) — a luminance key for the dark-background eye and a
colour-distance key for the flat-background wordmark. This keeps the logo
pipeline reproducible and inside the firm (per the AGENTS.md privacy posture).
Re-tune the threshold / crop constants below if the source art is swapped.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

BRAND_DIR = Path(__file__).resolve().parent.parent / "app" / "assets" / "brand"
SOURCES_DIR = BRAND_DIR / "sources"

EYE_SOURCE = SOURCES_DIR / "EA6CA550-F8EB-41DE-8E4F-919E44FB27F5_1_105_c.jpeg"
WORDMARK_SOURCE = SOURCES_DIR / "BD72E93D-4254-4359-A773-27E3B9EFC75F_1_105_c.jpeg"

# Flat background colour of the wordmark source (warm sand) — keyed out.
_SAND_RGB = (242, 200, 121)


def _autocrop_alpha(img: Image.Image, *, pad: int = 24) -> Image.Image:
    """Crop to the alpha bounding box plus a small transparent padding."""
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        return img
    left, upper, right, lower = bbox
    return img.crop(
        (
            max(0, left - pad),
            max(0, upper - pad),
            min(img.width, right + pad),
            min(img.height, lower + pad),
        )
    )


def _finalize(arr: np.ndarray, alpha: np.ndarray, *, floor: float = 0.30) -> Image.Image:
    """Compose an RGBA image from an RGB array + a [0, 1] alpha; drop faint halo."""
    alpha = np.where(alpha < floor, 0.0, alpha)
    rgba = np.dstack([arr, alpha * 255.0]).astype(np.uint8)
    return _autocrop_alpha(Image.fromarray(rgba, "RGBA"))


def key_out_dark_background(src: Path, *, lo: float = 86.0, hi: float = 124.0) -> Image.Image:
    """Remove a dark textured background via a luminance + saturation alpha key.

    Keeps only pixels that are bright (the gold strokes) OR saturated (the teal
    fill); everything dark-and-desaturated (the textured black wall, including
    its lighter scuff marks) drops out. ``lo``/``hi`` bound the luminance ramp;
    the saturation rescue keeps the darker teal that luminance alone would lose.
    A relatively high alpha floor removes faint background-texture halo.
    """
    arr = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32)
    lum = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    alpha = np.clip((lum - lo) / (hi - lo), 0.0, 1.0)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = (mx - mn) / (mx + 1e-6)
    alpha = np.maximum(alpha, np.clip((sat - 0.30) / 0.22, 0.0, 1.0))
    return _finalize(arr, alpha, floor=0.45)


def key_out_sand_background(
    src: Path,
    *,
    crop_box: tuple[float, float, float, float],
    lo: float = 50.0,
    hi: float = 120.0,
) -> Image.Image:
    """Crop to ``crop_box`` (l, u, r, d fractions) then key out the flat sand background.

    The wordmark sits in the lower band of the falcon logo on a solid sand
    field; cropping first excludes the falcon, then a colour-distance ramp from
    the sand colour turns the field transparent while keeping the black letters.
    """
    img = Image.open(src).convert("RGB")
    left, upper, right, lower = crop_box
    img = img.crop(
        (
            int(left * img.width),
            int(upper * img.height),
            int(right * img.width),
            int(lower * img.height),
        )
    )
    arr = np.asarray(img, dtype=np.float32)
    dist = np.sqrt(((arr - np.array(_SAND_RGB, dtype=np.float32)) ** 2).sum(axis=2))
    alpha = np.clip((dist - lo) / (hi - lo), 0.0, 1.0)
    return _finalize(arr, alpha)


def main() -> int:
    if not EYE_SOURCE.exists() or not WORDMARK_SOURCE.exists():
        print(f"ERROR: brand source images not found under {SOURCES_DIR}.")
        print("This script is a one-time prep; the produced PNGs are git-tracked.")
        return 1

    eye = key_out_dark_background(EYE_SOURCE)
    eye.save(BRAND_DIR / "eye-of-horus.png")
    print(f"  wrote {BRAND_DIR / 'eye-of-horus.png'}  ({eye.width}x{eye.height})")

    wordmark = key_out_sand_background(WORDMARK_SOURCE, crop_box=(0.16, 0.60, 0.84, 0.93))
    wordmark.save(BRAND_DIR / "horus-wordmark.png")
    print(f"  wrote {BRAND_DIR / 'horus-wordmark.png'}  ({wordmark.width}x{wordmark.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
