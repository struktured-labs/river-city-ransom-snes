import unittest
from tools.build_balanced_pitch_trial import patch,pointer
from tools.build_pitch_pair_trial import sequence


class BalancedPitchTests(unittest.TestCase):
    def fixture(self):
        data=bytearray(12500);labels={}
        for voice,at in ((0,12000),(1,12200)):
            code=pointer(voice)+sequence(voice)+bytes((0xe4,0x40+4*voice,0x28,16))
            data[at:at+len(code)]=code;labels[f'publish{voice}_audible']=at+0x400
        return bytes(data),dict(driver=labels)

    def test_preserves_size_and_untouched_bytes(self):
        data,layout=self.fixture();result,meta=patch(data,layout)
        self.assertEqual(len(result),len(data));allowed=set()
        for c in meta['changes']:
            allowed.update(range(c['offset'],c['offset']+len(bytes.fromhex(c['before']))))
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(data,result))))
        with self.assertRaises(ValueError):patch(result,layout)

    def test_requires_pointer_and_following_reload(self):
        data,layout=self.fixture()
        for at in (12000,12040,12200,12240):
            bad=bytearray(data);bad[at]^=1
            with self.assertRaises(ValueError):patch(bytes(bad),layout)
