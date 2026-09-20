"""Relink the historical camera deadline on the exact current candidate; offline only."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

HELPER = 0x7F00


def assemble(out, service):
    if not 0x2000 <= service < 0x4000:
        raise ValueError('Invalid runtime service')
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'SERVICE={service}', '-I', 'snes',
        '-o', str(out/'guard.o'), 'snes/camera_guard_reprobe.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/camera_guard_reprobe.cfg',
        '-o', str(out/'guard.bin'), str(out/'guard.o')], check=True)
    return (out/'guard.bin').read_bytes()


def patch(image, helper, start, end, service):
    if (len(image) != 0x200000 or len(helper) != 128
            or helper[:3] != bytes.fromhex('ad801b') or not 0x2000 <= start < end < 0x4000):
        raise ValueError('Unexpected image/helper/camera layout')
    needle = b'\x20'+service.to_bytes(2, 'little')
    result = bytearray(image)
    sites = []
    allowed = set(range(0xFFDC, 0xFFE0))
    for bank in range(1, 9):
        base = bank*65536
        block = image[base+start:base+end]
        if block.count(needle) != 1 or image[base+HELPER:base+HELPER+128] != b'\xff'*128:
            raise ValueError('Missing/ambiguous camera service or occupied helper')
        site = base+start+block.index(needle)
        result[site+1:site+3] = HELPER.to_bytes(2, 'little')
        result[base+HELPER:base+HELPER+128] = helper
        sites.append(site)
        allowed.update((site+1, site+2))
        allowed.update(range(base+HELPER, base+HELPER+128))
    checksum(result)
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Unrelated cartridge change')
    return bytes(result), sites


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    rom = parent/'native-cpu.sfc'
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(rom) != meta['rom_sha256'] or not meta['experimental_second_tick_prepare']:
        raise ValueError('Need exact retained-producer parent')
    labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
              for r in (parent/'native_runtime.lbl').read_text().splitlines()}
    service = labels['second_tick_prepare_service']
    shutil.copytree(parent, out)
    helper = assemble(out, service)
    data, sites = patch(rom.read_bytes(), helper, labels['camera_deferred_nmi_exit'],
                        labels['camera_deferred_nmi_enable'], service)
    (out/'native-cpu.sfc').write_bytes(data)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_camera_guard_reprobe=dict(
        default_enabled=False, release_ready=False, helper=HELPER, sites=sites, service=service,
        cutoff=194, production_worst_case_bound_proven=False,
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/camera_guard_reprobe.asm'),
            Path('snes/camera_guard_reprobe.cfg'), Path('snes/second_tick_deadline.inc'),
            Path('tools/build_inline_pitch_trial.py'), rom, parent/'manifest.json',
            parent/'native_runtime.lbl', out/'guard.bin')},
        scope='Historical line194 admission rule, not a newly proved worst-case bound. '
              'Late camera work remains pending for the unchanged interrupt-exit fallback. '
              'All helpers, graphics, timers and SPC otherwise unchanged; needs new route qualification.'))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), sha256=meta['rom_sha256'], sites=sites)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
