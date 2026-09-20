import unittest

import numpy as np

from tools.decode_obs_chunked_pcm import decode


def fixture(frames=5000, fmt=2):
    dtype = '<i2' if fmt == 2 else '<i4'
    raw = np.arange(frames*2, dtype=dtype).reshape(-1, 2)
    common = raw.astype('<f4')/(32768 if fmt == 2 else 2147483648)
    rows = ['B,1', f'I,2,10,1,{frames},1000,{fmt}']
    for offset in range(0, frames, 1024):
        block = raw[offset:offset+1024]
        rows.append(f'D,I,10,1,{offset},{len(block)},{block.tobytes().hex()}')
    rows.append(f'M,3,10,1,{frames},1000')
    for offset in range(0, frames, 1024):
        block = common[offset:offset+1024]
        rows.append(f'D,M,10,1,{offset},{len(block)},{block[:,0].tobytes().hex()},{block[:,1].tobytes().hex()}')
    return raw, common, rows+['Z,4']


class ChunkedPCMTests(unittest.TestCase):
    def test_complete_large_and_boundary_packets(self):
        for frames in (1, 800, 1024, 1025, 1479, 1600, 5000, 8192):
            for fmt in (2, 3):
                raw, common, rows = fixture(frames, fmt)
                a, b, index = decode('\n'.join(rows))
                self.assertTrue(np.array_equal(a, raw))
                self.assertTrue(np.array_equal(b, common))
                self.assertEqual(index[0]['input_frames'], frames)

    def test_missing_duplicate_overlap_and_truncation(self):
        _, _, rows = fixture()
        damaged = [rows[:3]+rows[4:], rows[:3]+[rows[2]]+rows[3:]]
        damaged.append([r.replace('D,I,10,1,1024,', 'D,I,10,1,1000,') for r in rows])
        damaged.append(rows[:2]+[rows[2][:-2]]+rows[3:])
        damaged.append(rows[:-2]+[rows[-1]])
        for text in damaged:
            with self.assertRaises(ValueError):
                decode('\n'.join(text))

    def test_pair_sequence_source_timestamp_and_rejection(self):
        _, _, rows = fixture()
        text = '\n'.join(rows)
        for mutated in (text.replace(',10,1,', ',10,2,'),
                        text.replace('M,3,10,1,', 'M,3,11,1,'),
                        text.replace('M,3,10,1,5000,1000', 'M,3,10,1,5000,1001'),
                        text.replace('I,2,10,1,5000', 'I,2,10,1,8193'),
                        text.replace('Z,4', 'X,3,9000\nZ,4'),
                        text.replace('B,1', 'B,5'), text.replace('Z,4', '')):
            with self.assertRaises(ValueError):
                decode(mutated)

    def test_nonfinite_common_rejected(self):
        _, _, rows = fixture(1)
        rows[4] = 'D,M,10,1,0,1,0000c07f,00000000'
        with self.assertRaises(ValueError):
            decode('\n'.join(rows))
