#!/usr/bin/env python3
"""Photo -> multicolor-FLI (.fli / FLIP) converter.

    python3 convert.py photo.jpg [-o out.fli] [--dither fs|bayer4|bayer8|hybrid]
                        [--strength 0..1] [--sat S] [--gamma G] [--crop dx,dy]

Two-pass conversion: pass 1 picks the FLI attributes (per-cell color-RAM
color, per-4x1-sliver screen color pair) from undithered perceptual (OkLab)
distances; pass 2 dithers each pixel against the 4 colors its sliver can
actually show. Settings persist in a `<photo>.c64.json` sidecar so each
photo keeps its own tuning.
"""

import argparse
import dataclasses
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import c64color
import fli

W, H = 160, 200            # multicolor resolution
# Photos map onto columns 3-38: cols 0-2 are the FLI bug (always black) and
# col 39 is blanked too so the visible picture sits centered on screen
# (with all 37 usable columns it would hang 12 hires pixels right of center).
VIS_COLS = 36
VISW = VIS_COLS * 4        # 144 visible pixels
DISPLAY_ASPECT = (VISW * 2) / H   # mc pixels are 2 hires pixels wide

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21],
]) / 64.0


@dataclasses.dataclass
class Settings:
    dither: str = "hybrid"
    strength: float = 0.85
    sat: float = 1.1
    gamma: float = 1.0
    crop: str = "0,0"       # fractional offset of the crop window, -1..1
    pad: int = 0            # C64 color for the side bars on portrait photos


def sidecar_path(photo):
    return photo.with_name(photo.name + ".c64.json")


def load_sidecar(photo):
    p = sidecar_path(pathlib.Path(photo))
    if p.exists():
        return Settings(**json.loads(p.read_text()))
    return Settings()


def save_sidecar(photo, settings):
    sidecar_path(pathlib.Path(photo)).write_text(
        json.dumps(dataclasses.asdict(settings), indent=1))


