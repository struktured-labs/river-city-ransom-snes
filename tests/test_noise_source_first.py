import unittest
from unittest.mock import patch as mock_patch

from tools.build_noise_source_first import CONFIGURE, HOOK, RETURN, VOLUME, patch


class NoiseSourceFirst(unittest.TestCase):
    def fixture(self):
        engine = bytearray(0x4000)
        engine[0x323:0x323+len(HOOK)] = HOOK
        return bytes(engine)

    def test_paths_preserve_volume_and_mute_before_source(self):
        engine = self.fixture()
        with mock_patch('tools.build_noise_source_first.interpolation_patch',return_value=(engine,{})):
            changed, detail = patch(engine,b'original',8)
        helper = bytes.fromhex(detail['helper_hex'])
        audible = helper[4:4+helper[3]]
        muted = helper[4+helper[3]:]
        self.assertEqual(audible,b'\x2d'+CONFIGURE+b'\xae'+VOLUME+RETURN)
        self.assertEqual(muted,VOLUME+CONFIGURE+RETURN)
        self.assertEqual(changed[0x323:0x326],bytes.fromhex('5fe035'))
        self.assertEqual(len(changed),len(engine))
        self.assertTrue(all(a==b or 0x323<=i<0x326 or 0x31e0<=i<0x31e0+len(helper)
                            for i,(a,b) in enumerate(zip(engine,changed))))

    def test_wrong_engine_and_occupied_helper_rejected(self):
        engine = self.fixture()
        with mock_patch('tools.build_noise_source_first.interpolation_patch',return_value=(engine,{})):
            with self.assertRaises(ValueError):
                patch(engine+b'\0',b'original',8)
        occupied = bytearray(engine); occupied[0x31e0]=1
        with mock_patch('tools.build_noise_source_first.interpolation_patch',return_value=(bytes(occupied),{})):
            with self.assertRaises(ValueError):
                patch(bytes(occupied),b'original',8)


if __name__ == '__main__':
    unittest.main()
