"""Experimental sprite-only preparation directly after the NES OAM copy."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PREIMAGE = bytes.fromhex('e220a9018d871cc220')
REPLACEMENT = bytes.fromhex('220078c0eaeaeaeaea')


def patch(original, helper, site):
    if len(original) != 0x200000 or len(helper) != 256:
        raise ValueError('Wrong cartridge/helper extent')
    if original[0x7800:0x7900] != b'\xff'*256:
        raise ValueError('Occupied sprite helper slot')
    image = bytearray(original); image[0x7800:0x7900] = helper
    allowed = set(range(0x7800, 0x7900)) | set(range(0xffdc, 0xffe0))
    for bank in range(1, 9):
        at = bank*65536+site
        if original[at:at+9] != PREIMAGE:
            raise ValueError('Changed replicated NES OAM-copy hook')
        image[at:at+9] = REPLACEMENT
        allowed.update(range(at, at+9))
    checksum(image)
    if any(i not in allowed for i, (a, b) in enumerate(zip(original, image)) if a != b):
        raise ValueError('Unrelated cartridge change')
    return image


def build(parent, out):
    if out.exists(): raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']: raise ValueError('Unbound parent')
    boot = labels(parent/'native_boot.lbl'); runtime = labels(parent/'native_runtime.lbl')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p, out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'SPRITE_DELTA={boot["prepare_sprite_delta"]}',
        '-o', str(out/'sprite-copy.o'), 'snes/sprite_copy_prepare.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/sprite_copy_prepare.cfg',
        '-Ln', str(out/'sprite-copy.lbl'), '-o', str(out/'sprite-copy.bin'),
        str(out/'sprite-copy.o')], check=True)
    image = patch(rom.read_bytes(), (out/'sprite-copy.bin').read_bytes(), runtime['@dma_copied'])
    (out/'native-cpu.sfc').write_bytes(image)
    paths = [Path(__file__), Path('snes/sprite_copy_prepare.asm'), Path('snes/sprite_copy_prepare.cfg'),
        Path('tools/audio_packet_log.py'), Path('tools/build_inline_pitch_trial.py'),
        Path('tests/test_sprite_copy_prepare.py'), Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'),
        rom, parent/'manifest.json', parent/'native_boot.lbl', parent/'native_runtime.lbl',
        out/'sprite-copy.bin', out/'sprite-copy.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_sprite_copy_prepare=dict(
        parent=str(parent), site=runtime['@dma_copied'], helper=0x7800,
        delta=boot['prepare_sprite_delta'], sources={str(p): sha(p) for p in paths},
        release_ready=False, scope=__doc__+' Existing delta routine clears dirtiness and requests OAM DMA. '
        'No BG/CHR/palette work is moved. Existing sound engine unchanged. CPU deadline impact unqualified.'))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('parent', 'out'): p.add_argument('--'+key, type=Path, required=True)
    build(**vars(p.parse_args()))
