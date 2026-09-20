import unittest

from tools.capture_route_checkpoints import checkpoint_frames


class CheckpointSelectionTests(unittest.TestCase):
    def test_unique_interior_frames_only(self):
        self.assertEqual(checkpoint_frames('2,10,99',100),[2,10,99])
        for value in ('','0','100','101','2,2','10,2','-1','x','2,'):
            with self.assertRaises(ValueError):checkpoint_frames(value,100)
