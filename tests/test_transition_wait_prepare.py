"""Structural guards for the forced-blank wait-slack producer experiment."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TransitionWaitPrepareTests(unittest.TestCase):
    def test_poll_consumes_only_real_wait_slack_and_rechecks_pending(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('transition_wait_prepare_poll:', 1)[1].split(
            '.ifdef EXPERIMENTAL_DEFERRED_GAME_NMI', 1)[0]
        self.assertIn('php\n    pha\n    lda a:$010B\n    cmp #2\n    bcs @done', block)
        self.assertIn('stz $4200\n    lda a:$1CF0\n    beq @enable', block)
        self.assertIn('stz a:$1CF0', block)
        self.assertIn('lda #1\n    sta a:$1CF7', block)
        self.assertIn('jsl $C00000+video_prepare_bridge', block)
        self.assertIn('stz a:$1CF7', block)
        self.assertIn('load_interrupt_enable\n    sta $4200', block)
        self.assertIn('@done:\n    pla\n    plp\n    rts', block)

    def test_converter_never_overwrites_a_pending_split_pass(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('@game_budget:', 1)[1].split('.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER', 1)[0]
        self.assertIn('lda $1CA0\n    cmp #2', block)
        self.assertIn('lda $1CF0\n    bne @transition_fallback', block)
        self.assertIn('sta $1CF0', block)
        self.assertIn('@transition_fallback:', block)
        self.assertIn('@transition_normal_budget:', block)

    def test_one_row_override_is_confined_to_the_split_pass(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('@game_budget:', 1)[1].split('@set_budget:', 1)[0]
        self.assertIn('.ifdef EXPERIMENTAL_TRANSITION_WAIT_PREPARE', block)
        self.assertIn('lda $1CF7\n    bne @transition_one_row', block)

    def test_transition_completion_clears_obsolete_pending_pass(self):
        source = (ROOT / 'snes/native_video.asm').read_text()
        block = source.split('transition_ready:', 1)[1].split('row_room:', 1)[0]
        self.assertIn('stz $1CA0\n.ifdef EXPERIMENTAL_TRANSITION_WAIT_PREPARE\n', block)
        self.assertIn('stz $1CF0', block)

    def test_builder_guards_patch_and_records_flag(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("wait_preimage = bytes.fromhex('eaeaea')", source)
        self.assertIn("symbols['transition_wait_prepare_poll']", source)
        self.assertIn('"experimental_transition_wait_prepare": experimental_transition_wait_prepare', source)
        self.assertIn("'--experimental-transition-wait-prepare'", source)


if __name__ == '__main__':
    unittest.main()
