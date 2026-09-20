import unittest
from tools.check_reset_controls import inspect


class ResetControlTests(unittest.TestCase):
    def trace(self):
        rows = [['K', '0', '0', '0bcb'], ['K', '0', '15', '0456']]
        for frame in range(341):
            number = str(frame+1)
            reset = frame % 32 == 0 or frame in (180, 240)
            rows.append(['P', number, str(int(reset)), '3008'])
            if reset and not 120 <= frame < 180:
                rows.append(['K', number, '1', '302c'])
            if frame == 0:
                rows.append(['K', number, '1', '04c5'])
        return rows

    def test_complete_schedule(self):
        self.assertTrue(inspect(self.trace())['passed'])

    def deferred_trace(self):
        return [[*r[:3], '3035' if r[3]=='302c' else r[3]] for r in self.trace()
                if r != ['K', '1', '1', '04c5']]

    def test_deferred_schedule(self):
        self.assertTrue(inspect(self.deferred_trace(), deferred=True)['passed'])

    def test_deferred_duplicate_duty_detected(self):
        rows = self.deferred_trace()
        index = rows.index(['P', '33', '1', '3008'])
        rows.insert(index+1, ['K', '33', '1', '04c5'])
        self.assertFalse(inspect(rows, deferred=True)['passed'])

    def test_dual_pulse_mask_and_lost_voice(self):
        rows = self.deferred_trace()
        for row in rows:
            if int(row[1]) > 0 and row[2] == '1':
                row[2] = '3'
        self.assertTrue(inspect(rows, deferred=True, both_pulses=True)['passed'])
        for row in rows:
            if row[0] == 'K' and row[1] == '33':
                row[2] = '1'
        self.assertFalse(inspect(rows, deferred=True, both_pulses=True)['passed'])

    def test_missing_reset_detected(self):
        rows = [r for r in self.trace() if not (r[0]=='K' and r[1]=='33')]
        self.assertFalse(inspect(rows)['passed'])

    def test_muted_keyon_detected(self):
        rows = self.trace()
        index = rows.index(['P', '129', '1', '3008'])
        rows.insert(index+1, ['K', '129', '1', '302c'])
        self.assertFalse(inspect(rows)['passed'])

    def test_truncation_and_duplicate_startup_rejected(self):
        with self.assertRaises(ValueError):
            inspect(self.trace()[:-1])
        rows = self.trace()
        rows.insert(0, rows[0])
        with self.assertRaises(ValueError):
            inspect(rows)
