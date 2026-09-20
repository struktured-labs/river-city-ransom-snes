from pathlib import Path
import tempfile
import unittest

from tools.build_compact_pair_reprobe import HELPER, SIZE, assemble, patch
from tools.build_hidden_index_trial import assemble as scalar_assemble
from tools.check_compact_pair_reprobe import inject, mutate
from tools.review_compact_pair_reprobe import with_initial


class CompactPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cls.helper = assemble(root)
            cls.scalar, _ = scalar_assemble(root/'scalar', 0xA77D, 779, True)

    def image(self):
        image = bytearray(b'\xff'*0x200000)
        image[0xA77D:0xA77D+len(self.scalar)] = self.scalar
        return image

    def test_exact_scope_and_neighbor_preservation(self):
        image = self.image()
        image[0xAA88:0xAA95] = bytes(range(13))
        result = patch(image, self.helper, self.scalar, 0xA77D)
        allowed = set(range(0xA77D, 0xA780)) | set(range(HELPER, HELPER+SIZE)) | set(range(0xFFDC, 0xFFE0))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b))
        self.assertEqual(result[0xAA88:0xAA95], bytes(range(13)))
        self.assertEqual(result[HELPER:HELPER+SIZE], self.helper)
        with self.assertRaises(ValueError):
            patch(result, self.helper, self.scalar, 0xA77D)

    def test_changed_preimage_and_occupied_tail_fail(self):
        for at in (0xA77D+400, HELPER, HELPER+SIZE-1):
            image = self.image()
            image[at] ^= 1
            with self.assertRaises(ValueError):
                patch(image, self.helper, self.scalar, 0xA77D)

    def test_fixture_uses_exact_helper_and_trampoline(self):
        result = inject(self.image(), 0xA77D, self.helper)
        self.assertEqual(result[0xA77D:0xA780], bytes.fromhex('4c00d5'))
        self.assertEqual(result[HELPER:HELPER+SIZE], self.helper)

    def test_fixture_refuses_overlap_wrong_entry_and_size(self):
        for kind in ('overlap', 'entry', 'size'):
            image = self.image()
            if kind == 'overlap':
                image[HELPER+SIZE-1] = 0
            elif kind == 'entry':
                image[0xA77D] ^= 1
            else:
                image.pop()
            with self.assertRaises(ValueError):
                inject(image, 0xA77D, self.helper)

    def test_mutants_require_unique_equal_length_patterns(self):
        self.assertEqual(mutate(bytes.fromhex('010203'), '02', '04'), bytes.fromhex('010403'))
        for old, new in (('ff', '00'), ('01', '0000'), ('01', '04')):
            with self.assertRaises(ValueError):
                mutate(bytes.fromhex('01020301'), old, new)

    def test_initial_boundary_comes_from_complete_saved_ram(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = bytes(i & 255 for i in range(131072))
            (root/'initial.ram').write_bytes(raw)
            rows = [dict(frame=11)]
            result = with_initial(root, dict(restored_frame=10), rows)
            self.assertEqual(result[0]['game_ram_hex'], raw[:2048].hex())
            self.assertEqual(result[0]['native_ram_hex'], raw[0x1C00:0x2000].hex())
            self.assertEqual(result[1:], rows)
            with self.assertRaises(ValueError):
                with_initial(root, dict(restored_frame=9), rows)
