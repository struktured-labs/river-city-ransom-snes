import tempfile
from pathlib import Path
import unittest

from tools.build_oam_hide_tail import ADDRESS, HELPER, HOOK, ORIGINAL, assemble, patch


class OamHideTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            cls.helper = assemble(Path(directory))

    def image(self):
        image = bytearray(b'\xff'*0x200000)
        for bank in range(1, 9):
            at = bank*65536+ADDRESS
            image[at:at+len(ORIGINAL)] = ORIGINAL
        return image

    def test_patch_scope_and_original_fallback_remain(self):
        image = self.image()
        result = patch(image, self.helper)
        allowed = set(range(0xFFDC, 0xFFE0))
        for bank in range(1, 9):
            base = bank*65536
            self.assertEqual(result[base+ADDRESS:base+ADDRESS+len(ORIGINAL)], HOOK+ORIGINAL[3:])
            self.assertEqual(result[base+HELPER:base+HELPER+0x300], self.helper)
            allowed.update(range(base+ADDRESS, base+ADDRESS+3))
            allowed.update(range(base+HELPER, base+HELPER+0x300))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b))
        with self.assertRaises(ValueError):
            patch(result, self.helper)

    def test_missing_original_and_occupied_padding_rejected(self):
        for at in (8*65536+ADDRESS+21, 3*65536+HELPER+767):
            image = self.image()
            image[at] ^= 1
            with self.assertRaises(ValueError):
                patch(image, self.helper)

    def test_wrong_sizes_and_helper_rejected(self):
        for image, helper in ((self.image()[:-1], self.helper),
                              (self.image(), self.helper[:-1]),
                              (self.image(), b'\0'*768)):
            with self.assertRaises(ValueError):
                patch(image, helper)

    def test_dispatch_targets_preserve_exact_descending_store_sequence(self):
        # Independent decoding of actual assembled dispatch and fall-through.
        jmp = self.helper.index(b'\x7c')
        table = int.from_bytes(self.helper[jmp+1:jmp+3], 'little')-HELPER
        for count in range(4, 256, 4):
            pc = int.from_bytes(self.helper[table+count:table+count+2], 'little')-HELPER
            stores = []
            while self.helper[pc] == 0x8D:
                stores.append(int.from_bytes(self.helper[pc+1:pc+3], 'little'))
                pc += 3
            self.assertEqual(stores, list(range(0x200+count, 0x204, -4)))
            self.assertEqual(self.helper[pc:pc+7], bytes.fromhex('a204e0044cf7df'))

    def test_zero_and_unaligned_dispatch_keep_original_entries(self):
        self.assertEqual(self.helper[:20], bytes.fromhex(
            'ae2d05d0034cf7df8a2903f005a9f04ce9dfa9f0'))
