import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import fli
import preview
from c64color import PALETTE_RGB


def test_render_decodes_all_pixel_sources():
    img = fli.FliImage()
    row, col = 4, 10
    # bank for scanline y is y & 7; give each bank a distinct screen byte
    for line in range(8):
        img.screens[line, row, col] = (line + 1) << 4 | (8 + line)
    img.color[row, col] = 7
    # bitmap byte for cell line 2: pixel pairs %00 %01 %10 %11
    img.bitmap[row, col, 2] = 0b00011011
    out = preview.render(img)
    assert out.size == (320, 200)
    px = np.asarray(out)
    y = row * 8 + 2
    scr = img.screens[2, row, col]
    expect = [0, scr >> 4, scr & 15, 7]
    for pair in range(4):
        x = (col * 4 + pair) * 2  # doubled horizontally
        assert tuple(px[y, x]) == tuple(PALETTE_RGB[expect[pair]]), pair


def test_render_black_default():
    out = preview.render(fli.FliImage())
    assert not np.asarray(out).any()
