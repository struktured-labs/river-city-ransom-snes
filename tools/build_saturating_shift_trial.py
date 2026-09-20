"""Default-off, bank-replicated shortcut for a 256-count signed-shift entry."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_signed_shift_trial import ADDRESS, OPTIMIZED

HELPER = 0x7fc0
HOOK = bytes.fromhex('a2054cc07f')+b'\xea'*12


def patch(image, helper):
    if len(helper) != 64 or len(HOOK) != len(OPTIMIZED):
        raise ValueError('Unexpected helper/hook size')
    result = bytearray(image)
    allowed = set(range(0xffdc, 0xffe0))
    for bank in range(1, 9):
        base = bank*65536
        at, gap = base+ADDRESS, base+HELPER
        if (image[at:at+17] != OPTIMIZED or image[gap:gap+64] != b'\xff'*64 or
                image[at+17:at+20] != bytes.fromhex('a52638')):
            raise ValueError('Changed loop, continuation or occupied replicated helper space')
        result[at:at+17] = HOOK
        result[gap:gap+64] = helper
        allowed.update(range(at, at+17)); allowed.update(range(gap, gap+64))
    checksum(result)
    if len(result) != len(image) or any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result)


def assemble(out):
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out/'helper.o'), 'snes/saturating_shift.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/saturating_shift.cfg', '-Ln', str(out/'helper.lbl'),
                    '-o', str(out/'helper.bin'), str(out/'helper.o')], check=True)
    return (out/'helper.bin').read_bytes()


def build(parent, out):
    manifest = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256'] or not manifest.get('experimental_signed_shift'):
        raise ValueError('Need exact signed-shift parent')
    shutil.copytree(parent, out)
    helper = assemble(out)
    changed = patch(rom.read_bytes(), helper)
    (out/'native-cpu.sfc').write_bytes(changed)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_saturating_shift=dict(
        entry=ADDRESS, body_entry=ADDRESS+2, helper=HELPER, continuation=ADDRESS+17,
        banks=list(range(1, 9)), hook=HOOK.hex(), default_enabled=False, release_ready=False,
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/saturating_shift.asm'),
            Path('snes/saturating_shift.cfg'), Path('tools/build_signed_shift_trial.py'),
            Path('tools/build_inline_pitch_trial.py'), rom, parent/'manifest.json', out/'helper.bin')},
        scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
