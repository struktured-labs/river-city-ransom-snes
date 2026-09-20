"""Move the repaired offline recorder inside the original two-tick busy wait."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256'] or meta['experimental_raster']:
        raise ValueError('Need authenticated non-raster parent')
    for key in ('diagnostic_camera_log', 'camera_idle_log', 'idle_camera_branch_repair'):
        for p, h in meta[key]['sources'].items():
            if sha(Path(p)) != h:
                raise ValueError('Changed source: '+p)
    image = bytearray(rom.read_bytes())
    original = bytes(image)
    out.mkdir(parents=True)
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out/'wait.o'), 'snes/camera_wait_log.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/camera_wait_log.cfg',
                    '-Ln', str(out/'wait.lbl'), '-o', str(out/'wait.bin'), str(out/'wait.o')], check=True)
    helper = (out/'wait.bin').read_bytes()
    old_stub = bytes.fromhex('20b8fa2200e4c060')
    allowed = set(range(0xFFDC, 0xFFE0))
    for bank in range(1, 9):
        base = bank*65536
        if (image[base+0xF2C6:base+0xF2D0] != bytes.fromhex('20007bad0b01c90290f9') or
                image[base+0x7B00:base+0x7B00+len(helper)] != old_stub+b'\xff'*(len(helper)-len(old_stub))):
            raise ValueError('Changed hook or occupied helper padding')
        image[base+0xF2C6:base+0xF2CC] = bytes.fromhex('20b8fa4c007b')
        image[base+0x7B00:base+0x7B00+len(helper)] = helper
        allowed.update(range(base+0xF2C6, base+0xF2CC))
        allowed.update(range(base+0x7B00, base+0x7B00+len(helper)))
    checksum(image)
    if any(i not in allowed for i, (a,b) in enumerate(zip(original,image)) if a != b):
        raise ValueError('Unrelated mutation')
    (out/'native-cpu.sfc').write_bytes(image)
    for name in ('seed.srm', 'native_boot.lbl', 'native_runtime.lbl', 'logger.lbl', 'logger.bin', 'idle.bin'):
        shutil.copyfile(parent/name, out/name)
    paths = (Path(__file__), Path('snes/camera_wait_log.asm'), Path('snes/camera_wait_log.cfg'),
             Path('tools/build_inline_pitch_trial.py'), rom, parent/'manifest.json')
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), camera_wait_log=dict(
        sources={str(p): sha(p) for p in paths}, helper_bytes=len(helper), qualified=False,
        deployed=False, scope='Original FAB8 call restored. Recorder only inside incomplete '
        'two-tick wait, early scanout, no pending/deferred interrupt context. NMI disabled '
        'before native mode, restored after emulation mode. Admission bound still empirical.'))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], helper_bytes=len(helper))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
