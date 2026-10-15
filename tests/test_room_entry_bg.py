import hashlib, tempfile, unittest
from pathlib import Path
from tools.build_room_entry_bg import build, LOOP, HOOK, HELPER, HELPER_CODE

PARENT = Path('build/trial-logo-sfx-4305e/native-cpu.sfc')
EXPECT = '4407c7d597a5306b01bc8c99f42a3bd63cd8f6baa93016b2fb8d62a74efc3168'


@unittest.skipUnless(PARENT.exists(), 'needs local 4305e ROM (not committed)')
class RoomEntryBg(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'f.sfc'
            build(PARENT, out)
            a, b = PARENT.read_bytes(), out.read_bytes()
            self.assertEqual(hashlib.sha256(b).hexdigest(), EXPECT)
            allowed = set()
            for bank in range(1, 9):
                o = bank * 0x10000
                allowed |= set(range(o + LOOP + 2, o + LOOP + 3))       # bne -> bra
                allowed |= set(range(o + HOOK, o + HOOK + 3))           # sta -> jsr helper
                allowed |= set(range(o + HELPER, o + HELPER + len(HELPER_CODE)))
                self.assertEqual(b[o + LOOP:o + LOOP + 4].hex(), 'a5058007')
                self.assertEqual(b[o + HOOK:o + HOOK + 3].hex(), '20a07f')
            allowed |= set(range(0xFFDC, 0xFFE0))
            self.assertTrue(all(i in allowed for i in range(len(a)) if a[i] != b[i]))

    def test_wrong_parent_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            bad = Path(t) / 'bad.sfc'
            bad.write_bytes(b'\0' * 0x10000)
            with self.assertRaises(AssertionError):
                build(bad, Path(t) / 'o.sfc')


if __name__ == '__main__':
    unittest.main()
