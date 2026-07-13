import json
import subprocess
import sys
import pathlib

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import convert
import preview
from c64color import PALETTE_RGB

ROOT = pathlib.Path(__file__).resolve().parents[1]


def solid(rgb, size=(800, 600)):
    return Image.new("RGB", size, tuple(rgb))


def test_solid_palette_color_converts_losslessly():
    img = convert.convert_image(solid(PALETTE_RGB[5]), convert.Settings(dither="fs"))
    idx = preview.indices(img)
    vis = idx[:, 12:12 + convert.VISW]  # skip FLI-bug cols + blank col 39
    assert set(np.unique(vis)) == {5}


def test_colorbars_lossless():
    # 16 vertical bars of exact palette colors
    bar = np.zeros((600, 800, 3), dtype=np.uint8)
    for i in range(16):
        bar[:, i * 50:(i + 1) * 50] = PALETTE_RGB[i]
    img = convert.convert_image(Image.fromarray(bar), convert.Settings(dither="bayer4"))
    idx = preview.indices(img)
    # sample near the center of each bar (visible area maps to x 12..155)
    for i in range(16):
        x = 12 + int((i + 0.5) / 16 * convert.VISW)
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


def test_tail_lines_share_screen_colors():
    # rasters 248-250 redisplay line 196's screen colors on real hardware;
    # the converter emits identical bytes for banks 4-7 of the last cell
    # row so the display matches the intent exactly
    rng = np.random.default_rng(5)
    noise = rng.integers(0, 256, (600, 800, 3), dtype=np.uint8)
    img = convert.convert_image(Image.fromarray(noise), convert.Settings())
    for bank in (5, 6, 7):
        assert (img.screens[bank, 24] == img.screens[4, 24]).all()


def test_portrait_gets_padded_sides():
    img = convert.convert_image(solid(PALETTE_RGB[5], size=(600, 800)),
                                convert.Settings(dither="bayer4", pad=11))
    idx = preview.indices(img)
    # side bars in pad color, photo (green) in the middle
    assert set(np.unique(idx[20:180, 14:30])) == {11}
    assert set(np.unique(idx[20:180, 130:146])) == {11}
    mid = idx[20:180, 70:90]
    assert (mid == 5).mean() > 0.9


def test_sidecar_records_only_pinned_keys(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    s = convert.Settings(sat=1.2)
    convert.save_sidecar(p, s, {"sat"})
    assert json.loads((tmp_path / "x.jpg.c64.json").read_text()) == {"sat": 1.2}
    loaded = convert.load_sidecar(p)
    assert loaded.sat == 1.2
    assert loaded.dither == convert.Settings().dither   # unpinned -> default
    assert convert.raw_sidecar(p) == {"sat": 1.2}


def test_save_sidecar_writes_no_file_when_nothing_pinned(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    convert.save_sidecar(p, convert.Settings(), set())
    assert not convert.sidecar_path(p).exists()


def test_save_sidecar_removes_existing_file_when_unpinned(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    convert.save_sidecar(p, convert.Settings(sat=1.2), {"sat"})
    assert convert.sidecar_path(p).exists()
    convert.save_sidecar(p, convert.Settings(), set())
    assert not convert.sidecar_path(p).exists()


def test_raw_sidecar_is_empty_when_absent(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    assert convert.raw_sidecar(p) == {}
    assert convert.load_sidecar(p) == convert.Settings()


def test_legacy_full_sidecar_still_loads(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    (tmp_path / "x.jpg.c64.json").write_text(json.dumps({
        "dither": "bayer8", "strength": 0.5, "sat": 1.2, "gamma": 0.9,
        "crop": "0,0", "pad": 0, "mode": "fli"}))
    assert convert.load_sidecar(p) == convert.Settings(
        dither="bayer8", strength=0.5, sat=1.2, gamma=0.9)
    assert convert.raw_sidecar(p)["mode"] == "fli"   # legacy file pins mode


def test_hires_mode_packs_flip_container():
    import modes
    img, out = modes.convert_hires(solid(PALETTE_RGB[5]), convert.Settings())
    # all 8 screen banks identical (display reads bank 0; dup compresses away)
    for bank in range(1, 8):
        assert (img.screens[bank] == img.screens[0]).all()
    assert len(img.pack()) == 15727
    assert out.shape == (200, 320)


def test_afli_mode_per_line_pairs():
    import modes
    import numpy as np
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 256, (600, 900, 3), dtype=np.uint8)
    img, out = modes.convert_afli(Image.fromarray(noise), convert.Settings())
    # screen banks must differ (per-line pairs), unlike plain hires
    assert any((img.screens[b] != img.screens[0]).any() for b in range(1, 8))
    assert len(img.pack()) == 15727


def test_afli_tail_lines_share_screen_colors():
    # rasters 248-250 redisplay line 196's screen colors, and resolve lines
    # 197-199's bitmap bits against that pair -- so the pair must be shared,
    # or those pixels invert wherever the light/dark order disagrees
    import modes
    import numpy as np
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 256, (600, 900, 3), dtype=np.uint8)
    img, out = modes.convert_afli(Image.fromarray(noise), convert.Settings())
    for bank in (5, 6, 7):
        assert (img.screens[bank, 24] == img.screens[4, 24]).all()
    # what the VIC actually paints on lines 196-199 == what the converter meant
    for y in range(196, 200):
        for c in range(modes.VIS0, modes.VIS0 + modes.VIS_COLS):
            hi, lo = img.screens[4, 24, c] >> 4, img.screens[4, 24, c] & 15
            bits = np.unpackbits(np.uint8([img.bitmap[24, c, y % 8]]))
            shown = np.where(bits == 1, hi, lo)
            assert (shown == out[y, c*8:c*8+8]).all(), f"line {y} cell {c}"


def test_default_mode_applies_but_is_not_persisted(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    out = tmp_path / "x.fli"
    subprocess.run([sys.executable, str(ROOT / "convert.py"), str(p),
                    "-o", str(out), "--default-mode", "afli"],
                   check=True, cwd=ROOT)
    assert out.exists()
    assert convert.raw_sidecar(p) == {}          # nothing pinned, nothing written


def test_explicit_mode_is_persisted_and_beats_default(tmp_path):
    p = tmp_path / "x.jpg"
    solid((10, 200, 30)).save(p)
    out = tmp_path / "x.fli"
    subprocess.run([sys.executable, str(ROOT / "convert.py"), str(p),
                    "-o", str(out), "--mode", "hires",
                    "--default-mode", "afli"], check=True, cwd=ROOT)
    assert convert.raw_sidecar(p) == {"mode": "hires"}
