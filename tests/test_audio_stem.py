import unittest
from unittest.mock import patch
import ctypes as C

from tools.capture_audio_stem import options_for, isolated
from tools.smoke_libretro import Variable


class AudioStemTests(unittest.TestCase):
    def test_triangle_is_third_voice_and_complement_preserves_others(self):
        for system, count in (('nes',5),('snes',8)):
            only=options_for(system,'triangle');rest=options_for(system,'without-triangle')
            self.assertEqual(len(only),count)
            self.assertEqual(set(only),set(rest))
            for key, value in only.items():
                self.assertEqual(value==b'enabled',key.endswith(b'_3'))
                self.assertNotEqual(value,rest[key])

    def test_post_load_update_is_delivered_once(self):
        class FakeCore:
            def __init__(self):
                def setter(callback):
                    self.callback = callback
                self.retro_set_environment = setter
        callback_type = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
        @callback_type
        def original(cmd, data):
            if cmd == 17:
                C.cast(data, C.POINTER(C.c_bool))[0] = False
                return True
            return False
        core = FakeCore()
        with patch.object(C, 'CDLL', return_value=core):
            with isolated('snes', 'noise'):
                wrapped = C.CDLL('fake')
                wrapped.retro_set_environment(original)
                for key, expected in options_for('snes', 'noise').items():
                    var = Variable(key, None)
                    self.assertTrue(core.callback(15, C.byref(var)))
                    self.assertEqual(var.value, expected)
                flag = C.c_bool(False)
                self.assertTrue(core.callback(17, C.byref(flag)))
                self.assertTrue(flag.value)
                self.assertTrue(core.callback(17, C.byref(flag)))
                self.assertFalse(flag.value)

    def test_only_fourth_voice_is_noise(self):
        for system, count in (('nes', 5), ('snes', 8)):
            noise = options_for(system, 'noise')
            rest = options_for(system, 'without-noise')
            self.assertEqual(len(noise), count)
            self.assertEqual(set(noise), set(rest))
            self.assertEqual(sum(v == b'enabled' for v in noise.values()), 1)
            for key, value in noise.items():
                self.assertEqual(value == b'enabled', key.endswith(b'_4'))
                self.assertNotEqual(value, rest[key])

    def test_unknown_modes_rejected(self):
        for system, mode in (('snes', 'all'), ('unknown', 'noise')):
            with self.assertRaises(ValueError):
                options_for(system, mode)
