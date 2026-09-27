import unittest
import zlib

from tools.release_patch import apply_bps


def enc(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def make_patch(src, dst):
    """SourceRead of the shared prefix, then TargetRead of the rest (synthetic, no ROM)."""
    body = bytearray(b'BPS1' + enc(len(src)) + enc(len(dst)) + enc(0))
    k = 0
    while k < min(len(src), len(dst)) and src[k] == dst[k]:
        k += 1
    if k:
        body += enc(((k - 1) << 2) | 0)
    if len(dst) > k:
        body += enc(((len(dst) - k - 1) << 2) | 1) + dst[k:]
    body += zlib.crc32(src).to_bytes(4, 'little') + zlib.crc32(dst).to_bytes(4, 'little')
    return bytes(body) + zlib.crc32(body).to_bytes(4, 'little')


class ReleasePatch(unittest.TestCase):
    src = bytes(range(256)) * 4
    dst = bytes(range(256)) * 2 + b'SNES' * 300

    def test_round_trip(self):
        self.assertEqual(apply_bps(make_patch(self.src, self.dst), self.src), self.dst)

    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source CRC32'):
            apply_bps(make_patch(self.src, self.dst), b'\x01' + self.src[1:])

    def test_corrupt_patch_rejected(self):
        p = bytearray(make_patch(self.src, self.dst))
        p[20] ^= 1
        with self.assertRaisesRegex(ValueError, 'patch CRC'):
            apply_bps(bytes(p), self.src)


if __name__ == '__main__':
    unittest.main()
