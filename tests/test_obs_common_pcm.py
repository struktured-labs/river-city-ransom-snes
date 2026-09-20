import unittest
import numpy as np
from tools.decode_obs_common_pcm import decode


def fixture():
    x = np.array([[123, -300], [-1200, 30000]], dtype='<i2')
    y = x.astype('<f4')/32768
    text = (f'B,1\nI,2,10,1,2,1000,2,{x.tobytes().hex()}\n'
            f'M,3,10,1,2,1000,{y[:,0].tobytes().hex()},{y[:,1].tobytes().hex()}\nZ,4\n')
    return x, y, text


class CommonPCMTests(unittest.TestCase):
    def test_native_payloads(self):
        x, y, text = fixture()
        a, b, index = decode(text)
        self.assertTrue(np.array_equal(a, x))
        self.assertTrue(np.array_equal(b, y))
        self.assertEqual(index[0]['common_first'], 0)

    def test_truncated_payload_rejected(self):
        _, _, text = fixture()
        with self.assertRaises(ValueError):
            decode(text.replace('7b00', '7b'))

    def test_missing_pair_rejected(self):
        _, _, text = fixture()
        with self.assertRaises(ValueError):
            decode('\n'.join(r for r in text.splitlines() if not r.startswith('M,')))

    def test_skipped_sequence_rejected(self):
        _, _, text = fixture()
        with self.assertRaises(ValueError):
            decode(text.replace(',10,1,', ',10,2,'))

    def test_timestamp_mismatch_rejected(self):
        _, _, text = fixture()
        with self.assertRaises(ValueError):
            decode(text.replace('M,3,10,1,2,1000', 'M,3,10,1,2,1001'))

    def test_rejected_format_record_rejected(self):
        with self.assertRaises(ValueError):
            decode('B,1\nX,2,800\nZ,3\n')


if __name__ == '__main__':
    unittest.main()
