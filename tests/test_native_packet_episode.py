import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tests.test_audio_packet_log import fixture
from tools.audit_native_packet_episode import gaps, stable_export
from tools.read_mister_packet_export import acquire


class NativeEpisodeTests(unittest.TestCase):
    def test_verified_stability_then_corrupt_file_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'export'
            acquire(out, 1, reader=lambda: fixture(8), pause=lambda _: None)
            report, data = stable_export(out)
            self.assertEqual(report['total'], 8)
            self.assertEqual(data, fixture(8))
            (out/'snapshot-00.srm').write_bytes(fixture(9))
            with self.assertRaises(ValueError):
                stable_export(out)

    def test_one_snapshot_does_not_qualify(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'export'
            acquire(out, 1, reader=lambda: fixture(8), pause=lambda _: None)
            p = out/'report.json'
            report = json.loads(p.read_text())
            report['snapshots'] = report['snapshots'][-1:]
            p.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                stable_export(out)

    def test_every_exact_zero_interval_including_edges(self):
        pcm = np.ones((4000, 2), dtype=np.int16)
        pcm[:480] = 0
        pcm[900:1379] = 0  # below ten milliseconds
        pcm[1500:2000] = 0
        pcm[2500:] = 0
        self.assertEqual([(g['first'], g['last']) for g in gaps(pcm, 48000)],
                         [(0, 480), (1500, 2000), (2500, 4000)])
        pcm[1500:2000, 1] = 1
        self.assertEqual(len(gaps(pcm, 48000)), 2)
        with self.assertRaises(ValueError):
            gaps(pcm, 32040)
