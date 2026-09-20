import unittest

from tools.build_native import stub


class Fc60ImmediateStubControls(unittest.TestCase):
    def test_only_opt_in_tail_adds_transition_same_vblank_dispatch(self):
        ordinary = stub(0x8D, 0x2000, 0x2345, resume=0xFC73)
        immediate = stub(0x8D, 0x2000, 0x2345, resume=0xFC73, immediate_nmi=True,
                         software_nmi=0x80FB)
        wait = bytes.fromhex('ad124230fb')
        self.assertIn(wait, ordinary)
        self.assertIn(wait, immediate)
        self.assertIn(bytes.fromhex('5cfb80c0'), immediate)
        self.assertIn(bytes.fromhex('ada01cc901'), immediate)
        self.assertTrue(ordinary.endswith(bytes.fromhex('4c73fc')))
        self.assertTrue(immediate.endswith(bytes.fromhex('4c73fc')))


if __name__ == '__main__':
    unittest.main()
