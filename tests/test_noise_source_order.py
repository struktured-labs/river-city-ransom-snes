import unittest

from tools.audit_noise_source_order import late_source


class NoiseSourceOrder(unittest.TestCase):
    def test_late_non_and_prior_builtin(self):
        writes = [dict(packet=1, tick=10, register=0x30, value=8),
                  dict(packet=1, tick=19, register=0x31, value=8),
                  dict(packet=1, tick=48, register=0x3d, value=8)]
        r = late_source(writes,[1])[0]
        self.assertTrue(r['late'])
        self.assertEqual(r['volume_to_source_ticks'],[38,29])
        prefix = [dict(packet=0,tick=1,register=0x3d,value=8)]
        self.assertFalse(late_source(prefix+writes,[1])[0]['late'])

    def test_missing_or_wrong_source_rejected(self):
        for writes in ([],[dict(packet=1,tick=10,register=0x3d,value=0)]):
            with self.assertRaises(ValueError):
                late_source(writes,[1])


if __name__ == '__main__':
    unittest.main()
