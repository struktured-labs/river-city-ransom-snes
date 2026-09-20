import unittest

from tools.build_noise_interpolation_trial import patch, sample


class NoiseInterpolationTrial(unittest.TestCase):
    def test_same_bits_and_explicit_nonclosing_cycle(self):
        decoded = []
        for repeats in (2, 8):
            data, state = sample(repeats)
            values = []
            for at in range(0, len(data), 9):
                self.assertEqual(data[at], 0xc3 if at+9 == len(data) else 0xc0)
                for byte in data[at+1:at+9]:
                    values.extend((byte >> 4, byte & 15))
            self.assertEqual(len(values), 8192*repeats)
            self.assertNotEqual(state, 1)
            for at in range(0, len(values), repeats):
                self.assertEqual(values[at:at+repeats], [values[at]]*repeats)
            decoded.append(values[::repeats])
        self.assertEqual(decoded[0], decoded[1])
        state = 1
        for value in decoded[0]:
            self.assertEqual(value, 9 if state & 1 else 7)
            state = (state >> 1) | (((state ^ (state >> 1)) & 1) << 14)

    def test_unknown_repeat_and_engine_rejected(self):
        for repeats in (0, 1, 4, 16):
            with self.assertRaises(ValueError):
                sample(repeats)
        with self.assertRaises(ValueError):
            patch(bytes(12415), 8)


if __name__ == '__main__':
    unittest.main()
