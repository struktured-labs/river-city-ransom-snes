import unittest
from tools.camera_audit import require_same_camera


class CameraAuditTests(unittest.TestCase):
    def test_both_camera_and_ninth_scroll_bit_must_match(self):
        reference = bytearray(2048)
        reference[0xDC:0xDE] = bytes((255, 1))
        reference[0xF6] = 255
        reference[0x3D] = 1
        self.assertEqual(require_same_camera(reference, reference), (511, 511))
        for address in (0xDC, 0xDD, 0xF6, 0x3D):
            altered = reference.copy()
            altered[address] ^= 1
            with self.assertRaises(ValueError):
                require_same_camera(reference, altered)

    def test_missing_ram_rejected(self):
        with self.assertRaises(ValueError):
            require_same_camera(bytes(2048), bytes(2047))
