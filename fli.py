"""FLIP container: trimmed multicolor-FLI image, 15727 bytes on disk.

10 raw FLI images (17.4K each) don't fit a 35-track D64, so the on-disk
format drops the three FLI-bug columns (0-2, always black) and all padding:

    0-1   load address $8000
    2..   screens  8 banks x 25 rows x 37 cols   (7400)
          bitmap   25 rows x 37 cells x 8 bytes  (7400)
          color    25 x 37                       ( 925)

The C64-side unpacker (src/unpack.asm) expands this backwards in place to
the VIC bank-B layout; `unpack_to_ram` is the Python reference for it:
screen byte (bank i, row r, col c) -> $8000+i*1024+r*40+c, bitmap cell ->
$A000+r*320+c*8, color -> $C000+r*40+c, columns 0-2 zeroed.

Multicolor pixel semantics: %00=$D021(black), %01=screen hi nibble,
%10=screen lo nibble, %11=color-RAM nibble. Scanline y uses screen bank y&7.
"""

import numpy as np

LOAD_ADDR = 0x8000
COLS = 40
VIS0 = 3                     # first visible column (0-2 = FLI bug, black)
NVIS = COLS - VIS0           # 37
ROWS = 25
PACKED_SIZE = 2 + 8 * ROWS * NVIS + ROWS * NVIS * 8 + ROWS * NVIS


class FliImage:
    def __init__(self):
        self.screens = np.zeros((8, ROWS, COLS), dtype=np.uint8)
        self.bitmap = np.zeros((ROWS, COLS, 8), dtype=np.uint8)
        self.color = np.zeros((ROWS, COLS), dtype=np.uint8)

    def pack(self):
        parts = [bytes([LOAD_ADDR & 0xFF, LOAD_ADDR >> 8])]
        parts.append(self.screens[:, :, VIS0:].tobytes())
        parts.append(self.bitmap[:, VIS0:, :].tobytes())
        parts.append(self.color[:, VIS0:].tobytes())
        data = b"".join(parts)
        assert len(data) == PACKED_SIZE
        return data

    @classmethod
    def unpack(cls, data):
        assert len(data) == PACKED_SIZE
        img = cls()
        body = np.frombuffer(data, dtype=np.uint8, offset=2)
        n = 8 * ROWS * NVIS
        img.screens[:, :, VIS0:] = body[:n].reshape(8, ROWS, NVIS)
        img.bitmap[:, VIS0:, :] = body[n:n + ROWS * NVIS * 8].reshape(ROWS, NVIS, 8)
        img.color[:, VIS0:] = body[n + ROWS * NVIS * 8:].reshape(ROWS, NVIS)
        return img

    def pixel_colors(self, y, x):
        """The 4 colors selectable by the pixel pair at multicolor (x, y)."""
        row, line, col = y // 8, y % 8, x // 4
        scr = int(self.screens[line, row, col])
        return [0, scr >> 4, scr & 15, int(self.color[row, col])]


def unpack_to_ram(data):
    """Reference expansion into a 64K image (bank B + color staging)."""
    img = FliImage.unpack(data)
    ram = bytearray(0x10000)
    for i in range(8):
        base = 0x8000 + i * 1024
        ram[base:base + ROWS * COLS] = img.screens[i].tobytes()
    ram[0xA000:0xA000 + ROWS * COLS * 8] = img.bitmap.tobytes()
    ram[0xC000:0xC000 + ROWS * COLS] = img.color.tobytes()
    return ram
