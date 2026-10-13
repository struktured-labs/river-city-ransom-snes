"""Freeze fix (no DB = program-bank windows) and Gamer stamina bar scale."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import build_freeze_fix as ff
from tools import stamina_bar_sweep as sweep

ROOT = Path(__file__).resolve().parent.parent
CA65 = ROOT / '.deps/cc65/bin/ca65'
# The freeze fix itself (build 4295); later features may move helper labels.
FIX_COMMIT = '2957b74'
SOURCES = ('difficulty_modes', 'gamer_outline', 'rumble', 'stamina_bar')


def code_lines(text):
    for line in text.splitlines():
        code = line.split(';', 1)[0].strip().lower()
        if code:
            yield code


def assemble(name, text=None):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        bin_, names = ff.assemble(text if text is not None else (ROOT / f'snes/{name}.asm').read_text(),
                                  str(ROOT / f'snes/{name}.cfg'), d, name)
    return bin_, names


class NoProgramBankDB(unittest.TestCase):
    def test_sources_never_touch_db(self):
        for name in SOURCES:
            ops = [l.split()[0] for l in code_lines((ROOT / f'snes/{name}.asm').read_text())]
            for op in ('phk', 'plb', 'mvn', 'mvp'):
                self.assertNotIn(op, ops, f'{name}.asm uses {op}')

    def test_assembled_helpers_have_no_phk_plb(self):
        if not CA65.exists():
            self.skipTest('cc65 not installed')
        for name in SOURCES:
            helper, _ = assemble(name)
            self.assertNotIn(ff.DB_WINDOW, helper, name)

    def test_parent_sources_had_the_windows(self):
        # The parent (4294) helpers are what froze; the check must see them.
        if not CA65.exists():
            self.skipTest('cc65 not installed')
        try:
            old = subprocess.run(['git', 'show', f'{ff.PARENT_COMMIT}:snes/difficulty_modes.asm'], cwd=ROOT,
                                 check=True, capture_output=True, text=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest('parent commit not available')
        helper, _ = assemble('difficulty_modes', old)
        self.assertIn(ff.DB_WINDOW, helper)

    def test_labels_keep_their_addresses(self):
        if not CA65.exists():
            self.skipTest('cc65 not installed')
        for name, slot, size in ff.HELPERS:
            try:
                old = subprocess.run(['git', 'show', f'{ff.PARENT_COMMIT}:snes/{name}.asm'], cwd=ROOT,
                                     check=True, capture_output=True, text=True).stdout
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.skipTest('parent commit not available')
            fixed = subprocess.run(['git', 'show', f'{FIX_COMMIT}:snes/{name}.asm'], cwd=ROOT,
                                   check=True, capture_output=True, text=True).stdout
            with tempfile.TemporaryDirectory() as d:
                cfg = Path(d) / f'{name}.cfg'
                cfg.write_bytes(subprocess.run(['git', 'show', f'{FIX_COMMIT}:snes/{name}.cfg'], cwd=ROOT,
                                               check=True, capture_output=True).stdout)
                b, nb = ff.assemble(fixed, str(cfg), Path(d), name)
                a, na = ff.assemble(old, str(cfg), Path(d), name)
            self.assertEqual(na, nb, name)
            self.assertEqual((len(a), len(b)), (size, size), name)


class Cpu:
    """Just the 6502/65816 emulation-mode opcodes stam_ticks uses."""

    def __init__(self, code, base, ram):
        self.code, self.base, self.ram = code, base, ram
        self.a = self.x = self.y = 0
        self.z = self.c = False
        self.stack = []

    def flags(self, v):
        self.z = (v & 0xFF) == 0
        return v & 0xFF

    def run(self, entry, y, divide):
        pc = entry
        self.y = y
        self.stack.append('ret')
        for _ in range(100):
            op = self.code[pc - self.base]
            arg = self.code[pc - self.base + 1:pc - self.base + 3]
            w = int.from_bytes(arg, 'little')
            if op == 0x08:
                self.stack.append('p'); pc += 1
            elif op == 0x28:
                self.stack.pop(); pc += 1
            elif op == 0xE2:
                pc += 2
            elif op == 0xAD:
                self.a = self.flags(self.ram[w]); pc += 3
            elif op == 0xB9:
                self.a = self.flags(self.ram[w + self.y]); pc += 3
            elif op == 0xC9:
                self.z = self.a == arg[0]; self.c = self.a >= arg[0]; pc += 2
            elif op == 0xF0:
                pc += 2 + (arg[0] - 256 if arg[0] > 127 and self.z else arg[0] if self.z else 0)
            elif op == 0x18:
                self.c = False; pc += 1
            elif op == 0x69:
                s = self.a + arg[0] + self.c
                self.c = s > 255; self.a = self.flags(s); pc += 2
            elif op == 0xAA:
                self.x = self.flags(self.a); pc += 1
            elif op == 0xA0:
                self.y = self.flags(arg[0]); pc += 2
            elif op == 0x3A:
                self.a = self.flags(self.a - 1); pc += 1
            elif op == 0x4A:
                self.c = bool(self.a & 1); self.a = self.flags(self.a >> 1); pc += 1
            elif op == 0x1A:
                self.a = self.flags(self.a + 1); pc += 1
            elif op == 0x4C:
                assert w == 0xDF7B, hex(w)
                self.a = divide(self.x, self.y)
                op = 0x60
            if op == 0x60:
                self.assertEmpty()
                return self.a
            if op not in (0x08, 0x28, 0xE2, 0xAD, 0xB9, 0xC9, 0xF0, 0x18, 0x69, 0xAA, 0xA0, 0x3A, 0x4A, 0x1A):
                raise AssertionError(f'unexpected opcode {op:02X} at {pc:04X}')
        raise AssertionError('runaway')

    def assertEmpty(self):
        if self.stack != ['ret']:
            raise AssertionError(f'stack not balanced: {self.stack}')


class StaminaBar(unittest.TestCase):
    def test_models(self):
        g = [sweep.gamer_ticks(s) for s in range(256)]
        self.assertEqual(g[0], 0)
        self.assertTrue(all(t > 0 for t in g[1:]))
        self.assertTrue(all(a <= b for a, b in zip(g, g[1:])))
        self.assertEqual(min(s for s, t in enumerate(g) if t == 16), 241)
        self.assertEqual(max(g), 16)
        for s in range(128):
            self.assertEqual(sweep.nes_ticks(s), min(16, -(-s // 8)))
        self.assertEqual([sweep.nes_ticks(s) for s in (248, 249, 255)], [16, 0, 0])   # the original wrap

    def test_assembled_helper_every_value_every_skill(self):
        if not CA65.exists():
            self.skipTest('cc65 not installed')
        helper, names = assemble('stamina_bar')
        entry = names['stam_ticks']
        self.assertEqual(helper[entry - ff.BAR_SLOT:entry - ff.BAR_SLOT + 3], bytes.fromhex('08e230'))
        for skill in (1, 2, 3, 4):
            for slot in (0, 1):
                for s in range(256):
                    ram = bytearray(0x800)
                    ram[0x64C], ram[0x4BF + slot] = skill, s
                    got = Cpu(helper, ff.BAR_SLOT, ram).run(entry, slot, lambda x, y: x // y)
                    if skill != 3:
                        # the original quotient, exactly; the 8-cell drawing loop shows at most 16
                        self.assertEqual(got, ((s + 7) & 0xFF) // 8, (skill, slot, s))
                    self.assertEqual(min(16, got), sweep.expected(skill, s), (skill, slot, s))


class Build(unittest.TestCase):
    def test_build_on_the_parent(self):
        parent = ROOT / 'build/rumble-4294'
        if not CA65.exists() or not (parent / 'native-cpu.sfc').exists():
            self.skipTest('parent build not present')
        with tempfile.TemporaryDirectory() as d:
            import contextlib, io, json, os
            cwd = os.getcwd()
            os.chdir(ROOT)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    ff.build(parent, Path(d) / 'out')
            finally:
                os.chdir(cwd)
            rom = (Path(d) / 'out/native-cpu.sfc').read_bytes()
            meta = json.loads((Path(d) / 'out/manifest.json').read_text())
        self.assertIn('freeze_fix', meta)
        for bank in ff.BANKS:
            self.assertNotIn(ff.DB_WINDOW, rom[bank * 65536 + 0x6900:bank * 65536 + 0x7200])
        self.assertEqual(rom[ff.HUD], 0x20)


if __name__ == '__main__':
    unittest.main()
