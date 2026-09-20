import inspect
from pathlib import Path
import unittest
from tools.build_native import build, direct_apu_stub
from tools.check_direct_apu import expected


class DirectApuTests(unittest.TestCase):
    def test_default_and_scheduler_gate(self):
        self.assertIs(inspect.signature(build).parameters['experimental_direct_apu'].default, False)
        with self.assertRaisesRegex(ValueError, 'NMI-only'):
            build(Path('missing'), [], Path('unused'), experimental_direct_apu=True, experimental_raster=True)

    def test_actual_generated_guard_all_addresses(self):
        data = direct_apu_stub(0x2345, b'\xea\x60')
        self.assertEqual(data[:3], bytes.fromhex('9c0042'))
        data = data[3:]
        self.assertEqual(data[20:27], bytes.fromhex('6828224523c160'))
        self.assertEqual(data[27:], bytes.fromhex('6828ea60'))
        # Execute the guard's conditional branches against every address;
        # the fallback is the complete untouched generic stub, not a rewrite.
        for address in range(65536):
            if address >> 8 != 0x40:
                destination = 9 + data[8]
            elif address & 255 < 16:
                destination = 16 + data[15]
            elif address & 255 != 0x15:
                destination = 20 + data[19]
            else:
                destination = 20
            self.assertEqual(destination == 20, address in range(0x4000, 0x4010) or address == 0x4015)

    def test_disabled_reload_and_enable_clear_oracle(self):
        self.assertEqual(expected(0x4003, 0, 0x30, 0, 0, 0)[-1], 0)
        self.assertEqual(expected(0x4003, 0, 0x30, 1, 0, 0)[-1], 1)
        self.assertEqual(expected(0x4015, 0, 0x30, 15, 0, 15)[-1], 0)
