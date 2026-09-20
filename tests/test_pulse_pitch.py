import unittest

from tools.audit_pulse_pitch import pitch_updates, sample_expectation, value_before


class PulsePitchTests(unittest.TestCase):
    def fixture(self, voice=0):
        writes = [dict(register=voice*16+r, tick=t, value=v)
                  for r,t,v in ((2,10,0xf0),(3,27,1),(2,90,0x10),(3,107,2))]
        updates = pitch_updates(writes, voice)
        tables = ([10,90], [27,107], [0xf0,0x10], [1,2])
        return updates, tables

    def test_completed_clock_boundary_is_strict(self):
        self.assertEqual(value_before([10], [7], 10), 0)
        self.assertEqual(value_before([10], [7], 11), 7)

    def test_split_bytes_and_completed_updates_both_voices(self):
        for voice, offset in ((0,10),(1,2)):
            updates, tables = self.fixture(voice)
            result = sample_expectation(100+offset, voice, 0, updates, *tables)
            self.assertEqual(result['expected'], 0x110)
            self.assertEqual(result['allowed'], [0x1f0,0x210])
            self.assertTrue(result['split_byte'])
            result = sample_expectation(108+offset, voice, 0, updates, *tables)
            self.assertEqual(result['expected'], 0x210)
            self.assertFalse(result['split_byte'])

    def test_kon_delay_suppresses_oscillator_advance(self):
        updates, tables = self.fixture()
        result = sample_expectation(110, 0, 1, updates, *tables)
        self.assertEqual(result['expected'], 0)
        self.assertEqual(result['registers'], 0x210)
        self.assertFalse(result['split_byte'])

    def test_unchanged_high_byte_is_not_a_split(self):
        updates, tables = self.fixture()
        tables[3][1] = 1
        updates[1]['new'] = 0x110
        result = sample_expectation(110, 0, 0, updates, *tables)
        self.assertFalse(result['split_byte'])

    def test_initial_state_and_invalid_pairs(self):
        updates, tables = self.fixture()
        self.assertEqual(sample_expectation(3,1,0,updates,*tables)['expected'], 0)
        for writes in ([dict(register=2,tick=10,value=1)],
                       [dict(register=3,tick=10,value=1),dict(register=2,tick=20,value=1)],
                       [dict(register=2,tick=10,value=1),dict(register=3,tick=10,value=1)]):
            with self.assertRaises(ValueError):
                pitch_updates(writes,0)


if __name__ == '__main__':
    unittest.main()
