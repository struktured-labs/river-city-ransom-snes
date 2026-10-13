import hashlib, tempfile, unittest
from pathlib import Path
from tools.build_logo_sfx_timing import build, D1

PARENT = Path('build/trial-weapon-rumble-4305d/native-cpu.sfc')
EXPECT = '6cac90a03db387b6e55a49d9987e3572ab2fe0ec070fef7b96f6b7f1e5f78229'


@unittest.skipUnless(PARENT.exists(), 'needs local 4305d ROM (not committed)')
class LogoSfxTiming(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'e.sfc'
            build(PARENT, out)
            a, b = PARENT.read_bytes(), out.read_bytes()
            self.assertEqual(hashlib.sha256(b).hexdigest(), EXPECT)
            diff = [i for i in range(len(a)) if a[i] != b[i]]
            # only the splash code bank $D1 (code area) and the header checksum
            self.assertTrue(all(D1 <= i < D1 + 0x1000 or 0xFFDC <= i < 0xFFE0 for i in diff))
            # reveal step still +3 per two VBlanks; hold count still 240
            self.assertEqual(b[D1 + 0x800:D1 + 0x809].hex(), '482010086818690360')
            self.assertIn(bytes.fromhex('a0f000'), b[D1:D1 + 0x200])


if __name__ == '__main__':
    unittest.main()
