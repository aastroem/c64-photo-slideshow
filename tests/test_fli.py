import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import fli


def random_image(seed=1):
    rng = np.random.default_rng(seed)
    img = fli.FliImage()
    img.screens = rng.integers(0, 256, (8, 25, 40), dtype=np.uint8)
    img.bitmap = rng.integers(0, 256, (25, 40, 8), dtype=np.uint8)
    img.color = rng.integers(0, 16, (25, 40), dtype=np.uint8)
    return img


def test_pack_length_and_addr():
    data = random_image().pack()
    assert len(data) == 15727
    assert data[0] == 0x00 and data[1] == 0x80  # load address $8000


def test_roundtrip_forces_left_columns_black():
    img = random_image(2)
    out = fli.FliImage.unpack(img.pack())
    for c in range(3):
        assert not out.screens[:, :, c].any()
        assert not out.bitmap[:, c, :].any()
        assert not out.color[:, c].any()
    assert (out.screens[:, :, 3:] == img.screens[:, :, 3:]).all()
    assert (out.bitmap[:, 3:, :] == img.bitmap[:, 3:, :]).all()
    assert (out.color[:, 3:] == img.color[:, 3:]).all()


def test_unpack_to_ram_layout():
    img = random_image(3)
    ram = fli.unpack_to_ram(img.pack())
    assert len(ram) == 0x10000
    for (i, r, c) in [(0, 0, 3), (7, 24, 39), (3, 12, 20)]:
        assert ram[0x8000 + i * 1024 + r * 40 + c] == img.screens[i, r, c]
    for (r, c, b) in [(0, 3, 0), (24, 39, 7), (10, 21, 4)]:
        assert ram[0xA000 + r * 320 + c * 8 + b] == img.bitmap[r, c, b]
    for (r, c) in [(0, 3), (24, 39), (7, 33)]:
        assert ram[0xC000 + r * 40 + c] == img.color[r, c]
    # FLI-bug columns are zero everywhere
    for r in (0, 12, 24):
        for c in (0, 1, 2):
            assert ram[0x8000 + 2 * 1024 + r * 40 + c] == 0
            assert ram[0xA000 + r * 320 + c * 8 + 5] == 0
            assert ram[0xC000 + r * 40 + c] == 0


def test_pixel_colors():
    img = random_image(4)
    row, line, col = 5, 3, 17
    y, x = row * 8 + line, col * 4 + 2
    pal = img.pixel_colors(y, x)
    scr = img.screens[line, row, col]
    assert pal == [0, scr >> 4, scr & 15, img.color[row, col]]
