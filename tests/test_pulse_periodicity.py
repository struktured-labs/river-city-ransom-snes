import unittest
import numpy as np
from tools.check_nes_disabled_reload import pulse_periodicity


class PulsePeriodicityTests(unittest.TestCase):
    def signal(self, hz):
        values = np.sin(2*np.pi*hz*np.arange(48000)/48000)
        return np.column_stack((values, values))

    def test_correct_fundamental(self):
        self.assertTrue(pulse_periodicity(self.signal(440), 48000, 440)['passed'])

    def test_octave_up_and_down_fail(self):
        for hz in (220, 880):
            self.assertFalse(pulse_periodicity(self.signal(hz), 48000, 440)['passed'])

    def test_silence_fails(self):
        self.assertFalse(pulse_periodicity(np.zeros((48000, 2)), 48000, 440)['passed'])

    def test_stronger_second_harmonic(self):
        wave = self.signal(440) + 1.4*self.signal(880)
        self.assertTrue(pulse_periodicity(wave, 48000, 440)['passed'])
