import unittest
from tools.build_chromatic_wub_trial import curve, patch, DESCENT, TAIL_PERIOD
from tools.build_sub_wub_trial import curve as parent_curve


class ChromaticWubTests(unittest.TestCase):
    def test_chromatic_steps_then_slower_loud_wubs(self):
        data = curve()
        self.assertEqual(len(data), 720)
        pitches = [int.from_bytes(data[i * 3:i * 3 + 2], 'little') * 1000 / 4096 for i in range(240)]
        volumes = [data[i * 3 + 2] for i in range(240)]
        self.assertAlmostEqual(pitches[0], 311, delta=1)
        self.assertAlmostEqual(pitches[DESCENT], 55, delta=1)
        plateaus = [pitches[i] for i in range(0, DESCENT, 5)]
        self.assertEqual(len(plateaus), 30)
        self.assertTrue(all(plateaus[i] > plateaus[i + 1] for i in range(29)))
        self.assertEqual(len({round(p, 3) for p in pitches[DESCENT:]}), 1)
        self.assertEqual(volumes[DESCENT], 127)
        self.assertEqual(volumes[DESCENT + TAIL_PERIOD], 127)
        self.assertLess(volumes[DESCENT + TAIL_PERIOD // 2], 40)
        self.assertTrue(all(v == 0 for v in volumes[235:]))
        parent_vol = parent_curve()[2]
        self.assertGreater(max(volumes), parent_vol)

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
