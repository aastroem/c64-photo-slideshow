import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import fli
from tests import asm_harness


def test_unpack_matches_python_reference():
    rng = np.random.default_rng(11)
    img = fli.FliImage()
    img.screens = rng.integers(1, 256, (8, 25, 40), dtype=np.uint8)
    img.bitmap = rng.integers(1, 256, (25, 40, 8), dtype=np.uint8)
    img.color = rng.integers(1, 16, (25, 40), dtype=np.uint8)
    packed = img.pack()

    ram = bytearray(0x10000)
    code = asm_harness.assemble('!src "unpack.asm"', org=0x2000)
    ram[0x2000:0x2000 + len(code)] = code
    ram[0x8000:0x8000 + len(packed) - 2] = packed[2:]

    asm_harness.run_sub(ram, 0x2000)

    ref = fli.unpack_to_ram(packed)
    for i in range(8):
        base = 0x8000 + i * 1024
        assert ram[base:base + 1000] == ref[base:base + 1000], f"screen bank {i}"
    assert ram[0xA000:0xBF40] == ref[0xA000:0xBF40], "bitmap"
    assert ram[0xC000:0xC3E8] == ref[0xC000:0xC3E8], "color staging"
