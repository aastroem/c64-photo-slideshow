"""Assemble ACME sources and run routines on the repo's 6502 core."""

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT / "tools"))

from cpu6502 import CPU  # noqa: E402

RETURN_MAGIC = 0xFFFF


GEN = ROOT / "build" / "gen"


def assemble(body, org=0x2000):
    """Assemble an ACME snippet (usually `!src`-ing a routine) at org.

    Returns the raw bytes placed at org.
    """
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "t.asm"
        out = pathlib.Path(td) / "t.prg"
        src.write_text(f"* = ${org:04x}\n{body}\n")
        subprocess.run(
            ["acme", "--cpu", "6510", "-I", str(SRC), "-I", str(GEN),
             "-f", "cbm", "-o", str(out), str(src)],
            check=True, capture_output=True, text=True)
        data = out.read_bytes()
        assert data[0] | (data[1] << 8) == org
        return data[2:]


def run_sub(ram, addr, max_steps=5_000_000):
    """JSR to addr and run until the matching RTS."""
    cpu = CPU(ram)
    cpu.push((RETURN_MAGIC - 1) >> 8)
    cpu.push((RETURN_MAGIC - 1) & 0xFF)
    cpu.pc = addr
    for _ in range(max_steps):
        cpu.step()
        if cpu.pc == RETURN_MAGIC:
            return cpu
    raise AssertionError(f"routine at ${addr:04x} did not return")
