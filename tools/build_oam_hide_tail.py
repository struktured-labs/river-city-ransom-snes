"""Default-off unrolled original unused-sprite hiding, with no altered game ticks."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ADDRESS = 0xDFE2
HELPER = 0x7C00
ORIGINAL = bytes.fromhex('ae2d05f010a9f0e004f00a9d0002cacacaca4ce9df60')
HOOK = bytes.fromhex('4c007c')


def assemble(out):
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out/'hide.o'),
                    'snes/oam_hide_tail.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/oam_hide_tail.cfg',
                    '-o', str(out/'hide.bin'), str(out/'hide.o')], check=True)
    return (out/'hide.bin').read_bytes()


def patch(image, helper):
    if len(image) != 0x200000 or len(helper) != 0x300 or helper[:3] != ORIGINAL[:3]:
        raise ValueError('Wrong cartridge or helper shape')
    result = bytearray(image)
    allowed = set(range(0xFFDC, 0xFFE0))
    for bank in range(1, 9):
        base = bank*65536
        if image[base+ADDRESS:base+ADDRESS+len(ORIGINAL)] != ORIGINAL:
            raise ValueError('Changed original sprite-hide routine')
        if image[base+HELPER:base+HELPER+len(helper)] != b'\xff'*len(helper):
            raise ValueError('Occupied helper padding')
        result[base+ADDRESS:base+ADDRESS+3] = HOOK
        result[base+HELPER:base+HELPER+len(helper)] = helper
        allowed.update(range(base+ADDRESS, base+ADDRESS+3))
        allowed.update(range(base+HELPER, base+HELPER+len(helper)))
    checksum(result)
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Unrelated cartridge change')
    return bytes(result)


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    rom = parent/'native-cpu.sfc'
    manifest = json.loads((parent/'manifest.json').read_text())
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Changed parent')
    shutil.copytree(parent, out)
    helper = assemble(out)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(), helper))
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_oam_hide_tail=dict(
        default_enabled=False, release_ready=False, address=ADDRESS, helper=HELPER,
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/oam_hide_tail.asm'),
            Path('snes/oam_hide_tail.cfg'), Path('tools/build_inline_pitch_trial.py'),
            rom, parent/'manifest.json', out/'hide.bin')},
        scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
