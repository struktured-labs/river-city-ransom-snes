"""Gamer stamina saturates at 255 instead of collapsing to 1 (build 4302, #31).

clamp_stam ran the original "0 or bit 7 set -> 1" test before its Gamer
branch, so Gamer bosses whose base stamina is 96+ (templates 17, 19-22,
Simon 118) spawned with 1. Only clamp_stam's 21 bytes ($70BB-$70CF) change
in each of the 8 helper copies; every exported label keeps its address.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT = Path('build/savestate-bridge-4301')
SLOT = 0x7058
SPAN = (0x70BB, 0x70D0)
PAINT_HOOK = (0xE8, 0xE9, 0xEA)       # gamer_outline's JMP on paint_skill


def assemble(source, out, stem):
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out / f'{stem}.o'), str(source)], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/difficulty_modes.cfg', '-Ln', str(out / f'{stem}.lbl'),
                    '-o', str(out / f'{stem}.bin'), str(out / f'{stem}.o')], check=True)
    return (out / f'{stem}.bin').read_bytes(), (out / f'{stem}.lbl').read_text()


def build(out, base_commit='HEAD'):
    rom = PARENT / 'native-cpu.sfc'
    meta = json.loads((PARENT / 'manifest.json').read_text())
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM hash mismatch')
    out.mkdir(parents=True, exist_ok=False)
    helper, labels = assemble(Path('snes/difficulty_modes.asm'), out, 'difficulty_modes')
    with tempfile.TemporaryDirectory() as d:
        old_src = Path(d) / 'old.asm'
        old_src.write_text(subprocess.run(['git', 'show', f'{base_commit}:snes/difficulty_modes.asm'],
                                          check=True, capture_output=True, text=True).stdout)
        old, old_labels = assemble(old_src, Path(d), 'old')
    if labels != old_labels:
        raise ValueError('Exported labels moved')
    lo, hi = SPAN[0] - SLOT, SPAN[1] - SLOT
    if [i for i in range(len(helper)) if helper[i] != old[i] and not lo <= i < hi]:
        raise ValueError('Source changed outside clamp_stam')
    b = bytearray(rom.read_bytes())
    changes = []
    for bank in range(1, 9):
        base = (bank << 16) + SLOT
        if b[base + lo:base + hi] != old[lo:hi]:
            raise ValueError(f'Bank {bank} clamp_stam preimage mismatch')
        b[base + lo:base + hi] = helper[lo:hi]
        changes.append(dict(offset=base + lo, before=old[lo:hi].hex(), after=helper[lo:hi].hex()))
        diff = [i for i in range(len(helper)) if b[base + i] != helper[i]]
        if tuple(diff) != PAINT_HOOK:
            raise ValueError(f'Bank {bank} helper diverges from source at {[hex(SLOT + i) for i in diff]}')
    checksum(b)
    for p in PARENT.iterdir():
        if p.is_file() and not (out / p.name).exists():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(b)
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), gamer_stam_cap=dict(
        parent=str(PARENT), changes=changes, hardware_verified=False, scope=__doc__.strip(),
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/difficulty_modes.asm'), rom)}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(meta['rom_sha256'])


if __name__ == '__main__':
    build(Path('build/gamer-stam-cap-4302'))
