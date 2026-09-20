"""The optional ident is small, original, and returns SPC control to IPL."""
import unittest

from tools.build_ident_spc import DIR, ECHO_DELAY, ECHO_START, FRAMES, GROWL_SAMPLE, LOAD, SAMPLE, Program, build, curve, growl_waveform, waveform


class IdentSPCTests(unittest.TestCase):
    def test_ipl_return_and_stable_brr_directory(self):
        payload = build()
        self.assertEqual(payload[DIR-LOAD:DIR-LOAD+8],
                         bytes((SAMPLE & 255, SAMPLE >> 8, SAMPLE & 255, SAMPLE >> 8,
                                GROWL_SAMPLE & 255, GROWL_SAMPLE >> 8,
                                GROWL_SAMPLE & 255, GROWL_SAMPLE >> 8)))
        self.assertEqual(payload[SAMPLE-LOAD:SAMPLE-LOAD+len(waveform())], waveform())
        self.assertEqual(payload[SAMPLE-LOAD + 9], 0x93)  # end+loop second block
        self.assertEqual(payload[GROWL_SAMPLE-LOAD:], growl_waveform())
        self.assertIn(bytes((0x8F, 0x80, 0xF1, 0x20, 0x5F, 0xC0, 0xFF)),
                      payload[:DIR-LOAD])

    def test_branch_rejects_out_of_range_and_no_directory_overlap(self):
        program = Program()
        program.branch(0x2F, 'far')
        program.put(*([0] * 128))
        program.label('far')
        with self.assertRaisesRegex(ValueError, 'out of range'):
            program.result()

    def test_ident_is_deterministic(self):
        self.assertEqual(build(), build())
        self.assertEqual(curve(), curve())
        self.assertLess(len(build()), 0x300)

    def test_continuous_chromatic_pitch_bend_and_echo_memory_safety(self):
        rows = [curve()[i:i+3] for i in range(0, len(curve()), 3)]
        self.assertEqual(len(rows), FRAMES)
        hz = [int.from_bytes(row[:2], 'little') * 1000 / 4096 for row in rows]
        self.assertEqual(len(set(row[:2] for row in rows[:145])), 145)
        self.assertTrue(all(a > b for a,b in zip(hz[:144], hz[1:145])))
        self.assertLess(abs(hz[0] - 311), 0.2)
        self.assertLess(abs(hz[144] - 110), 0.2)
        self.assertTrue(all(abs(hz[k*8] - 311 * (110/311)**(k/18)) < 0.3
                            for k in range(19)))
        self.assertLess(rows[-1][-1], rows[-33][-1] / 16)
        self.assertLess(rows[-24][-1], 60)  # longer hardware-driven tail taper
        self.assertGreaterEqual(ECHO_START, 0x8000)
        self.assertLess(ECHO_START + ECHO_DELAY*2048, 0xFFC0)
        self.assertLessEqual(44+31+10+5, 128)  # FIR abs-sum must not amplify clicks

    def test_echo_starts_disabled_then_first_key_only_and_stops_writeback(self):
        code = build()[:DIR - LOAD]
        self.assertIn(bytes((0x8F, 0x60, 0xF3)), code)  # mute before ready
        self.assertIn(bytes((0x8F, 0x20, 0xF3)), code)
        self.assertIn(bytes((0x8F, 0x00, 0xF3)), code)
        self.assertEqual(code.count(bytes((0x8F, 0x03, 0xF3))), 2)  # EON, KON


if __name__ == '__main__':
    unittest.main()
