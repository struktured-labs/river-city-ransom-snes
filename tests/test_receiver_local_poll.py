import unittest
from tools.build_receiver_local_poll import patch,ORIGIN,CODE


class LocalPollTests(unittest.TestCase):
    def setUp(self):
        self.engine=bytearray(0x3140)
        self.guards={0x2eda:bytes.fromhex('3ef4f0035fa02fe4f5d440'),
                     0x2ba0:bytes.fromhex('e4fdf0033f84325fda32'),
                     0x2e84:bytes.fromhex('c49f4d6d')}
        for at,code in self.guards.items():self.engine[at:at+len(code)]=code

    def test_patch_footprint_and_targets(self):
        changed=patch(self.engine)
        allowed=set(range(ORIGIN-0x400,ORIGIN-0x400+len(CODE)))|{0x2edf,0x2ee0}
        self.assertTrue({i for i,(a,b) in enumerate(zip(self.engine,changed)) if a!=b}<=allowed)
        self.assertEqual(len(changed),len(self.engine))
        self.assertEqual(changed[0x2ee1:0x2ee5],bytes.fromhex('e4f5d440'))
        self.assertEqual(CODE[7:11],bytes.fromhex('3ef4d0f5'))
        self.assertEqual(ORIGIN+11+(CODE[10]-256),ORIGIN)
        self.assertEqual(CODE[11:],bytes.fromhex('5fe132'))

    def test_guard_or_padding_mutation_rejected(self):
        for at,code in self.guards.items():
            for i in range(len(code)):
                bad=self.engine.copy();bad[at+i]^=1
                with self.assertRaises(ValueError):patch(bad)
        for i in range(len(CODE)):
            bad=self.engine.copy();bad[ORIGIN-0x400+i]=1
            with self.assertRaises(ValueError):patch(bad)
        with self.assertRaises(ValueError):patch(patch(self.engine))
