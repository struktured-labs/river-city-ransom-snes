from copy import deepcopy
import unittest

from tools.audit_pulse_onset import characterize, parse_voice


class PulseOnsetTests(unittest.TestCase):
    def fixture(self):
        writes = [dict(register=76, value=1, packet=1, tick=90)]
        records = [['K', '0', '1', '100', '1']]
        for i in range(96):
            values = ['V', 0, 1, i, 101+32*i, 1, max(0, 5-i),
                      100 if i >= 6 else 0, 100, 3, 3000, 496, 200, 24, 24, 8]
            records.append(list(map(str, values)))
        regs = [0]*128
        regs[0], regs[1], regs[2], regs[4], regs[0x0c] = 24, 24, 100, 3, 127
        ready = {1: dict(tick=310, registers=regs)}
        return records, writes, ready

    def test_complete_actual_startup(self):
        records, writes, ready = self.fixture()
        result = characterize(parse_voice(records, writes), ready)
        self.assertEqual(result['eligible'], 1)
        self.assertEqual(result['wrong_first_pitch'], 0)
        self.assertEqual(result['stale_nonzero_samples'], 0)

    def test_old_pitch_nonzero_contribution_is_caught(self):
        records, writes, ready = self.fixture()
        records[7][7] = '200'  # First post-startup oscillator advance.
        result = characterize(parse_voice(records, writes), ready)
        self.assertEqual(result['wrong_first_pitch'], 1)
        self.assertEqual(result['stale_nonzero_samples'], 1)
        records[7][12] = '0'  # Same bad pitch, but not a nonzero contribution.
        result = characterize(parse_voice(records, writes), ready)
        self.assertEqual(result['wrong_first_pitch'], 1)
        self.assertEqual(result['stale_nonzero_samples'], 0)

    def test_missing_sample_wrong_clock_delay_and_unconsumed_kon_rejected(self):
        records, writes, _ = self.fixture()
        for field in (3, 4, 6):
            bad = deepcopy(records)
            bad[7][field] = str(int(bad[7][field])+1)
            with self.assertRaises(ValueError):
                parse_voice(bad, writes)
        with self.assertRaises(ValueError):
            parse_voice(records[:-1], writes)
        with self.assertRaises(ValueError):
            parse_voice(records, writes+[dict(register=76, value=2, packet=1, tick=90)])

    def test_muted_target_is_not_counted_as_active_wrong_onset(self):
        records, writes, ready = self.fixture()
        records[7][7] = '200'
        ready[1]['registers'][0:2] = [0, 0]
        result = characterize(parse_voice(records, writes), ready)
        self.assertEqual(result['eligible'], 0)
        self.assertEqual(result['wrong_first_pitch'], 0)


if __name__ == '__main__':
    unittest.main()
