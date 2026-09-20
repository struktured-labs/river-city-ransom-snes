import unittest
from pathlib import Path
from tools.build_staged_receiver_fixture import stage,BUFFER


class Fixture(unittest.TestCase):
    def setUp(self):
        data=Path('build/early-oam-live-half-game-3955/native-cpu.sfc').read_bytes()
        self.engine=data[0x120000:0x123140]

    def test_only_dispatch_and_append(self):
        result,labels=stage(self.engine)
        self.assertEqual(result[:0x87],self.engine[:0x87])
        self.assertEqual(result[0x8a:len(self.engine)],self.engine[0x8a:])
        self.assertEqual(result[0x87:0x8a],bytes.fromhex('5f4035'))
        self.assertTrue(all(0x3540<=pc<BUFFER for pc in labels.values()))
        self.assertEqual(result[BUFFER-0x400:],bytes(24))

    def test_wrong_parent_and_repeat_rejected(self):
        for at in (0,0x87,0x2eda,len(self.engine)-1):
            bad=bytearray(self.engine);bad[at]^=1
            with self.assertRaises(ValueError):stage(bytes(bad))
        with self.assertRaises(ValueError):stage(stage(self.engine)[0])
