import unittest

from tools.build_receiver_poll_trial import patch


class ReceiverPollTrialTests(unittest.TestCase):
    def fixture(self):
        engine=bytearray(12415)
        layout=dict(driver=dict(receiver_clock=0x327d,receiver_clock_done=0x32a1,receiver=0x32da,receiver_wait=0x3303))
        engine[0x2e7d:0x2e7d+11]=bytes.fromhex('e4fdd0035fa132c49f4d6d')
        engine[0x2f03:0x2f03+6]=bytes.fromhex('3f7d325fda32')
        return bytes(engine),layout

    def test_scope_and_branch_targets(self):
        original,layout=self.fixture();result,meta=patch(original,layout)
        allowed={i for c in meta['changes'] for i in range(c['offset'],c['offset']+len(bytes.fromhex(c['before'])))}
        self.assertEqual(len(original),len(result))
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,result))))
        start=meta['helper_spc']-0x400
        self.assertEqual(result[start+4+result[start+3]],0x5f)
        self.assertEqual(int.from_bytes(result[start+5:start+7],'little'),0x3284)
        with self.assertRaises(ValueError):patch(result,layout)

    def test_all_preimages_fail_closed(self):
        original,layout=self.fixture()
        for address in (0x2e7d,0x2e7f,0x2e81,0x2e84,0x2f03,0x2ba0):
            bad=bytearray(original);bad[address]^=1
            with self.assertRaises(ValueError):patch(bytes(bad),layout)


if __name__=='__main__':unittest.main()
