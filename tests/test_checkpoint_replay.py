import os
import unittest
from unittest.mock import Mock, patch

from tools.replay_route_checkpoint import reference_slice, replay


class CheckpointReplayTests(unittest.TestCase):
    def test_native_stereo_boundaries_are_not_aligned_or_trimmed(self):
        pcm=bytes(range(40))
        row=dict(audio_start_sample=3,audio=dict(samples=4))
        self.assertEqual(reference_slice(row,pcm),pcm[12:28])
        self.assertNotEqual(reference_slice(row,pcm),pcm[16:32])

    def test_missing_and_invalid_audio_ranges_fail_closed(self):
        for start,count in ((-1,1),(0,0),(9,2),(11,1)):
            with self.assertRaises(ValueError):
                reference_slice(dict(audio_start_sample=start,audio=dict(samples=count)),bytes(40))

    def test_historical_observer_override_refused_before_loading_core(self):
        with patch.dict(os.environ,{'RCR_INSTRUCTION_TRACE':'incompatible.csv'}):
            with self.assertRaisesRegex(ValueError,'Historical trace counters'):
                replay(None,None,None,None,2426,120,Mock(exists=lambda:False))
