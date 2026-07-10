import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import gen_tables
from tests import asm_harness

gen_tables.write_all(asm_harness.GEN)

WRAP = ('jmp music_init\n'
        'jmp music_play\n'
        '!src "music.asm"\n!src "note_table.asm"\n')


def test_player_produces_plausible_sid_writes():
    ram = bytearray(0x10000)
    code = asm_harness.assemble(WRAP, org=0x2000)
    ram[0x2000:0x2000 + len(code)] = code
    asm_harness.run_sub(ram, 0x2000)          # music_init via jmp shim
    assert ram[0xD418] == 0x0F                # volume up
    freqs = set()
    gates = 0
    for _ in range(400):                      # 8 seconds
        cpu = asm_harness.CPU(ram)
        cpu.push((asm_harness.RETURN_MAGIC - 1) >> 8)
        cpu.push((asm_harness.RETURN_MAGIC - 1) & 0xFF)
        cpu.pc = 0x2003                       # music_play (after 3-byte jmp)
        while cpu.pc != asm_harness.RETURN_MAGIC:
            cpu.step()
        freqs.add(bytes(ram[0xD400:0xD402]))
        gates += ram[0xD404] & 1
    assert len(freqs) > 3, "bass frequency should change over time"
    assert 0 < gates < 400, "gate should toggle"
