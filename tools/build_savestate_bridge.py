"""MiSTer savestates through a native-vector bridge on the NMI (build 4301).

See snes/savestate_bridge.asm. The emulation NMI vector $FFFA moves from the
original handler ($80FB) to bridge_nmi in free bank-0 space; the native IRQ
vector $FFEE must still point at an RTI (native_interrupt, $8228), which is
the no-save path's return.
"""
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT = Path('build/difficulty-x-fix-4300')
GAME_NMI = 0x80FB
NATIVE_RTI = 0x8228


def word(b, at):
    return b[at] | b[at + 1] << 8


def build(out):
    rom = PARENT / 'native-cpu.sfc'
    meta = json.loads((PARENT / 'manifest.json').read_text())
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Parent ROM hash mismatch')
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out / 'savestate_bridge.o'),
                    'snes/savestate_bridge.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/savestate_bridge.cfg',
                    '-Ln', str(out / 'savestate_bridge.lbl'),
                    '-o', str(out / 'savestate_bridge.bin'),
                    str(out / 'savestate_bridge.o')], check=True)
    names = {ln.split()[2].lstrip('.'): int(ln.split()[1], 16)
             for ln in (out / 'savestate_bridge.lbl').read_text().splitlines()}
    code = (out / 'savestate_bridge.bin').read_bytes()
    at = names['bridge_nmi']
    b = bytearray(rom.read_bytes())
    if b[at:at + len(code)] != b'\xff' * len(code):
        raise ValueError('Bridge space is not free')
    if word(b, 0xFFFA) != GAME_NMI:
        raise ValueError('Emulation NMI vector moved')
    if word(b, 0xFFEE) != NATIVE_RTI or b[NATIVE_RTI] != 0x40:
        raise ValueError('Native IRQ vector must reach an RTI')
    b[at:at + len(code)] = code
    b[0xFFFA:0xFFFC] = at.to_bytes(2, 'little')
    checksum(b)
    for p in PARENT.iterdir():
        if p.is_file() and not (out / p.name).exists():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(b)
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), savestate_bridge=dict(
        parent=str(PARENT), bridge=hex(at), nmi_vector=[hex(GAME_NMI), hex(at)],
        hardware_verified=False, scope=__doc__.strip(),
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/savestate_bridge.asm'),
                                          Path('snes/savestate_bridge.cfg'), rom)}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(meta['rom_sha256'])


if __name__ == '__main__':
    build(Path('build/savestate-bridge-4301'))
