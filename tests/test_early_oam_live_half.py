import unittest
from pathlib import Path
from tools.build_early_oam_live_half import assemble,patch,START,OLD


class EarlyHalfPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=Path('build/receiver-local-poll-game-3934/native-cpu.sfc').read_bytes()
        cls.helper=assemble()

    def test_only_hook_helper_checksum_change(self):
        image=patch(self.original,self.helper)
        self.assertEqual(len(image),len(self.original))
        changed={i for i,(a,b) in enumerate(zip(self.original,image)) if a!=b}
        allowed=set(range(START,START+len(self.helper)))|set(range(0x7300,0x7303))|set(range(0xffdc,0xffe0))
        self.assertLessEqual(changed,allowed)
        self.assertEqual(image[0x7300:0x7303],bytes.fromhex('4c0051'))
        self.assertEqual(image[0x120000:0x123140],self.original[0x120000:0x123140])

    def test_every_hook_guard_and_padding_byte(self):
        for at in [*range(0x7300,0x7300+len(OLD)),*range(START,START+len(self.helper))]:
            bad=bytearray(self.original);bad[at]^=1
            with self.assertRaises(ValueError):patch(bad,self.helper)

    def test_repeat_application_rejected(self):
        with self.assertRaises(ValueError):patch(patch(self.original,self.helper),self.helper)
