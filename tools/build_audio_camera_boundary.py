"""Experimental safe-boundary audio service before retained camera work."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    rom = parent / 'native-cpu.sfc'
    if out.exists() or sha(rom) != '60a73e42f287c3103b21751dca39cd37af1b3d7d31253da828b0979f855f636b':
        raise ValueError('Exact3695 and fresh output required')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out / p.name)
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out / 'boundary.o'),
                    'snes/audio_camera_boundary.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_camera_boundary.cfg',
                    '-Ln', str(out / 'boundary.lbl'), '-o', str(out / 'boundary.bin'),
                    str(out / 'boundary.o')], check=True)
    helper = (out / 'boundary.bin').read_bytes()
    image = bytearray(rom.read_bytes())
    changes = []
    def change(at, before, after):
        if len(before) != len(after) or image[at:at+len(before)] != before:
            raise ValueError(f'Changed code/padding {at:x}')
        image[at:at+len(before)] = after
        changes.append(dict(offset=at, before=before.hex(), after=after.hex()))
    for bank in range(1, 9):
        base = bank << 16
        if image[base+0x325f:base+0x3262] != bytes.fromhex('209332'):
            raise ValueError('Changed camera continuation')
        change(base+0x7b80, b'\xff' * len(helper), helper)
        change(base+0x325c, bytes.fromhex('9c0042'), bytes.fromhex('4c807b'))
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    sources = [Path(__file__), Path('snes/audio_camera_boundary.asm'),
               Path('snes/audio_camera_boundary.cfg'), Path('tools/build_inline_pitch_trial.py'),
               Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), rom, parent / 'manifest.json']
    meta = json.loads((parent / 'manifest.json').read_text())
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_audio_camera_boundary=dict(
        sources={str(p): sha(p) for p in sources}, changes=changes, release_ready=False, scope=__doc__))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    build(**vars(parser.parse_args()))
