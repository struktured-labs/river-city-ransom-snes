"""Independent gate controls; executed cartridge variants live in report3660."""
import unittest

from tools.check_audio_tick_recovery import assess


def completed(mode=2, line=111):
    ram = bytearray(0x20000)
    ram[0x1810] = 1
    ram[0x1806] = 33
    ram[0x1809] = 32
    for i in range(32):
        token = (0xfffd + i) & 0xffff
        ram[0x1900+i] = token & 255
        ram[0x1920+i] = token >> 8
        ram[0x1940+i] = line & 255
        ram[0x1960+i] = line >> 8
        ram[0x1980+i] = 1 if mode in (0, 1) else mode
    ram[0x1a00:0x1a09] = bytes.fromhex('cdab78bc397e3412ff')
    if mode in (0, 1):
        ram[0x1805] = 32
        ram[0x180a] = 128
    return ram


class AudioTickRecoveryTests(unittest.TestCase):
    def test_all_routes_and_token_wrap(self):
        for mode, resume, line in ((0, 0, 80), (1, 60, 80),
                                   (2, 110, 111), (3, 250, 251)):
            with self.subTest(mode=mode):
                self.assertEqual(assess(completed(mode, line), mode, resume)['failures'], [])

    def test_accounted_but_late_is_not_a_timing_pass(self):
        result = assess(completed(line=240), 2, 110)
        self.assertTrue(result['checks']['actual_calls'])
        self.assertTrue(result['checks']['ordered_unique_tokens'])
        self.assertIn('service_timing', result['failures'])

    def test_each_logged_token_and_timestamp_matters(self):
        for i in range(32):
            for address, gate in ((0x1900+i, 'ordered_unique_tokens'),
                                  (0x1940+i, 'service_timing'),
                                  (0x1980+i, 'source_routes')):
                ram = completed()
                ram[address] = 0
                # The wrapped token at index3 is legitimately zero.
                if address == 0x1903:
                    ram[address] = 1
                self.assertIn(gate, assess(ram, 2, 110)['failures'])

    def test_missing_completion_and_spurious_irq(self):
        ram = completed()
        ram[0x1810] = 0
        ram[0x1805] = 1
        self.assertIn('complete', assess(ram, 2, 110)['failures'])
        self.assertIn('no_spurious_irq', assess(ram, 2, 110)['failures'])

    def test_register_damage_and_short_capture(self):
        for offset, gate in ((0, 'a'), (1, 'a'), (2, 'x'), (3, 'y'),
                             (4, 'flags'), (5, 'db'), (6, 'direct_page'),
                             (7, 'direct_page'), (8, 'stack')):
            ram = completed()
            ram[0x1a00+offset] = 0
            self.assertIn(gate, assess(ram, 2, 110)['failures'])
        with self.assertRaises(ValueError):
            assess(bytes(100), 2, 110)
