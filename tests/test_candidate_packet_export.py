import json
from pathlib import Path
import tempfile
import unittest

from tools.benchmark_report import sha
from tools.read_candidate_packet_export import target


class CandidateExportTests(unittest.TestCase):
    def test_target_bound_to_exact_cartridge(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'native-cpu.sfc').write_bytes(b'test cartridge')
            digest = sha(root/'native-cpu.sfc')
            (root/'manifest.json').write_text(json.dumps(dict(rom_sha256=digest,
                diagnostic_packet_log=dict(requires_sram_seed_sha256='seed'))))
            boot = dict(rom_sha256=digest, rom='/media/fat/games/SNES/RCR-SNES-'+digest[:12]+'.sfc',
                        launcher='/media/fat/RCR-SNES-'+digest[:12]+'.mgl')
            path = root/'boot.json'
            path.write_text(json.dumps(boot))
            self.assertEqual(target(root, path)[0], '/media/fat/saves/SNES/RCR-SNES-'+digest[:12]+'.sav')
            for key in ('rom_sha256', 'rom', 'launcher'):
                path.write_text(json.dumps(dict(boot, **{key: 'wrong'})))
                with self.assertRaises(ValueError):
                    target(root, path)

    def test_unseeded_cartridge_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'native-cpu.sfc').write_bytes(b'game')
            digest = sha(root/'native-cpu.sfc')
            (root/'manifest.json').write_text(json.dumps(dict(rom_sha256=digest)))
            (root/'boot.json').write_text(json.dumps(dict(rom_sha256=digest)))
            with self.assertRaises(ValueError):
                target(root, root/'boot.json')
