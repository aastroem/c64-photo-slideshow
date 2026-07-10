import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import c64color
import gen_tables


def test_fade256_consistent_with_fade16():
    ft = c64color.fade_table()
    t256 = gen_tables.fade256()
    for v in (0x00, 0x15, 0xF7, 0xFF, 0x3C):
        assert t256[v] == (ft[v >> 4] << 4) | ft[v & 15]


def test_note_table_a4():
    lo, hi = gen_tables.note_tables()
    assert len(lo) == len(hi) == 96
    reg = lo[57] | (hi[57] << 8)
    freq = reg * 985248 / 16777216
    assert abs(freq - 440.0) < 1.0


def test_fli_lines_shape():
    txt = gen_tables.fli_lines()
    # line 0 is handled by the entry code; 199 unrolled late-badline lines
    assert txt.count("sta $d011") == 199
    assert txt.count("sta $d018") == 199
    # screen banks cycle: line 1 uses bank 1 ($18), some line uses bank 7
    assert "lda #$18" in txt and "lda #$78" in txt
    # yscroll for line 1 = (3+1)&7 = 4 -> $3c
    assert "lda #$3c" in txt


def test_writes_files(tmp_path):
    gen_tables.write_all(tmp_path)
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {"fade_tables.asm", "note_table.asm", "fli_lines.asm"}
