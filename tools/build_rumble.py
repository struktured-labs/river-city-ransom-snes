"""Rumble on the port-1 pad (MiSTer SNES core / LRG SNES Rumble protocol).

Adds snes/rumble.asm at $6B00 in every bank 1-8 of a gamer-outline build:
the joypad path's exit (@joy_done, "jmp done" at $244C) goes through
rumble_frame, which sends the running pulse's level packet once per frame
after the game's own pad read; the damage routine (SNES bank 5) starts
pulses at $8DD5 (every hit that dealt or blocked a blow) and $8D10 (a hit
on a goon already lying down). See tools/rumble_pulses.py for the table.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.rumble_pulses import pulse_table, weapon_table

SLOT, SIZE = 0x6B00, 0x200
# Weapon profiles (snes/rumble.cfg TAB and WPN areas), free $FF in banks 1-8.
AREAS = ((0x6B00, 0x200), (0x6D24, 0xDC), (0x6F08, 0xF8))
LATCH = 0x8CF4
OLD_LATCH = bytes.fromhex('38e507')             # sec / sbc $07 (stamina - damage)
JOY_DONE = 0x244C
OLD_JOY_DONE = bytes.fromhex('4cd62a')          # jmp done ($2AD6)
HIT_BANK = 5
HIT = 0x8DD5
OLD_HIT = bytes.fromhex('a604bd4f00')           # ldx $04 / lda a:$4F,x
DOWN = 0x8D10
OLD_DOWN = bytes.fromhex('a9129d4f00')          # lda #$12 / sta a:$4F,x
WRIO_STORE = bytes.fromhex('8f014200')          # sta f:$004201


def helper_checks(helper, names):
    for need in ('rumble_frame', 'rumble_hit', 'rumble_down', 'pulse_level', 'pulse_frames'):
        if need not in names:
            raise ValueError(f'{need} is missing from the helper')
    at = lambda n: names[n] - SLOT
    if helper[at('rumble_frame'):at('rumble_frame') + 2] != bytes.fromhex('e230'):
        raise ValueError('rumble_frame does not pin 8-bit registers')
    for n in ('rumble_hit', 'rumble_down'):
        if helper[at(n):at(n) + 3] != bytes.fromhex('08e230'):
            raise ValueError(f'{n} does not save P and pin 8-bit registers')
    if helper.count(bytes.fromhex('28a604bd4f0060')) != 1:
        raise ValueError('rumble_hit must end with the replaced instructions')
    if helper.count(bytes.fromhex('28a9129d4f0060')) != 1:
        raise ValueError('rumble_down must end with the replaced instructions')
    if helper.count(bytes.fromhex('4cd62a')) < 1:
        raise ValueError('rumble_frame never returns to done')
    # every WRIO write keeps bit 7 (port-2 IOBit / counter latch) high
    i = helper.find(WRIO_STORE)
    stores = 0
    while i >= 0:
        stores += 1
        if helper[i - 2] != 0xA9 or not helper[i - 1] & 0x80:
            raise ValueError(f'WRIO store at +{i:#x} is not preceded by lda #imm with bit 7 set')
        i = helper.find(WRIO_STORE, i + 1)
    if stores != 2 or helper.count(bytes.fromhex('a980900' + '2a9c0' + '8f014200')) != 1:
        raise ValueError('Unexpected WRIO stores')
    if bytes.fromhex('9c0142') in helper or bytes.fromhex('9c014200') in helper:
        raise ValueError('stz WRIO would pulse port-2 IOBit')
    table = pulse_table()
    lv = bytes((s << 4) | w for _, s, w, _ in table)
    fr = bytes(f for *_, f in table)
    if helper[at('pulse_level'):at('pulse_level') + len(lv)] != lv:
        raise ValueError('Assembled pulse levels differ from the table')
    if helper[at('pulse_frames'):at('pulse_frames') + len(fr)] != fr:
        raise ValueError('Assembled pulse frames differ from the table')
    for n in ('dmg_latch', 'weapon_of', 'start_weapon', 'env_level', 'wpn_strong', 'kind_class'):
        if n not in names:
            raise ValueError(f'{n} is missing from the helper')
    if names['dmg_latch'] < 0x6D24:
        raise ValueError('Weapon areas not linked')


def assemble(work):
    """Assemble snes/rumble.asm into work/. Returns (main slot bytes,
    [(addr, bytes)] for every area, labels)."""
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(work / 'rumble.o'), 'snes/rumble.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/rumble.cfg', '-Ln', str(work / 'rumble.lbl'),
                    '-o', str(work / 'rumble.bin'), str(work / 'rumble.o')], check=True)
    blob = (work / 'rumble.bin').read_bytes()
    if len(blob) != sum(n for _, n in AREAS):
        raise ValueError(f'Helper is {len(blob)} bytes, areas hold {sum(n for _, n in AREAS)}')
    parts, i = [], 0
    for at, n in AREAS:
        parts.append((at, blob[i:i + n]))
        i += n
    names = {}
    for line in (work / 'rumble.lbl').read_text().splitlines():
        f = line.split()
        if len(f) >= 3 and f[2].startswith('.'):
            names[f[2][1:]] = int(f[1], 16)
    helper_checks(parts[0][1], names)
    return parts[0][1], parts, names


def patch_image(image, parts, names, replace=None):
    """Write the helper areas into banks 1-8 and point the hooks at them.
    replace=None: the areas must be free ($FF) and the hooks original.
    replace=old labels: the parent already has an older rumble helper at
    SLOT; its hooks must point at the old labels (the TAB/WPN areas and the
    damage latch must still be free / original). Returns the changed offsets."""
    allowed = set(range(0xffdc, 0xffe0))
    jmp = lambda n, src: b'\x4c' + src[n].to_bytes(2, 'little')
    jsr = lambda n, src: b'\x20' + src[n].to_bytes(2, 'little') + b'\xea\xea'
    for bank in range(1, 9):
        base = bank * 65536
        for at, data in parts:
            old = image[base + at:base + at + len(data)]
            if old != b'\xff' * len(data) and not (replace and at == SLOT):
                raise ValueError(f'Occupied rumble area ${at:04X} in bank {bank}')
            image[base + at:base + at + len(data)] = data
            allowed.update(range(base + at, base + at + len(data)))
        want = jmp('rumble_frame', replace) if replace else OLD_JOY_DONE
        if image[base + JOY_DONE:base + JOY_DONE + 3] != want:
            raise ValueError(f'@joy_done moved in bank {bank}')
        image[base + JOY_DONE:base + JOY_DONE + 3] = jmp('rumble_frame', names)
        allowed.update(range(base + JOY_DONE, base + JOY_DONE + 3))
    base = HIT_BANK * 65536
    for at, old, name in ((HIT, OLD_HIT, 'rumble_hit'), (DOWN, OLD_DOWN, 'rumble_down')):
        want = jsr(name, replace) if replace else old
        if image[base + at:base + at + 5] != want:
            raise ValueError(f'Damage routine moved at bank {HIT_BANK} ${at:04X}')
        image[base + at:base + at + 5] = jsr(name, names)
        allowed.update(range(base + at, base + at + 5))
    if image[base + LATCH:base + LATCH + 3] != OLD_LATCH:
        raise ValueError(f'Stamina subtraction moved at bank {HIT_BANK} ${LATCH:04X}')
    image[base + LATCH:base + LATCH + 3] = b'\x20' + names['dmg_latch'].to_bytes(2, 'little')
    allowed.update(range(base + LATCH, base + LATCH + 3))
    return allowed


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM does not match its manifest')
    if meta.get('experimental_rumble'):
        raise ValueError('Parent already has rumble')
    final, work = out, Path(tempfile.mkdtemp(prefix='rumble-'))
    helper, parts_, names = assemble(work)
    image = bytearray(rom.read_bytes())
    allowed = patch_image(image, parts_, names)
    checksum(image)
    if any(i not in allowed for i, (a, b) in enumerate(zip(rom.read_bytes(), image)) if a != b):
        raise ValueError('Unrelated ROM mutation')
    final.mkdir(parents=True)
    for n in ('native_runtime.lbl', 'gamer_outline.lbl', 'gamer_outline.bin', 'gamer_outline.o'):
        if (parent / n).exists():
            shutil.copy2(parent / n, final / n)
    for n in ('rumble.o', 'rumble.bin', 'rumble.lbl'):
        shutil.move(str(work / n), final / n)
    shutil.rmtree(work)
    (final / 'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(final / 'native-cpu.sfc'), experimental_rumble=dict(
        parent=str(parent), parent_rom_sha256=sha(rom), helper=SLOT, size=SIZE,
        hooks={'joy_done': f'banks 1-8 ${JOY_DONE:04X}', 'hit': f'bank {HIT_BANK} ${HIT:04X}',
               'down': f'bank {HIT_BANK} ${DOWN:04X}', 'damage_latch': f'bank {HIT_BANK} ${LATCH:04X}'},
        ram='$7EF800-$7EF80D', protocol='LRG SNES Rumble: $72 + level on port-1 IOBit (WRIO bit 6), clocked by $4016 reads',
        pulses=[dict(event=e, strong=s, weak=w, frames=f) for e, s, w, f in pulse_table()],
        weapons=[dict(zip(('weapon', 'strong', 'weak', 'frames', 'envelope'), r)) for r in weapon_table()],
        sources={str(p): sha(p) for p in (Path('snes/rumble.asm'), Path('snes/rumble.cfg'),
                                          Path(__file__), Path('tools/rumble_pulses.py'))}))
    (final / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    used = len(helper.rstrip(b'\xff'))
    print(json.dumps(dict(out=str(final), rom_sha256=meta['rom_sha256'], helper_used=used,
                          helper_slack=SIZE - used, symbols={k: hex(v) for k, v in names.items()})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
