# HORUS brand assets

Visual identity for the HORUS observability dashboard (`app/`), per ADR-036 (#103).

## Files

| File | Tracked? | What it is |
|------|----------|------------|
| `eye-of-horus.png` | yes | The Eye-of-Horus mark (gold + teal), background removed. Used as the favicon, the sidebar logo, and the Home hero mark. Colourful, so it reads on both light and dark backgrounds. |
| `horus-wordmark.png` | yes | The "HORUS" wordmark, background removed, cropped to the lettering. Used in the Home hero. |
| `sources/` | **no** (git-ignored) | The raw logo source JPEGs the originals were derived from. Local-only. |

## How the PNGs are produced

The tracked PNGs are generated from the raw sources by:

```sh
uv run python scripts/prepare_brand_assets.py
```

Background removal is done **locally** (Pillow + NumPy — a luminance key for the
dark-background eye, a colour-distance key for the flat-background wordmark) so the
logo pipeline needs no external service and runs entirely inside the firm. Re-run
the script after swapping the source art; tune the threshold / crop constants in it
if the new art differs.

## Palette (the brand)

| Token | Hex | Role |
|-------|-----|------|
| Antique gold | `#C9A227` | Primary accent; the "winner" emphasis |
| Deep teal | `#0E4D45` | Structural / secondary; links |
| Warm sand | `#F2C879` | Soft fills / highlights |
| Ink | `#1A1A1A` | Text |
| Warm off-white | `#FBFAF7` | Canvas |

Chrome colours live in `.streamlit/config.toml`; data-encoding (outcome) colours
live in `app/components/theme.py`.

## Provenance / licensing note

The source images were downloaded as design inspiration and adapted into the working
brand for this thesis prototype. Before any external publication of the thesis,
confirm licensing of the source art or commission an original mark — the dashboard
loads only the produced PNGs, so swapping in a final logo is a one-file change.
