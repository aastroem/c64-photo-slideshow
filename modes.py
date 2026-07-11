"""Non-FLI slide modes: standard hires bitmap (color / mono / greys) and
PETSCII text mode (dither-then-structural-match, petsciiator-style).

On disk:
- hires slides use the normal FLIP container with all 8 screen banks
  identical (fg<<4|bg per cell) -- the duplication compresses away, and the
  C64-side unpack/dissolve machinery is unchanged. Display is plain bitmap
  mode reading screen bank 0.
- petscii slides ship as a RAW bank image (load addr $8000 + 16384 bytes +
  1000 color bytes): the char matrix duplicated across the 8 screen slots,
  the chargen charset embedded in the first 2K of the bitmap area (the VIC
  reads glyphs from $6000 in text mode), colors in the staging area. The
  C64 skips the unpacker for these; the dissolve carries matrix, charset
  and colors over cell by cell.

Photos occupy columns 3-38 (like FLI slides) so every mode shares the same
centered frame.
"""

import math
import random

import numpy as np
from PIL import Image, ImageFilter, ImageOps

import c64color
import charset
import fli

W, H = 320, 200
VIS0, VIS_COLS = 3, 36
VISW = VIS_COLS * 8                 # 288 hires pixels
GREY_LADDER = [0, 11, 12, 15, 1]

_pal_ok = c64color.palette_oklab()
_pal_lin = c64color.palette_linear()


def _prepare(photo, s):
    img = ImageOps.exif_transpose(photo.convert("RGB"))
    if s.sat != 1.0:
        from PIL import ImageEnhance
        img = ImageEnhance.Color(img).enhance(s.sat)
    if s.gamma != 1.0:
        arr = np.asarray(img, dtype=np.float64) / 255.0
        img = Image.fromarray((arr ** s.gamma * 255 + 0.5).astype(np.uint8))
    dx, dy = (float(v) for v in s.crop.split(","))
    w, h = img.size
    aspect = VISW / H
    if w / h >= 1.1:
        cw = min(w, int(h * aspect)); ch = min(h, int(w / aspect))
        x0 = (w - cw) // 2 + int(dx * (w - cw) / 2)
        y0 = (h - ch) // 2 + int(dy * (h - ch) / 2)
        vis = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((VISW, H), Image.LANCZOS)
    else:
        pw = max(2, round(w / h * H))
        photo_r = img.resize((pw, H), Image.LANCZOS)
        vis = Image.new("RGB", (VISW, H),
                        tuple(int(v) for v in c64color.PALETTE_RGB[s.pad & 15]))
        vis.paste(photo_r, ((VISW - pw) // 2, 0))
    vis = vis.filter(ImageFilter.UnsharpMask(radius=1, percent=70, threshold=2))
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    canvas[:, VIS0 * 8:VIS0 * 8 + VISW] = np.asarray(vis)
    return canvas


def _oklab_px(work, y, x):
    cbrt = math.cbrt
    cw_ = c64color.CHROMA_WEIGHT
    rr = min(max(work[y][x][0], -0.25), 1.25)
    gg = min(max(work[y][x][1], -0.25), 1.25)
    bb = min(max(work[y][x][2], -0.25), 1.25)
    l_ = cbrt(0.4122214708*rr + 0.5363325363*gg + 0.0514459929*bb)
    m_ = cbrt(0.2119034982*rr + 0.6806995451*gg + 0.1073969566*bb)
    s_ = cbrt(0.0883024619*rr + 0.2817188376*gg + 0.6299787005*bb)
    L = 0.2104542553*l_ + 0.7936177850*m_ - 0.0040720468*s_
    A = (1.9779984951*l_ - 2.4285922050*m_ + 0.4505937099*s_)*cw_
    B = (0.0259040371*l_ + 0.7827717662*m_ - 0.8086757660*s_)*cw_
    return rr, gg, bb, L, A, B

_NEIGH = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, .1), (1, -1, .1), (-1, 1, .1), (-1, -1, .1))


def _dizzy(lin, cand_for, strength, seed=0xC64):
    """Random-order error diffusion; cand_for(y, x) -> iterable of palette
    indices allowed at that pixel. Returns (H, W) palette indices."""
    work = [row.tolist() for row in lin]
    out = np.zeros((H, W), dtype=int)
    visited = [[False]*W for _ in range(H)]
    order = list(range(W*H))
    random.Random(seed).shuffle(order)
    for idx in order:
        y, x = divmod(idx, W)
        rr, gg, bb, L, A, B = _oklab_px(work, y, x)
        best, bi = 1e9, 0
        for pi in cand_for(y, x):
            pl, pa, pb = _pal_ok[pi]
            dd = (L-pl)**2 + (A-pa)**2 + (B-pb)**2
            if dd < best:
                best, bi = dd, int(pi)
        out[y, x] = bi
        visited[y][x] = True
        er = rr - _pal_lin[bi][0]; eg = gg - _pal_lin[bi][1]; eb = bb - _pal_lin[bi][2]
        denom = 0.0; tg = []
        for dx, dy, wt in _NEIGH:
            xx, yy = x+dx, y+dy
            if 0 <= xx < W and 0 <= yy < H and not visited[yy][xx]:
                denom += wt; tg.append((xx, yy, wt))
        if denom:
            f = strength/denom
            for xx, yy, wt in tg:
                px = work[yy][xx]
                px[0] += er*wt*f; px[1] += eg*wt*f; px[2] += eb*wt*f
    return out


