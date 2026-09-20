"""Default-off exact native palette compare with loop bookkeeping removed."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ADDRESS = 0xAA9C
HELPER = 0xD300
CHANGED = 0xAAB7
SPRITES = 0xAB20
ORIGINAL = bytes.fromhex('a20000bf003f7fdf80557ed00ee8e8e02000d0efe2204c20ab')
HOOK = bytes.fromhex('4c00d3')


def assemble(out):
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'CHANGED={CHANGED}',
        '-D', f'SPRITES={SPRITES}', '-o', str(out/'compare.o'),
        'snes/palette_compare_unrolled.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/palette_compare_unrolled.cfg',
        '-o', str(out/'compare.bin'), str(out/'compare.o')], check=True)
    return (out/'compare.bin').read_bytes()


def patch(image, helper):
    if len(image) != 0x200000 or len(helper) != 512 or helper[:4] != bytes.fromhex('af003f7f'):
        raise ValueError('Unexpected cartridge/helper shape')
    if image[ADDRESS:ADDRESS+len(ORIGINAL)] != ORIGINAL:
        raise ValueError('Changed palette comparator')
    if image[HELPER:HELPER+512] != b'\xff'*512:
        raise ValueError('Occupied helper padding')
    result = bytearray(image)
    result[ADDRESS:ADDRESS+3] = HOOK
    result[HELPER:HELPER+512] = helper
    checksum(result)
    allowed = set(range(ADDRESS, ADDRESS+3)) | set(range(HELPER, HELPER+512)) | set(range(0xFFDC, 0xFFE0))
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
    labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
              for r in (parent/'native_boot.lbl').read_text().splitlines()}
    if labels['prepare_palette'] != ADDRESS-7 or labels['prepare_sprites'] != SPRITES:
        raise ValueError('Unexpected palette layout')
    shutil.copytree(parent, out)
    helper = assemble(out)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(), helper))
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_palette_compare_unrolled=dict(
        default_enabled=False, release_ready=False, address=ADDRESS, helper=HELPER,
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/palette_compare_unrolled.asm'),
            Path('snes/palette_compare_unrolled.cfg'), Path('tools/build_inline_pitch_trial.py'),
            rom, parent/'manifest.json', parent/'native_boot.lbl', out/'compare.bin')},
        scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
