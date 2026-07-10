#!/usr/bin/env python3
"""Render a .fli (FLIP) file back to PNG exactly as the VIC-II would show it.

Shares palette and pixel semantics with the converter, so judging quality on
the Mac needs no C64 build.

    python3 preview.py image.fli [-o out.png]
"""

import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fli
from c64color import PALETTE_RGB


def indices(img):
    """Decode a FliImage to a (200, 160) array of palette indices."""
    out = np.zeros((200, 160), dtype=np.uint8)
    for y in range(200):
        row, line = y // 8, y % 8
        scr = img.screens[line, row]          # (40,) bytes for this scanline
        bits = img.bitmap[row, :, line]       # (40,) bitmap bytes
        for col in range(40):
            pal = (0, scr[col] >> 4, scr[col] & 15, img.color[row, col])
            b = int(bits[col])
            for pair in range(4):
                out[y, col * 4 + pair] = pal[(b >> (2 * (3 - pair))) & 3]
    return out


def render(img):
    """FliImage -> 320x200 PIL image (multicolor pixels doubled)."""
    idx = indices(img)
    rgb = PALETTE_RGB[idx]
    return Image.fromarray(rgb.repeat(2, axis=1), "RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fli_file", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path)
    args = ap.parse_args()
    img = fli.FliImage.unpack(args.fli_file.read_bytes())
    out = args.out or args.fli_file.with_suffix(".png")
    render(img).save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
