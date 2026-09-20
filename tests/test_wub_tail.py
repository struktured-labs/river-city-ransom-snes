import unittest
import numpy as np
from tools.audit_wub_tail import characterize
from tools.build_wub_tail_trial import curve, patch
from tools.build_ident_spc import curve as original


class WubTailTests(unittest.TestCase):
    def test_executed_pcm_checker_rejects_flat_or_wrong_pitch(self):
        rate, count = 32040, 534
        rows = [dict(frame=i+1, phase=2, ident_note=i, audio_sample_count=count) for i in range(240)]
        volume = np.frombuffer(curve(),dtype=np.uint8).reshape(240,3)[:,2]/116
        t = np.arange(240*count)/rate
        def pcm(hz, gains):
            mono = (4000*np.sin(2*np.pi*hz*t)*np.repeat(gains,count)).astype(np.int16)
            return np.column_stack((mono,mono))
        good = characterize(pcm(110, volume),rate,rows)
        self.assertTrue(good['passed'],good['gates'])
        flat = volume.copy(); flat[144:219] = 1
        self.assertFalse(characterize(pcm(110,flat),rate,rows)['gates']['three_deep_pulses'])
        self.assertFalse(characterize(pcm(125,volume),rate,rows)['gates']['fixed_low_note'])

    def test_descent_unchanged_three_deep_slow_pulses_then_stop(self):
        data = curve()
        self.assertEqual(data[:432], original()[:432])
        self.assertEqual(len(data), 720)
        self.assertEqual(len({data[i*3:i*3+2] for i in range(144, 240)}), 1)
        self.assertEqual([data[i*3+2] for i in (144, 174, 204)], [116]*3)
        self.assertTrue(all(data[i*3+2] <= 7 for i in (159, 189)))
        self.assertTrue(all(data[i*3+2] == 0 for i in range(219, 240)))

    def test_only_tail_and_checksum_change(self):
        image = bytearray(b'\xff'*0x200000)
        image[0x110400:0x110400+720] = original()
        changed, offset = patch(image, original(), curve())
        self.assertEqual(offset, 0x110400)
        allowed = set(range(offset+432, offset+720)) | set(range(0xffdc, 0xffe0))
        self.assertTrue(all(i in allowed for i, (a,b) in enumerate(zip(image, changed)) if a != b))
        with self.assertRaises(ValueError):
            patch(changed, original(), curve())
