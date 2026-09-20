"""Avoid full audio context-save overhead when no pending camera-boundary tick exists."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    rom = parent / 'native-cpu.sfc'
    if out.exists() or sha(rom) != 'aad7692ad0a8b34e68a4723f277ccc58269d02b8ab7a3318f5ec1a6daf21870d':
        raise ValueError('Exact3737 and fresh output required')
    image = bytearray(rom.read_bytes()); changes = []
    # STZ4200; PHP/PHA; LDA pending; BNE full; PLA/PLP/JMP325F;
    # full: PLA/PLP/JMP7B80. Hidden B is untouched on the inactive path.
    helper = bytes.fromhex('9c00420848ada31cd00568284c5f3268284c807b')
    for bank in range(1, 9):
        for offset, before, after in [(0x7be0, b'\xff'*len(helper), helper),
                                      (0x325c, bytes.fromhex('4c807b'), bytes.fromhex('4ce07b'))]:
            at = (bank << 16) + offset
            if image[at:at+len(before)] != before:
                raise ValueError(f'Changed code/padding at {at:x}')
            image[at:at+len(before)] = after
            changes.append(dict(offset=at, before=before.hex(), after=after.hex()))
    checksum(image); out.mkdir(parents=True)
    for path in parent.iterdir():
        if path.is_file():
            shutil.copy2(path, out / path.name)
    (out / 'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent / 'manifest.json').read_text())
    sources = [Path(__file__), Path('tools/build_inline_pitch_trial.py'), rom, parent / 'manifest.json']
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_audio_boundary_fast=dict(
        sources={str(p): sha(p) for p in sources}, changes=changes, release_ready=False, scope=__doc__))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    build(**vars(parser.parse_args()))
