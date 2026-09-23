"""Patch Intermediate and Gamer Mode onto a native parent (4146)."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ROOT = Path(__file__).resolve().parents[1]
SLOT, SIZE = 0x7058, 0x1A8


def labels(path):
    out = {}
    for line in path.read_text().splitlines():
        if line.startswith('al '):
            parts = line.split()
            out[parts[2].lstrip('.')] = int(parts[1], 16)
    return out


def word(n):
    return struct.pack('<H', n)


def patch_bytes(image, offset, old, new):
    if image[offset:offset + len(old)] != old:
        raise ValueError(f'Preimage mismatch at ${offset:06X}')
    if len(new) > len(old):
        raise ValueError('Patch longer than preimage')
    image[offset:offset + len(new)] = new
    if len(new) < len(old):
        image[offset + len(new):offset + len(old)] = b'\xea' * (len(old) - len(new))


def snes_unique(prg_off):
    bank = prg_off // 0x4000
    return (bank + 1) * 0x10000 + 0x8000 + (prg_off % 0x4000)


def snes_fixed(prg_off):
    rel = prg_off - 0x1C000
    return [(b + 1) * 0x10000 + 0xC000 + rel for b in range(8)]


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM hash mismatch')
    out.mkdir(parents=True)
    for name in ('native_runtime.lbl', 'native_boot.lbl'):
        shutil.copy2(parent / name, out / name)
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out / 'difficulty_modes.o'),
                    'snes/difficulty_modes.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/difficulty_modes.cfg',
                    '-Ln', str(out / 'difficulty_modes.lbl'),
                    '-o', str(out / 'difficulty_modes.bin'),
                    str(out / 'difficulty_modes.o')], check=True)
    helper = (out / 'difficulty_modes.bin').read_bytes()
    if len(helper) != SIZE:
        raise ValueError('Helper size')
    sym = labels(out / 'difficulty_modes.lbl')
    image = bytearray(rom.read_bytes())
    for bank in range(1, 9):
        at = bank * 65536 + SLOT
        if image[at:at + SIZE] != b'\xff' * SIZE:
            raise ValueError('Occupied difficulty slot')
        image[at:at + SIZE] = helper

    def jsr(name):
        return b'\x20' + word(sym[name])

    def jmp(name):
        return b'\x4c' + word(sym[name])

    patch_bytes(image, snes_unique(0x13900), bytes.fromhex('8c3400'), jmp('apply_combat'))
    patch_bytes(image, snes_unique(0x13923), bytes.fromhex('8c3400'), jmp('apply_stam'))
    patch_bytes(image, snes_unique(0x138d1), bytes.fromhex('ac4c06187946b9'), jsr('add_skill'))
    patch_bytes(image, snes_unique(0x17b44), bytes.fromhex('ad4c06c902900160ee4c064c7bbb'), jmp('menu_next'))
    patch_bytes(image, snes_unique(0x17b55), bytes.fromhex('ce4c06d021ee4c0660'), jmp('menu_prev'))
    patch_bytes(image, snes_unique(0x17bfe), bytes.fromhex('20c0e260'), jmp('extra_level'))
    patch_bytes(image, snes_unique(0x17ad5), bytes.fromhex('20c0e2'), jsr('extra_level'))
    patch_bytes(image, snes_unique(0x1a316), bytes.fromhex('bdaf04293f'), jsr('load_agility'))
    patch_bytes(image, snes_unique(0x1a389), bytes.fromhex('bdaf04293f'), jsr('load_agility'))
    for at in snes_fixed(0x1f97c):
        patch_bytes(image, at, bytes.fromhex('a9018d70068d4c0660'), jmp('load_sram'))

    # Original LEVEL script draws NOVICE then ADVANCED. Blank the second
    # name so the first paint is already a single skill.
    packed = bytes.fromhex('46cdced5c8c2c4080048c0c3d5c0cdc2c4c3')
    blanked = bytes.fromhex('460000000000000800480000000000000000')
    if image.count(packed) != 1:
        raise ValueError('LEVEL NOVICE/ADVANCED script not unique')
    at = image.index(packed)
    patch_bytes(image, at, packed, blanked)

    image[0xFFD6] = 2
    image[0xFFD8] = 3
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    meta.update(
        rom_sha256=sha(out / 'native-cpu.sfc'),
        experimental_difficulty_modes=dict(
            parent=str(parent), helper=SLOT, size=SIZE,
            novice=1, intermediate=4, advanced=2, gamer=3,
            sources={str(p): sha(p) for p in (
                Path('snes/difficulty_modes.asm'), Path('snes/difficulty_modes.cfg'),
                Path(__file__), rom, out / 'difficulty_modes.bin')},
            release_ready=False,
        ),
    )
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], symbols={k: hex(v) for k, v in sym.items() if not k.startswith('__')})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
