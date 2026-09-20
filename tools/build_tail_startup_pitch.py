"""Lower-overhead restart staging: bit branches and tail jumps, same upload."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_balanced_startup_game import patch as balanced_patch
from tools.build_compact_startup_pitch import STAGE, ORDINARY, VALID, sections
from tools.build_inline_pitch_trial import checksum


def bit_relative(origin, target):
    delta = target-(origin+3)
    if not -128 <= delta <= 127:
        raise ValueError('Bit branch out of range')
    return delta & 255


def lower(engine, layout):
    data = bytearray(engine); changes = []
    old_sections = sections()
    for voice in (0, 1):
        site = layout['driver'][f'publish{voice}_audible']+33
        resume = site+7
        address = VALID+1+voice*2
        # BBC preserves A (the already-loaded high DSP register address).
        # Both paths tail-jump back after the old seven-byte publisher tail:
        # no extra CALL/RET pair and no execution of replacement NOP padding.
        stage = bytes((0x13+voice*0x20, 0x54, bit_relative(STAGE[voice], ORDINARY[voice]),
            0xc9, address & 255, address >> 8,
            0xcc, (address+1) & 255, (address+1) >> 8,
            0xe5, VALID & 255, VALID >> 8, 0x08, 1 << voice,
            0xc5, VALID & 255, VALID >> 8,
            0x5f, resume & 255, resume >> 8))
        ordinary = bytes((0x8f, voice*16+2, 0xf2, 0xd8, 0xf3, 0xda, 0xf2,
                          0x5f, resume & 255, resume >> 8))
        for at, old, new in (
            (STAGE[voice], old_sections[STAGE[voice]], stage),
            (ORDINARY[voice], old_sections[ORDINARY[voice]], ordinary),
            (site, bytes((0x3f, STAGE[voice] & 255, STAGE[voice] >> 8))+bytes(4),
             bytes((0x5f, STAGE[voice] & 255, STAGE[voice] >> 8))+bytes(4))):
            offset = at-0x400
            if len(new) > len(old) or data[offset:offset+len(old)] != old:
                raise ValueError('Changed tail helper/preimage or occupied extent')
            new = new+bytes(len(old)-len(new))
            data[offset:offset+len(old)] = new
            changes.append(dict(offset=offset, before=old.hex(), after=new.hex()))
    return bytes(data), dict(changes=changes, scope=__doc__,
        contract='BBC preserves A high-register selector; X/Y contain prefetched pitch. '
                 'Resume instruction overwrites A/N/Z; no extra return address is pushed.')


def patch(engine, layout):
    balanced, detail = balanced_patch(engine, layout)
    result, optimized = lower(balanced, layout)
    return result, dict(detail, tail_optimization=optimized)


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh cartridge required')
    meta = json.loads((parent/'manifest.json').read_text()); rom = parent/'native-cpu.sfc'
    original = rom.read_bytes()
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Unbound parent')
    at = meta['sweep_driver_rom_offset']; size = meta['sweep_driver_layout']['engine_bytes']
    engine, detail = patch(original[at:at+size], meta['sweep_driver_layout'])
    image = bytearray(original); image[at:at+size] = engine; checksum(image)
    if len(engine) != size or any(a != b for i, (a, b) in enumerate(zip(original, image))
        if not (at <= i < at+size or 0xffdc <= i < 0xffe0)):
        raise ValueError('Unrelated ROM/upload change')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image); (out/'engine.bin').write_bytes(engine)
    paths = [Path(__file__), Path('tests/test_tail_startup_pitch.py'),
        Path('tools/build_balanced_startup_game.py'), Path('tools/build_compact_startup_pitch.py'),
        Path('tools/build_inline_pitch_trial.py'), parent/'manifest.json', rom,
        out/'native-cpu.sfc', out/'engine.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_startup_pitch=dict(detail, parent=str(parent), release_ready=False,
            sources={str(p): sha(p) for p in paths}))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'], spc_sha256=meta['spc_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'): p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