def _cell_pairs(lab, variant):
    if variant == "hires-mono":
        return np.tile(np.array([0, 1]), (25, 40, 1))
    if variant == "hires-greys":
        pal_L = _pal_ok[GREY_LADDER, 0]
        pairs = np.zeros((25, 40, 2), dtype=int)
        Lch = lab[..., 0]
        for r in range(25):
            for c in range(40):
                m = Lch[r*8:r*8+8, c*8:c*8+8].mean()
                i = int(np.clip(np.searchsorted(pal_L, m), 1, len(GREY_LADDER)-1))
                pairs[r, c] = (GREY_LADDER[i-1], GREY_LADDER[i])
        return pairs
    D = ((lab[:, :, None, :] - _pal_ok[None, None, :, :])**2).sum(-1)
    near = D.argmin(-1)
    pairs = np.zeros((25, 40, 2), dtype=int)
    for r in range(25):
        for c in range(40):
            block = near[r*8:r*8+8, c*8:c*8+8].ravel()
            pairs[r, c] = np.bincount(block, minlength=16).argsort()[-2:]
    return pairs


def convert_hires(photo, s, variant="hires"):
    """-> (FliImage with 8 identical screens, (H,W) preview indices)."""
    canvas = _prepare(photo, s)
    lin = c64color.srgb_to_linear(canvas)
    lab = c64color.linear_to_oklab(lin)
    pairs = _cell_pairs(lab, variant)
    pairs[:, :VIS0] = 0
    pairs[:, VIS0 + VIS_COLS:] = 0
    out = _dizzy(lin, lambda y, x: pairs[y//8, x//8], s.strength)
    img = fli.FliImage()
    for r in range(25):
        for c in range(40):
            hi, lo = int(pairs[r, c, 1]), int(pairs[r, c, 0])
            cell = out[r*8:r*8+8, c*8:c*8+8]
            bits = (cell == hi).astype(np.uint8)
            for yy in range(8):
                img.bitmap[r, c, yy] = int(np.packbits(bits[yy])[0])
            img.screens[:, r, c] = (hi << 4) | lo
    img.color[:] = 0
    img.screens[:, :, :VIS0] = 0
    img.screens[:, :, VIS0 + VIS_COLS:] = 0
    img.bitmap[:, :VIS0] = 0
    img.bitmap[:, VIS0 + VIS_COLS:] = 0
    return img, out


def _feat10(mask):
    m = mask.astype(float)
    xs, ys = np.meshgrid(np.arange(8), np.arange(8))
    return np.array([
        m[:4, :4].sum(), m[:4, 4:].sum(), m[4:, :4].sum(), m[4:, 4:].sum(),
        m[3:7, 3:7].sum(),
        (m * ((xs == ys) | ((7 - ys) == xs)).T).sum(),
        m[:, 0].sum(), m[:, 7].sum(), m[0, :].sum(), m[7, :].sum(),
    ])


def convert_petscii(photo, s):
    """-> (screen codes (25,40), fg colors (25,40), preview indices).

    Background is always black so the machine's $D021 never changes."""
    glyphs = charset.glyphs().reshape(256, 64)
    gfeat = np.stack([_feat10(glyphs[g].reshape(8, 8)) for g in range(256)])
    canvas = _prepare(photo, s)
    lin = c64color.srgb_to_linear(canvas)
    quant = _dizzy(lin, lambda y, x: range(16), s.strength)
    bg = 0
    screen = np.zeros((25, 40), dtype=np.uint8)
    color = np.zeros((25, 40), dtype=np.uint8)
    out = np.zeros((H, W), dtype=int)
    for r in range(25):
        for c in range(40):
            if c < VIS0 or c >= VIS0 + VIS_COLS:
                screen[r, c] = 32
                color[r, c] = 0
                continue
            cellq = quant[r*8:r*8+8, c*8:c*8+8]
            mask = cellq != bg
            if not mask.any():
                gi, fi = 32, 0
            else:
                gi = int(((gfeat - _feat10(mask))**2).sum(1).argmin())
                fi = int(np.bincount(cellq[mask].ravel(), minlength=16).argmax())
            screen[r, c] = gi
            color[r, c] = fi
            cell = glyphs[gi].reshape(8, 8)
            out[r*8:r*8+8, c*8:c*8+8] = np.where(cell, fi, bg)
    return screen, color, out


def pack_petscii(screen, color):
    """RAW bank-B image: loads at $8000, no unpacking needed on the C64."""
    glyphs_rom = charset.find_chargen().read_bytes()[:2048]
    bank = bytearray(16384)
    matrix = bytes(int(screen[r, c]) for r in range(25) for c in range(40))
    for i in range(8):                       # 8 identical screen slots
        bank[i*1024:i*1024 + 1000] = matrix
    bank[8192:8192 + 2048] = glyphs_rom      # charset at $A000 -> $6000
    colors = bytes(int(color[r, c]) for r in range(25) for c in range(40))
    return bytes([0x00, 0x80]) + bytes(bank) + colors


def render_preview(out_indices):
    return Image.fromarray(c64color.PALETTE_RGB[out_indices].astype('uint8'))
