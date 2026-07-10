import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import c64color
import gen_tables
from tests import asm_harness

gen_tables.write_all(asm_harness.GEN)  # make sure includes exist

FADE_WRAP = '!src "fade.asm"\n!src "fade_tables.asm"\n'
DIS_WRAP = ('dis_lo = $c400\ndis_hi = $c800\n'
            'jmp dissolve_cells\n'      # $2000
            'jmp gen_order\n'           # $2003
            '!src "dissolve.asm"\n!src "order.asm"\n')


def load(ram, body):
    code = asm_harness.assemble(body, org=0x2000)
    ram[0x2000:0x2000 + len(code)] = code


def test_fade_pass_matches_python_and_reaches_black():
    rng = np.random.default_rng(3)
    scr = rng.integers(0, 256, 1000, dtype=np.uint8)
    col = rng.integers(0, 16, 1000, dtype=np.uint8)
    ram = bytearray(0x10000)
    load(ram, FADE_WRAP)
    ram[0x4000:0x43E8] = scr.tobytes()
    ram[0xD800:0xDBE8] = col.tobytes()

    t256 = gen_tables.fade256()
    ft = c64color.fade_table()

    asm_harness.run_sub(ram, 0x2000)  # fade_pass is first label
    assert list(ram[0x4000:0x43E8]) == [t256[v] for v in scr]
    assert list(ram[0xD800:0xDBE8]) == [ft[v] for v in col]

    for _ in range(7):
        asm_harness.run_sub(ram, 0x2000)
    assert not any(ram[0x4000:0x43E8])
    assert not any(ram[0xD800:0xDBE8])


def dissolve_ram():
    rng = np.random.default_rng(9)
    ram = bytearray(0x10000)
    load(ram, DIS_WRAP)
    for i in range(8):
        base = 0x8000 + i * 1024
        ram[base:base + 1000] = rng.integers(1, 256, 1000, dtype=np.uint8).tobytes()
    ram[0xA000:0xBF40] = rng.integers(1, 256, 8000, dtype=np.uint8).tobytes()
    ram[0xC000:0xC3E8] = rng.integers(1, 16, 1000, dtype=np.uint8).tobytes()
    asm_harness.run_sub(ram, 0x2003)          # gen_order fills $C400/$C800
    return ram


def read_order(ram):
    return [ram[0xC400 + k] | (ram[0xC800 + k] << 8) for k in range(1000)]


def test_gen_order_is_shuffled_permutation():
    ram = dissolve_ram()
    order = read_order(ram)
    assert sorted(order) == list(range(1000))
    assert order[:20] != list(range(20))


def run_cells(ram, chunks):
    # dissolve_cells is the entry label; A = cell count
    code_base = 0x2000
    for n in chunks:
        cpu = asm_harness.CPU(ram)
        cpu.a = n
        cpu.push((asm_harness.RETURN_MAGIC - 1) >> 8)
        cpu.push((asm_harness.RETURN_MAGIC - 1) & 0xFF)
        cpu.pc = code_base
        while cpu.pc != asm_harness.RETURN_MAGIC:
            cpu.step()


def test_dissolve_full_copy():
    ram = dissolve_ram()
    run_cells(ram, [125] * 8)  # 1000 cells
    for i in range(8):
        a, b = 0x4000 + i * 1024, 0x8000 + i * 1024
        assert ram[a:a + 1000] == ram[b:b + 1000], f"bank {i}"
    assert ram[0x6000:0x7F40] == ram[0xA000:0xBF40]
    assert ram[0xD800:0xDBE8] == ram[0xC000:0xC3E8]


def test_dissolve_partial_follows_order():
    ram = dissolve_ram()
    order = read_order(ram)
    run_cells(ram, [244])
    done = set(order[:244])
    for o in range(1000):
        got = ram[0xD800 + o]
        want = ram[0xC000 + o] if o in done else 0
        assert got == want, f"cell {o}"
