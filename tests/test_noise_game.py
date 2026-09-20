import copy
import struct
import unittest

from tools.audit_noise_game import exact_patch, same_execution
from tools.prepare_audio import nearest_clock_engine


class NoiseGameTests(unittest.TestCase):
    def test_execution_gate_retains_all_non_audio_fields(self):
        rows = [dict(frame=1, game_ram_hex='00'*2048, video_sha256='a', audio={'peak': 1}, audio_start_sample=0)]
        changed = copy.deepcopy(rows)
        changed[0]['audio']['peak'] = 2
        self.assertEqual(same_execution(rows, changed), 1)
        for key, value in (('video_sha256', 'b'), ('audio_start_sample', 1), ('game_ram_hex', '01'*2048)):
            bad = copy.deepcopy(changed)
            bad[0][key] = value
            with self.assertRaises(ValueError):
                same_execution(rows, bad)
        with self.assertRaises(ValueError):
            same_execution(rows, [])
        rows[0]['game_ram_hex'] = ''
        with self.assertRaises(ValueError):
            same_execution(rows, rows)

    def test_only_table_and_checksum_permitted(self):
        engine = bytes(0x849)+bytes([63]*6+[62]*4+[60,59,57,56,53,50])+bytes(32)
        original = bytearray(b'\xff'*0x200000)
        original[0x9000:0x9000+len(engine)] = engine
        expected = bytearray(original)
        expected[0x9000:0x9000+len(engine)] = nearest_clock_engine(engine)
        expected[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
        checksum = sum(expected)&65535
        struct.pack_into('<HH', expected, 0xFFDC, checksum^65535, checksum)
        proof = exact_patch(bytes(original), bytes(expected), engine)
        self.assertEqual(proof['engine_offset'], 0x9000)
        for offset in (0x8000, 0x9001, 0xA000, 0xFFDC):
            bad = bytearray(expected); bad[offset] ^= 1
            with self.assertRaises(ValueError):
                exact_patch(bytes(original), bytes(bad), engine)
