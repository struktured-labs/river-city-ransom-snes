"""Structural ABI checks for the exact OAM snapshot dirty gate."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OamDirtyGateTests(unittest.TestCase):
    def test_both_translated_write_paths_mark_the_gate(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        dma = source.split('@dma:', 1)[1].split('dispatch_ppudata:', 1)[0]
        direct = source.split('@oamdata:', 1)[1].split('@scroll:', 1)[0]
        self.assertIn('mvn $7E0000,$7E0000', dma)
        self.assertIn('sta a:$1C87', dma)
        self.assertIn('sta a:$1000,x', direct)
        self.assertIn('sta a:$1C87', direct)

    def test_clean_and_changed_paths_consume_the_gate(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('prepare_sprites:', 1)[1].split('prepare_tail:', 1)[0]
        self.assertLess(block.index('cmp $1C86'), block.index('lda $1C87'))
        self.assertIn('jmp prepare_tail', block)
        self.assertEqual(block.count('stz $1C87'), 2)


if __name__ == '__main__':
    unittest.main()
