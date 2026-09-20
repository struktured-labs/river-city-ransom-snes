import unittest

import numpy as np

from tools.audit_hardware_menu_envelope import compare, envelope, integral, sensitivity


class HardwareMenuEnvelopeTests(unittest.TestCase):
    def signals(self):
        rate=4000
        t=np.arange(18*rate)/rate
        signal=(2000+900*np.sin(2*np.pi*3.7*t)+500*np.sin(2*np.pi*1.3*t))*np.sin(2*np.pi*223*t)
        reference=np.column_stack((signal, signal)).astype(np.int16)
        recorded=np.zeros((len(reference)+rate,2), dtype=np.int16)
        at=round(.031*rate)
        recorded[at:at+len(reference)]=(reference*np.array([.4,.6])).astype(np.int16)
        return reference,recorded,rate

    def test_single_calibration_then_independent_holdout(self):
        a,b,r=self.signals()
        result=compare(a,b,r,r,1,16,.025)
        self.assertTrue(result['holdout']['passed'])
        self.assertAlmostEqual(result['calibration']['lag'], .031)
        np.testing.assert_allclose(result['calibration']['gains'], [.4,.6], atol=.001)
        self.assertEqual(result['holdout']['bins'],1200)

    def test_pcm_mutants_are_rejected_without_refit(self):
        a,b,r=self.signals()
        result=compare(a,b,r,r,1,16,.025)
        controls=sensitivity(a,b,r,r,1,16,result)
        self.assertEqual(len(controls),4)
        self.assertTrue(all(x['rejected'] for x in controls.values()))

    def test_holdout_corruption_cannot_change_calibration(self):
        a,b,r=self.signals()
        clean=compare(a,b,r,r,1,16,.025)
        b[6*r:8*r]=0
        broken=compare(a,b,r,r,1,16,.025)
        self.assertEqual(clean['calibration'],broken['calibration'])
        self.assertFalse(broken['holdout']['passed'])

    def test_truncation_short_coverage_and_out_of_range_lag_fail(self):
        a,b,r=self.signals()
        for args in ((a,b[:8*r],r,r,1,16,.025),(a,b,r,r,1,8,.025),
                     (a,b,r,r,1,16,5)):
            with self.assertRaises(ValueError):compare(*args)

    def test_nonfinite_flat_and_dead_channel_fail(self):
        a,b,r=self.signals()
        for broken in (np.zeros_like(b), np.full_like(b,1000), b*np.array([1,0])):
            with self.assertRaises(ValueError):compare(a,broken,r,r,1,16,.025)
        with self.assertRaises(ValueError):integral(np.full((5,2),float('nan')))

    def test_fractional_rate_grid_has_no_cumulative_rounding_drift(self):
        x=np.full((32040*2,2),1000,dtype=np.int16)
        result=envelope(integral(x),32040,0,2)
        self.assertEqual(result.shape,(200,2))
        np.testing.assert_array_equal(result,1000)


if __name__ == '__main__':unittest.main()
