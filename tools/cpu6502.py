"""Tiny 6502 emulator — just enough to run a C64 decruncher and dump RAM.
All 64KB treated as RAM; I/O and ROM banking ignored (reads/writes go to RAM).
"""

class CPU:
    def __init__(self, mem):
        self.m = mem  # bytearray(65536)
        self.a = self.x = self.y = 0
        self.sp = 0xfd
        self.pc = 0
        self.n = self.v = self.z = self.c = self.d = False
        self.i = True
        self.instr_count = 0
        self.write_count = 0

    # -- helpers --
    def rd(self, addr):
        return self.m[addr & 0xffff]

    def wr(self, addr, val):
        self.m[addr & 0xffff] = val & 0xff
        self.write_count += 1

    def push(self, v):
        self.m[0x100 + self.sp] = v & 0xff
        self.sp = (self.sp - 1) & 0xff

    def pop(self):
        self.sp = (self.sp + 1) & 0xff
        return self.m[0x100 + self.sp]

    def setnz(self, v):
        v &= 0xff
        self.n = v >= 0x80
        self.z = v == 0
        return v

    def flags_byte(self):
        return (self.n << 7) | (self.v << 6) | 0x20 | 0x10 | (self.d << 3) | (self.i << 2) | (self.z << 1) | int(self.c)

    def set_flags(self, b):
        self.n = bool(b & 0x80); self.v = bool(b & 0x40)
        self.d = bool(b & 0x08); self.i = bool(b & 0x04)
        self.z = bool(b & 0x02); self.c = bool(b & 0x01)

    # -- addressing: return address --
    def imm(self):
        a = self.pc; self.pc = (self.pc + 1) & 0xffff; return a
    def zp(self):
        return self.rd(self.imm())
    def zpx(self):
        return (self.rd(self.imm()) + self.x) & 0xff
    def zpy(self):
        return (self.rd(self.imm()) + self.y) & 0xff
    def ab(self):
        lo = self.rd(self.imm()); hi = self.rd(self.imm()); return lo | (hi << 8)
    def abx(self):
        return (self.ab() + self.x) & 0xffff
    def aby(self):
        return (self.ab() + self.y) & 0xffff
    def inx_(self):
        z = (self.rd(self.imm()) + self.x) & 0xff
        return self.m[z] | (self.m[(z + 1) & 0xff] << 8)
    def iny_(self):
        z = self.rd(self.imm())
        return ((self.m[z] | (self.m[(z + 1) & 0xff] << 8)) + self.y) & 0xffff

    # -- operations --
    def adc(self, v):
        if self.d:
            # NMOS 6502 decimal mode: Z from binary result, N/V from
            # intermediate high nibble, C from BCD carry
            c_in = int(self.c)
            self.z = ((self.a + v + c_in) & 0xff) == 0
            lo = (self.a & 0x0f) + (v & 0x0f) + c_in
            hi = (self.a & 0xf0) + (v & 0xf0)
            if lo > 0x09:
                hi += 0x10
                lo += 0x06
            self.n = (hi & 0x80) != 0
            self.v = (~(self.a ^ v) & (self.a ^ hi) & 0x80) != 0
            if hi > 0x90:
                hi += 0x60
            self.c = hi > 0xff
            self.a = ((hi & 0xf0) | (lo & 0x0f)) & 0xff
        else:
            r = self.a + v + int(self.c)
            self.v = (~(self.a ^ v) & (self.a ^ r) & 0x80) != 0
            self.c = r > 0xff
            self.a = self.setnz(r)

    def sbc(self, v):
        if not self.d:
            self.adc(v ^ 0xff)
            return
        # NMOS 6502 decimal mode: all flags from binary result,
        # only the stored result is BCD-adjusted
        c_in = int(self.c)
        r = self.a - v - (1 - c_in)
        self.c = r >= 0
        self.v = ((self.a ^ v) & (self.a ^ r) & 0x80) != 0
        self.setnz(r & 0xff)
        lo = (self.a & 0x0f) - (v & 0x0f) - (1 - c_in)
        hi = (self.a >> 4) - (v >> 4)
        if lo & 0x10:
            lo -= 6
            hi -= 1
        if hi & 0x10:
            hi -= 6
        self.a = ((hi << 4) | (lo & 0x0f)) & 0xff

    def cmp_(self, reg, v):
        r = reg - v
        self.c = r >= 0
        self.setnz(r & 0xff)

    def branch(self, cond):
        off = self.rd(self.imm())
        if cond:
            if off >= 0x80: off -= 0x100
            self.pc = (self.pc + off) & 0xffff

    def asl(self, v):
        self.c = bool(v & 0x80); return self.setnz((v << 1) & 0xff)
    def lsr(self, v):
        self.c = bool(v & 1); return self.setnz(v >> 1)
    def rol(self, v):
        r = ((v << 1) | int(self.c)) & 0xff; self.c = bool(v & 0x80); return self.setnz(r)
    def ror(self, v):
        r = (v >> 1) | (0x80 if self.c else 0); self.c = bool(v & 1); return self.setnz(r)

    def step(self):
        op = self.rd(self.pc)
        self.pc = (self.pc + 1) & 0xffff
        self.instr_count += 1
        s = self

        # loads/stores
        if   op == 0xa9: s.a = s.setnz(s.rd(s.imm()))
        elif op == 0xa5: s.a = s.setnz(s.rd(s.zp()))
        elif op == 0xb5: s.a = s.setnz(s.rd(s.zpx()))
        elif op == 0xad: s.a = s.setnz(s.rd(s.ab()))
        elif op == 0xbd: s.a = s.setnz(s.rd(s.abx()))
        elif op == 0xb9: s.a = s.setnz(s.rd(s.aby()))
        elif op == 0xa1: s.a = s.setnz(s.rd(s.inx_()))
        elif op == 0xb1: s.a = s.setnz(s.rd(s.iny_()))
        elif op == 0xa2: s.x = s.setnz(s.rd(s.imm()))
        elif op == 0xa6: s.x = s.setnz(s.rd(s.zp()))
        elif op == 0xb6: s.x = s.setnz(s.rd(s.zpy()))
        elif op == 0xae: s.x = s.setnz(s.rd(s.ab()))
        elif op == 0xbe: s.x = s.setnz(s.rd(s.aby()))
        elif op == 0xa0: s.y = s.setnz(s.rd(s.imm()))
        elif op == 0xa4: s.y = s.setnz(s.rd(s.zp()))
        elif op == 0xb4: s.y = s.setnz(s.rd(s.zpx()))
        elif op == 0xac: s.y = s.setnz(s.rd(s.ab()))
        elif op == 0xbc: s.y = s.setnz(s.rd(s.abx()))
        elif op == 0x85: s.wr(s.zp(), s.a)
        elif op == 0x95: s.wr(s.zpx(), s.a)
        elif op == 0x8d: s.wr(s.ab(), s.a)
        elif op == 0x9d: s.wr(s.abx(), s.a)
        elif op == 0x99: s.wr(s.aby(), s.a)
        elif op == 0x81: s.wr(s.inx_(), s.a)
        elif op == 0x91: s.wr(s.iny_(), s.a)
        elif op == 0x86: s.wr(s.zp(), s.x)
        elif op == 0x96: s.wr(s.zpy(), s.x)
        elif op == 0x8e: s.wr(s.ab(), s.x)
        elif op == 0x84: s.wr(s.zp(), s.y)
        elif op == 0x94: s.wr(s.zpx(), s.y)
        elif op == 0x8c: s.wr(s.ab(), s.y)
        # transfers
        elif op == 0xaa: s.x = s.setnz(s.a)
        elif op == 0xa8: s.y = s.setnz(s.a)
        elif op == 0x8a: s.a = s.setnz(s.x)
        elif op == 0x98: s.a = s.setnz(s.y)
        elif op == 0xba: s.x = s.setnz(s.sp)
        elif op == 0x9a: s.sp = s.x
        # stack
        elif op == 0x48: s.push(s.a)
        elif op == 0x68: s.a = s.setnz(s.pop())
        elif op == 0x08: s.push(s.flags_byte())
        elif op == 0x28: s.set_flags(s.pop())
        # logic
        elif op == 0x29: s.a = s.setnz(s.a & s.rd(s.imm()))
        elif op == 0x25: s.a = s.setnz(s.a & s.rd(s.zp()))
        elif op == 0x35: s.a = s.setnz(s.a & s.rd(s.zpx()))
        elif op == 0x2d: s.a = s.setnz(s.a & s.rd(s.ab()))
        elif op == 0x3d: s.a = s.setnz(s.a & s.rd(s.abx()))
        elif op == 0x39: s.a = s.setnz(s.a & s.rd(s.aby()))
        elif op == 0x21: s.a = s.setnz(s.a & s.rd(s.inx_()))
        elif op == 0x31: s.a = s.setnz(s.a & s.rd(s.iny_()))
        elif op == 0x09: s.a = s.setnz(s.a | s.rd(s.imm()))
        elif op == 0x05: s.a = s.setnz(s.a | s.rd(s.zp()))
        elif op == 0x15: s.a = s.setnz(s.a | s.rd(s.zpx()))
        elif op == 0x0d: s.a = s.setnz(s.a | s.rd(s.ab()))
        elif op == 0x1d: s.a = s.setnz(s.a | s.rd(s.abx()))
        elif op == 0x19: s.a = s.setnz(s.a | s.rd(s.aby()))
        elif op == 0x01: s.a = s.setnz(s.a | s.rd(s.inx_()))
        elif op == 0x11: s.a = s.setnz(s.a | s.rd(s.iny_()))
        elif op == 0x49: s.a = s.setnz(s.a ^ s.rd(s.imm()))
        elif op == 0x45: s.a = s.setnz(s.a ^ s.rd(s.zp()))
        elif op == 0x55: s.a = s.setnz(s.a ^ s.rd(s.zpx()))
        elif op == 0x4d: s.a = s.setnz(s.a ^ s.rd(s.ab()))
        elif op == 0x5d: s.a = s.setnz(s.a ^ s.rd(s.abx()))
        elif op == 0x59: s.a = s.setnz(s.a ^ s.rd(s.aby()))
        elif op == 0x41: s.a = s.setnz(s.a ^ s.rd(s.inx_()))
        elif op == 0x51: s.a = s.setnz(s.a ^ s.rd(s.iny_()))
        # bit
        elif op == 0x24:
            v = s.rd(s.zp()); s.z = (s.a & v) == 0; s.n = bool(v & 0x80); s.v = bool(v & 0x40)
        elif op == 0x2c:
            v = s.rd(s.ab()); s.z = (s.a & v) == 0; s.n = bool(v & 0x80); s.v = bool(v & 0x40)
        # arithmetic
        elif op == 0x69: s.adc(s.rd(s.imm()))
        elif op == 0x65: s.adc(s.rd(s.zp()))
        elif op == 0x75: s.adc(s.rd(s.zpx()))
        elif op == 0x6d: s.adc(s.rd(s.ab()))
        elif op == 0x7d: s.adc(s.rd(s.abx()))
        elif op == 0x79: s.adc(s.rd(s.aby()))
        elif op == 0x61: s.adc(s.rd(s.inx_()))
        elif op == 0x71: s.adc(s.rd(s.iny_()))
        elif op == 0xe9: s.sbc(s.rd(s.imm()))
        elif op == 0xe5: s.sbc(s.rd(s.zp()))
        elif op == 0xf5: s.sbc(s.rd(s.zpx()))
        elif op == 0xed: s.sbc(s.rd(s.ab()))
        elif op == 0xfd: s.sbc(s.rd(s.abx()))
        elif op == 0xf9: s.sbc(s.rd(s.aby()))
        elif op == 0xe1: s.sbc(s.rd(s.inx_()))
        elif op == 0xf1: s.sbc(s.rd(s.iny_()))
        # compare
        elif op == 0xc9: s.cmp_(s.a, s.rd(s.imm()))
        elif op == 0xc5: s.cmp_(s.a, s.rd(s.zp()))
        elif op == 0xd5: s.cmp_(s.a, s.rd(s.zpx()))
        elif op == 0xcd: s.cmp_(s.a, s.rd(s.ab()))
        elif op == 0xdd: s.cmp_(s.a, s.rd(s.abx()))
        elif op == 0xd9: s.cmp_(s.a, s.rd(s.aby()))
        elif op == 0xc1: s.cmp_(s.a, s.rd(s.inx_()))
        elif op == 0xd1: s.cmp_(s.a, s.rd(s.iny_()))
        elif op == 0xe0: s.cmp_(s.x, s.rd(s.imm()))
        elif op == 0xe4: s.cmp_(s.x, s.rd(s.zp()))
        elif op == 0xec: s.cmp_(s.x, s.rd(s.ab()))
        elif op == 0xc0: s.cmp_(s.y, s.rd(s.imm()))
        elif op == 0xc4: s.cmp_(s.y, s.rd(s.zp()))
        elif op == 0xcc: s.cmp_(s.y, s.rd(s.ab()))
        # inc/dec
        elif op == 0xe6: a = s.zp(); s.wr(a, s.setnz(s.rd(a) + 1))
        elif op == 0xf6: a = s.zpx(); s.wr(a, s.setnz(s.rd(a) + 1))
        elif op == 0xee: a = s.ab(); s.wr(a, s.setnz(s.rd(a) + 1))
        elif op == 0xfe: a = s.abx(); s.wr(a, s.setnz(s.rd(a) + 1))
        elif op == 0xc6: a = s.zp(); s.wr(a, s.setnz(s.rd(a) - 1))
        elif op == 0xd6: a = s.zpx(); s.wr(a, s.setnz(s.rd(a) - 1))
        elif op == 0xce: a = s.ab(); s.wr(a, s.setnz(s.rd(a) - 1))
        elif op == 0xde: a = s.abx(); s.wr(a, s.setnz(s.rd(a) - 1))
        elif op == 0xe8: s.x = s.setnz(s.x + 1)
        elif op == 0xc8: s.y = s.setnz(s.y + 1)
        elif op == 0xca: s.x = s.setnz(s.x - 1)
        elif op == 0x88: s.y = s.setnz(s.y - 1)
        # shifts
        elif op == 0x0a: s.a = s.asl(s.a)
        elif op == 0x06: a = s.zp(); s.wr(a, s.asl(s.rd(a)))
        elif op == 0x16: a = s.zpx(); s.wr(a, s.asl(s.rd(a)))
        elif op == 0x0e: a = s.ab(); s.wr(a, s.asl(s.rd(a)))
        elif op == 0x1e: a = s.abx(); s.wr(a, s.asl(s.rd(a)))
        elif op == 0x4a: s.a = s.lsr(s.a)
        elif op == 0x46: a = s.zp(); s.wr(a, s.lsr(s.rd(a)))
        elif op == 0x56: a = s.zpx(); s.wr(a, s.lsr(s.rd(a)))
        elif op == 0x4e: a = s.ab(); s.wr(a, s.lsr(s.rd(a)))
        elif op == 0x5e: a = s.abx(); s.wr(a, s.lsr(s.rd(a)))
        elif op == 0x2a: s.a = s.rol(s.a)
        elif op == 0x26: a = s.zp(); s.wr(a, s.rol(s.rd(a)))
        elif op == 0x36: a = s.zpx(); s.wr(a, s.rol(s.rd(a)))
        elif op == 0x2e: a = s.ab(); s.wr(a, s.rol(s.rd(a)))
        elif op == 0x3e: a = s.abx(); s.wr(a, s.rol(s.rd(a)))
        elif op == 0x6a: s.a = s.ror(s.a)
        elif op == 0x66: a = s.zp(); s.wr(a, s.ror(s.rd(a)))
        elif op == 0x76: a = s.zpx(); s.wr(a, s.ror(s.rd(a)))
        elif op == 0x6e: a = s.ab(); s.wr(a, s.ror(s.rd(a)))
        elif op == 0x7e: a = s.abx(); s.wr(a, s.ror(s.rd(a)))
        # jumps
        elif op == 0x4c: s.pc = s.ab()
        elif op == 0x6c:
            a = s.ab()
            # 6502 page-wrap bug
            lo = s.rd(a); hi = s.rd((a & 0xff00) | ((a + 1) & 0xff))
            s.pc = lo | (hi << 8)
        elif op == 0x20:
            a = s.ab()
            ret = (s.pc - 1) & 0xffff
            s.push(ret >> 8); s.push(ret & 0xff)
            s.pc = a
        elif op == 0x60:
            lo = s.pop(); hi = s.pop()
            s.pc = ((lo | (hi << 8)) + 1) & 0xffff
        elif op == 0x40:
            s.set_flags(s.pop())
            lo = s.pop(); hi = s.pop()
            s.pc = lo | (hi << 8)
        # branches
        elif op == 0x10: s.branch(not s.n)
        elif op == 0x30: s.branch(s.n)
        elif op == 0x50: s.branch(not s.v)
        elif op == 0x70: s.branch(s.v)
        elif op == 0x90: s.branch(not s.c)
        elif op == 0xb0: s.branch(s.c)
        elif op == 0xd0: s.branch(not s.z)
        elif op == 0xf0: s.branch(s.z)
        # flags
        elif op == 0x18: s.c = False
        elif op == 0x38: s.c = True
        elif op == 0x58: s.i = False
        elif op == 0x78: s.i = True
        elif op == 0xb8: s.v = False
        elif op == 0xd8: s.d = False
        elif op == 0xf8: s.d = True
        elif op == 0xea: pass  # NOP
        # undocumented opcodes (subset games commonly use)
        elif op in (0x1a, 0x3a, 0x5a, 0x7a, 0xda, 0xfa): pass          # NOP
        elif op in (0x80, 0x82, 0x89, 0xc2, 0xe2): s.imm()             # NOP #imm
        elif op in (0x04, 0x44, 0x64): s.zp()                          # NOP zp
        elif op in (0x14, 0x34, 0x54, 0x74, 0xd4, 0xf4): s.zpx()       # NOP zp,X
        elif op == 0x0c: s.ab()                                        # NOP abs
        elif op in (0x1c, 0x3c, 0x5c, 0x7c, 0xdc, 0xfc): s.abx()       # NOP abs,X
        elif op == 0xa7: s.a = s.x = s.setnz(s.rd(s.zp()))             # LAX zp
        elif op == 0xb7: s.a = s.x = s.setnz(s.rd(s.zpy()))            # LAX zp,Y
        elif op == 0xaf: s.a = s.x = s.setnz(s.rd(s.ab()))             # LAX abs
        elif op == 0xbf: s.a = s.x = s.setnz(s.rd(s.aby()))            # LAX abs,Y
        elif op == 0xa3: s.a = s.x = s.setnz(s.rd(s.inx_()))           # LAX (zp,X)
        elif op == 0xb3: s.a = s.x = s.setnz(s.rd(s.iny_()))           # LAX (zp),Y
        elif op == 0x87: s.wr(s.zp(), s.a & s.x)                       # SAX zp
        elif op == 0x97: s.wr(s.zpy(), s.a & s.x)                      # SAX zp,Y
        elif op == 0x8f: s.wr(s.ab(), s.a & s.x)                       # SAX abs
        elif op == 0x83: s.wr(s.inx_(), s.a & s.x)                     # SAX (zp,X)
        elif op in (0x0b, 0x2b):                                       # ANC #imm
            s.a = s.setnz(s.a & s.rd(s.imm())); s.c = s.n
        elif op == 0xc7: a = s.zp(); v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v)   # DCP zp
        elif op == 0xd7: a = s.zpx(); v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v)  # DCP zp,X
        elif op == 0xcf: a = s.ab(); v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v)   # DCP abs
        elif op == 0xdf: a = s.abx(); v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v)  # DCP abs,X
        elif op == 0xdb: a = s.aby(); v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v)  # DCP abs,Y
        elif op == 0xd3: a = s.iny_(); v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v) # DCP (zp),Y
        elif op == 0xe7: a = s.zp(); v = (s.rd(a)+1) & 0xff; s.wr(a, v); s.sbc(v)         # ISC zp
        elif op == 0xf7: a = s.zpx(); v = (s.rd(a)+1) & 0xff; s.wr(a, v); s.sbc(v)        # ISC zp,X
        elif op == 0xef: a = s.ab(); v = (s.rd(a)+1) & 0xff; s.wr(a, v); s.sbc(v)         # ISC abs
        elif op == 0xff: a = s.abx(); v = (s.rd(a)+1) & 0xff; s.wr(a, v); s.sbc(v)        # ISC abs,X
        elif op == 0x07: a = s.zp(); v = s.asl(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a | v)   # SLO zp
        elif op == 0x0f: a = s.ab(); v = s.asl(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a | v)   # SLO abs
        elif op == 0x27: a = s.zp(); v = s.rol(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a & v)   # RLA zp
        elif op == 0x47: a = s.zp(); v = s.lsr(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a ^ v)   # SRE zp
        elif op == 0x67: a = s.zp(); v = s.ror(s.rd(a)); s.wr(a, v); s.adc(v)                 # RRA zp
        # remaining RMW-combo undocumented addressing modes (SLO/RLA/SRE/RRA/DCP/ISC)
        elif op == 0xeb: s.sbc(s.rd(s.imm()))                          # USBC #imm
        elif op == 0xbb:                                               # LAS abs,Y
            v = s.rd(s.aby()) & s.sp; s.a = s.x = s.sp = s.setnz(v)
        elif op == 0x4b: s.a = s.lsr(s.a & s.rd(s.imm()))              # ALR #imm
        elif op == 0x6b:                                               # ARR #imm
            t = s.a & s.rd(s.imm()); s.a = s.setnz(((t >> 1) | (0x80 if s.c else 0)) & 0xff)
            s.c = bool(s.a & 0x40); s.v = bool((s.a >> 6 ^ s.a >> 5) & 1)
        elif op == 0xcb:                                               # SBX #imm
            v = s.rd(s.imm()); t = (s.a & s.x) - v; s.c = t >= 0; s.x = s.setnz(t & 0xff)
        elif op == 0x8b: s.a = s.setnz(s.a & s.x & s.rd(s.imm()))      # XAA #imm (approx)
        elif op in (0x03,0x13,0x17,0x1b,0x1f, 0x23,0x2f,0x33,0x37,0x3b,0x3f,
                    0x43,0x4f,0x53,0x57,0x5b,0x5f, 0x63,0x6f,0x73,0x77,0x7b,0x7f,
                    0xc3,0xe3,0xf3,0xfb):
            mode = op & 0x1f
            if   mode == 0x03: a = s.inx_()
            elif mode == 0x07: a = s.zp()
            elif mode == 0x0f: a = s.ab()
            elif mode == 0x13: a = s.iny_()
            elif mode == 0x17: a = s.zpx()
            elif mode == 0x1b: a = s.aby()
            else:              a = s.abx()   # 0x1f
            fam = op & 0xe0
            if fam == 0x00: v = s.asl(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a | v)   # SLO
            elif fam == 0x20: v = s.rol(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a & v) # RLA
            elif fam == 0x40: v = s.lsr(s.rd(a)); s.wr(a, v); s.a = s.setnz(s.a ^ v) # SRE
            elif fam == 0x60: v = s.ror(s.rd(a)); s.wr(a, v); s.adc(v)               # RRA
            elif fam == 0xc0: v = (s.rd(a)-1) & 0xff; s.wr(a, v); s.cmp_(s.a, v)     # DCP
            elif fam == 0xe0: v = (s.rd(a)+1) & 0xff; s.wr(a, v); s.sbc(v)           # ISC
        elif op == 0x00:  # BRK
            raise StopIteration(f'BRK at ${(s.pc-1)&0xffff:04x}')
        else:
            raise StopIteration(f'unimplemented opcode ${op:02x} at ${(s.pc-1)&0xffff:04x}')
