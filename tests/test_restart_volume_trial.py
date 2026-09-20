import hashlib
import json
from pathlib import Path
import unittest

from tools.build_restart_volume_trial import ENGINE_SHA, HELPERS, LATE, patch


class RestartVolumeTrialTests(unittest.TestCase):
    def setUp(self):
        root = Path('build/sprite-fused-phase80-3342')
        self.meta = json.loads((root/'manifest.json').read_text())
        at = self.meta['sweep_driver_rom_offset']
        self.engine = (root/'native-cpu.sfc').read_bytes()[at:at+12415]

    def test_patch_is_bounded_and_preserves_receiver(self):
        self.assertEqual(hashlib.sha256(self.engine).hexdigest(),ENGINE_SHA)
        baseline, trial, detail = patch(self.engine,self.meta['sweep_driver_layout'])
        self.assertEqual(len(trial),len(baseline))
        self.assertEqual(baseline[:len(self.engine)],self.engine)
        self.assertEqual(trial[0x2b40:0x2b74],self.engine[0x2b40:0x2b74])
        self.assertEqual(trial[0x2ba0:0x2baa],self.engine[0x2ba0:0x2baa])
        allowed = {c['address']-0x400+i for c in detail['changes'] for i in range(len(bytes.fromhex(c['after'])))}
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(trial,baseline)) if a != b))
        self.assertEqual(LATE+18,0x34b0)
        self.assertEqual(HELPERS[1]+15,LATE)

    def test_rejects_different_engine(self):
        wrong = bytearray(self.engine); wrong[0x2b40] = 1
        with self.assertRaises(ValueError): patch(bytes(wrong),self.meta['sweep_driver_layout'])

    def test_rejects_different_publisher_site(self):
        layout = self.meta['sweep_driver_layout']
        wrong = dict(layout,driver=dict(layout['driver'],publish0_volume=0x3300))
        with self.assertRaises(ValueError): patch(self.engine,wrong)


if __name__ == '__main__': unittest.main()