def prepare(photo, s):
    """Load, orient, grade, crop and scale to a 200x148 visible target."""
    img = ImageOps.exif_transpose(photo.convert("RGB"))
    if s.sat != 1.0:
        img = ImageEnhance.Color(img).enhance(s.sat)
    if s.gamma != 1.0:
        arr = np.asarray(img, dtype=np.float64) / 255.0
        img = Image.fromarray((arr ** s.gamma * 255 + 0.5).astype(np.uint8))
    dx, dy = (float(v) for v in s.crop.split(","))
    w, h = img.size
    if w / h >= 1.1:                        # landscape: crop to fill
        cw = min(w, int(h * DISPLAY_ASPECT))
        ch = min(h, int(w / DISPLAY_ASPECT))
        x0 = (w - cw) // 2 + int(dx * (w - cw) / 2)
        y0 = (h - ch) // 2 + int(dy * (h - ch) / 2)
        img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((VISW, H), Image.LANCZOS)
    else:                                    # portrait: fit height, pad sides
        mcw = max(2, round(w / h * H / 2))   # mc pixels are 2 hires px wide
        photo = img.resize((mcw, H), Image.LANCZOS)
        img = Image.new("RGB", (VISW, H),
                        tuple(int(v) for v in c64color.PALETTE_RGB[s.pad & 15]))
        img.paste(photo, ((VISW - mcw) // 2, 0))
    return img.filter(ImageFilter.UnsharpMask(radius=1, percent=60, threshold=2))


def pick_attributes(lab):
    """Pass 1: per-cell color-RAM color and per-sliver screen color pairs.

    lab: (200,160,3) OkLab image. Returns (screens, colorram, D) where
    D is the per-pixel distance-squared to each of the 16 colors.
    """
    pal = c64color.palette_oklab()
    d = lab[:, :, None, :] - pal[None, None, :, :]
    D = (d * d).sum(-1)                                   # (200,160,16)
    near = np.argmin(D, axis=-1)

    colorram = np.zeros((fli.ROWS, fli.COLS), dtype=np.uint8)
    for r in range(fli.ROWS):
        for c in range(fli.VIS0, fli.COLS):
            block = near[r * 8:r * 8 + 8, c * 4:c * 4 + 4].ravel()
            nonblack = block[block != 0]
            if len(nonblack):
                colorram[r, c] = np.bincount(nonblack, minlength=16).argmax()

    # sliver-wise: (200, 40, 4, 16) distances
    Ds = D.reshape(H, fli.COLS, 4, 16)
    cram_idx = np.repeat(colorram[np.newaxis, :, :], 8, axis=0).reshape(-1, fli.COLS)
    # base = min(black, colorram) per pixel of each sliver
    base = np.minimum(Ds[..., 0],
                      np.take_along_axis(
                          Ds, cram_idx[:, :, None, None].astype(np.int64), 3)[..., 0])
    best_err = np.full((H, fli.COLS), np.inf)
    best_a = np.zeros((H, fli.COLS), dtype=np.uint8)
    best_b = np.zeros((H, fli.COLS), dtype=np.uint8)
    for a in range(1, 16):
        Da = np.minimum(base, Ds[..., a])
        for b in range(a, 16):
            err = np.minimum(Da, Ds[..., b]).sum(-1)
            better = err < best_err
            best_err[better] = err[better]
            best_a[better] = a
            best_b[better] = b

    # Lines 196-199 share one screen byte per cell: rasters 248-250 sit past
    # the VIC's badline window, so the hardware re-displays line 196's screen
    # colors on the last three lines. Optimizing the four lines jointly makes
    # the real display pixel-identical to the converter's intent.
    tail = slice(196, 200)
    tail_err = np.full(fli.COLS, np.inf)
    tail_a = np.zeros(fli.COLS, dtype=np.uint8)
    tail_b = np.zeros(fli.COLS, dtype=np.uint8)
    for a in range(1, 16):
        Da = np.minimum(base[tail], Ds[tail, :, :, a])
        for b in range(a, 16):
            err = np.minimum(Da, Ds[tail, :, :, b]).sum(axis=(0, 2))
            better = err < tail_err
            tail_err[better] = err[better]
            tail_a[better] = a
            tail_b[better] = b
    for y in range(196, 200):
        best_a[y] = tail_a
        best_b[y] = tail_b

    screens = np.zeros((8, fli.ROWS, fli.COLS), dtype=np.uint8)
    sb = (best_a.astype(np.uint8) << 4) | best_b
    for y in range(H):
        screens[y % 8, y // 8] = sb[y]
    return screens, colorram, D


def candidate_tables(screens, colorram):
    """Per-pixel table of the 4 selectable color indices, shape (200,160,4)."""
    cand = np.zeros((H, W, 4), dtype=np.uint8)
    for y in range(H):
        scr = screens[y % 8, y // 8]
        for col in range(fli.COLS):
            cand[y, col * 4:col * 4 + 4] = (
                0, scr[col] >> 4, scr[col] & 15, colorram[y // 8, col])
    return cand


def _sliver_nearest(lab, cand):
    pal = c64color.palette_oklab()
    d = lab[:, :, None, :] - pal[None, None, :, :]
    D = (d * d).sum(-1)
    Dc = np.take_along_axis(D, cand.astype(np.int64), axis=2)
    pick = np.argmin(Dc, axis=2)
    return (np.take_along_axis(cand, pick[..., None], 2)[..., 0],
            np.take_along_axis(Dc, pick[..., None], 2)[..., 0])


def dither_ordered(lin, cand, matrix, strength):
    off = (matrix[np.tile(np.arange(H), (W, 1)).T % matrix.shape[0],
                  np.tile(np.arange(W), (H, 1)) % matrix.shape[1]] - 0.5)
    adj = np.clip(lin + off[..., None] * 0.30 * strength, 0, 1)
    dithered, _ = _sliver_nearest(c64color.linear_to_oklab(adj), cand)
    plain, dist = _sliver_nearest(c64color.linear_to_oklab(lin), cand)
    exact = dist < 1e-5   # already a palette color: don't dither it
    dithered[exact] = plain[exact]
    return dithered


def dither_fs(lin, cand, strength):
    """Serpentine Floyd-Steinberg in linear RGB, nearest match in OkLab."""
    pal_lin = c64color.palette_linear()
    pal_lab = c64color.palette_oklab()
    cl = pal_lin[cand]        # (200,160,4,3)
    cb = pal_lab[cand]
    work = [row.tolist() for row in lin]
    out = np.zeros((H, W), dtype=np.uint8)
    cbrt = math.cbrt
    for y in range(H):
        xs = range(W) if y % 2 == 0 else range(W - 1, -1, -1)
        sgn = 1 if y % 2 == 0 else -1
        for x in xs:
            r, g, b = work[y][x]
            rr = min(max(r, -0.25), 1.25)
            gg = min(max(g, -0.25), 1.25)
            bb = min(max(b, -0.25), 1.25)
            l_ = cbrt(0.4122214708 * rr + 0.5363325363 * gg + 0.0514459929 * bb)
            m_ = cbrt(0.2119034982 * rr + 0.6806995451 * gg + 0.1073969566 * bb)
            s_ = cbrt(0.0883024619 * rr + 0.2817188376 * gg + 0.6299787005 * bb)
            cw = c64color.CHROMA_WEIGHT
            L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
            A = (1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_) * cw
            B = (0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_) * cw
            best, bi = 1e9, 0
            for i in range(4):
                pl, pa, pb = cb[y, x, i]
                dd = (L - pl) ** 2 + (A - pa) ** 2 + (B - pb) ** 2
                if dd < best:
                    best, bi = dd, i
            out[y, x] = cand[y, x, bi]
            er = (rr - cl[y, x, bi, 0]) * strength
            eg = (gg - cl[y, x, bi, 1]) * strength
            eb = (bb - cl[y, x, bi, 2]) * strength
            if 0 <= x + sgn < W:
                px = work[y][x + sgn]
                px[0] += er * 7 / 16; px[1] += eg * 7 / 16; px[2] += eb * 7 / 16
            if y + 1 < H:
                if 0 <= x - sgn < W:
                    px = work[y + 1][x - sgn]
                    px[0] += er * 3 / 16; px[1] += eg * 3 / 16; px[2] += eb * 3 / 16
                px = work[y + 1][x]
                px[0] += er * 5 / 16; px[1] += eg * 5 / 16; px[2] += eb * 5 / 16
                if 0 <= x + sgn < W:
                    px = work[y + 1][x + sgn]
                    px[0] += er * 1 / 16; px[1] += eg * 1 / 16; px[2] += eb * 1 / 16
    return out


def local_variance(lab_l):
    """3x3 local variance of OkLab lightness, for the hybrid dither mask."""
    p = np.pad(lab_l, 1, mode="edge")
    stack = np.stack([p[dy:dy + H, dx:dx + W]
                      for dy in range(3) for dx in range(3)])
    return stack.var(axis=0)


def convert_image(photo, settings=None):
    s = settings or Settings()
    vis = prepare(photo, s)
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    canvas[:, fli.VIS0 * 4:(fli.VIS0 + VIS_COLS) * 4] = np.asarray(vis)

    lin = c64color.srgb_to_linear(canvas)
    lab = c64color.linear_to_oklab(lin)
    screens, colorram, _ = pick_attributes(lab)
    cand = candidate_tables(screens, colorram)

    if s.dither == "fs":
        chosen = dither_fs(lin, cand, s.strength)
    elif s.dither == "bayer4":
        chosen = dither_ordered(lin, cand, BAYER4, s.strength)
    elif s.dither == "bayer8":
        chosen = dither_ordered(lin, cand, BAYER8, s.strength)
    elif s.dither == "hybrid":
        flat = local_variance(lab[..., 0]) < 0.0004
        chosen = dither_fs(lin, cand, s.strength)
        chosen_b = dither_ordered(lin, cand, BAYER8, s.strength * 0.8)
        chosen[flat] = chosen_b[flat]
    else:
        raise SystemExit(f"unknown dither mode {s.dither!r}")

    # pack chosen palette indices into bitmap pixel pairs via the slot they
    # occupy in each pixel's candidate table
    img = fli.FliImage()
    img.screens, img.color = screens, colorram
    slot = np.argmax(cand == chosen[..., None], axis=2)  # first matching slot
    for y in range(H):
        row, line = y // 8, y % 8
        sl = slot[y]
        for col in range(fli.VIS0, fli.COLS):
            i = col * 4
            img.bitmap[row, col, line] = (
                (sl[i] << 6) | (sl[i + 1] << 4) | (sl[i + 2] << 2) | sl[i + 3])
    # FLI-bug columns stay black
    img.screens[:, :, :fli.VIS0] = 0
    img.color[:, :fli.VIS0] = 0
    img.bitmap[:, :fli.VIS0] = 0
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path)
    ap.add_argument("--dither", choices=["fs", "bayer4", "bayer8", "hybrid"])
    ap.add_argument("--strength", type=float)
    ap.add_argument("--sat", type=float)
    ap.add_argument("--gamma", type=float)
    ap.add_argument("--crop")
    args = ap.parse_args()

    s = load_sidecar(args.photo)
    for k in ("dither", "strength", "sat", "gamma", "crop"):
        v = getattr(args, k)
        if v is not None:
            setattr(s, k, v)
    save_sidecar(args.photo, s)

    img = convert_image(Image.open(args.photo), s)
    out = args.out or args.photo.with_suffix(".fli")
    out.write_bytes(img.pack())

    import preview
    pv = out.with_name(out.stem + "_preview.png")
    preview.render(img).resize((640, 400), Image.NEAREST).save(pv)
    print(f"wrote {out} and {pv}  ({s})")


if __name__ == "__main__":
    main()
