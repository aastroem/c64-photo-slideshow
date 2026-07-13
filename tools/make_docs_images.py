#!/usr/bin/env python3
"""Regenerate the README figures from the shipped deck in samples/.

    python3 tools/make_docs_images.py          # writes docs/img/*.png

Every tile is the real converter output, cropped to the visible FLI frame
(36 columns = 288x200 hires pixels), so the figures show what the C64 shows.
demo.gif is separate: python3 mkdisk.py && python3 make_demo_gif.py
"""

import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import convert
import modes
import preview

SAMPLES = ROOT / "samples"
OUT = ROOT / "docs" / "img"

# the visible frame: 36 of 40 columns, starting after the 3 FLI-bug columns
X0, VISW2 = 3 * 8, convert.VISW * 2          # 24 .. 312 in render() coords
TW, TH = VISW2, 200                          # 288x200, the true 1.44:1 frame

DITHERS = ["dizzy", "fs", "atkinson", "riemersma", "bayer4", "bayer8", "hybrid"]
DISPLAY_MODES = ["fli", "afli", "hires", "hires-mono", "hires-greys"]

INK, DIM, BG = (255, 255, 255), (168, 168, 176), (18, 18, 20)


def tile(photo, mode="fli", dither="dizzy", strength=0.5):
    """One converted slide as a 288x200 RGB image."""
    s = convert.Settings(mode=mode, dither=dither, strength=strength)
    img_in = Image.open(photo)
    if mode == "fli":
        img = convert.convert_image(img_in, s)
        return preview.render(img).crop((X0, 0, X0 + VISW2, 200))
    conv = modes.convert_afli if mode == "afli" else (
        lambda p, st: modes.convert_hires(p, st, variant=mode))
    _, idx = conv(img_in, s)
    return modes.render_preview(idx).crop((X0, 0, X0 + VISW2, 200))


def sheet(tiles, cols, title, out, scale=1):
    """tiles: list of (label, PIL image). Labels sit under each tile."""
    lbl, pad, head = 18, 10, 30 if title else 0
    w, h = TW * scale, TH * scale
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGB", (cols * (w + pad) + pad,
                           rows * (h + lbl + pad) + pad + head), BG)
    d = ImageDraw.Draw(im)
    if title:
        d.text((pad, 9), title, fill=INK)
    for i, (label, t) in enumerate(tiles):
        x = pad + (i % cols) * (w + pad)
        y = head + pad + (i // cols) * (h + lbl + pad)
        if scale != 1:
            t = t.resize((w, h), Image.NEAREST)
        im.paste(t, (x, y))
        d.text((x + 1, y + h + 3), label, fill=DIM)
    im.save(out)
    print(f"wrote {out.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    photos = sorted(SAMPLES.glob("[0-9][0-9].jpg"))
    if not photos:
        sys.exit(f"no numbered photos in {SAMPLES}")
    pick = {p.stem: p for p in photos}

    # 1. samples.png — a spread of the deck, as it ships (multicolor FLI)
    spread = ["07", "08", "11", "12", "15", "18", "05", "13"]
    sheet([(p, tile(pick[p])) for p in spread if p in pick], 4,
          None, OUT / "samples.png")

    # 2. dithers.png — one photo through every dither, strength 0.5
    subject = pick.get("08", photos[0])          # crocus field + facade + sky
    sheet([(d, tile(subject, dither=d)) for d in DITHERS], 4,
          f"{subject.name} - dither modes at strength 0.5, multicolor FLI",
          OUT / "dithers.png")

    # 3. modes.png — display modes, on a detailed subject and a dark one, so
    #    AFLI's hires win and its lack of a black to dither toward both show
    rows = [pick.get("18", photos[0]), pick.get("04", photos[-1])]
    tiles = [(f"{m}  ({p.name})", tile(p, mode=m))
             for p in rows for m in DISPLAY_MODES]
    sheet(tiles, len(DISPLAY_MODES),
          "display modes (dizzy 0.5) - a detail-rich subject, then a dark one",
          OUT / "modes.png")


if __name__ == "__main__":
    main()
