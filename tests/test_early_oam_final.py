import unittest
from pathlib import Path
from tools.early_oam_final_slack import patch
from tools.early_oam_palette import patch as prior
from tools.review_early_oam_final import blocks, sprite_cohort


class EarlyFinalTests(unittest.TestCase):
    def test_only_final_deadline_and_checksum_change_from_prior(self):
        source=Path('build/guarded-volume-game-3408/native-cpu.sfc').read_bytes()
        a,_=prior(source);b,_=patch(source)
        changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        self.assertEqual(b[0x86df],254)
        self.assertTrue(all(i==0x86df or 0xffdc<=i<0xffe0 for i in changed))

    def test_target_missing_or_late_render_fails(self):
        g=dict(left_censored=False,source_frame=2020,first_render={'frame':2021},source_to_first_render_frames=1)
        data=dict(first=1978,last=2024,structural_passed=True,generations=[g])
        self.assertTrue(sprite_cohort(data)['passed'])
        g['first_render']=None
        self.assertFalse(sprite_cohort(data)['passed'])
        g['first_render']={'frame':2022};g['source_to_first_render_frames']=2
        self.assertFalse(sprite_cohort(data)['passed'])

    def test_followthrough_cannot_be_omitted(self):
        with self.assertRaises(ValueError):
            sprite_cohort(dict(first=1978,last=2020,structural_passed=True,generations=[]))

    def test_snapshot_truncation_is_not_silent(self):
        raw=Path('build/row-checkpoints-3448/frame-08232.savestate').read_bytes()
        self.assertEqual(len(blocks(raw)['VRA']),65536)
        with self.assertRaises(ValueError):blocks(raw[:100])


if __name__=='__main__':unittest.main()
