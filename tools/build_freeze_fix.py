"""Freeze fix and Gamer stamina bar scale on top of a rumble build (4294).

Freeze: three helper layers (difficulty modes, Gamer outline, rumble) read
their tables with PHB / PHK / PLB ... PLB, i.e. DB = the program bank ($C1-$C8)
for a few instructions with NMI enabled. The NMI handler and the translated
game use absolute addressing and assume DB mirrors the system area, so an NMI
inside that window ran with DB=$C5: its "STZ $4200" / "LDA $4210" hit ROM and
the NMI tail's "LDA $4212 / BMI" at $339x read ROM with bit 7 set forever.
The fixed helpers read their tables with long addressing and never change DB.
They are re-assembled from the edited sources; every label keeps its address
and only the bytes that differ from the parent's sources are written, after
checking the parent ROM holds the parent's bytes there.

Stamina bar: snes/stamina_bar.asm at $6D00 in banks 1-8; bank 1 $BB86 (the
HUD bar's "(stamina + 7) / 8") calls stam_ticks, which keeps the original
computation outside Gamer mode and uses ceil(stamina / 16) in Gamer mode.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_COMMIT = '235d561'
HELPERS = (('difficulty_modes', 0x7058, 0x1A8),
           ('gamer_outline', 0x6900, 0x200),
           ('rumble', 0x6B00, 0x200))
BAR_SLOT, BAR_SIZE = 0x6D00, 0x100
HUD = 0x10000 + 0xBB86                     # SNES bank 1 = NES bank 0 $BB86
OLD_HUD = bytes.fromhex('b9bf04186907aaa008207bdf')
BANKS = range(1, 9)
DB_WINDOW = bytes.fromhex('4bab')          # phk / plb


def assemble(source_text, cfg, work, name):
    src = work / f'{name}.asm'
    src.write_text(source_text)
    subprocess.run(['.deps/cc65/bin/ca65', '-I', 'snes', '-o', str(work / f'{name}.o'), str(src)], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', cfg, '-Ln', str(work / f'{name}.lbl'),
                    '-o', str(work / f'{name}.bin'), str(work / f'{name}.o')], check=True)
    names = {}
    for line in (work / f'{name}.lbl').read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == 'al':
            names[parts[2].lstrip('.')] = int(parts[1], 16)
    return (work / f'{name}.bin').read_bytes(), names


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM does not match its manifest')
    if not meta.get('experimental_rumble'):
        raise ValueError('Parent is not a rumble build')
    if meta.get('freeze_fix'):
        raise ValueError('Parent already has the freeze fix')
    work = Path(tempfile.mkdtemp(prefix='freeze-fix-'))
    parent_bytes = rom.read_bytes()
    image = bytearray(parent_bytes)
    allowed = set(range(0xffdc, 0xffe0))
    changed = {}
    for name, slot, size in HELPERS:
        old_src = subprocess.run(['git', 'show', f'{PARENT_COMMIT}:snes/{name}.asm'], check=True,
                                 capture_output=True, text=True).stdout
        cfg = f'snes/{name}.cfg'
        old, old_names = assemble(old_src, cfg, work, f'{name}-parent')
        new, new_names = assemble(Path(f'snes/{name}.asm').read_text(), cfg, work, name)
        if len(old) != size or len(new) != size:
            raise ValueError(f'{name}: helper size changed')
        if old_names != new_names:
            moved = {k: (old_names.get(k), new_names.get(k)) for k in set(old_names) | set(new_names)
                     if old_names.get(k) != new_names.get(k)}
            raise ValueError(f'{name}: labels moved {moved}')
        if DB_WINDOW in new:
            raise ValueError(f'{name}: still has a PHK/PLB window')
        diff = [i for i in range(size) if old[i] != new[i]]
        for bank in BANKS:
            base = bank * 65536 + slot
            for i in diff:
                if image[base + i] != old[i]:
                    raise ValueError(f'{name}: bank {bank} ${slot + i:04X} is not the parent source byte')
                image[base + i] = new[i]
                allowed.add(base + i)
        changed[name] = dict(slot=f'${slot:04X}', bytes_per_bank=len(diff),
                             first=f'${slot + diff[0]:04X}', last=f'${slot + diff[-1]:04X}')
    bar, bar_names = assemble(Path('snes/stamina_bar.asm').read_text(), 'snes/stamina_bar.cfg', work, 'stamina_bar')
    if len(bar) != BAR_SIZE:
        raise ValueError('stamina_bar size')
    entry = bar_names['stam_ticks']
    if bar[entry - BAR_SLOT:entry - BAR_SLOT + 3] != bytes.fromhex('08e230'):
        raise ValueError('stam_ticks does not save P and pin 8-bit registers at entry')
    if DB_WINDOW in bar:
        raise ValueError('stamina_bar changes DB')
    for bank in BANKS:
        base = bank * 65536 + BAR_SLOT
        if image[base:base + BAR_SIZE] != b'\xff' * BAR_SIZE:
            raise ValueError(f'Occupied stamina-bar slot in bank {bank}')
        image[base:base + BAR_SIZE] = bar
        allowed.update(range(base, base + BAR_SIZE))
    if image[HUD:HUD + len(OLD_HUD)] != OLD_HUD:
        raise ValueError('HUD bar code moved')
    # jsr stam_ticks / bra over the rest of the replaced sequence
    hook = b'\x20' + entry.to_bytes(2, 'little') + b'\x80' + bytes([len(OLD_HUD) - 5]) + b'\xea' * (len(OLD_HUD) - 5)
    image[HUD:HUD + len(OLD_HUD)] = hook
    allowed.update(range(HUD, HUD + len(OLD_HUD)))
    # No helper slot of any bank may keep a DB = program-bank window.
    for bank in BANKS:
        for lo, hi in ((0x6900, 0x7200),):
            if DB_WINDOW in image[bank * 65536 + lo:bank * 65536 + hi]:
                raise ValueError(f'PHK/PLB window left in bank {bank} ${lo:04X}-${hi:04X}')
    checksum(image)
    if any(i not in allowed for i, (a, b) in enumerate(zip(parent_bytes, image)) if a != b):
        raise ValueError('Unrelated ROM mutation')
    out.mkdir(parents=True)
    for n in ('native_runtime.lbl', 'gamer_outline.lbl', 'gamer_outline.bin', 'gamer_outline.o',
              'rumble.o', 'rumble.bin', 'rumble.lbl'):
        if (parent / n).exists():
            shutil.copy2(parent / n, out / n)
    for n in ('gamer_outline.bin', 'gamer_outline.lbl', 'rumble.bin', 'rumble.lbl',
              'difficulty_modes.bin', 'difficulty_modes.lbl', 'stamina_bar.bin', 'stamina_bar.lbl'):
        shutil.copy2(work / n, out / n)
    shutil.rmtree(work)
    (out / 'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), freeze_fix=dict(
        parent=str(parent), parent_rom_sha256=sha(rom),
        db_windows_removed=changed,
        stamina_bar=dict(helper=f'${BAR_SLOT:04X}', entry=f'${entry:04X}', hook='bank 1 $BB86',
                         gamer='ceil(stamina/16), 0..16 ticks', other_modes='original (stamina+7)/8'),
        sources={str(p): sha(p) for p in (Path('snes/difficulty_modes.asm'), Path('snes/gamer_outline.asm'),
                                          Path('snes/rumble.asm'), Path('snes/stamina_bar.asm'),
                                          Path('snes/stamina_bar.cfg'), Path(__file__))}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], changed=changed,
                          stam_ticks=hex(entry), bar_used=len(bar.rstrip(b'\xff')))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
