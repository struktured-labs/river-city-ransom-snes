import ctypes as C
import hashlib
import unittest

from tools.capture_video_pipeline_state import REGIONS, read


class VideoPipelineStateTests(unittest.TestCase):
    def test_exact_ranges_and_no_writes(self):
        raw = bytes(i % 251 for i in range(0x20000))
        buffer = C.create_string_buffer(raw)
        value = read(C.addressof(buffer), len(raw))
        for name, (start, count) in REGIONS.items():
            self.assertEqual(value[name], raw[start:start+count].hex())
        self.assertEqual(value['palette']['ppu_shadow'], raw[0x13f00:0x13f20].hex())
        self.assertEqual(value['game_ram_sha256'], hashlib.sha256(raw[:2048]).hexdigest())
        self.assertEqual(buffer.raw[:len(raw)], raw)

    def test_rejects_short_or_null_memory(self):
        for pointer, size in ((0, 0x20000), (1, 8192), (1, 0x40000)):
            with self.assertRaises(ValueError):
                read(pointer, size)
