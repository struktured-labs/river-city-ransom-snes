import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.benchmark_report import sha
from tools.build_active_hidden_budget_trial import patch as active
from tools.build_saturating_shift_trial import patch as shift, ADDRESS, OPTIMIZED
from tools.capture_combat_checkpoints import checkpoint_frames
from tools.replay_combat_checkpoint import guarded_variant


class CombatCheckpointTests(unittest.TestCase):
    def fixture(self, root, variant):
        parent,trial = root/'parent',root/'trial'
        parent.mkdir();trial.mkdir()
        image = bytearray(b'\xff'*2097152)
        for bank in range(1,9):
            at = bank*65536+ADDRESS
            image[at:at+20] = OPTIMIZED+bytes.fromhex('a52638')
        branch = bytes.fromhex('ada01cc902d004a9108002a9028d6b1c')
        image[0x8010:0x8010+len(branch)] = branch
        (parent/'native-cpu.sfc').write_bytes(image)
        meta = dict(rom_sha256=sha(parent/'native-cpu.sfc'),
                    hidden_compact_index=dict(new_end=0x8100,end=0x810d))
        (parent/'manifest.json').write_text(json.dumps(meta))
        labels = 'al 008001 .native_prepare\nal 008200 .prepare_palette\n'
        for directory in (parent,trial):
            (directory/'native_boot.lbl').write_text(labels)
            (directory/'native_runtime.lbl').write_text('same runtime layout\n')
        helper = b'\xea'*64
        (trial/'helper.bin').write_bytes(helper)
        changed = bytes(image)
        if variant in ('active','both'):
            changed,_ = active(changed,0x8001,0x8200,0x8100,0x810d)
        if variant in ('shift','both'):
            changed = shift(changed,helper)
        (trial/'native-cpu.sfc').write_bytes(changed)
        (trial/'manifest.json').write_text(json.dumps(dict(rom_sha256=sha(trial/'native-cpu.sfc'))))
        return parent,trial,helper

    def test_each_exact_patch_composition(self):
        for variant in ('shift','active','both'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as d:
                parent,trial,helper = self.fixture(Path(d),variant)
                with patch('tools.replay_combat_checkpoint.assemble',return_value=helper):
                    self.assertEqual(guarded_variant(parent,trial,variant,0xc080fb)['variant'],variant)

    def test_changed_rom_even_with_updated_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent,trial,helper = self.fixture(Path(d),'shift')
            rom = trial/'native-cpu.sfc';data = bytearray(rom.read_bytes());data[0x12345] ^= 1
            rom.write_bytes(data)
            (trial/'manifest.json').write_text(json.dumps(dict(rom_sha256=sha(rom))))
            with patch('tools.replay_combat_checkpoint.assemble',return_value=helper), self.assertRaises(ValueError):
                guarded_variant(parent,trial,'shift',0xc080fb)

    def test_checkpoint_inside_replaced_instruction_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent,trial,helper = self.fixture(Path(d),'shift')
            with patch('tools.replay_combat_checkpoint.assemble',return_value=helper), self.assertRaises(ValueError):
                guarded_variant(parent,trial,'shift',0xc1c3bb)

    def test_arbitrary_helper_and_moved_labels_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent,trial,helper = self.fixture(Path(d),'both')
            with patch('tools.replay_combat_checkpoint.assemble',return_value=b'\x60'*64), self.assertRaises(ValueError):
                guarded_variant(parent,trial,'both',0xc080fb)
            (trial/'native_runtime.lbl').write_text('moved')
            with self.assertRaises(ValueError):
                guarded_variant(parent,trial,'both',0xc080fb)

    def test_checkpoint_range_is_strict(self):
        self.assertEqual(checkpoint_frames('2555,4174',4916),[2555,4174])
        for value in ('0','4916','4174,2555','2555,2555'):
            with self.assertRaises(ValueError):
                checkpoint_frames(value,4916)
