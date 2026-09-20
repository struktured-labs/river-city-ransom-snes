import unittest

from tools.check_second_tick_deadline import decision


class DeadlineTests(unittest.TestCase):
    def test_boundaries(self):
        for line in range(262):
            self.assertEqual(decision(line), line in range(194))

    def test_high_bit_is_not_low_scanline(self):
        for line in range(256,262):
            self.assertFalse(decision(line))
            self.assertTrue(decision(line & 255))
