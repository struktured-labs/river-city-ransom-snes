import unittest

from tools.build_pitch_pair_trial import patch, sequence


class PitchPairTrialTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(12415)
        labels={}
        for voice,at in ((0,12000),(1,12200)):
            image[at:at+17]=sequence(voice)
            labels[f'publish{voice}_audible']=at+0x400
            labels[f'publish{voice}_envelope']=at+0x400+50
        return bytes(image),dict(driver=labels)

    def test_only_checked_regions_changed_and_targets_resume_after_sequence(self):
        engine,layout=self.fixture()
        result,meta=patch(engine,layout)
        self.assertEqual(len(result),len(engine))
        allowed={i for c in meta['changes'] for i in range(c['offset'],c['offset']+len(bytes.fromhex(c['before'])))}
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(engine,result))))
        for voice,at in ((0,12000),(1,12200)):
            helper=0x2ba0+voice*0x20
            self.assertEqual(int.from_bytes(result[at+1:at+3],'little'),helper+0x400)
            self.assertEqual(result[helper+22],0x5f)
            self.assertEqual(int.from_bytes(result[helper+23:helper+25],'little'),at+17+0x400)
        with self.assertRaises(ValueError):patch(result,layout)

    def test_occupied_helper_padding_and_missing_preimage_rejected(self):
        engine,layout=self.fixture()
        for at in (0x2ba0,0x2bc0,12000,12200):
            bad=bytearray(engine);bad[at]^=1
            with self.assertRaises(ValueError):patch(bytes(bad),layout)


if __name__=='__main__':unittest.main()
