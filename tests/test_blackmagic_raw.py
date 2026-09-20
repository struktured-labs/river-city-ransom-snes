from copy import deepcopy
import unittest

from tools.capture_blackmagic_raw import debug_path,without_debug
from tools.capture_mister_dual_audio import episode
from tools.mister_pad_sequence import validate


class RawCaptureTests(unittest.TestCase):
    def node(self,path=''):
        return dict(info=dict(params={'Props':[dict(mute=True,volume=1.0,
            params=['debug.wav-path',path,'resample.quality',4])]}))

    def test_debug_path_is_separate_from_speaker_mute(self):
        node=self.node('/tmp/capture.wav');before=deepcopy(node)
        self.assertEqual(debug_path(node),'/tmp/capture.wav')
        self.assertEqual(without_debug(node),self.node()['info']['params']['Props'])
        self.assertEqual(node,before)

    def test_other_adapter_changes_remain_visible(self):
        node=self.node('/tmp/capture.wav');node['info']['params']['Props'][0]['mute']=False
        self.assertNotEqual(without_debug(node),without_debug(self.node()))

    def test_malformed_missing_or_ambiguous_params_fail(self):
        for props in ([],[dict(params=[])],[dict(params=['debug.wav-path'])],[{},{}]):
            with self.assertRaises(ValueError):debug_path(dict(info=dict(params={'Props':props})))

    def test_episode_fits_recording_and_releases_controls(self):
        events=episode();self.assertAlmostEqual(validate(events),22.5)
        self.assertEqual(events[-1],dict(keys=[],seconds=2))
        self.assertEqual(sum(e['keys']==['start'] for e in events),4)
