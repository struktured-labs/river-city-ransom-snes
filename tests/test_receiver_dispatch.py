import unittest
from tools.build_receiver_dispatch_trial import patch


def fixture():
    data=bytearray(0x400)
    data[0x100:0x107]=bytes.fromhex('3ef4f0035f2005')
    data[0x120:0x126]=bytes.fromhex('5fa006000000')
    data[0x2a0:0x2aa]=bytes.fromhex('e4fdf0033f80055f0005')
    return bytes(data),dict(driver=dict(receiver=0x500,receiver_wait=0x520)),dict(helper_spc=0x6a0,pending_entry_spc=0x580)


class DispatchTests(unittest.TestCase):
    def test_only_jump_target_changes(self):
        data,layout,poll=fixture();new,metadata=patch(data,layout,poll)
        self.assertEqual(new[0x100:0x107],bytes.fromhex('3ef4f0035fa006'))
        self.assertEqual([i for i,(a,b) in enumerate(zip(data,new)) if a!=b],[0x105,0x106])
        self.assertEqual(metadata['expected_clocks_saved_per_miss'],3)

    def test_reject_modified_compare_wait_or_helper(self):
        data,layout,poll=fixture()
        for offset in (0x100,0x102,0x105,0x120,0x123,0x2a0,0x2a4,0x2a8):
            with self.subTest(offset=offset):
                bad=bytearray(data);bad[offset]^=1
                with self.assertRaises(ValueError):patch(bad,layout,poll)
