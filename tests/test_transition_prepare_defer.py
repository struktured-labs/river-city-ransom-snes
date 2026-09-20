"""Guard checks for forced-blank-only graphics producer deferral."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TransitionPrepareDeferTests(unittest.TestCase):
    def test_only_state_one_bypasses_coroutine_prepare(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('nmi_task_return:', 1)[1].split('dec a:$1C0A', 1)[0]
        self.assertIn('.ifdef EXPERIMENTAL_TRANSITION_PREPARE_DEFER', block)
        self.assertIn('lda a:$1CA0\n    cmp #1\n    bne :+\n    lda a:$0042\n    beq :++', block)
        self.assertIn('jsl $C00000+video_prepare_bridge', block)

    def test_builder_keeps_it_explicit(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("'EXPERIMENTAL_TRANSITION_PREPARE_DEFER=1'", source)
        self.assertIn("'--experimental-transition-prepare-defer'", source)

    def test_forced_blank_drain_only_is_exempt_from_vblank_latch(self):
        source = (ROOT / 'snes/native_video.asm').read_text()
        block = source.split('; Hardware assertion: consumer must not extend past VBlank.', 1)[1].split('rts', 1)[0]
        self.assertLess(block.index('lda $1CA0'), block.index('lda $4212'))
        self.assertIn('bne :+', block)


if __name__ == '__main__':
    unittest.main()
