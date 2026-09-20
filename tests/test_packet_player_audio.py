import unittest
import numpy as np
from tools.audit_packet_player_audio import envelope, unexpected_silence


class PacketAudioTests(unittest.TestCase):
    def test_native_rate_rms_including_nonintegral_bins(self):
        for rate in (32040,48000):
            pcm=np.full((rate,2),123,dtype=np.int16)
            np.testing.assert_array_equal(envelope(rate,pcm),np.full(100,123))

    def test_injected_drop_and_signed_fixed_offsets(self):
        reference=np.ones(500)
        for offset in (-50,0,50):
            observed=np.ones(600)
            observed[200+offset:210+offset]=0
            self.assertEqual(unexpected_silence(reference,observed,offset,100,400),
                [dict(reference_seconds=2,duration_ms=100)])

    def test_rest_low_energy_and_short_gap_not_certified_as_pop_detection(self):
        reference=np.ones(500);observed=np.ones(500)
        reference[100:120]=0;observed[100:120]=0
        reference[200:220]=.01;observed[200:220]=0
        observed[300:302]=0
        self.assertEqual(unexpected_silence(reference,observed,0,0,500),[])

    def test_missing_audio_bounds_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):envelope(48000,np.full((10,2),np.nan))
        with self.assertRaises(ValueError):envelope(48000,np.zeros(10))
        for observed,offset in ((np.zeros(100),0),(np.ones(100),1)):
            with self.assertRaises(ValueError):unexpected_silence(np.ones(100),observed,offset,0,100)
