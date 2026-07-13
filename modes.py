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

# ---- block color-pair selection -------------------------------------------
# A hires block (8x8 cell, or an 8x1 strip in AFLI) can show exactly two
# colors. Picking them by majority vote per block -- as this file used to --
# throws away detail (the two most *common* colors are rarely the two that
# best reconstruct the block under dithering) and, because each block decides
# alone, neighbouring blocks disagree and the seams show up on the block grid.
#
# So: score every pair by the error it actually leaves after dithering,
#   E(a,b) = sum over the block's pixels of min(d(px,a), d(px,b)),
# which is what the FLI path in convert.py already does; then let neighbours
# talk to each other by minimising E plus a penalty for disagreeing with the
# adjacent blocks' pairs (a Markov random field, solved by iterated
# conditional modes). A gradient then holds one pair across many blocks and
# the dither carries it, while an edge still breaks to a new pair because
# there the error term outweighs the coherence penalty.
_PAIRS = [(a, b) for a in range(16) for b in range(a, 16)]
_NPAIR = len(_PAIRS)                                   # 136
_PAIR_HI = np.array([p[1] for p in _PAIRS])
_PAIR_LO = np.array([p[0] for p in _PAIRS])
# How unlike are two pairs: 0 identical, 1 share a color, 2 disjoint. Counted
# as multisets, not sets -- a flat block's pair is (a, a), and set() would
# collapse it and score it 1 against *itself*, so the coherence term would
# push flat regions (sky, water) apart instead of holding them together.
def _pdist(p, q):
    common = sum(min(p.count(v), q.count(v)) for v in set(p) | set(q))
    return 2 - common


_PDIST = np.array([[_pdist(p, q) for q in _PAIRS] for p in _PAIRS],
                  dtype=np.float64)


def _pair_energy(Dblocks):
    """Dblocks: (..., npix, 16) distances -> (..., 136) post-dither error."""
    shape = Dblocks.shape[:-2]
    E = np.empty(shape + (_NPAIR,))
    for i, (a, b) in enumerate(_PAIRS):
        E[..., i] = np.minimum(Dblocks[..., a], Dblocks[..., b]).sum(-1)
    return E


def _icm(E, lam_h, lam_v, sweeps=6, pdist=None):
    """Minimise E + lam * sum_neighbours PDIST over a (R,C) grid of blocks.

    Checkerboard (not all-at-once) updates: a Jacobi sweep can oscillate
    between two equally good configurations and never settle.
    """
    pdist = _PDIST if pdist is None else pdist
    p = E.argmin(-1).astype(np.int64)
    if lam_h <= 0 and lam_v <= 0:
        return p
    R, C = p.shape
    rr, cc = np.meshgrid(np.arange(R), np.arange(C), indexing="ij")
    for _ in range(sweeps):
        changed = 0
        for parity in (0, 1):
            cost = E.copy()
            if lam_v > 0:
                cost[1:] += lam_v * pdist[:, p[:-1]].transpose(1, 2, 0)
                cost[:-1] += lam_v * pdist[:, p[1:]].transpose(1, 2, 0)
            if lam_h > 0:
                cost[:, 1:] += lam_h * pdist[:, p[:, :-1]].transpose(1, 2, 0)
                cost[:, :-1] += lam_h * pdist[:, p[:, 1:]].transpose(1, 2, 0)
            new = cost.argmin(-1)
            m = ((rr + cc) % 2 == parity) & (new != p)
            changed += int(m.sum())
            p[m] = new[m]
        if not changed:
            break
    return p


def _solve_pairs(Dblocks, coherence, lam_v_scale=1.0, allowed=None):
    """(..., npix, 16) distances -> (R, C, 2) [lo, hi] color pairs.

    allowed: restrict the search to these indices into _PAIRS (the grey
    variants may only use the ladder, not the full palette).
    """
    E = _pair_energy(Dblocks)
    pdist = _PDIST
    if allowed is not None:
        keep = np.asarray(allowed)
        E = E[..., keep]
        pdist = _PDIST[np.ix_(keep, keep)]   # distances in the subset's own space
    lam = 0.0
    if coherence > 0:
        # scale the penalty to the image's own error magnitude, so `coherence`
        # means the same thing on a flat photo and a busy one
        lam = coherence * float(np.median(E.min(-1)))
    idx = _icm(E, lam, lam * lam_v_scale, pdist=pdist)
    if allowed is not None:
        idx = np.asarray(allowed)[idx]
    return np.stack([_PAIR_LO[idx], _PAIR_HI[idx]], axis=-1)


