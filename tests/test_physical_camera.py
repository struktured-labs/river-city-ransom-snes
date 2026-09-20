import unittest

import numpy as np

from tools.audit_physical_camera import analyze, cadence, displacement


class PhysicalCameraTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.random.default_rng(42).integers(0,256,(24,256,3),dtype=np.uint8)

    def test_recovers_camera_sign_and_zero(self):
        for shift in range(-4,5):
            result=displacement(self.frame,np.roll(self.frame,shift,axis=1))
            self.assertTrue(result['accepted'])
            self.assertEqual(result['camera_delta'],-shift)

    def test_rejects_flat_and_unrelated_scenery(self):
        flat=np.full_like(self.frame, [0,255,255])
        self.assertFalse(displacement(flat,flat)['accepted'])
        self.assertFalse(displacement(self.frame,255-self.frame)['accepted'])

    def test_two_frame_cadence_and_inserted_duplicate(self):
        frames=np.array([np.roll(self.frame,-2*(i//2),axis=1) for i in range(12)])
        self.assertEqual(analyze(frames)['histogram'],{2:4})
        changed=analyze(np.insert(frames,5,frames[4],axis=0))
        self.assertEqual(changed['histogram'],{2:3,3:1})

    def test_unmatched_pair_and_direction_change_break_join(self):
        pairs=[dict(frame=i+2,accepted=True,camera_delta=d)
               for i,d in enumerate([2,0,2,0,-2,0,-2])]
        self.assertEqual(cadence(pairs)['histogram'],{2:2})
        pairs[1]['accepted']=False
        self.assertEqual(cadence(pairs)['histogram'],{2:1})

    def test_invalid_strip_shape_rejected(self):
        with self.assertRaises(ValueError):displacement(self.frame,self.frame[:,:100])
        with self.assertRaises(ValueError):displacement(self.frame[:,:3],self.frame[:,:3])
        with self.assertRaises(ValueError):cadence([dict(frame=3,accepted=True,camera_delta=0)])
