import unittest

from tools.nes_scroll_trace import validate


class NesScrollTraceTests(unittest.TestCase):
    def test_requested_window_and_observed_extent(self):
        rows=[['7000','15','10','e2b1','00f6','255'],['8548','240','20','e200','2005','0']]
        self.assertEqual(validate(rows,7000,9000,8548),dict(records=2,observed_first=7000,observed_last=8548))

    def test_stale_default_window_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'ignored requested'):
            validate([['6500','15','10','e2b1','00f6','255']],7000,9000,8548)

    def test_invalid_and_nonmonotonic_events_fail(self):
        good=['7000','15','10','e2b1','00f6','255']
        for rows in ([],[good[:-1]],[good,good],[good[:4]+['4016','0']],
                     [['8549','15','10','e2b1','00f6','255']]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):validate(rows,7000,9000,8548)
