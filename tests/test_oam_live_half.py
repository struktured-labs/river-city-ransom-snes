import inspect
from pathlib import Path
import unittest

from tools.build_native import build
from tools.check_oam_live_half import checksum


class OamLiveHalfTests(unittest.TestCase):
    def test_default_off_and_requires_delta_producer(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_oam_live_half'].default)
        with self.assertRaisesRegex(ValueError, 'delta producer'):
            build(Path('unused.nes'), [], Path('unused'), experimental_oam_live_half=True)

    def test_mutant_checksums_are_consistent(self):
        image = bytearray(2*1024*1024)
        image[0x8000] = 0x42
        checksum(image)
        expected = sum(image) & 65535
        actual = int.from_bytes(image[0xffde:0xffe0], 'little')
        complement = int.from_bytes(image[0xffdc:0xffde], 'little')
        self.assertEqual(actual, expected)
        self.assertEqual(complement ^ actual, 65535)