# the grey variants may only draw from the luminance ladder
_LADDER_PAIRS = [i for i, (a, b) in enumerate(_PAIRS)
                 if a in GREY_LADDER and b in GREY_LADDER and a != b]


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


def _cell_pairs(lab, variant, coherence=0.0):
    if variant == "hires-mono":
        return np.tile(np.array([0, 1]), (25, 40, 1))
    D = ((lab[:, :, None, :] - _pal_ok[None, None, :, :])**2).sum(-1)
    cells = (D.reshape(25, 8, 40, 8, 16)      # (rows, y, cols, x, color)
              .transpose(0, 2, 1, 3, 4)
              .reshape(25, 40, 64, 16))       # 64 px per 8x8 cell
    # the grey variant is the same problem on a restricted palette: picking the
    # ladder rung from a cell's *mean* luminance is the same blind per-cell
    # heuristic, and banded for the same reason
    allowed = _LADDER_PAIRS if variant == "hires-greys" else None
    return _solve_pairs(cells, coherence, allowed=allowed)


def convert_hires(photo, s, variant="hires"):
    """-> (FliImage with 8 identical screens, (H,W) preview indices)."""
    canvas = _prepare(photo, s)
    lin = c64color.srgb_to_linear(canvas)
    lab = c64color.linear_to_oklab(lin)
    pairs = _cell_pairs(lab, variant, s.coherence)
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


def convert_afli(photo, s):
    """AFLI: hires bitmap with a fresh 2-color pair per 8x1 line strip.
    Packs into the FLIP container exactly like FLI (screen bank y%8 holds
    line y's pairs); the C64 displays it with the FLI IRQ, multicolor off."""
    canvas = _prepare(photo, s)
    lin = c64color.srgb_to_linear(canvas)
    lab = c64color.linear_to_oklab(lin)
    D = ((lab[:, :, None, :] - _pal_ok[None, None, :, :])**2).sum(-1)
    strips = D.reshape(H, 40, 8, 16)          # 8 px per 8x1 strip
    E = _pair_energy(strips)                  # (200, 40, 136)

    # Lines 197-199 (rasters 248-250) sit past the badline window, so the VIC
    # redisplays line 196's screen colors there -- and it resolves *their*
    # bitmap bits against that pair, which would invert pixels wherever the
    # light/dark order disagrees. Score lines 196-199 as one block, as the FLI
    # converter does (convert.py), so bit 1 always means the same ink.
    E[196:200] = E[196:200].sum(0) / 4.0

    lam = s.coherence * float(np.median(E.min(-1))) if s.coherence > 0 else 0.0
    # vertical coherence matters more here: a pair that flips line to line
    # makes the image shimmer in horizontal bands, which reads worse than the
    # 8-pixel column seams that horizontal coherence fixes
    idx = _icm(E, lam, lam * 2.0)
    idx[196:200] = idx[196]                   # one screen byte for the tail
    pairs = np.stack([_PAIR_LO[idx], _PAIR_HI[idx]], axis=-1)
    pairs[:, :VIS0] = 0
    pairs[:, VIS0 + VIS_COLS:] = 0
    out = _dizzy(lin, lambda y, x: pairs[y, x//8], s.strength)
    img = fli.FliImage()
    for y in range(H):
        r, ln = y // 8, y % 8
        for c in range(40):
            hi, lo = int(pairs[y, c, 1]), int(pairs[y, c, 0])
            strip = out[y, c*8:c*8+8]
            img.bitmap[r, c, ln] = int(np.packbits((strip == hi).astype(np.uint8))[0])
            img.screens[ln, r, c] = (hi << 4) | lo
    img.color[:] = 0
    # the AFLI bug renders the left 3 columns light grey (no background
    # fallback in hires); paint the right blank column grey too and give
    # the preview the same bands -- the display uses a grey border so the
    # whole thing reads as an intentional frame
    img.screens[:, :, :VIS0] = 0xFF
    img.screens[:, :, VIS0 + VIS_COLS:] = 0xFF
    img.bitmap[:, :VIS0] = 0
    img.bitmap[:, VIS0 + VIS_COLS:] = 0
    out[:, :VIS0 * 8] = 15
    out[:, (VIS0 + VIS_COLS) * 8:] = 15
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
