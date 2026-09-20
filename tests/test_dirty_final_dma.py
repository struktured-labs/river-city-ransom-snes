"""Structural guards for generation-gated final OAM/palette DMA."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DirtyFinalDmaTests(unittest.TestCase):
    def test_producer_marks_both_changed_generations(self):
        source = (ROOT/'snes/native_prepare.asm').read_text()
        palette = source.split('prepare_palette:', 1)[1].split('prepare_sprites:', 1)[0]
        sprites = source.split('prepare_sprites:', 1)[1].split('prepare_tail:', 1)[0]
        self.assertEqual(palette.count('sta $1CED'), 2)
        self.assertEqual(sprites.count('sta $1CEE'), 2)
        self.assertIn('@palette_changed16:', palette)
        self.assertIn('@sprite_changed16:', sprites)

    def test_consumer_clears_only_after_each_dma(self):
        source = (ROOT/'snes/native_video.asm').read_text()
        block = source.split('; Publish prepared OAM.', 1)[1].split('lda $1C20', 1)[0]
        self.assertLess(block.index('lda $1CEE'), block.index('stz $2102'))
        self.assertLess(block.index('sta $420B'), block.index('stz $1CEE'))
        self.assertLess(block.index('lda $1CED'), block.index('stz $2121'))
        self.assertLess(block.rindex('sta $420B'), block.index('stz $1CED'))

    def test_palette_only_path_initializes_its_own_dma_channel(self):
        source = (ROOT/'snes/native_video.asm').read_text()
        palette = source.split('@palette_batch:', 1)[1].split('; Only the 32 used palette', 1)[0]
        self.assertIn('stz $4300', palette)
        self.assertIn('lda #$7E\n    sta $4304', palette)
        fixture = (ROOT/'snes/video_test.asm').read_text()
        self.assertIn('stz $4304\n    lda #1\n    sta $1CA0', fixture)
        self.assertIn('@palette_only_vblank:\n    lda $4212\n    bpl @palette_only_vblank\n    jsr native_video', fixture)
        self.assertIn('lda $4304\n    cmp #$7E', fixture)

    def test_builder_exposes_and_records_opt_in(self):
        source = (ROOT/'tools/build_native.py').read_text()
        self.assertIn("'EXPERIMENTAL_DIRTY_FINAL_DMA=1'", source)
        self.assertIn('"experimental_dirty_final_dma": experimental_dirty_final_dma', source)
        self.assertIn("'--experimental-dirty-final-dma'", source)


if __name__ == '__main__':
    unittest.main()
