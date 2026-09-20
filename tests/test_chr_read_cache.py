import inspect
import unittest

from tools.build_native import build
from tools.check_chr_read_cache import patch_runtime


class ChrReadCacheTests(unittest.TestCase):
    def test_experimental_default_off(self):
        self.assertIs(inspect.signature(build).parameters['experimental_chr_read_cache'].default, False)

    def test_pair_experimental_default_off(self):
        self.assertIs(inspect.signature(build).parameters['experimental_chr_read_pair'].default, False)

    def test_mutation_patches_all_runtime_banks_and_checksum(self):
        image = bytes(2*1024*1024)
        result = patch_runtime(image, 0x2345, b'\0\0', b'\xea\xea')
        for bank in range(1, 9):
            self.assertEqual(result[bank*65536+0x2345:bank*65536+0x2347], b'\xea\xea')
        self.assertEqual(int.from_bytes(result[0xffde:0xffe0], 'little'), sum(result) & 65535)
        self.assertEqual(image[0x12345:0x12347], b'\0\0')

    def test_mutation_refuses_wrong_preimage_or_width(self):
        image = bytes(2*1024*1024)
        with self.assertRaisesRegex(ValueError, 'preimage'):
            patch_runtime(image, 0x2345, b'\xff', b'\xea')
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            patch_runtime(image, 0x2345, b'\0', b'\xea\xea')
