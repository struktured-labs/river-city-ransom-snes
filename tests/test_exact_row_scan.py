import unittest
from pathlib import Path
from tools.review_exact_row_scan import publication_gate
from tools.build_bounded_scan_limit import patch as limit_patch
from tools.half_row_scan import patch as half_patch


def event(delay=3, status='published'):
    return dict(row=25,col=10,previous=0,value=198,source_frame=100,vram_latency=delay,status=status)


class ExactRowScanTests(unittest.TestCase):
    def test_delayed_or_missing_generation_cannot_pass(self):
        self.assertTrue(publication_gate([event(7)],[event(3)])['nonregression'])
        self.assertFalse(publication_gate([event(3)],[event(7)])['nonregression'])
        self.assertFalse(publication_gate([event()],[])['nonregression'])
        self.assertFalse(publication_gate([event()],[event(None,'right_censored')])['nonregression'])

    def test_changed_source_frame_is_not_aligned_away(self):
        changed=event();changed['source_frame']+=1
        r=publication_gate([event()],[changed])
        self.assertFalse(r['same_sources']);self.assertEqual(len(r['missing']),2)

    def test_half_scan_changes_no_other_mechanism(self):
        image=Path('build/guarded-volume-game-3408/native-cpu.sfc').read_bytes()
        trial, changes=half_patch(image)
        self.assertEqual(trial[0x838d:0x8390],bytes.fromhex('a04000'))
        self.assertTrue(all(i==0x838e or 0xffdc<=i<0xffe0 for i in changes))

    def test_bound_limit_preserves_helper_and_rejects_changed_code(self):
        image=Path('build/bounded-row-scan-game-3453/native-cpu.sfc').read_bytes()
        trial=limit_patch(image,64)
        self.assertEqual(image[0x7300:0x7400],trial[0x7300:0x7400])
        mutant=bytearray(image);mutant[0x7300]^=1
        with self.assertRaises(ValueError):limit_patch(mutant,64)


if __name__=='__main__': unittest.main()
