"""Static checks for the executed unrolled OAM comparison experiment."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OamCompareTests(unittest.TestCase):
    def test_unroll_uses_equality_carry_for_exact_stride(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('.ifdef EXPERIMENTAL_OAM_COMPARE_UNROLL', 1)[1].split('.else', 1)[0]
        self.assertIn('.repeat 8, word', block)
        self.assertIn('bne @sprite_changed16', block)
        self.assertIn('adc #15', block)
        self.assertIn('cpx #256', block)

    def test_checker_mutates_mismatch_branch(self):
        source = (ROOT / 'tools/check_oam_compare.py').read_text()
        self.assertIn("expected_case=7", source)
        self.assertIn("oam_compare_unroll=True", source)


if __name__ == '__main__':
    unittest.main()
