"""Gamer Mode red goon outline and skill name. Does not install the P2 AI.

Goons are chosen by the game's own actor data, not by screen distance. The
NES metasprite writer stores each sprite attribute for actor slot $47; both
stores become a JSR that stores it with NES attribute bit 2 set when slot $47 is an enemy slot
(2-7) whose class $04F5 is a gang member or boss (< $19), outside shops.
The SNES sprite attribute map sends bit 2 to palette +4, and palettes 4-7
are copies of 0-3 whose color 1 (outline) is NES red. The copy is made in
the existing palette batch, which only runs when a palette changed.

The skill name is written only to the NES nametable shadow, only on the
settings screen, and published through the normal dirty-row path.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

# $6900-$6FFF is empty in the parent. Difficulty code begins at $7058.
SLOT, SIZE = 0x6900, 0x200
# Last of the four sprite-palette DMAs in the final palette batch (bank $C0).
# The lda #$B0 that selects palette 3 is 17 bytes before this lda #1.
PALETTE = 0x84F4
OLD_PALETTE = bytes.fromhex('a9018d0b42')
# NES metasprite writer in the fixed bank (every bank 1-8). Its two sprite
# attribute stores, sta $0202,x, become JSR goon_sta:
#   EEDC lda $07 / eor $05 / EEE0 sta $0202,x / lda $31 / beq EEEE
#   EEE7 lda ($30),y / eor $05 / EEEB sta $0202,x / EEEE jmp $3454
META = 0xEEDC
OLD_META = bytes.fromhex('a5074505' '9d0202' 'a531' 'f007' 'b130' '4505' '9d0202' '4c5434')
META_STORES = (0xEEE0, 0xEEEB)
# paint_skill in the difficulty helper. Its entry becomes a JMP to name_paint.
PAINT = 0x7140
OLD_PAINT = bytes.fromhex('08e230ad4c06')
# NES OAM attribute -> SNES OAM attribute table (bank $C0).
ATTR_MAP = 0xC7D3
GOON_BIT = 0x04          # NES attribute bit 2, unused by NES hardware
RED_NES = 0x16
RED_SNES = 0x00BB        # native_palette[$16]
PLAYER_SLOTS = (0, 1)     # Alex, Ryan
ENEMY_SLOTS = range(2, 8)
TOWNSFOLK_CLASS = 0x19    # $04F5 classes: 0-8 gangs, 9-$18 bosses, $19+ townsfolk


def nes_attr_map(goon_red=True):
    """SNES attribute for every NES attribute byte (sprite_attribute_map)."""
    out = []
    for a in range(256):
        v = (a & 0xC0) | ((a & 3) << 1) | (0 if a & 0x20 else 0x30)
        if goon_red and a & GOON_BIT:
            v |= 0x08
        out.append(v)
    return bytes(out)


def outline_colors(colors):
    """Copy one 4-color sprite palette and replace color 1 with NES red."""
    if len(colors) != 4:
        raise ValueError('A sprite palette has 4 colors')
    out = list(colors)
    out[1] = RED_NES
    return out


def is_enemy(slot, actor_class, shop=0):
    """Actor slot $47 and class $04F5,slot, as the metasprite hook tests them."""
    return not shop and slot in ENEMY_SLOTS and actor_class < TOWNSFOLK_CLASS


def marked_attr(attr, slot, actor_class, skill, shop=0):
    """NES attribute after the metasprite hook for a sprite of this actor."""
    if skill == 3 and is_enemy(slot, actor_class, shop):
        return attr | GOON_BIT
    return attr


def sprite_palette(nes_attr, slot, actor_class, skill, shop=0):
    """SNES palette that the sprite ends up on."""
    return (nes_attr_map()[marked_attr(nes_attr, slot, actor_class, skill, shop)] >> 1) & 7


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM does not match its manifest')
    if meta.get('experimental_ai_p2'):
        raise ValueError('Parent already has the companion')
    if meta.get('experimental_gamer_outline'):
        raise ValueError('Parent already has a gamer outline')
    # Assemble in a scratch directory so a failed build leaves no output dir.
    final, out = out, Path(tempfile.mkdtemp(prefix='gamer-outline-'))
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out / 'gamer_outline.o'),
                    'snes/gamer_outline.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/gamer_outline.cfg',
                    '-Ln', str(out / 'gamer_outline.lbl'), '-o', str(out / 'gamer_outline.bin'),
                    str(out / 'gamer_outline.o')], check=True)
    helper = (out / 'gamer_outline.bin').read_bytes()
    if len(helper) != SIZE:
        raise ValueError(f'Helper is {len(helper)} bytes, slot is {SIZE}')
    names = {}
    for line in (out / 'gamer_outline.lbl').read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].startswith('.'):
            names[parts[2][1:]] = int(parts[1], 16)
    for need in ('goon_sta', 'name_paint', 'pal_red'):
        if need not in names:
            raise ValueError(f'{need} is missing from the helper')
    # ca65 sizes immediates from .a8/.i8, not from SEP. A 16-bit LDA #$BB
    # would leave a BRK in the CGRAM write.
    if bytes.fromhex('a9bb00') in helper or bytes.fromhex('a20000') in helper:
        raise ValueError('An immediate was assembled 16-bit')
    if helper.count(bytes.fromhex('a9bb8d2221')) != 4:
        raise ValueError('Red outline color writes missing')
    if helper.count(bytes.fromhex('9d0202')) != 2:
        raise ValueError('goon_sta must perform the attribute store on both paths')
    goon = names['goon_sta'] - SLOT
    # php / sep #$30 first: every hook entry pins its register width.
    if helper[goon:goon + 3] != bytes.fromhex('08e230'):
        raise ValueError('goon_sta does not pin 8-bit registers')
    pal = names['pal_red'] - SLOT
    if helper[pal:pal + 5] != bytes.fromhex('08e220c210'):
        raise ValueError('pal_red does not pin A8/X16')
    image = bytearray(rom.read_bytes())
    work, out = out, final
    out.mkdir(parents=True)
    shutil.copy2(parent / 'native_runtime.lbl', out / 'native_runtime.lbl')
    for name in ('gamer_outline.o', 'gamer_outline.bin', 'gamer_outline.lbl'):
        shutil.move(str(work / name), out / name)
    shutil.rmtree(work)
    if image[PALETTE:PALETTE + len(OLD_PALETTE)] != OLD_PALETTE:
        raise ValueError('Palette DMA site moved')
    if image[PALETTE - 17:PALETTE - 15] != bytes.fromhex('a9b0'):
        raise ValueError('Palette hook is not the palette-3 DMA')
    if image[ATTR_MAP:ATTR_MAP + 256] != nes_attr_map(goon_red=False):
        raise ValueError('Sprite attribute map moved')
    allowed = set(range(0xffdc, 0xffe0))
    allowed.update(range(PALETTE, PALETTE + len(OLD_PALETTE)))
    allowed.update(range(ATTR_MAP, ATTR_MAP + 256))
    pal_red = names['pal_red']
    image[PALETTE:PALETTE + len(OLD_PALETTE)] = (
        bytes((0x22, pal_red & 0xFF, pal_red >> 8, 0xC1)) + b'\xea')
    image[ATTR_MAP:ATTR_MAP + 256] = nes_attr_map()
    for bank in range(1, 9):
        base = bank * 65536
        at = base + SLOT
        if image[at:at + SIZE] != b'\xff' * SIZE:
            raise ValueError('Occupied gamer-outline slot')
        if image[base + META:base + META + len(OLD_META)] != OLD_META:
            raise ValueError(f'Metasprite attribute stores moved in bank {bank}')
        if image[base + PAINT:base + PAINT + len(OLD_PAINT)] != OLD_PAINT:
            raise ValueError(f'paint_skill moved in bank {bank}')
        image[at:at + SIZE] = helper
        for store in META_STORES:
            image[base + store:base + store + 3] = b'\x20' + names['goon_sta'].to_bytes(2, 'little')
            allowed.update(range(base + store, base + store + 3))
        image[base + PAINT:base + PAINT + 3] = b'\x4c' + names['name_paint'].to_bytes(2, 'little')
        allowed.update(range(at, at + SIZE))
        allowed.update(range(base + PAINT, base + PAINT + 3))
    checksum(image)
    if any(i not in allowed for i, (a, b) in enumerate(zip(rom.read_bytes(), image)) if a != b):
        raise ValueError('Unrelated ROM mutation')
    (out / 'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_gamer_outline=dict(
        parent=str(parent), helper=SLOT, size=SIZE, ai_companion=False,
        sources={str(p): sha(p) for p in (
            Path('snes/gamer_outline.asm'), Path('snes/gamer_outline.cfg'), Path(__file__))},
        note=('Goon sprites (actor type 2) get NES attr bit 2 in the metasprite writer; '
              'the SNES attribute map sends it to palette +4 (red outline copies made in '
              'the palette batch). Skill name via NES nametable shadow on the settings screen only.')))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    used = len(helper.rstrip(b'\xff'))
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'],
                          helper_used=used, helper_slack=SIZE - used,
                          symbols={k: hex(v) for k, v in names.items() if not k.startswith('__')})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
