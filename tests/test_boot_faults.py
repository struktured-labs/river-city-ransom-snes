import copy
import hashlib
from pathlib import Path
import unittest

from tools.boot_faults import Monitor, binding, verify_rows


class BootFaultTests(unittest.TestCase):
    clean = dict(adapter=0, spc=0, depth=0, publish_check=0, overrun=0)
    dirty = dict(adapter=85, spc=85, depth=85, publish_check=85, overrun=85)

    def test_preboot_ram_is_not_game_telemetry(self):
        monitor = Monitor()
        self.assertEqual(monitor.observe(0xd100d2, self.dirty), (False, None))
        self.assertEqual(monitor.observe(0xc08050, self.clean), (True, None))

    def test_game_fault_immediately_after_handoff(self):
        monitor = Monitor()
        monitor.observe(0xd100d2, self.dirty)
        self.assertEqual(monitor.observe(0xc08050, self.dirty), (True, 'adapter_fault'))

    def test_reentering_splash_cannot_hide_faults(self):
        monitor = Monitor()
        monitor.observe(0xc08050, self.clean)
        self.assertEqual(monitor.observe(0xd100d2, self.dirty), (True, 'adapter_fault'))

    def test_unexpected_bank_fails_closed(self):
        self.assertEqual(Monitor().observe(0x008050, self.dirty), (True, 'adapter_fault'))

    def test_vblank_latch_after_handoff(self):
        raw = dict(self.clean, publish_check=1, overrun=1)
        self.assertEqual(Monitor().observe(0xc08050, raw), (True, 'vblank_overrun'))

    def fixture(self):
        policy = dict(policy='d1-preboot-one-way-v1', checker_sha256=hashlib.sha256(
            Path('tools/boot_faults.py').read_bytes()).hexdigest())
        report = dict(system='snes', boot_fault_policy=policy, capture_complete=True)
        rows = [dict(native=dict(pc=pc), fault_registers=raw, adapter_monitor_active=active,
                     phase='boot_to_menu', fault=fault) for pc, raw, active, fault in
                ((0xd100d2, self.dirty, False, None), (0xc08050, self.clean, True, None),
                 (0xc78050, self.dirty, True, 'adapter_fault'))]
        return report, rows

    def test_verifier_rejects_hidden_fault_and_disabled_monitor(self):
        report, rows = self.fixture()
        verify_rows(report, rows)
        for field, value in (('fault', None), ('adapter_monitor_active', False)):
            mutant = copy.deepcopy(rows)
            mutant[-1][field] = value
            with self.assertRaises(ValueError):
                verify_rows(report, mutant)

    def test_verifier_requires_handoff_and_preboot_phase(self):
        report, rows = self.fixture()
        with self.assertRaises(ValueError):
            verify_rows(report, rows[:1])
        rows[0]['phase'] = 'idle'
        with self.assertRaises(ValueError):
            verify_rows(report, rows)

    def test_authenticate_reset_and_entry_not_just_manifest(self):
        image = bytearray(0x120000)
        image[0x8000:0x8005] = bytes.fromhex('5c0000d1ea')
        image[0x110000:0x110005] = bytes.fromhex('7818fbc238')
        manifest = dict(splash={'hold_frames': 240}, rom_sha256=hashlib.sha256(image).hexdigest())
        self.assertIsNotNone(binding(image, manifest))
        image[0x8001] = 1
        manifest['rom_sha256'] = hashlib.sha256(image).hexdigest()
        with self.assertRaises(ValueError):
            binding(image, manifest)
