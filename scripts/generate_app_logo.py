"""Build the MAV application icon set from a selected black-and-white wordmark.

Pass ``--source`` when adopting a new wordmark. The script normalizes the
bright artwork onto the production rounded black tile, writes the 1024 px
master, and regenerates every PNG/ICO/ICNS derivative. Without ``--source`` it
rebuilds the derivatives from the checked-in 1024 px master.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_DIR = ROOT / "src" / "virtual_array" / "assets"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
MASTER_SIZE = 1024
TILE_INSET = 32
TILE_RADIUS = 176
WORDMARK_WIDTH = 880
SEAM_BANDS = ((0.315, 0.415), (0.62, 0.72))


def _bright_artwork_mask(source: Image.Image) -> Image.Image:
    """Extract bright wordmark pixels while ignoring a dark source canvas."""

    rgba = source.convert("RGBA")
    luminance = ImageOps.grayscale(rgba)
    visible_luminance = ImageChops.multiply(luminance, rgba.getchannel("A"))
    mask = visible_luminance.point(lambda value: 255 if value >= 128 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("The source image contains no bright logo artwork.")
    return mask.crop(bbox)


def _build_master(source_path: Path) -> Image.Image:
    with Image.open(source_path) as source:
        wordmark = _bright_artwork_mask(source)

    target_height = max(1, round(wordmark.height * WORDMARK_WIDTH / wordmark.width))
    wordmark = wordmark.resize(
        (WORDMARK_WIDTH, target_height),
        Image.Resampling.NEAREST,
    )
    seam_draw = ImageDraw.Draw(wordmark)
    for start_ratio, end_ratio in SEAM_BANDS:
        start_y = round(wordmark.height * start_ratio)
        end_y = round(wordmark.height * end_ratio) - 1
        seam_draw.rectangle((0, start_y, wordmark.width - 1, end_y), fill=0)

    master = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(master)
    draw.rounded_rectangle(
        (
            TILE_INSET,
            TILE_INSET,
            MASTER_SIZE - TILE_INSET - 1,
            MASTER_SIZE - TILE_INSET - 1,
        ),
        radius=TILE_RADIUS,
        fill=(0, 0, 0, 255),
    )

    x = (MASTER_SIZE - wordmark.width) // 2
    y = (MASTER_SIZE - wordmark.height) // 2
    white = Image.new("RGBA", wordmark.size, (255, 255, 255, 255))
    master.paste(white, (x, y), wordmark)
    return master


def _load_master(asset_dir: Path) -> Image.Image:
    master_path = asset_dir / "mimo_array_logo_1024.png"
    if not master_path.exists():
        raise FileNotFoundError(
            f"Missing {master_path}; pass --source to create the master first."
        )
    with Image.open(master_path) as image:
        return image.convert("RGBA")


def _write_icon_set(master: Image.Image, asset_dir: Path) -> None:
    asset_dir.mkdir(parents=True, exist_ok=True)
    for size in PNG_SIZES:
        output = asset_dir / f"mimo_array_logo_{size}.png"
        icon = (
            master.copy()
            if size == MASTER_SIZE
            else master.resize((size, size), Image.Resampling.LANCZOS)
        )
        icon.save(output, format="PNG", optimize=True)

    master.save(
        asset_dir / "mimo_array_logo.ico",
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )
    master.save(asset_dir / "mimo_array_logo.icns", format="ICNS")


def build_icon_set(source_path: Path | None, asset_dir: Path) -> None:
    master = _build_master(source_path) if source_path is not None else _load_master(asset_dir)
    _write_icon_set(master, asset_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="Selected black-background wordmark image used to create a new master.",
    )
    parser.add_argument(
        "--asset-dir",
        type=Path,
        default=DEFAULT_ASSET_DIR,
        help=f"Destination directory (default: {DEFAULT_ASSET_DIR}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve() if args.source is not None else None
    asset_dir = args.asset_dir.resolve()
    build_icon_set(source, asset_dir)
    print(f"Generated MAV icon assets in {asset_dir}")


if __name__ == "__main__":
    main()
