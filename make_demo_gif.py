#!/usr/bin/env python3
"""Render an animated GIF of a slideshow run from the built .fli files.

    python3 mkdisk.py && python3 make_demo_gif.py [-o docs/img/demo.gif]

Frame-faithful: uses the converted slides and the exact dissolve cell order
the C64 generates at runtime (same LFSR + Fisher-Yates as src/order.asm).
Only the pacing is compressed: static holds are shortened so the GIF loops
briskly; the dissolve pattern itself is the real thing.
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fli
import preview

FPS = 12
DISSOLVE_FRAMES = 18            # ~1.5 s, like the real ~1.3 s
SHOW_FRAMES = 20                # compressed from the real 8 s
CELLS = 1000


def dissolve_order():
    """Port of src/order.asm: Fisher-Yates driven by a 16-bit Galois LFSR."""
    order = list(range(CELLS))
    lo, hi = 0xE1, 0xAC
    def rand():
        nonlocal lo, hi
        c1 = hi & 1
        hi >>= 1
        c2 = lo & 1
        lo = (lo >> 1) | (c1 << 7)
        if c2:
            hi ^= 0xB4
        return lo | ((hi & 3) << 8)
    for i in range(CELLS - 1, 0, -1):
        while True:
            j = rand()
            if j <= i:
                break
        order[i], order[j] = order[j], order[i]
    return order


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", type=pathlib.Path,
                    default=pathlib.Path("docs/img/demo.gif"))
    args = ap.parse_args()

    here = pathlib.Path(__file__).resolve().parent
    flis = sorted((here / "build").glob("pic[0-9][0-9].fli"))
    if not flis:
        raise SystemExit("no build/picNN.fli files -- run mkdisk.py first")
    slides = [np.asarray(preview.render(fli.FliImage.unpack(p.read_bytes())))
              for p in flis]
    order = dissolve_order()
    per_frame = -(-CELLS // DISSOLVE_FRAMES)

    canvas = np.zeros_like(slides[0])
    frames = []
    for target in slides + [slides[0]]:      # end by dissolving back to #1
        pos = 0
        for _ in range(DISSOLVE_FRAMES):
            for o in order[pos:pos + per_frame]:
                r, c = divmod(o, 40)
                canvas[r * 8:r * 8 + 8, c * 8:c * 8 + 8] = \
                    target[r * 8:r * 8 + 8, c * 8:c * 8 + 8]
            pos += per_frame
            frames.append(canvas.copy())
        frames += [canvas.copy()] * SHOW_FRAMES

    with tempfile.TemporaryDirectory() as td:
        for i, f in enumerate(frames):
            Image.fromarray(f).save(f"{td}/f{i:04d}.png")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
            "-i", f"{td}/f%04d.png",
            "-vf", "split[a][b];[a]palettegen=max_colors=32[p];[b][p]paletteuse=dither=none",
            "-loop", "0", str(args.out)], check=True)
    size = args.out.stat().st_size
    print(f"{args.out}: {len(frames)} frames, {len(frames)/FPS:.0f}s, "
          f"{size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
