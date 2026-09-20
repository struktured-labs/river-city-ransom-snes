"""Experimental real sound-driver phase80 with explicit deferred ownership."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

PARENT = '8a184ed9c0d24e3a70a2f99caac17f6c4aa1654f66b3dc072412cffcd546b0af'


def build(parent, out):
    rom = parent/'native-cpu.sfc'
    if out.exists() or sha(rom) != PARENT:
        raise ValueError('Exact3631 and fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    if meta['rom_sha256'] != PARENT:
        raise ValueError('Changed manifest')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out/'phase.o'),
                    'snes/audio_phase_trial.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_phase_trial.cfg',
                    '-Ln', str(out/'phase.lbl'), '-o', str(out/'phase.bin'),
                    str(out/'phase.o')], check=True)
    labels = symbols(out/'phase.lbl')
    original = rom.read_bytes()
    image = bytearray(original)
    changes = []

    def replace(offset, before, after, purpose):
        if len(before) != len(after) or image[offset:offset+len(before)] != before:
            raise ValueError(f'Changed {purpose} at {offset:x}')
        image[offset:offset+len(after)] = after
        changes.append(dict(offset=offset, before=before.hex(), after=after.hex(), purpose=purpose))

    def call(label):
        return b'\x22'+labels[label].to_bytes(2, 'little')+b'\xc1'

    helper = (out/'phase.bin').read_bytes()
    for bank in range(1, 9):
        base = bank << 16
        replace(base+0x7800, b'\xff'*len(helper), helper, 'scheduler')
        replace(base+0x3325, bytes.fromhex('adfd1cf016'),
                b'\x4c'+labels['exit_gate'].to_bytes(2, 'little')+b'\xea\xea', 'exit ownership')
        # Full opcode context; exclude the shadow query that does not enable IRQ.
        locations = []
        for offset in range(base, base+65536):
            if original.startswith(bytes.fromhex('ad201c29808d0042'), offset) or original.startswith(
                    bytes.fromhex('ad201c2980f0038d0042'), offset):
                locations.append(offset)
        if len(locations) != 43:
            raise ValueError(f'Unexpected enable-site count {len(locations)}')
        for offset in locations:
            replace(offset, bytes.fromhex('ad201c2980'), call('recover')+b'\xea', 'guarded enable')
    early_sites = [i for i in range(len(original)) if original.startswith(bytes.fromhex('22005fc1'), i)]
    # New helper service calls are deliberately not in the original search.
    if len(early_sites) != 9:
        raise ValueError(f'Unexpected early-audio sites {early_sites}')
    for offset in early_sites:
        replace(offset, bytes.fromhex('22005fc1'), call('arm'), 'early driver becomes owned pending tick')
    # Drain old pending work before graphics on the next real NMI.
    wrapper = call('drain')+bytes.fromhex('4c9381')
    replace(0xd900, b'\xff'*len(wrapper), wrapper, 'fallback wrapper')
    replace(0x810d, bytes.fromhex('209381'), bytes.fromhex('2000d9'), 'native publisher hook')
    replace(0x8222, bytes.fromhex('48ad11426840'),
            b'\x5c'+labels['irq_entry'].to_bytes(2, 'little')+b'\xc1\xea\xea', 'IRQ entry')
    checksum(image)
    (out/'native-cpu.sfc').write_bytes(image)
    sources = [Path(__file__), Path('snes/audio_phase_trial.asm'), Path('snes/audio_phase_trial.cfg'),
               Path('tools/build_inline_pitch_trial.py'), Path('tools/build_retained_producer_guard.py'),
               Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), rom, parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_audio_phase=dict(
        sources={str(p):sha(p) for p in sources}, changes=changes, labels=labels,
        release_ready=False, scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], patches=len(changes))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
