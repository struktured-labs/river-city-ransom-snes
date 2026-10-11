"""Difficulty clamps keep the caller's actor slot in X (build 4300).

clamp_combat/clamp_stam tested the skill with LDX $064C. Their callers, the
spawn loop at $B83E ("LDA $B9D6,Y / JSR $B900 / STA $049F,X", nine stats),
index the stat arrays with X, so every boss-class spawn (class >= 9) stored its
stats at slot $064C instead of its own slot: slot 4 on Intermediate, which is
the next array's slot 0 (Alex). The clamps now test through Y, which apply_*
already restore from $34. Only those 4 bytes change in each of the 8 helper
copies; paint_skill's gamer-outline JMP at $7140 is preserved.
"""
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT = Path('build/autojoy-compat-4299')
PARENT_SHA = '3b442dc89d88'
SLOT = 0x7058
# (offset in helper, shipped byte, fixed byte): LDX abs -> LDY abs, CPX # -> CPY #
EDITS = ((0x4B, 0xAE, 0xAC), (0x4E, 0xE0, 0xC0), (0x69, 0xAE, 0xAC), (0x6C, 0xE0, 0xC0))


def build(out):
    rom = PARENT / 'native-cpu.sfc'
    if not sha(rom).startswith(PARENT_SHA):
        raise ValueError('Parent ROM hash mismatch')
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out / 'difficulty_modes.o'),
                    'snes/difficulty_modes.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/difficulty_modes.cfg',
                    '-Ln', str(out / 'difficulty_modes.lbl'),
                    '-o', str(out / 'difficulty_modes.bin'),
                    str(out / 'difficulty_modes.o')], check=True)
    helper = (out / 'difficulty_modes.bin').read_bytes()
    old = rom.read_bytes()
    b = bytearray(old)
    changes = []
    for bank in range(1, 9):
        base = (bank << 16) + SLOT
        for off, before, after in EDITS:
            if b[base + off] != before or helper[off] != after:
                raise ValueError(f'Unexpected byte at ${base + off:06X}')
            b[base + off] = after
            changes.append(dict(offset=base + off, before=f'{before:02x}', after=f'{after:02x}'))
        # Everything else in the copy must already match the assembled source,
        # apart from the gamer-outline hook on paint_skill.
        diff = [i for i in range(len(helper)) if b[base + i] != helper[i]]
        if diff != [0xE8, 0xE9, 0xEA]:
            raise ValueError(f'Bank {bank} helper diverges from source at {[hex(SLOT + i) for i in diff]}')
    checksum(b)
    for p in PARENT.iterdir():
        if p.is_file() and not (out / p.name).exists():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(b)
    meta = json.loads((PARENT / 'manifest.json').read_text())
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), difficulty_x_fix=dict(
        parent=str(PARENT), changes=changes, hardware_verified=False, scope=__doc__.strip(),
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/difficulty_modes.asm'), rom)}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(meta['rom_sha256'])


if __name__ == '__main__':
    build(Path('build/difficulty-x-fix-4300'))
