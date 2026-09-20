import unittest
from tools import capture_audio_stem as stems
from tools.capture_pulse_stem import pulse_options,pulse_policy


class PulseStemTests(unittest.TestCase):
    def test_exact_voice(self):
        for system,count in (('nes',5),('snes',8)):
            for voice in (1,2):
                options=pulse_options(system,f'pulse{voice}')
                self.assertEqual(len(options),count)
                enabled=[key for key,value in options.items() if value==b'enabled']
                self.assertEqual(len(enabled),1)
                self.assertTrue(enabled[0].endswith(str(voice).encode()))

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):pulse_options('snes','noise')
        with self.assertRaises(ValueError):pulse_options('other','pulse1')

    def test_restores_policy_on_failure(self):
        original=stems.options_for
        with self.assertRaises(RuntimeError):
            with pulse_policy():
                self.assertIs(stems.options_for,pulse_options)
                raise RuntimeError('test')
        self.assertIs(stems.options_for,original)
