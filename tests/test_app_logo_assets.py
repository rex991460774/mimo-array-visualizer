from pathlib import Path

from PIL import Image


ASSET_DIR = Path(__file__).resolve().parents[1] / "src" / "virtual_array" / "assets"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)


def test_logo_png_set_is_complete_and_square() -> None:
    for size in PNG_SIZES:
        path = ASSET_DIR / f"mimo_array_logo_{size}.png"
        assert path.exists()
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.mode == "RGBA"
            assert image.size == (size, size)


def test_logo_master_has_transparent_corners_and_opaque_center() -> None:
    with Image.open(ASSET_DIR / "mimo_array_logo_1024.png") as image:
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((512, 512))[3] == 255

        opaque = rgba.getchannel("A").getbbox()
        assert opaque is not None
        assert opaque[0] > 0
        assert opaque[1] > 0
        assert opaque[2] < rgba.width
        assert opaque[3] < rgba.height


def test_logo_master_contains_black_tile_and_white_wordmark() -> None:
    with Image.open(ASSET_DIR / "mimo_array_logo_1024.png") as image:
        colors = set(image.convert("RGBA").get_flattened_data())

    assert (0, 0, 0, 0) in colors
    assert (0, 0, 0, 255) in colors
    assert (255, 255, 255, 255) in colors


def test_logo_wordmark_has_two_continuous_horizontal_seams() -> None:
    with Image.open(ASSET_DIR / "mimo_array_logo_1024.png") as image:
        rgba = image.convert("RGBA")
        white = rgba.point(
            lambda value: 255 if value == 255 else 0,
        ).getchannel("R")
        bbox = white.getbbox()

    assert bbox is not None
    left, top, right, bottom = bbox
    wordmark_height = bottom - top
    for ratio in (0.36, 0.67):
        y = top + round((wordmark_height - 1) * ratio)
        assert white.crop((left, y, right, y + 1)).getbbox() is None


def test_windows_icon_contains_expected_frames() -> None:
    with Image.open(ASSET_DIR / "mimo_array_logo.ico") as image:
        assert image.format == "ICO"
        assert image.ico.sizes() == {
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        }


def test_macos_icon_contains_retina_sizes() -> None:
    with Image.open(ASSET_DIR / "mimo_array_logo.icns") as image:
        assert image.format == "ICNS"
        sizes = set(image.info["sizes"])

    assert (16, 16, 2) in sizes
    assert (32, 32, 2) in sizes
    assert (256, 256, 2) in sizes
    assert (512, 512, 2) in sizes
