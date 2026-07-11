"""Locate and decode the C64 character ROM (PETSCII glyphs) from the
user's VICE installation -- we never redistribute Commodore's ROM.

    glyphs = charset.glyphs()        # (256, 8, 8) bool, uppercase/gfx bank
    glyphs = charset.glyphs(bank=1)  # lowercase bank
"""

import os
import pathlib

import numpy as np

SEARCH = [
    os.environ.get("VICE_DATADIR", ""),
    "/opt/homebrew/share/vice/C64",
    "/usr/local/share/vice/C64",
    "/usr/share/vice/C64",
    os.path.expanduser("~/.local/share/vice/C64"),
]


def find_chargen():
    for d in SEARCH:
        if not d:
            continue
        p = pathlib.Path(d)
        if not p.is_dir():
            continue
        for name in ("chargen-901225-01.bin", "chargen"):
            f = p / name
            if f.is_file() and f.stat().st_size in (4096, 8192):
                return f
        hits = sorted(p.glob("chargen*"))
        if hits:
            return hits[0]
    raise FileNotFoundError(
        "C64 chargen ROM not found -- install VICE (brew install vice) or "
        "point VICE_DATADIR at a directory containing chargen*.bin")


def glyphs(bank=0):
    """All 256 glyphs of a charset bank as a (256, 8, 8) boolean array."""
    rom = find_chargen().read_bytes()
    data = rom[bank * 2048:(bank + 1) * 2048]
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    return bits.reshape(256, 8, 8).astype(bool)
