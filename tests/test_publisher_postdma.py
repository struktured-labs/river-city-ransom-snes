import unittest

from tools.build_publisher_postdma_deadline import patch
from tools.check_publisher_postdma import verify


class PublisherPostdmaTests(unittest.TestCase):
    def test_patch_only_native_continuation_and_free_helper(self):
        image=bytearray(b'\xff'*0x200000)
        image[0x843b:0x8440]=bytes.fromhex('2014868000')
        result=patch(image,b'\xea'*256,0x843b,0x7300,0x8614)
        allowed=set(range(0x7300,0x7400))|set(range(0x843b,0x843e))|set(range(0xffdc,0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b))
        with self.assertRaises(ValueError):patch(result,b'\xea'*256,0x843b,0x7300,0x8614)
        with self.assertRaises(ValueError):patch(image,b'\xea'*255,0x843b,0x7300,0x8614)

    def test_independent_oracle_checks_wrap_width_and_ownership(self):
        ram=bytearray(131072);ram[0x6000:0x6008]=bytes.fromhex('00003412001eff1f')
        ram[0x1d00]=ram[0x1d7f]=3;ram[0x6010]=2
        case=dict(cursor=126,rows=2,line=249,transition=0)
        verify(ram,case)
        for at in (0x6000,0x6002,0x6004,0x6006,0x6009,0x1d00,0x1d7f,0x1b87,0x6010):
            bad=bytearray(ram);bad[at]^=1
            with self.assertRaises(ValueError):verify(bad,case)
        bad=bytearray(ram);bad[0x6008]=0x20
        with self.assertRaises(ValueError):verify(bad,case)
        ram[0x6010]=1
        verify(ram,dict(case,line=240))
        verify(ram,dict(case,transition=2))
        verify(ram,case,negative=True)


if __name__=='__main__':unittest.main()
