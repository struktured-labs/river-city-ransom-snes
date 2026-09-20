import tempfile
from pathlib import Path
import unittest

from tools.build_palette_compare_unrolled import (
    ADDRESS, CHANGED, HELPER, HOOK, ORIGINAL, SPRITES, assemble, patch)
from tools.review_palette_compare import palette_sections


class PaletteCompareUnrolledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            cls.helper = assemble(Path(directory))

    def image(self):
        image = bytearray(b'\xff'*0x200000)
        image[ADDRESS:ADDRESS+len(ORIGINAL)] = ORIGINAL
        return image

    def test_exact_patch_scope(self):
        original = self.image()
        result = patch(original, self.helper)
        allowed = set(range(ADDRESS, ADDRESS+3)) | set(range(HELPER, HELPER+512)) | set(range(0xFFDC, 0xFFE0))
        self.assertEqual(result[ADDRESS:ADDRESS+len(ORIGINAL)], HOOK+ORIGINAL[3:])
        self.assertEqual(result[HELPER:HELPER+512], self.helper)
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(original, result)) if a != b))
        with self.assertRaises(ValueError):
            patch(result, self.helper)

    def test_wrong_original_and_occupied_padding(self):
        for at in (ADDRESS+12, HELPER+511):
            original = self.image()
            original[at] ^= 1
            with self.assertRaises(ValueError):
                patch(original, self.helper)

    def test_bad_shapes(self):
        for original, helper in ((self.image()[:-1], self.helper),
                (self.image(), self.helper[:-1]), (self.image(), b'\0'*512)):
            with self.assertRaises(ValueError):
                patch(original, helper)

    def test_every_assembled_word_and_mismatch_flag_restore(self):
        for word in range(16):
            expected = (b'\xaf'+(0x7F3F00+word*2).to_bytes(3, 'little')+
                b'\xcf'+(0x7E5580+word*2).to_bytes(3, 'little')+
                b'\xf0\x08\x08\xa2'+(word*2).to_bytes(2, 'little')+
                b'\x28\x4c'+CHANGED.to_bytes(2, 'little'))
            self.assertEqual(len(expected), 18)
            self.assertEqual(self.helper[word*18:(word+1)*18], expected)

    def test_match_restores_index_flags_and_width(self):
        expected = bytes.fromhex('a22000e02000e2204c')+SPRITES.to_bytes(2, 'little')
        self.assertEqual(self.helper[288:288+len(expected)], expected)
        self.assertEqual(self.helper[288+len(expected):], b'\xff'*(512-288-len(expected)))

    def test_timing_requires_matched_stack_and_complete_phase(self):
        rows = [dict(pc=1, s=100, clock=10, opcode=0xAD),
                dict(pc=2, s=100, clock=50, opcode=0xAD)]
        self.assertEqual(palette_sections(rows, 1, 2)[0]['clocks'], 40)
        rows[1]['s'] = 98
        with self.assertRaises(ValueError):
            palette_sections(rows, 1, 2)

    def test_timing_rejects_interrupt_and_absent_phase(self):
        rows = [dict(pc=1, s=100, clock=10, opcode=0xAD),
                dict(pc=3, s=97, clock=30, opcode=0x40),
                dict(pc=2, s=100, clock=50, opcode=0xAD)]
        with self.assertRaises(ValueError):
            palette_sections(rows, 1, 2)
        with self.assertRaises(ValueError):
            palette_sections(rows[1:], 1, 2)
