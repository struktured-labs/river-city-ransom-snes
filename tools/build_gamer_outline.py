"""Gamer clothing outline only. Does not install the P2 companion.

Goon sprites keep their NES palette. The fused OAM tail sets bit 3 so
they use a copy of that palette with a red outline. Shirts stay. The
joypad poll is not used to recolor anyone.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_difficulty_modes import snes_unique
from tools.build_inline_pitch_trial import checksum

# $6900-$6FFF is empty in the parent. Difficulty code begins at $7058.
SLOT, SIZE = 0x6900, 0x400
# Leave the vblank OAM address reset alone. A hook there, and a per-sprite
# call in the prepare loop, blows the Start fade on the MiSTer.
VIDEO = 0x5100
OLD_VIDEO = bytes.fromhex('9c02219c0321')
ATTR_STORE = 0xB55E
OLD_ATTR = bytes.fromhex('9f03507e')
# prepare_sprite_delta tail stays stock. The fused copy is where the
# on-screen attributes are, after each goon's own palette is chosen.
FRAME = 0xC7AB
OLD_FRAME = bytes.fromhex('9c871cad791c')
FUSED = 0x3215
OLD_FUSED = bytes.fromhex('9c871cc230')
# Last of the four sprite-palette DMAs. The lda #$B0 that selects
# palette 3 is 16 bytes before this sta $420B. Used only to draw the
# skill name on the message-speed screen.
PALETTE = 0x84F4
OLD_PALETTE = bytes.fromhex('a9018d0b42')
# Every-frame register write. A hook here froze the MiSTer two seconds
# into the level. Leave it.
FINAL = 0x84F9
OLD_FINAL = bytes.fromhex('ad201c2902')
JOY = 0xFD8E
# paint_skill. Replaced with RTS so the level nametable is not rewritten
# with the skill name outside the message-speed screen.
PAINT = 0x7140
OLD_PAINT = bytes.fromhex('08e230ad4c06')
MENU_JSR = snes_unique(0x17B1F)
RED_NES = 0x16
NEAR = 28


def outline_colors(colors):
    """Copy one 4-color sprite palette and replace color 1 with NES red."""
    if len(colors) != 4:
        raise ValueError('A sprite palette has 4 colors')
    out = list(colors)
    out[1] = RED_NES
    return out


def sprite_palette(index, x, y, anchors, skill, goons=()):
    """SNES palette. A goon's own palette plus 4. Everyone else stays."""
    if skill != 3 or y >= 0xF0 or index > 3:
        return index
    if any(abs(x - anchor) < NEAR for anchor in anchors):
        return index
    if any(abs(x - goon) < 25 for goon in goons):
        return index + 4
    return index


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM does not match its manifest')
    if meta.get('experimental_ai_p2'):
        raise ValueError('Parent already has the companion')
    poll = labels(parent / 'native_runtime.lbl')['native_joypad_poll']
    out.mkdir(parents=True)
    shutil.copy2(parent / 'native_runtime.lbl', out / 'native_runtime.lbl')
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'POLL={poll}',
                    '-o', str(out / 'gamer_outline.o'), 'snes/gamer_outline.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/gamer_outline.cfg',
                    '-Ln', str(out / 'gamer_outline.lbl'), '-o', str(out / 'gamer_outline.bin'),
                    str(out / 'gamer_outline.o')], check=True)
    helper = (out / 'gamer_outline.bin').read_bytes()
    if len(helper) != SIZE:
        raise ValueError(f'Helper is {len(helper)} bytes, slot is {SIZE}')
    if helper[:2] == b'\xff\xff':
        raise ValueError('Helper entry is empty')
    # ca65 sizes immediates from .a8/.i8, not from SEP. A 16-bit LDA #$BB
    # would leave a BRK in the CGRAM write.
    if bytes.fromhex('a9bb00') in helper or bytes.fromhex('a20000') in helper:
        raise ValueError('An immediate was assembled 16-bit')
    if bytes.fromhex('a9bb') not in helper or bytes.fromhex('4cffff') not in helper:
        raise ValueError('Red outline or skill-gate jump missing')
    if bytes.fromhex('4c') + poll.to_bytes(2, 'little') not in helper:
        raise ValueError('Joypad poll jump missing')
    names = {}
    for line in (out / 'gamer_outline.lbl').read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].startswith('.'):
            names[parts[2][1:]] = int(parts[1], 16)
    for need in ('joy_outline', 'fused_outline', 'upload_red', 'menu_skill', 'street_maintain'):
        if need not in names:
            raise ValueError(f'{need} is missing from the helper')
    if names['joy_outline'] != SLOT:
        raise ValueError('Joypad outline is not the helper entry')
    gate = labels(parent / 'difficulty_modes.lbl')['skill_gate']
    helper = bytearray(helper)
    jump = helper.find(bytes.fromhex('4cffff'))
    if jump < 0 or helper.find(bytes.fromhex('4cffff'), jump + 1) >= 0:
        raise ValueError('skill_gate jump is not unique')
    helper[jump + 1:jump + 3] = gate.to_bytes(2, 'little')
    image = bytearray(rom.read_bytes())
    if image[VIDEO:VIDEO + len(OLD_VIDEO)] != OLD_VIDEO:
        raise ValueError('OAM DMA entry moved')
    if image[ATTR_STORE:ATTR_STORE + 4] != OLD_ATTR:
        raise ValueError('Sprite attribute store moved')
    if image[FRAME:FRAME + len(OLD_FRAME)] != OLD_FRAME:
        raise ValueError('Sprite-prepare tail moved')
    if image[FUSED:FUSED + len(OLD_FUSED)] != OLD_FUSED:
        raise ValueError('Fused OAM copy tail moved')
    if image[PALETTE:PALETTE + len(OLD_PALETTE)] != OLD_PALETTE:
        raise ValueError('Palette DMA site moved')
    if image[PALETTE - 17:PALETTE - 15] != bytes.fromhex('a9b0'):
        raise ValueError('Palette hook is not the palette-3 DMA')
    if image[FINAL:FINAL + len(OLD_FINAL)] != OLD_FINAL:
        raise ValueError('Final vblank tail moved')
    for bank in range(1, 9):
        at = bank * 65536 + PAINT
        if image[at:at + len(OLD_PAINT)] != OLD_PAINT:
            raise ValueError(f'paint_skill moved in bank {bank}')
    menu_jsr = image[MENU_JSR:MENU_JSR + 3]
    if menu_jsr != b'\x20' + gate.to_bytes(2, 'little'):
        raise ValueError('Skill menu JSR is not skill_gate')
    joy = b'\x4c' + poll.to_bytes(2, 'little')

    def jsl(name):
        addr = names[name]
        return bytes((0x22, addr & 0xFF, (addr >> 8) & 0xFF, 0xC1))

    allowed = set(range(0xffdc, 0xffe0))
    allowed.update(range(PALETTE, PALETTE + len(OLD_PALETTE)))
    allowed.update(range(MENU_JSR, MENU_JSR + 3))
    allowed.update(range(FINAL, FINAL + len(OLD_FINAL)))
    allowed.update(range(FUSED, FUSED + len(OLD_FUSED)))
    image[PALETTE:PALETTE + len(OLD_PALETTE)] = jsl('upload_red') + b'\xea'
    image[FINAL:FINAL + len(OLD_FINAL)] = jsl('street_maintain') + b'\xea'
    image[FUSED:FUSED + len(OLD_FUSED)] = jsl('fused_outline') + b'\xea'
    image[MENU_JSR:MENU_JSR + 3] = b'\x20' + names['menu_skill'].to_bytes(2, 'little')
    for bank in range(1, 9):
        at = bank * 65536 + PAINT
        allowed.add(at)
        image[at] = 0x60
    joy_hook = b'\x4c' + SLOT.to_bytes(2, 'little')
    for bank in range(1, 9):
        at, hook = bank * 65536 + SLOT, bank * 65536 + JOY
        if image[at:at + SIZE] != b'\xff' * SIZE:
            raise ValueError('Occupied gamer-outline slot')
        if image[hook:hook + 3] != joy:
            raise ValueError('Joypad hook is not the stock poll')
        image[at:at + SIZE] = helper
        image[hook:hook + 3] = joy_hook
        allowed.update(range(at, at + SIZE))
        allowed.update(range(hook, hook + 3))
    checksum(image)
    if any(i not in allowed for i, (a, b) in enumerate(zip(rom.read_bytes(), image)) if a != b):
        raise ValueError('Unrelated ROM mutation')
    if image[VIDEO:VIDEO + len(OLD_VIDEO)] != OLD_VIDEO:
        raise ValueError('OAM DMA hook was modified')
    if image[FRAME:FRAME + len(OLD_FRAME)] != OLD_FRAME:
        raise ValueError('Sprite-prepare tail was modified')
    if image[FUSED] != 0x22 or image[FUSED + 3] != 0xC1:
        raise ValueError('Fused outline hook did not land')
    if image[FINAL] != 0x22 or image[FINAL + 3] != 0xC1:
        raise ValueError('Sidewalk hook did not land')
    if image[0x1fd8e:0x1fd91] != joy_hook:
        raise ValueError('Joypad hook did not land')
    (out / 'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_gamer_outline=dict(
        parent=str(parent), helper=SLOT, size=SIZE, ai_companion=False,
        video=VIDEO,
        note='Gamer outline recolors NES palette 3 from the joypad poll. No P2 AI.'))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    used = next(i for i, b in enumerate(helper) if helper[i:] == b'\xff' * (SIZE - i))
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'],
                          helper_used=used, helper_slack=SIZE - used)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
