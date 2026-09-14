import random
import unittest

from tools.rom import Rom, convert_chr
from tools.checksum import finalize, verify


def synthetic_rom():
    h = bytearray(b"NES\x1a" + bytes(12))
    h[4:7] = bytes((8, 16, 0x40))
    return h + bytes(262144)


class RomTests(unittest.TestCase):
    def test_header_and_vectors(self):
        data = synthetic_rom()
        data[16 + 131072 - 6:16 + 131072] = bytes.fromhex("00 e1 80 e0 20 e2")
        rom = Rom.parse(data)
        self.assertEqual(rom.mapper, 4)
        self.assertEqual(rom.report()["vectors"], {"nmi": "e100", "reset": "e080", "irq": "e220"})

    def test_malformed(self):
        good = synthetic_rom()
        for data in (b"", b"NES\x1a", good[:-1], good + b"\0"):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                Rom.parse(data)
        for index, value in ((6, 0x44), (7, 8), (7, 1), (12, 1)):
            data = good.copy()
            data[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                Rom.parse(data)

    def test_wrong_game_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "checksums"):
            Rom.parse(synthetic_rom()).require_rcr_us()

    def test_every_pixel_preserved(self):
        data = random.Random(418).randbytes(16 * 256)
        for bpp in (2, 4):
            output = convert_chr(data, bpp)
            self.assertEqual(len(output), len(data) * bpp // 2)
            for tile in range(256):
                for y in range(8):
                    for x in range(8):
                        bit = 7 - x
                        nes = ((data[tile * 16 + y] >> bit) & 1) | (((data[tile * 16 + y + 8] >> bit) & 1) << 1)
                        offset = tile * bpp * 8 + y * 2
                        snes = ((output[offset] >> bit) & 1) | (((output[offset + 1] >> bit) & 1) << 1)
                        self.assertEqual(nes, snes)
                if bpp == 4:
                    self.assertEqual(output[tile * 32 + 16:tile * 32 + 32], bytes(16))

    def test_bad_tile_input(self):
        for data, bpp in ((b"a", 2), (bytes(16), 8)):
            with self.assertRaises(ValueError):
                convert_chr(data, bpp)

    def test_checksum(self):
        data = bytearray(32768)
        data[0] = 0x78
        data[0x7fd5:0x7fd8] = bytes((0x20, 0, 5))
        data[0x7ffc:0x7ffe] = bytes((0, 0x80))
        result = finalize(data)
        verify(result)
        self.assertEqual(finalize(result), result)
        result[1] ^= 1
        with self.assertRaises(ValueError):
            verify(result)


if __name__ == "__main__":
    unittest.main()
