import unittest
from pathlib import Path
from tools.build_audio_regular_irq import patch


class RegularIRQ(unittest.TestCase):
    def setUp(self):
        self.image = Path('build/early-oam-live-half-game-3955/native-cpu.sfc').read_bytes()

    def test_exact_footprint(self):
        result = patch(self.image)
        allowed = set(range(0xffdc, 0xffe0))
        for bank in range(1, 9):
            at = bank * 65536 + 0x7be0
            allowed.update(range(at+3, at+6))
            self.assertEqual(result[at:at+6], bytes.fromhex('9c00424c5f32'))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.image, result))))
        self.assertEqual(len(result), len(self.image))
        self.assertEqual(result[0x120000:0x123140], self.image[0x120000:0x123140])

    def test_every_guard_and_repeat_rejected(self):
        for bank in range(1, 9):
            for offset in range(20):
                bad = bytearray(self.image)
                bad[bank * 65536 + 0x7be0 + offset] ^= 1
                with self.assertRaises(ValueError):
                    patch(bad)
        with self.assertRaises(ValueError):
            patch(patch(self.image))


if __name__ == '__main__':
    unittest.main()
