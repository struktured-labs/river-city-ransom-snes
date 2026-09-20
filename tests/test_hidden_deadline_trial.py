import json
from pathlib import Path
import tempfile
import unittest

from tools.benchmark_report import sha
from tools.build_hidden_deadline_trial import build


class HiddenDeadlineTrialTests(unittest.TestCase):
    def parent(self,root,mutation):
        root.mkdir()
        data=bytearray([255])*2097152
        guard=bytes.fromhex('ada01c29ff00c90200d006207da74c')
        data[0x8900:0x8900+len(guard)]=guard
        mutation(data)
        (root/'native-cpu.sfc').write_bytes(data)
        (root/'native_boot.lbl').write_text('al 008807 .native_prepare\nal 00AA95 .prepare_palette\nal 00A77D .prepare_hidden_direct_row\n')
        (root/'manifest.json').write_text(json.dumps(dict(rom_sha256=sha(root/'native-cpu.sfc'),experimental_hidden_direct_rows=True)))

    def test_invalid_deadline_before_any_files(self):
        for limit in (0,31,161,True,96.0):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                build(Path('/nonexistent-parent'),limit,Path('/nonexistent-output'))

    def test_guard_and_unique_call_required(self):
        for mutation in (lambda b:b.__setitem__(0x8900,0),
                         lambda b:b.__setitem__(slice(0x8980,0x8984),bytes.fromhex('207da74c'))):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);self.parent(root/'parent',mutation)
                with self.assertRaises(ValueError):build(root/'parent',128,root/'out')
                self.assertFalse((root/'out').exists())

    def test_occupied_padding_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.parent(root/'parent',lambda b:b.__setitem__(0xd300,0))
            with self.assertRaises(ValueError):build(root/'parent',128,root/'out')
            self.assertFalse((root/'out').exists())
