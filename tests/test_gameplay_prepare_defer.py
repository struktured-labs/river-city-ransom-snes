"""Structural guards for camera-commit gameplay graphics scheduling."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GameplayPrepareDeferTests(unittest.TestCase):
    def test_camera_tail_preserves_original_result_and_services_latch(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('camera_prepare_exit:', 1)[1].split('nmi_task_return:', 1)[0]
        self.assertIn('sbc $3B\n    sta $F6\n    php\n    pha', block)
        self.assertIn('stz a:$1CBC', block)
        self.assertIn('inc a:$1CBE', block)
        self.assertIn('jsl $C00000+video_prepare_bridge', block)
        self.assertLess(block.index('stz $4200'), block.index('video_prepare_bridge'))
        self.assertIn('pla\n    plp\n    rts', block)

    def test_next_nmi_fallback_precedes_new_gameplay_tick(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('nmi_rti_return:', 1)[1].split('@restore:', 1)[0]
        fallback = block.index('inc a:$1CBF')
        sound = block.index('jsr $FA54')
        scheduled = block.index('inc a:$1CBD')
        self.assertLess(fallback, sound)
        self.assertLess(sound, scheduled)
        self.assertIn('lda a:$1CBC\n    bne @restore', block)
        self.assertIn('lda a:$1CBA\n    bne @restore', block)
        self.assertIn('lda a:$0100\n    and #$C0\n    cmp #$C0\n    beq @restore', block)

    def test_gameplay_pass_doubles_rows_when_idle_pass_is_removed(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('@game_budget:', 1)[1].split('@set_budget:', 1)[0]
        self.assertIn('.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER\n    lda #4', block)
        self.assertIn('.else\n    lda #2', block)

    def test_builder_patches_exact_camera_tail_only_when_requested(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("camera_preimage = bytes.fromhex('e53b85f660')", source)
        self.assertIn("else 'camera_prepare_exit'", source)
        self.assertIn("word(symbols[camera_entry])", source)
        self.assertIn("'--experimental-gameplay-prepare-defer'", source)
        self.assertIn("'EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER=1'", source)


if __name__ == '__main__':
    unittest.main()
