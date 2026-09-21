import unittest
from tools.build_chromatic_wub_trial import curve, patch, stepped_curve, DESCENT, PEAK
from tools.build_sub_wub_trial import curve as parent_curve


class ChromaticWubTests(unittest.TestCase):
    def test_smooth_log_slide_then_slow_wubs(self):
        data = curve()
        self.assertEqual(len(data), 720)
        pitches = [int.from_bytes(data[i * 3:i * 3 + 2], 'little') for i in range(240)]
        hz = [p * 1000 / 4096 for p in pitches]
        volumes = [data[i * 3 + 2] for i in range(240)]
        self.assertAlmostEqual(hz[0], 311, delta=1)
        self.assertAlmostEqual(hz[DESCENT - 1], 55, delta=1)
        self.assertEqual(len(set(pitches[:DESCENT])), DESCENT)
        self.assertTrue(all(pitches[i] > pitches[i + 1] for i in range(DESCENT - 1)))
        self.assertLess(max(pitches[i] - pitches[i + 1] for i in range(DESCENT - 1)), 20)
        self.assertEqual(len(set(pitches[DESCENT:])), 1)
        self.assertLessEqual(max(volumes), PEAK)
        self.assertGreater(volumes[6], volumes[0])
        self.assertLess(abs(volumes[DESCENT] - volumes[DESCENT - 1]), 40)
        self.assertLess(volumes[-1], 8)
        self.assertNotEqual(curve(), stepped_curve())

    def test_parent_is_not_this_shape(self):
        old, new = parent_curve(), curve()
        self.assertNotEqual(old, new)
        self.assertEqual(len(old), 720)

    def test_only_ident_table_master_and_checksum_change(self):
        image = bytearray(b'\xff' * 0x200000)
        image[0x110400:0x110400 + 720] = parent_curve()
        image[0x110800:0x110803] = bytes.fromhex('8f70f3')
        image[0x110810:0x110813] = bytes.fromhex('8f70f3')
        changed, offset = patch(bytes(image))
        self.assertEqual(offset, 0x110400)
        with self.assertRaises(ValueError):
            patch(changed)
