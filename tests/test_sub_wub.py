import unittest
import numpy as np
from tools.audit_sub_wub import measure
from tools.build_sub_wub_trial import curve, patch
from tools.build_wub_tail_trial import curve as old_curve


class SubWubTests(unittest.TestCase):
    def test_pcm_gates_reject_wrong_note_flat_tail_and_no_stop(self):
        rate, count = 32040, 534
        rows = [dict(frame=i+1,phase=2,ident_note=i,audio_sample_count=count) for i in range(240)]
        volume = np.frombuffer(curve(),dtype=np.uint8).reshape(240,3)[:,2]/116
        t = np.arange(240*count)/rate
        def check(hz, gains):
            mono=(4000*np.sin(2*np.pi*hz*t)*np.repeat(gains,count)).astype(np.int16)
            return measure(np.column_stack((mono,mono)),rate,rows)['gates']
        good=check(55,volume)
        self.assertTrue(all(good.values()),good)
        self.assertFalse(check(110,volume)['fixed_55hz_note'])
        flat=volume.copy(); flat[144:219]=1
        self.assertFalse(check(55,flat)['three_deep_pulses'])
        nonstop=volume.copy(); nonstop[219:]=1
        self.assertFalse(check(55,nonstop)['decayed_before_stop'])

    def test_fixed_sub_note_envelope_and_stop(self):
        data = curve()
        pitches = [int.from_bytes(data[i*3:i*3+2], 'little') for i in range(240)]
        self.assertEqual(len(data), 720)
        self.assertEqual(data[144*3+2::3], old_curve()[144*3+2::3])
        self.assertTrue(all(a >= b for a,b in zip(pitches, pitches[1:])))
        self.assertEqual(set(pitches[144:]), {225})
        self.assertEqual([data[i*3+2] for i in (144,174,204)], [116]*3)
        self.assertEqual(set(data[219*3+2::3]), {0})

    def test_only_pitch_and_checksum_changes(self):
        image = bytearray(b'\xff'*0x200000)
        image[0x110400:0x110400+720] = old_curve()
        new, offset = patch(image)
        allowed = {offset+i*3+j for i in range(240) for j in (0,1)} | {offset+3*i+2 for i in range(114,144)} | set(range(0xffdc,0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a != b))
        with self.assertRaises(ValueError):
            patch(new)
