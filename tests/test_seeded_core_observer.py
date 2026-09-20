import ctypes as C
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.run_seeded_benchmark import seeded_core
from tools.run_seeded_sram import seed_bytes
from tools.smoke_libretro import Game


class SeededCoreObserverTests(unittest.TestCase):
    def test_process_image_and_unrelated_libraries_are_not_wrapped(self):
        sentinel = object()
        with patch.object(C, 'CDLL', return_value=sentinel) as loader:
            with seeded_core(Path('/expected/core.so'), seed_bytes(), []):
                self.assertIs(C.CDLL(None), sentinel)
                self.assertIs(C.CDLL('/different/core.so'), sentinel)
            self.assertIs(C.CDLL, loader)
        self.assertEqual(loader.call_count, 2)

    def test_restore_loader_after_failure(self):
        original = C.CDLL
        with self.assertRaisesRegex(RuntimeError, 'capture failed'):
            with seeded_core(Path('/expected/core.so'), seed_bytes(), []):
                raise RuntimeError('capture failed')
        self.assertIs(C.CDLL, original)

    def check_load(self, *, success=True, size=None, pointer=True):
        data = seed_bytes()
        backing = C.create_string_buffer(len(data))
        load = Mock(return_value=success)
        core = SimpleNamespace(retro_load_game=load,
            retro_get_memory_data=Mock(return_value=C.addressof(backing) if pointer else 0),
            retro_get_memory_size=Mock(return_value=len(data) if size is None else size))
        observed = []
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'core.so'
            rom = Path(directory) / 'rom.sfc'
            path.write_bytes(b'fake core')
            rom.write_bytes(b'fake rom')
            game = Game(str(rom).encode(), None, 0, None)
            with patch.object(C, 'CDLL', return_value=core):
                with seeded_core(path, data, observed):
                    loaded = C.CDLL(str(path))
                    result = loaded.retro_load_game(C.byref(game))
        return result, observed, backing.raw, core

    def test_successful_load_seeds_all_bytes_and_records_one_rom(self):
        result, observed, backing, _ = self.check_load()
        self.assertTrue(result)
        self.assertEqual(backing, seed_bytes())
        self.assertEqual(len(observed), 1)
        self.assertEqual(set(observed[0]), {'rom', 'rom_sha256', 'core', 'core_sha256'})

    def test_failed_load_does_not_touch_sram(self):
        result, observed, backing, core = self.check_load(success=False)
        self.assertFalse(result)
        self.assertEqual(observed, [])
        self.assertEqual(backing, bytes(len(seed_bytes())))
        core.retro_get_memory_data.assert_not_called()

    def test_wrong_size_and_null_pointer_rejected(self):
        for args in ({'size': 8192}, {'pointer': False}):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, 'mapping'):
                self.check_load(**args)


if __name__ == '__main__':
    unittest.main()
