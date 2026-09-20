import unittest

from tools.build_retained_entry import patch,HELPER,SIZE
from tools.check_retained_entry import expected,matrix,independent
from tools.check_retained_wait import independent as wait_check


class RetainedEntryTests(unittest.TestCase):
    def test_patch_only_native_prefix_mirrored_helper_and_checksum(self):
        image=bytearray(b'\xff'*0x200000);image[0x80fb:0x8102]=bytes.fromhex('9c004248ad1042')
        new=patch(image,b'\xea'*SIZE,HELPER,0x80fb)
        allowed=set(range(0x80fb,0x8102))|set(range(0xffdc,0xffe0))
        for bank in range(1,9):allowed.update(range(bank*65536+HELPER,bank*65536+HELPER+SIZE))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a!=b))
        with self.assertRaises(ValueError):patch(new,b'\xea'*SIZE,HELPER,0x80fb)

    def test_retained_and_current_bodies_have_distinct_ids_but_two_packets(self):
        c=matrix()[0];r=expected(c)
        self.assertEqual(r['bodies'],[1,2]);self.assertEqual(r['audio'],[1,2])
        r=expected(dict(c,OLD_ID=65535));self.assertEqual(r['bodies'],[65535,0])
        r=expected(dict(c,MISMATCH=-1));self.assertFalse(r['admitted'])
        self.assertEqual(r['bodies'],[2])

    def test_independent_oracle_rejects_missing_or_duplicate_audio_and_body(self):
        c=matrix()[0];r=bytearray(131072)
        abi=bytes((0x57,0x3c,0x35,0xa6,0x59,0x34,0x12,0x83,c['STACK']))
        r[0x6000:0x6009]=abi;r[0x6020:0x6029]=abi
        r[0x1b90:0x1b92]=bytes((2,2));r[0x6080:0x6084]=r[0x6100:0x6104]=bytes((1,0,2,0))
        r[0x1b88]=r[0x1b8a]=1;r[0x1c04]=2;r[0x6040:0x6045]=bytes((1,2,0,1,2))
        r[0x1ce4]=2;r[0x1ce6]=1
        independent(r,c)
        for at in (0x1b90,0x1b91,0x6080,0x6102,0x1b87,0x1c04,0x1ce4,0x6008):
            bad=bytearray(r);bad[at]^=1
            with self.assertRaises(ValueError):independent(bad,c)

    def test_active_wait_cannot_burn_the_remaining_display_frame(self):
        r=bytearray(131072);r[0x6000:0x6006]=bytes((0xa6,0x59,0x34,0x12,0x83,255))
        c=dict(LINE=40,STACK=255)
        r[0x6006]=41;wait_check(r,c)
        r[0x6006]=250
        with self.assertRaises(ValueError):wait_check(r,c)
        wait_check(r,dict(c,LINE=240))


if __name__=='__main__':unittest.main()
