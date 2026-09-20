import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_sound_commit import expected, PREIMAGE


class SoundCommitTests(unittest.TestCase):
    def test_default_and_dependency(self):
        self.assertIs(inspect.signature(build).parameters['experimental_sound_commit'].default, False)
        with self.assertRaisesRegex(ValueError, 'requires direct APU'):
            build(Path('missing'), [], Path('unused'), experimental_sound_commit=True)

    def test_original_branch_targets(self):
        self.assertEqual(len(PREIMAGE), 30)
        self.assertEqual(7 + PREIMAGE[6], 17)  # BCS effect
        self.assertEqual(12 + PREIMAGE[11], 29)  # BNE muted RTS
        self.assertEqual(17 + PREIMAGE[16], 23)  # BEQ write

    def test_muted_music_preserves_packet_but_effects_ignore_mute(self):
        row = (0x40, 255, 0x30, 1, 0, 0, 0, 19, 128)
        got = expected(row)
        self.assertEqual(got[:4], bytes((128, 0xb0, 0, 19)))
        self.assertEqual(got[9+3], 0xaa)
        self.assertEqual(got[-1], 0)
        got = expected((*row[:6], 4, 19, 128))
        self.assertEqual(got[9+3], 255)
        self.assertEqual(got[-1], 1)

    def test_enable_and_disabled_length(self):
        self.assertEqual(expected((0x40, 0, 0x30, 0, 0, 15, 0, 21, 0))[-1], 0)
        self.assertEqual(expected((0x40, 0, 0x30, 0, 0, 0, 0, 3, 0))[-1], 0)
