import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.audit_candidate_route_equivalence import SHOP_PROMPT_OFFSETS, compare, patch_scope
from tools.benchmark_report import sha


class CandidateRouteEquivalenceTests(unittest.TestCase):
    def test_rejects_any_rom_change_outside_shop_accesses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_rom, new_rom = root/'old.sfc', root/'new.sfc'
            old = bytearray(2097152)
            new = bytearray(old)
            patches = {offset: dict(offset=offset) for offset in SHOP_PROMPT_OFFSETS}
            for offset in SHOP_PROMPT_OFFSETS:
                new[0x30000+offset:0x30000+offset+3] = b'\x11\x22\x33'
            new[0xffdc:0xffe0] = b'\x10\x20\x30\x40'
            old_rom.write_bytes(old)
            new_rom.write_bytes(new)
            manifest_old = dict(patches=[], source_rom_sha256='nes', spc_sha256='spc', rom_sha256=sha(old_rom))
            manifest_new = dict(manifest_old, patches=list(patches.values()), rom_sha256=sha(new_rom))
            old_manifest, new_manifest = root/'old.json', root/'new.json'
            old_manifest.write_text(json.dumps(manifest_old))
            new_manifest.write_text(json.dumps(manifest_new))
            self.assertEqual(len(patch_scope(old_rom, new_rom, old_manifest, new_manifest)), 34)
            new[0x400] = 1
            new_rom.write_bytes(new)
            manifest_new['rom_sha256'] = sha(new_rom)
            new_manifest.write_text(json.dumps(manifest_new))
            with self.assertRaisesRegex(ValueError, 'outside'):
                patch_scope(old_rom, new_rom, old_manifest, new_manifest)

    def test_identical_frame_metrics_cannot_hide_different_wav_or_image(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_rom, new_rom = root/'old.sfc', root/'new.sfc'
            old_rom.write_bytes(b'old')
            new_rom.write_bytes(b'new')
            old_capture, new_capture = root/'old', root/'new'
            old_capture.mkdir()
            new_capture.mkdir()
            for capture in (old_capture, new_capture):
                (capture/'audio.wav').write_bytes(b'original wav')
            scenario = 'a'*64
            base = dict(system='snes', scenario_name='traversal-shop-exit', scenario_sha256=scenario,
                        capture_complete=True)
            receipts = [dict(base, rom_sha256=sha(old_rom)), dict(base, rom_sha256=sha(new_rom))]
            row = dict(video_sha256='frame', ram_sha256='ram', input_delivered=[], input_requested=[],
                       audio={'samples': 1}, audio_start_sample=0, fault=None)
            rows_before, rows_after = [row]*7001, [row]*7001
            with mock.patch('tools.audit_candidate_route_equivalence.verify_capture',
                            side_effect=[(receipts[0], rows_before), (receipts[1], rows_after)]):
                self.assertTrue(all(compare(old_capture, new_capture, old_rom, new_rom)['gates'].values()))
            (new_capture/'audio.wav').write_bytes(b'mismatched wav')
            rows_after = list(rows_after)
            rows_after[6] = dict(row, video_sha256='wrong frame')
            with mock.patch('tools.audit_candidate_route_equivalence.verify_capture',
                            side_effect=[(receipts[0], rows_before), (receipts[1], rows_after)]):
                gates = compare(old_capture, new_capture, old_rom, new_rom)['gates']
            self.assertFalse(gates['full_wav_bytes'])
            self.assertFalse(gates['every_frame_video_hash'])


if __name__ == '__main__':
    unittest.main()
