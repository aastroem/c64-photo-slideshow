import json
import sys
import pathlib

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import convert
import preview
from c64color import PALETTE_RGB


def solid(rgb, size=(800, 600)):
    return Image.new("RGB", size, tuple(rgb))


def test_solid_palette_color_converts_losslessly():
    img = convert.convert_image(solid(PALETTE_RGB[5]), convert.Settings(dither="fs"))
    idx = preview.indices(img)
    vis = idx[:, 12:]  # skip FLI-bug columns
    assert set(np.unique(vis)) == {5}


def test_colorbars_lossless():
    # 16 vertical bars of exact palette colors
    bar = np.zeros((600, 800, 3), dtype=np.uint8)
    for i in range(16):
        bar[:, i * 50:(i + 1) * 50] = PALETTE_RGB[i]
    img = convert.convert_image(Image.fromarray(bar), convert.Settings(dither="bayer4"))
    idx = preview.indices(img)
    # sample near the center of each bar (visible area maps to x 12..159)
    for i in range(16):
        x = 12 + int((i + 0.5) / 16 * 148)
        col = idx[50:150, x]
        vals, counts = np.unique(col, return_counts=True)
        assert vals[np.argmax(counts)] == i, f"bar {i}"


def test_every_pixel_respects_sliver_palette():
    rng = np.random.default_rng(7)
    noise = rng.integers(0, 256, (600, 800, 3), dtype=np.uint8)
    photo = Image.fromarray(noise).resize((800, 600))
    img = convert.convert_image(photo, convert.Settings(dither="hybrid"))
    idx = preview.indices(img)
    for y in range(0, 200, 17):
        for x in range(12, 160, 13):
            assert idx[y, x] in img.pixel_colors(y, x)


def test_left_columns_black():
    img = convert.convert_image(solid((255, 255, 255)), convert.Settings())
    assert not img.screens[:, :, :3].any()
    assert not img.bitmap[:, :3, :].any()
    assert not img.color[:, :3].any()


def test_portrait_gets_padded_sides():
    img = convert.convert_image(solid(PALETTE_RGB[5], size=(600, 800)),
                                convert.Settings(dither="bayer4", pad=11))
    idx = preview.indices(img)
    # side bars in pad color, photo (green) in the middle
    assert set(np.unique(idx[20:180, 14:30])) == {11}
    assert set(np.unique(idx[20:180, 130:146])) == {11}
    mid = idx[20:180, 70:90]
    assert (mid == 5).mean() > 0.9


def test_sidecar_roundtrip(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    s = convert.Settings(dither="bayer8", strength=0.5, sat=1.2, gamma=0.9)
    convert.save_sidecar(p, s)
    loaded = convert.load_sidecar(p)
    assert loaded == s
    assert json.loads((tmp_path / "x.jpg.c64.json").read_text())["dither"] == "bayer8"
