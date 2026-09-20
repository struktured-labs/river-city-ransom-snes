"""Structural guards for the forced-blank game-first transition experiment."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TransitionGameFirstTests(unittest.TestCase):
    def test_nmi_skips_only_unready_transition_publication(self):
        source = (ROOT/'snes/native_boot.asm').read_text()
        nmi = source.split('nmi:', 1)[1].split('publish_video:', 1)[0]
        gate = ('lda a:$1CA0\n    beq @publish_before_game\n'
                '    lda a:$1CEF\n    beq @published_or_deferred')
        self.assertIn(gate, nmi)
        self.assertLess(nmi.index('@publish_before_game:'), nmi.index('jsr publish_video'))
        self.assertLess(nmi.index('jsr publish_video'), nmi.index('stz a:$1CEF'))

    def test_post_game_paths_publish_only_while_transition_is_hidden(self):
        source = (ROOT/'snes/native_runtime.asm').read_text()
        guarded = ('lda a:$1CA0\n    beq :+\n'
                   '    jsl $C00000+video_publish_bridge\n:')
        self.assertEqual(source.count(guarded), 2)

    def test_active_display_readiness_latches_for_next_vblank(self):
        source = (ROOT/'snes/native_video.asm').read_text()
        block = source.split('transition_ready:', 1)[1].split('row_room:', 1)[0]
        self.assertIn('lda $4212\n    bmi @finish_transition', block)
        self.assertIn('lda #1\n    sta $1CEF\n    rts', block)
        self.assertLess(block.index('stz $1CEF'), block.index('stz $1CA0'))

    def test_builder_requires_immediate_transition_producer(self):
        source = (ROOT/'tools/build_native.py').read_text()
        self.assertIn("'--experimental-transition-game-first'", source)
        self.assertIn('"experimental_transition_game_first": experimental_transition_game_first', source)
        self.assertIn('Transition game-first requires transition prepare defer', source)

    def test_builder_exposes_existing_grouped_row_scan(self):
        source = (ROOT/'tools/build_native.py').read_text()
        self.assertIn("'--experimental-row-scan'", source)
        self.assertIn('"experimental_row_scan": experimental_row_scan', source)
        self.assertIn("'EXPERIMENTAL_ROW_SCAN=1'", source)


if __name__ == '__main__':
    unittest.main()
