"""Savestate bridge layout (issue #30); hardware round trip is in the commit notes."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CA65 = ROOT / '.deps/cc65/bin/ca65'
LD65 = ROOT / '.deps/cc65/bin/ld65'
PARENT = ROOT / 'build/difficulty-x-fix-4300/native-cpu.sfc'


def assemble():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        subprocess.run([str(CA65), '-o', str(d / 'b.o'), str(ROOT / 'snes/savestate_bridge.asm')], check=True)
        subprocess.run([str(LD65), '-C', str(ROOT / 'snes/savestate_bridge.cfg'), '-Ln', str(d / 'b.lbl'),
                        '-o', str(d / 'b.bin'), str(d / 'b.o')], check=True)
        names = {ln.split()[2].lstrip('.'): int(ln.split()[1], 16) for ln in (d / 'b.lbl').read_text().splitlines()}
        return (d / 'b.bin').read_bytes(), names


@unittest.skipUnless(CA65.exists() and LD65.exists(), 'cc65 not installed')
class Bridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.names = assemble()

    def test_frame_is_a_native_rti_to_bridge_return_in_bank_0(self):
        c, ret = self.code, self.names['bridge_return']
        self.assertEqual((c[0], c[3]), (0xF4, 0xF4))            # two PEAs
        stack = []                                            # push order: hi then lo, per PEA
        for at in (1, 4):
            stack += [c[at + 1], c[at]]
        p, pcl, pch, pb = stack[::-1]                         # native RTI pull order
        self.assertEqual((pb, pch << 8 | pcl), (0, ret))
        self.assertEqual(p & 0x3C, 0x34)                      # M, X, I set; D clear

    def test_reads_the_native_irq_vector_in_native_mode(self):
        self.assertEqual(self.code[6:11], bytes.fromhex('18fb6ceeff'))   # CLC XCE JMP ($FFEE)

    def test_return_restores_emulation_then_game_nmi_or_rtl(self):
        c = self.code[self.names['bridge_return'] - self.names['bridge_nmi']:]
        self.assertEqual(c[:2], bytes.fromhex('38fb'))                  # SEC XCE
        self.assertEqual(c[2:5], bytes.fromhex('2c1242'))               # BIT $4212
        self.assertEqual(c[7:10], bytes.fromhex('4cfb80'))              # JMP $80FB
        self.assertEqual(self.code[-1], 0x6B)                           # skip path ends in RTL

    def test_parent_vectors(self):
        if not PARENT.exists():
            self.skipTest('4300 not built')
        rom = PARENT.read_bytes()
        self.assertEqual(rom[0xFFFA] | rom[0xFFFB] << 8, 0x80FB)
        irq = rom[0xFFEE] | rom[0xFFEF] << 8
        self.assertEqual(rom[irq], 0x40)                                # native IRQ reaches an RTI
        at = self.names['bridge_nmi']
        self.assertEqual(rom[at:at + len(self.code)], b'\xff' * len(self.code))


if __name__ == '__main__':
    unittest.main()
