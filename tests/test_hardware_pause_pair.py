import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import wave
import numpy as np
from tools.audit_hardware_pause_pair import audit, compare, measure, interval_label


class HardwarePausePairTests(unittest.TestCase):
    def setUp(self):
        self.game = np.tile(np.array([[200, -200], [-200, 200]], dtype='<i2'), (24000, 1))
        self.pause = np.zeros_like(self.game)

    def test_narrow_pass(self):
        result = compare(self.game, self.pause, 48000, 1, 1)
        self.assertTrue(result['sampled_pause_pair_passed'])
        self.assertFalse(result['pop_free_verified'])
        self.assertFalse(result['nes_speed_verified'])
        self.assertFalse(result['release_ready'])
        self.assertEqual(result['gameplay']['max_adjacent_step'], 400)

    def test_recording_labels_come_from_current_manifest(self):
        description={'gameplay':dict(recording_offset_seconds=62565,seconds=30)}
        self.assertEqual(interval_label(description,'gameplay'),'62565–62595 seconds')
        for offset,seconds in ((-1,20),(float('nan'),20),(0,0),('wrong',20)):
            with self.assertRaises(ValueError):
                interval_label({'gameplay':dict(recording_offset_seconds=offset,seconds=seconds)},'gameplay')

    def test_review_binds_current_identity_intervals_and_media(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in (('game.wav',self.game),('pause.wav',self.pause)):
                with wave.open(str(root/name),'wb') as output:
                    output.setparams((2,2,48000,0,'NONE','not compressed'))
                    output.writeframes(data.tobytes())
            for name in ('view.png','video.mp4'):
                (root/name).write_bytes(b'opaque review artifact')
            description=dict(rom_sha256='8'*64,rom_identity_scope='Test identity scope',
                gameplay=dict(file='game.wav',recording_offset_seconds=62565,seconds=1),
                paused=dict(file='pause.wav',recording_offset_seconds=62605,seconds=1),
                screenshots=[dict(file='view.png',caption='Test frame')],
                video=dict(file='video.mp4',scope='Test video scope'),
                artifacts=['game.wav','pause.wav','view.png','video.mp4'])
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps(description))
            audit(manifest,root/'review')
            page=(root/'review/index.html').read_text()
            self.assertIn('8888888',page)
            self.assertIn('62565–62566 seconds',page)
            self.assertIn('62605–62606 seconds',page)
            self.assertNotIn('34835f8',page)
            self.assertNotIn('44920',page)
            for missing in ('view.png','video.mp4'):
                description['artifacts']=['game.wav','pause.wav','view.png','video.mp4']
                description['artifacts'].remove(missing)
                manifest.write_text(json.dumps(description))
                with self.assertRaisesRegex(ValueError,'Review media'):
                    audit(manifest,root/'rejected')

    def test_silence_dc_and_dead_channel_are_not_controls(self):
        dead_channel = self.game.copy()
        dead_channel[:, 1] = 0
        for bad in (self.pause, np.full_like(self.game, 10), dead_channel):
            self.assertFalse(compare(bad, self.pause, 48000, 1, 1)['sampled_pause_pair_passed'])

    def test_single_paused_sample_rejected(self):
        self.pause[123, 1] = 1
        self.assertFalse(compare(self.game, self.pause, 48000, 1, 1)['sampled_pause_pair_passed'])

    def test_bad_shape_rate_dtype_and_duration(self):
        for data, rate, seconds in ((self.game[:-1],48000,1), (self.game,48000,2),
                (self.game,48000,float('nan')), (self.game,48000,0),
                (self.game.astype(float),48000,1), (self.game[:,0],48000,1),
                (self.game,24000,2)):
            with self.assertRaises(ValueError):
                measure(data, rate, seconds)
