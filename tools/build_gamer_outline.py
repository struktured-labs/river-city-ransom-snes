"""Gamer Mode red goon outline and skill name. Does not install the P2 AI.

Goons are chosen by the game's own actor data, not by screen distance. The
NES metasprite writer stores each sprite attribute for actor slot $47; both
stores become a JSR that stores it with NES attribute bit 2 set when slot $47 is an enemy slot
(2-7) whose class $04F5 is a gang member or boss (< $19), outside shops.
A held-object part ($0012 = $80) is judged by the held actor $03B7,holder,
so a goon Alex carries stays red and a goon's weapon does not.
The SNES attribute map sends bit 2 to palette +4 for NES palettes 0, 1 and 3
(enemy head, jeans, shirt; palette 2 is items). In the 4bpp sprite tiles every
outline pixel (color 1) that touches a transparent pixel (the outer
silhouette) becomes color 5. Normal sprite palettes get color 5 = color 1 (kept in
the WRAM palette shadow, so the existing sprite palette DMA carries it: one
108-byte DMA replaces the four 8-byte ones); in Gamer palettes 4, 5 and 7 are
copies of 0, 1 and 3 with color 5 red.

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
# The four 22-byte sprite-palette DMA blocks end at PALETTE + 5. Block 0
# (palette 0) becomes one 108-byte DMA of the shadow $7E5500 (colors 0-15 of
# palettes 0-2, 0-5 of palette 3); block 1 becomes the Gamer test and JSL.
PAL_BLOCKS = PALETTE - 83
OLD_PAL_BLOCK = 'a9{:02x}8d2121a2{:02x}558e0243a208008e0543a9018d0b42'
PAL_COUNT = PAL_BLOCKS + 11      # ldx #8 of block 0
PAL_SKIP = PAL_BLOCKS + 22       # start of block 1
# Red copies are current while this WRAM byte is CLEAN (see gamer_outline.asm).
RED_CLEAN, CLEAN = 0x7E551E, 0xA5
# Shadow color-1 stores (sta f:$7E55x2, A16) in pending_palette and the
# indexed prepare_palette store (sta f:$7E5500,x, A16), bank $C0. Each becomes
# a JSL to a helper that also keeps color 5 of the shadow equal to color 1.
SHADOW_STORES = {0x717A: ('8f02557e', 'sh_c1_0'), 0x71BE: ('8f22557e', 'sh_c1_1'),
                 0x7202: ('8f42557e', 'sh_c1_2'), 0x7246: ('8f62557e', 'sh_c1_3'),
                 0xAB14: ('9f00557e', 'sh_idx')}
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
# Zero-extended 4bpp copies of all 8192 CHR tiles (banks $CB-$CE), used only
# for sprites. Planes 2/3 are zero in the parent.
SPRITE_TILES, TILE_COUNT = 0xB0000, 8192
TRANSPARENT, OUTLINE, CLOTHES, SKIN, RED_INDEX = 0, 1, 2, 3, 5
ITEM_PALETTE = 2          # NES sprite palette 2: weapons and items, never red
# NES OAM attribute -> SNES OAM attribute table (bank $C0).
ATTR_MAP = 0xC7D3
GOON_BIT = 0x04          # NES attribute bit 2, unused by NES hardware
RED_NES = 0x16
RED_SNES = 0x00BB        # native_palette[$16]
PLAYER_SLOTS = (0, 1)     # Alex, Ryan
ENEMY_SLOTS = range(2, 8)
TOWNSFOLK_CLASS = 0x19    # $04F5 classes: 0-8 gangs, 9-$18 bosses, $19+ townsfolk


def nes_attr_map(goon_red=True):
    """SNES attribute for every NES attribute byte (sprite_attribute_map).
    Marked sprites on NES palettes 0, 1 and 3 (head, jeans, shirt) move to
    SNES palettes 4, 5 and 7; palette 2 (items) stays put."""
    out = []
    for a in range(256):
        v = (a & 0xC0) | ((a & 3) << 1) | (0 if a & 0x20 else 0x30)
        if goon_red and a & GOON_BIT and a & 3 != ITEM_PALETTE:
            v |= 0x08
        out.append(v)
    return bytes(out)


def outline_colors(colors):
    """SNES sprite palette entries 0-5 for one NES 4-color palette: the normal
    one (color 5 = color 1) and the red copy (color 5 = NES red). Color 4 is
    never used by any tile."""
    if len(colors) != 4:
        raise ValueError('A sprite palette has 4 colors')
    normal = list(colors) + [None, colors[1]]
    red = list(colors) + [None, RED_NES]
    return normal, red


def tile_pixels(tile):
    """8x8 color indices of a SNES 4bpp tile."""
    return [[((tile[2 * r] >> (7 - c)) & 1) | (((tile[2 * r + 1] >> (7 - c)) & 1) << 1)
             | (((tile[16 + 2 * r] >> (7 - c)) & 1) << 2) | (((tile[17 + 2 * r] >> (7 - c)) & 1) << 3)
             for c in range(8)] for r in range(8)]


def outline_tile(tile):
    """Recolor the outer silhouette: outline pixels (color 1) with a
    transparent 4-neighbour inside the tile become color 5 (bitplane 2 set).
    A tile edge counts as not outer (tiles are shared by many metasprites, so
    what lies across the edge is not known here). Interior dark pixels and
    every other color stay as they are. The tile must be zero-extended 2bpp."""
    tile = bytearray(tile)
    if len(tile) != 32 or any(tile[16:]):
        raise ValueError('Expected a zero-extended 4bpp tile')
    px = tile_pixels(tile)
    for r in range(8):
        for c in range(8):
            if px[r][c] != OUTLINE:
                continue
            near = [px[rr][cc] for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                    if 0 <= rr < 8 and 0 <= cc < 8]
            if TRANSPARENT in near:
                tile[16 + 2 * r] |= 0x80 >> c
    return bytes(tile)


# Sprite kind $00CB,slot: 0-7 use the human animation sets (bank 6 $8000);
# $08-$11 are weapons and other objects from the room object list.
BODY_KINDS = range(0, 8)
# $0012 is $80 while the metasprite writer draws a held object as part of its
# holder ($FC branch, $EE34-$EE67).
HELD_PART = 0x80


def is_enemy(slot, actor_class, shop=0, kind=2, part=0):
    """Slot, class $04F5 and kind $00CB of the actor a sprite belongs to (see
    sprite_actor), as the metasprite hook tests them."""
    return (not shop and slot in ENEMY_SLOTS and actor_class < TOWNSFOLK_CLASS
            and kind in BODY_KINDS)


def sprite_actor(slot, part, held):
    """Actor whose sprite is being written: the drawing slot $47, or the held
    actor $03B7,$47 while a held-object part ($0012 bit 7) is drawn."""
    return held if part & HELD_PART else slot


def marked_attr(attr, slot, actor_class, skill, shop=0, kind=2, part=0):
    """NES attribute after the metasprite hook for a sprite of this actor."""
    if skill == 3 and is_enemy(slot, actor_class, shop, kind, part):
        return attr | GOON_BIT
    return attr


def sprite_palette(nes_attr, slot, actor_class, skill, shop=0, kind=2, part=0):
    """SNES palette that the sprite ends up on."""
    return (nes_attr_map()[marked_attr(nes_attr, slot, actor_class, skill, shop, kind, part)] >> 1) & 7


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
    for need in ('goon_sta', 'name_paint', 'pal_red', 'sh_c1_0', 'sh_c1_1', 'sh_c1_2',
                 'sh_c1_3', 'sh_idx'):
        if need not in names:
            raise ValueError(f'{need} is missing from the helper')
    # ca65 sizes immediates from .a8/.i8, not from SEP. A 16-bit LDA #$BB
    # would leave a BRK in the CGRAM write.
    if bytes.fromhex('a9bb00') in helper or bytes.fromhex('a20000') in helper:
        raise ValueError('An immediate was assembled 16-bit')
    if helper.count(bytes.fromhex('a9bb8d2221')) != 3:
        raise ValueError('Red outline color writes missing')
    if helper.count(bytes.fromhex('9d0202')) != 2:
        raise ValueError('goon_sta must perform the attribute store on both paths')
    goon = names['goon_sta'] - SLOT
    # php / sep #$30 first: every hook entry pins its register width.
    if helper[goon:goon + 3] != bytes.fromhex('08e230'):
        raise ValueError('goon_sta does not pin 8-bit registers')
    asm = Path('snes/gamer_outline.asm').read_text()
    if f'RED_CLEAN = ${RED_CLEAN:06X}' not in asm or f'CLEAN = ${CLEAN:02X}' not in asm:
        raise ValueError('RED_CLEAN/CLEAN differ between builder and helper')
    idx = names['sh_idx'] - SLOT
    # sh_idx runs A16: its mask and compare must be 16-bit immediates.
    if helper[idx:idx + 12] != bytes.fromhex('9f00557e488a291f00c90200'):
        raise ValueError('sh_idx was not assembled A16')
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
    for n in range(4):
        old = bytes.fromhex(OLD_PAL_BLOCK.format(0x80 + 16 * n, 32 * n))
        if image[PAL_BLOCKS + 22 * n:PAL_BLOCKS + 22 * (n + 1)] != old:
            raise ValueError(f'Sprite palette DMA block {n} moved')
    for at, (old, _) in SHADOW_STORES.items():
        if image[at:at + 4] != bytes.fromhex(old):
            raise ValueError(f'Shadow color-1 store moved at {at:#x}')
    if image[ATTR_MAP:ATTR_MAP + 256] != nes_attr_map(goon_red=False):
        raise ValueError('Sprite attribute map moved')
    allowed = set(range(0xffdc, 0xffe0))
    allowed.update(range(ATTR_MAP, ATTR_MAP + 256))
    pal_red = names['pal_red']
    if image[PAL_COUNT:PAL_COUNT + 3] != bytes.fromhex('a20800'):
        raise ValueError('Sprite palette DMA count is not at PAL_COUNT')
    image[PAL_COUNT:PAL_COUNT + 3] = bytes.fromhex('a26c00')      # ldx #108
    # In the dropped DMA blocks (A8/X16, DB=0): lda $064C / cmp #3 / bne /
    # lda f:RED_CLEAN / cmp #CLEAN / beq / jsl pal_red / bra past the old
    # palette-3 trigger.
    clean = RED_CLEAN
    skip = (bytes.fromhex('ad4c06' 'c903' 'd00c') + bytes((0xAF, clean & 0xFF, (clean >> 8) & 0xFF, clean >> 16))
            + bytes((0xC9, CLEAN, 0xF0, 0x04))
            + bytes((0x22, pal_red & 0xFF, pal_red >> 8, 0xC1)) + b'\x80')
    skip += bytes((PALETTE + len(OLD_PALETTE) - (PAL_SKIP + len(skip) + 1),))
    image[PAL_SKIP:PAL_SKIP + len(skip)] = skip
    allowed.update(range(PAL_COUNT, PAL_COUNT + 3))
    allowed.update(range(PAL_SKIP, PAL_SKIP + len(skip)))
    for at, (_, name) in SHADOW_STORES.items():
        image[at:at + 4] = bytes((0x22, names[name] & 0xFF, names[name] >> 8, 0xC1))
        allowed.update(range(at, at + 4))
    image[ATTR_MAP:ATTR_MAP + 256] = nes_attr_map()
    recolored = 0
    for t in range(TILE_COUNT):
        at = SPRITE_TILES + 32 * t
        new = outline_tile(image[at:at + 32])
        if new != image[at:at + 32]:
            recolored += 1
            image[at:at + 32] = new
            allowed.update(range(at + 16, at + 32, 2))
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
              'the palette batch). Skill name via NES nametable shadow on the settings screen only. '
              'Silhouette outline pixels (next to transparent) recolored to color 5 in the 4bpp sprite tiles; '
              'red only on color 5 of palettes 4, 5 and 7; shadow color 5 = color 1; one sprite palette DMA; held parts judged by the held actor.'),
        recolored_tiles=recolored))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    used = len(helper.rstrip(b'\xff'))
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], recolored_tiles=recolored,
                          helper_used=used, helper_slack=SIZE - used,
                          symbols={k: hex(v) for k, v in names.items() if not k.startswith('__')})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
