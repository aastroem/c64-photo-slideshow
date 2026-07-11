import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import c64color


def test_palette_shape():
    assert c64color.PALETTE_RGB.shape == (16, 3)
    assert c64color.PALETTE_RGB.dtype == np.uint8
    assert tuple(c64color.PALETTE_RGB[0]) == (0, 0, 0)
    assert tuple(c64color.PALETTE_RGB[1]) == (255, 255, 255)


def test_oklab_white_lightness():
    lab = c64color.srgb_to_oklab(np.array([[255, 255, 255]], dtype=np.uint8))
    assert abs(lab[0, 0] - 1.0) < 1e-3
    lab0 = c64color.srgb_to_oklab(np.array([[0, 0, 0]], dtype=np.uint8))
    assert abs(lab0[0, 0]) < 1e-3


def test_nearest_black_white():
    pal = c64color.palette_oklab()
    px = c64color.srgb_to_oklab(np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8))
    idx = c64color.nearest(px, pal)
    assert idx[0] == 0
    assert idx[1] == 1


def test_fade_table_reaches_black():
    ft = c64color.fade_table()
    assert len(ft) == 16
    assert ft[0] == 0
    L = c64color.palette_oklab()[:, 0]
    for c in range(16):
        cur = c
        for _ in range(8):
            nxt = ft[cur]
            if cur != 0:
                assert L[nxt] < L[cur], f"luminance must drop: {cur}->{nxt}"
            cur = nxt
        assert cur == 0, f"color {c} did not fade to black in 8 steps"


def test_charset_loads_from_vice():
    import charset
    g = charset.glyphs()
    assert g.shape == (256, 8, 8)
    assert 0 < g.sum() < 256 * 64          # neither empty nor solid
    # second half of the bank inverts the first -- except inverse-@,
    # which has a one-pixel quirk in the genuine Commodore ROM
    mismatches = (g[128:] != ~g[:128]).sum(axis=(1, 2))
    assert (mismatches[1:] == 0).all()
    assert mismatches[0] <= 8
