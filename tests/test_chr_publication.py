import unittest
from tools.chr_publication_audit import inspect,episodes,pending_runs


def sample(frame,flag,match):
    jobs=[dict(slot=i,descriptor='00'*8,flag=0,source_equal=True) for i in range(24)]
    jobs[18]=dict(slot=18,descriptor='0020cd0000540008',flag=flag,source_equal=match)
    return dict(frame=frame,visible=True,jobs=jobs)


class ChrPublicationTests(unittest.TestCase):
    def test_retired_flag_without_matching_vram_fails(self):
        self.assertTrue(episodes([sample(1,1,False),sample(2,0,True),sample(3,1,False),sample(4,0,True)])['visible_cohort'][1]['passed'])
        self.assertFalse(episodes([sample(1,0,False),sample(2,1,False),sample(3,0,False)])['passed'])

    def test_missing_late_censored_and_left_censored_are_not_passes(self):
        for frames in ([sample(1,1,False),sample(2,0,True)],
                       [sample(1,0,False),sample(2,1,False),sample(3,1,False)],
                       [sample(1,0,False)]+[sample(i,1,False) for i in range(2,8)]+[sample(8,0,True)]):
            self.assertFalse(episodes(frames)['passed'])
        with self.assertRaises(ValueError):episodes([sample(1,0,False),sample(3,1,False)])

    def test_real_bytes_not_only_flags_or_hash_labels(self):
        raw=bytearray(196608);rom=bytearray(0x100000)
        raw[0x1590:0x1598]=bytes.fromhex('0020cd0000540008');rom[0xd2000]=123
        before=inspect(raw,rom)[18];self.assertEqual(before['mismatched_bytes'],1)
        self.assertFalse(before['source_equal']);raw[131072+0xa800]=123
        self.assertTrue(inspect(raw,rom)[18]['source_equal'])

    def test_pending_span_cannot_disappear_into_hidden_exclusion(self):
        rows=[dict(frame=i,native=dict(task=192,transition_state=0,ppu_mask=24,chr_jobs_pending=2)) for i in range(1,8)]
        rows[-1]['native']['transition_state']=1
        result=pending_runs(rows);self.assertFalse(result['passed']);self.assertEqual(result['max_pending_frames'],6)


if __name__=='__main__':unittest.main()
