"""C64 palette and perceptual color math shared by converter and previewer.

Palette is Pepto's measured VIC-II palette. All perceptual distances are
computed in OkLab, which is what makes photo conversions look right compared
to naive RGB matching.
"""

import numpy as np

PALETTE_RGB = np.array([
    (0x00, 0x00, 0x00),  # 0 black
    (0xFF, 0xFF, 0xFF),  # 1 white
    (0x68, 0x37, 0x2B),  # 2 red
    (0x70, 0xA4, 0xB2),  # 3 cyan
    (0x6F, 0x3D, 0x86),  # 4 purple
    (0x58, 0x8D, 0x43),  # 5 green
    (0x35, 0x28, 0x79),  # 6 blue
    (0xB8, 0xC7, 0x6F),  # 7 yellow
    (0x6F, 0x4F, 0x25),  # 8 orange
    (0x43, 0x39, 0x00),  # 9 brown
    (0x9A, 0x67, 0x59),  # 10 light red
    (0x44, 0x44, 0x44),  # 11 dark grey
    (0x6C, 0x6C, 0x6C),  # 12 grey
    (0x9A, 0xD2, 0x84),  # 13 light green
    (0x6C, 0x5E, 0xB5),  # 14 light blue
    (0x95, 0x95, 0x95),  # 15 light grey
], dtype=np.uint8)


def srgb_to_linear(rgb):
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return (c * 255.0 + 0.5).astype(np.uint8)


# Chroma differences are weighted above lightness so near-neutral areas
# (skies, haze) prefer white/grey over tinted brights like light green.
CHROMA_WEIGHT = 1.5


def linear_to_oklab(lin):
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack([
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        (1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s) * CHROMA_WEIGHT,
        (0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s) * CHROMA_WEIGHT,
    ], axis=-1)


def srgb_to_oklab(rgb):
    return linear_to_oklab(srgb_to_linear(rgb))


def palette_oklab():
    return srgb_to_oklab(PALETTE_RGB)


def palette_linear():
    return srgb_to_linear(PALETTE_RGB)


def nearest(oklab_px, pal_ok=None):
    """Indices of the perceptually nearest palette color for each pixel."""
    if pal_ok is None:
        pal_ok = palette_oklab()
    d = oklab_px[..., None, :] - pal_ok
    return np.argmin((d * d).sum(-1), axis=-1)


def fade_table():
    """Map each color to the nearest color of strictly lower lightness.

    Iterating the table fades any color to black (0) in at most 8 steps;
    exported to asm as both a 16-entry and a both-nibbles 256-entry table.
    """
    pal = palette_oklab()
    L = pal[:, 0]
    order = list(np.argsort(L))          # order[0] == black
    rank = {int(c): r for r, c in enumerate(order)}
    table = [0] * 16
    for c in range(1, 16):
        # candidates at least two luma ranks down, so any chain is <= 8 steps
        cands = [int(i) for i in order[:max(1, rank[c] - 1)]]
        d = pal[cands] - pal[c]
        table[c] = cands[int(np.argmin((d * d).sum(-1)))]
    return table
