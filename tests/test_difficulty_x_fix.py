"""apply_combat/apply_stam return with the caller's X and Y (issue #27).

The spawn loop at $B83E stores each stat with STA $049F,X right after the
call, so X must still be the actor slot. Runs the assembled helper in a small
emulation-mode interpreter for every skill, slot, class and value.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CA65 = ROOT / '.deps/cc65/bin/ca65'
LD65 = ROOT / '.deps/cc65/bin/ld65'
SLOT = 0x7058
B946 = (0xF0, 0x00, 0x10, 0x20)


def assemble():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        subprocess.run([str(CA65), '-o', str(d / 'h.o'), str(ROOT / 'snes/difficulty_modes.asm')], check=True)
        subprocess.run([str(LD65), '-C', str(ROOT / 'snes/difficulty_modes.cfg'), '-Ln', str(d / 'h.lbl'),
                        '-o', str(d / 'h.bin'), str(d / 'h.o')], check=True)
        names = {ln.split()[2].lstrip('.'): int(ln.split()[1], 16) for ln in (d / 'h.lbl').read_text().splitlines()}
        return (d / 'h.bin').read_bytes(), names


class Cpu:
    def __init__(self, code, ram):
        self.code, self.ram, self.far = code, ram, {}
        self.a = self.x = self.y = 0
        self.n = self.z = self.c = False
        self.stack = []

    def set(self, v):
        v &= 0xFF
        self.n, self.z = bool(v & 0x80), v == 0
        return v

    def cmp(self, r, v):
        self.c = r >= v
        self.set(r - v)

    def read(self, addr):
        if addr < 0x2000:
            return self.ram[addr]
        if 0xC1 <= addr >> 16 <= 0xC8 and 0xB946 <= (addr & 0xFFFF) <= 0xB949:
            return B946[(addr & 0xFFFF) - 0xB946]
        return self.far.get(addr, 0)

    def run(self, entry, a, x, y):
        self.a, self.x, self.y = a, x, y
        pc, depth = entry, 1
        for _ in range(200):
            op = self.code[pc - SLOT]
            b1 = self.code[pc - SLOT + 1] if pc - SLOT + 1 < len(self.code) else 0
            w = int.from_bytes(self.code[pc - SLOT + 1:pc - SLOT + 3], 'little')
            l = int.from_bytes(self.code[pc - SLOT + 1:pc - SLOT + 4], 'little')
            rel = pc + 2 + (b1 - 256 if b1 > 127 else b1)
            if op == 0x84: self.ram[b1] = self.y; pc += 2
            elif op == 0xA4: self.y = self.set(self.ram[b1]); pc += 2
            elif op == 0xBC: self.y = self.set(self.ram[w + self.x]); pc += 3
            elif op == 0xAC: self.y = self.set(self.ram[w]); pc += 3
            elif op == 0xAE: self.x = self.set(self.ram[w]); pc += 3
            elif op == 0xAD: self.a = self.set(self.ram[w]); pc += 3
            elif op == 0xC0: self.cmp(self.y, b1); pc += 2
            elif op == 0xE0: self.cmp(self.x, b1); pc += 2
            elif op == 0xC9: self.cmp(self.a, b1); pc += 2
            elif op == 0x90: pc = rel if not self.c else pc + 2
            elif op == 0xB0: pc = rel if self.c else pc + 2
            elif op == 0xF0: pc = rel if self.z else pc + 2
            elif op == 0xD0: pc = rel if not self.z else pc + 2
            elif op == 0x30: pc = rel if self.n else pc + 2
            elif op == 0x20: self.stack.append(pc + 3); depth += 1; pc = w
            elif op == 0x60:
                depth -= 1
                if depth == 0:
                    self.assertEqual_stack()
                    return self.a
                pc = self.stack.pop()
            elif op == 0x8F: self.far[l] = self.a; pc += 4
            elif op == 0xAF: self.a = self.set(self.read(l)); pc += 4
            elif op == 0x7F:
                s = self.a + self.read(l + self.x) + self.c
                self.c = s > 0xFF; self.a = self.set(s); pc += 4
            elif op == 0x69:
                s = self.a + b1 + self.c
                self.c = s > 0xFF; self.a = self.set(s); pc += 2
            elif op == 0x18: self.c = False; pc += 1
            elif op == 0xA8: self.y = self.set(self.a); pc += 1
            elif op == 0xAA: self.x = self.set(self.a); pc += 1
            elif op == 0xDA: self.stack.append(('x', self.x)); pc += 1
            elif op == 0xFA:
                tag, v = self.stack.pop()
                assert tag == 'x'
                self.x = self.set(v); pc += 1
            elif op == 0xA9: self.a = self.set(b1); pc += 2
            else:
                raise AssertionError(f'unexpected opcode {op:02X} at {pc:04X}')
        raise AssertionError('runaway')

    def assertEqual_stack(self):
        if self.stack:
            raise AssertionError(f'stack not balanced: {self.stack}')


def expected(value, skill, klass, cap):
    """The original $B900/$B923 result, with Intermediate's flat +8."""
    if klass < 9:
        return value
    v = (value + (8 if skill == 4 else B946[skill])) & 0xFF
    if v == 0 or v & 0x80:
        return 1
    if skill != 3 and v >= cap:
        return cap - 1
    return v


@unittest.skipUnless(CA65.exists() and LD65.exists(), 'cc65 not installed')
class KeepsCallerSlot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.names = assemble()

    def check(self, entry, cap):
        for skill in (1, 2, 3, 4):
            for slot in (0, 1, 2, 3):
                for klass in (0, 8, 9, 0x18, 0x19):
                    for value in range(256):
                        ram = bytearray(0x2000)
                        ram[0x64C], ram[0x4F5 + slot] = skill, klass
                        cpu = Cpu(self.code, ram)
                        got = cpu.run(self.names[entry], value, slot, 0x5A)
                        key = (entry, skill, slot, klass, value)
                        self.assertEqual(cpu.x, slot, key)
                        self.assertEqual(cpu.y, 0x5A, key)
                        self.assertEqual(got, expected(value, skill, klass, cap), key)

    def test_apply_combat(self):
        self.check('apply_combat', 0x40)

    def test_apply_stam(self):
        self.check('apply_stam', 0x80)


if __name__ == '__main__':
    unittest.main()
