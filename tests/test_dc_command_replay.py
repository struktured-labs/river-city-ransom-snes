import unittest
import numpy as np
from tools.build_dc_packet_replay import replace
from tools.build_dc_pulse_trial import patch
from tools.review_dc_command_replay import compare_window
from tests import test_dc_pulse_trial as pulse_fixtures


class DcCommandReplayTests(unittest.TestCase):
    def test_exact_patch_and_unrelated_change_refusal(self):
        old=pulse_fixtures.DcPulseTests().engine();new,_=patch(old)
        image=bytearray(0x200000);image[0x120000:0x120000+len(old)]=old
        changed,_=replace(image,old,new)
        self.assertEqual(changed[0x120000:0x120000+len(old)],new)
        bad=bytearray(new);bad[0]^=1
        with self.assertRaises(ValueError):replace(image,old,bad)

    def test_fixed_window_retains_regression_and_both_peak_locations(self):
        a=np.zeros((100,2),dtype=np.int16);a[30:]=1000
        b=a.copy();b[60:]=3000
        r=compare_window(a,b,10,90)
        self.assertEqual((r['parent_max_step'],r['trial_max_step']),(1000,2000))
        self.assertTrue(r['grows_over_one_percent'])
        self.assertEqual(r['parent_peak']['sample'],30)
        self.assertEqual(r['trial_peak']['sample'],60)
        self.assertFalse(compare_window(a,a,10,90)['grows_over_one_percent'])
        with self.assertRaises(ValueError):compare_window(a,b,0,90)
