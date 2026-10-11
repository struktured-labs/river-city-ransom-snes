import hashlib
import json
from pathlib import Path
import unittest

from tools.build_nested_audio import engine_patches, sender, OLD_SENDER
from tools.pn_spc_asm import assemble

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / '.deps/project-nested/Assembly'
SPEC = json.loads((ROOT / 'tools/dependencies.json').read_text())['project-nested']


class SenderTests(unittest.TestCase):
    def test_fits_old_slot_and_keeps_contract(self):
        code = sender()
        self.assertLessEqual(len(code), len(OLD_SENDER))
        self.assertEqual(code[-1], 0x60)
        self.assertTrue(code.endswith(bytes.fromhex('a017001860')))  # Y=$17, C clear
        self.assertIn(bytes.fromhex('ad150a8d4121ad160a8d4221a9d78d4021'), code)
        self.assertIn(bytes.fromhex('c01400'), code)   # last pair is $4012/$4013

    def test_timeout_branches_reach_rts(self):
        code = sender()
        for at in range(len(code) - 1):
            if code[at] == 0xB0 and code[at - 3] == 0x20:
                self.assertEqual(at + 2 + code[at + 1], len(code) - 1)


@unittest.skipUnless((DEPS / 'Project/Spc700/Spc.asm').exists(), 'run tools/bootstrap.py')
class ProjectNestedEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.labels = assemble(DEPS)

    def test_pinned_image(self):
        self.assertEqual(hashlib.sha256(self.engine).hexdigest(), SPEC['assembled_sha256'])
        self.assertEqual(self.labels['xfer'], 0x04A7)

    def test_patches(self):
        out, changes = engine_patches(self.engine, self.labels)
        self.assertEqual(len(changes), 2)
        self.assertEqual(len(out), len(self.engine))
        self.assertEqual(sum(a != b for a, b in zip(out, self.engine)), 9)
        self.assertNotIn(bytes.fromhex('e5ffbf'), out)

    def test_licence_pinned(self):
        text = (DEPS.parent / 'License.md').read_text()
        self.assertIn('Copyright 2020 Laurent Courville', text)
        self.assertIn('Permission is hereby granted, free of charge', text)


if __name__ == '__main__':
    unittest.main()
