import unittest
from pathlib import Path
from tools.build_audio_dual_boundary import patch
from tools.build_audio_pre_retained import HELPER


class DualBoundary(unittest.TestCase):
    def setUp(self):
        self.image=Path('build/audio-pre-retained-game-4041/native-cpu.sfc').read_bytes()

    def test_baseline_plus_only_recovery(self):
        result=patch(self.image)
        original=Path('build/early-oam-live-half-game-3955/native-cpu.sfc').read_bytes()
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base=bank*65536
            allowed.update(range(base+0x3268,base+0x326b))
            allowed.update(range(base+0x7f40,base+0x7f40+len(HELPER)))
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,result))))
        self.assertEqual(len(original),len(result))

    def test_guards(self):
        for bank in range(1,9):
            for off in range(8):
                bad=bytearray(self.image);bad[bank*65536+0x7be0+off]^=1
                with self.assertRaises(ValueError):patch(bad)
        with self.assertRaises(ValueError):patch(patch(self.image))
