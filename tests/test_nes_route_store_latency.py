import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.audit_display_cadence import cameras
from tools.benchmark_report import sha
from tools.capture_nes_route_store import capture


class NesRouteStoreTests(unittest.TestCase):
    def pixels(self):
        return [dict(frame=1,line=y,group=g,older_address=g,
            newer_address=g+1 if g<31 else 0x400,fine_x=0,mask=8)
            for y in range(32,192) for g in range(32)]

    def test_duplicate_fetch_cannot_replace_missing_group(self):
        rows=self.pixels();rows[-1]=rows[0].copy()
        with self.assertRaisesRegex(ValueError,'Duplicate'):cameras(rows,'nes',[1])

    def test_disabled_group_or_broken_shifter_sequence_rejected(self):
        for field,value in (('mask',0),('newer_address',999)):
            rows=self.pixels();rows[10][field]=value
            with self.assertRaises(ValueError):cameras(rows,'nes',[1])

    def test_single_late_group_preserved_as_split(self):
        rows=self.pixels();rows[-1]['fine_x']=1
        self.assertEqual(cameras(rows,'nes',[1]),{1:[0,1]})

    def fixture(self,root):
        rom=root/'original.nes';rom.write_bytes(b'original')
        core=root/'core.so';core.write_bytes(b'core')
        normal=root/'normal';normal.mkdir();(normal/'capture.json').write_text('{}')
        baseline=dict(system='nes',capture_complete=True,scenario_name='traversal-park-single-sweep',
            frame_images=True,full_ram_telemetry=False,nes_ppu_observer={},frames=2,rom_sha256=sha(rom))
        return rom,core,normal,root/'capture',baseline,[dict(game_ram_hex='00'*2048)]*2

    def test_complete_ram_is_used_even_with_legacy_flag_false(self):
        with tempfile.TemporaryDirectory() as temp:
            rom,core,normal,out,baseline,rows=self.fixture(Path(temp))
            def run(command,env,check):
                self.assertTrue(check);self.assertIn('--ppu-telemetry',command)
                self.assertIn('--full-ram-telemetry',command)
                self.assertEqual(env['RCR_NES_EVENT_PC1'],'e2b1')
                self.assertEqual(env['RCR_RENDER_LAST'],'2')
                out.mkdir();(out/'capture.json').write_text('{}')
            with patch('tools.capture_nes_route_store.verify_capture',return_value=(baseline,rows)),\
                 patch('tools.capture_nes_route_store.subprocess.run',side_effect=run),\
                 patch.dict(os.environ,{},clear=True):
                capture(rom,core,normal,out)
            self.assertIn('route_store_observer',json.loads((out/'capture.json').read_text()))

    def test_missing_ppu_or_ram_rejected_before_capture(self):
        for bad in ('ppu','ram'):
            with tempfile.TemporaryDirectory() as temp:
                rom,core,normal,out,baseline,rows=self.fixture(Path(temp))
                if bad=='ppu':del baseline['nes_ppu_observer']
                else:rows[0]['game_ram_hex']='00'
                with patch('tools.capture_nes_route_store.verify_capture',return_value=(baseline,rows)),\
                     patch('tools.capture_nes_route_store.subprocess.run') as run:
                    with self.assertRaisesRegex(ValueError,'RAM/PPU'):capture(rom,core,normal,out)
                    run.assert_not_called()

    def test_inherited_observer_environment_is_not_silently_merged(self):
        with tempfile.TemporaryDirectory() as temp:
            rom,core,normal,out,baseline,rows=self.fixture(Path(temp))
            with patch('tools.capture_nes_route_store.verify_capture',return_value=(baseline,rows)),\
                 patch.dict(os.environ,{'RCR_NES_EVENT_PC7':'ffff'},clear=True):
                with self.assertRaisesRegex(ValueError,'inherited'):capture(rom,core,normal,out)
