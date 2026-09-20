import unittest
from tools.build_inline_pitch_trial import patch,replacement
from tools.build_pitch_pair_trial import sequence


class InlinePitchTests(unittest.TestCase):
    def fixture(self):
        engine=bytearray(12500);labels={}
        for voice,at in ((0,12000),(1,12200)):
            engine[at:at+21]=sequence(voice)+bytes((0xe4,0x40+4*voice,0x28,16))
            labels[f'publish{voice}_audible']=at+0x400
            labels[f'publish{voice}_envelope']=at+0x400+50
        # Occupied receiver helper must not be touched.
        engine[0x2ba0:0x2baa]=bytes(range(10))
        return bytes(engine),dict(driver=labels)

    def test_size_and_only_two_verified_sequences(self):
        engine,layout=self.fixture();result,meta=patch(engine,layout)
        self.assertEqual(len(result),len(engine))
        allowed=set()
        for change in meta['changes']:
            at=change['offset'];allowed.update(range(at,at+17))
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(engine,result))))
        self.assertEqual(result[0x2ba0:0x2baa],engine[0x2ba0:0x2baa])
        for voice,at in ((0,12000),(1,12200)):
            self.assertEqual(result[at:at+17],replacement(voice))
        with self.assertRaises(ValueError):patch(result,layout)

    def test_changed_caller_or_sequence_rejected(self):
        engine,layout=self.fixture()
        for at in (12000,12017,12200,12218):
            bad=bytearray(engine);bad[at]^=1
            with self.assertRaises(ValueError):patch(bytes(bad),layout)
        with self.assertRaises(ValueError):replacement(2)
