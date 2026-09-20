"""Dependency and builder guards for the opt-in CHR scan latch."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChrDirtyGateTests(unittest.TestCase):
    def test_all_chr_dependencies_mark_the_latch(self):
        runtime = (ROOT / 'snes/native_runtime.asm').read_text()
        selector = runtime.split('mapper_write:', 1)[1].split('@data:', 1)[0]
        data = runtime.split('@chr:', 1)[1].split('inc a:$1C08', 1)[0]
        control = runtime.split('@ctrl:', 1)[1].split('sta a:$1C20', 1)[0]
        self.assertIn('eor a:$1C19\n    and #$80', selector)
        self.assertIn('cpx #6\n    bcs :+', data)
        self.assertIn('eor a:$1C20\n    and #$18', control)
        for block in (selector, data, control):
            self.assertIn('sta a:$1CBB', block)

    def test_first_scan_and_latched_scan_clear_once(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('prepare_chr:', 1)[1].split('ldy #0', 1)[0]
        self.assertIn('lda $1C79\n    beq @chr_dirty', block)
        self.assertIn('lda $1CBB\n    bne @chr_dirty\n    rts', block)
        self.assertIn('@chr_dirty:\n    stz $1CBB', block)

    def test_builder_keeps_gate_explicit(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("'EXPERIMENTAL_CHR_DIRTY_GATE=1'", source)
        self.assertIn("'--experimental-chr-dirty-gate'", source)


if __name__ == '__main__':
    unittest.main()
