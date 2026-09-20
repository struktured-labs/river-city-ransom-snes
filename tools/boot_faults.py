"""One-way fault-monitor ownership for the authenticated D1 preboot splash.

The game adapter's RAM does not exist yet while splash code owns the CPU.
Never use a grace period or permit re-entry to disable checks after handoff.
"""
import hashlib
from pathlib import Path


def binding(image, manifest):
    if not manifest.get('splash'):
        return None
    if (hashlib.sha256(image).hexdigest() != manifest['rom_sha256']
            or image[0x8000:0x8005] != bytes.fromhex('5c0000d1ea')
            or image[0x110000:0x110005] != bytes.fromhex('7818fbc238')):
        raise ValueError('Unknown splash reset/entry: cannot defer adapter monitoring')
    return dict(policy='d1-preboot-one-way-v1',
                checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def registers(ram):
    return dict(adapter=ram[0x1c06], spc=ram[0x1c0b], depth=ram[0x1c0a],
                publish_check=ram[0x1c79], overrun=ram[0x1c7b])


class Monitor:
    def __init__(self):
        self.game_started = False

    def observe(self, pc, raw):
        # C0 native reset follows D1 teardown. Any other unexpected bank also
        # activates checking rather than creating another exemption.
        self.game_started |= pc >> 16 != 0xd1
        fault = None
        if self.game_started:
            if raw['adapter'] or raw['spc'] or raw['depth'] > 1:
                fault = 'adapter_fault'
            if raw['publish_check'] == 1 and raw['overrun']:
                fault = 'vblank_overrun'
        return self.game_started, fault


def verify_rows(report, rows):
    policy = report.get('boot_fault_policy')
    if policy is None:
        if any('fault_registers' in r for r in rows):
            raise ValueError('Missing boot fault policy')
        return
    if (report['system'] != 'snes' or policy != dict(policy='d1-preboot-one-way-v1',
            checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())):
        raise ValueError('Unknown boot fault policy')
    monitor = Monitor()
    for row in rows:
        active, fault = monitor.observe(row['native']['pc'], row['fault_registers'])
        if row.get('adapter_monitor_active') != active or row['fault'] != fault:
            raise ValueError('Boot fault monitoring differs from observed CPU/RAM')
        if not active and row['phase'] != 'boot_to_menu':
            raise ValueError('Splash exemption outside preboot')
    if report['capture_complete'] and not monitor.game_started:
        raise ValueError('Complete capture never left splash')
