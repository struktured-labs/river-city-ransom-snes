"""Static coverage for the opt-in unrolled OAM converter."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SpriteUnrollTests(unittest.TestCase):
    def test_converter_clears_b_and_emits_all_sprites(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('.ifdef EXPERIMENTAL_SPRITE_UNROLL', 1)[1].split('.endif', 1)[0]
        self.assertIn('rep #$20\n    .a16\n    lda #0\n    sep #$20', block)
        self.assertIn('.repeat 64, sprite', block)
        self.assertIn('lda sprite_y_map,y', block)
        self.assertIn('lda sprite_attribute_map,y', block)
        self.assertIn('ldx #256', block)

    def test_builder_and_executed_checker_are_wired(self):
        builder = (ROOT / 'tools/build_native.py').read_text()
        checker = (ROOT / 'tools/check_sprite_unroll.py').read_text()
        self.assertIn("'EXPERIMENTAL_SPRITE_UNROLL=1'", builder)
        self.assertIn("'--experimental-sprite-unroll'", builder)
        self.assertIn("lda #$AB00", checker)
        self.assertIn('negative=True', checker)


if __name__ == '__main__':
    unittest.main()
