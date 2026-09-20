"""Isolate timer/recovery phase change; preserve all current interrupt guards."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out, phase):
    rom = parent / 'native-cpu.sfc'
    if (out.exists() or not 1 <= phase < 240 or sha(rom) !=
            '60a73e42f287c3103b21751dca39cd37af1b3d7d31253da828b0979f855f636b'):
        raise ValueError('Exact3695, valid phase and fresh output required')
    image = bytearray(rom.read_bytes())
    changes = []
    for bank in range(1, 9):
        for offset, before in ((0x7849, bytes.fromhex('a9508d0942')),
                               (0x78cf, bytes.fromhex('e0509007'))):
            at = (bank << 16) + offset
            if image[at:at + len(before)] != before:
                raise ValueError(f'Changed phase instruction at {at:x}')
            after = bytearray(before)
            after[1] = phase
            image[at:at + len(before)] = after
            changes.append(dict(offset=at, before=before.hex(), after=after.hex()))
    checksum(image)
    out.mkdir(parents=True)
    for path in parent.iterdir():
        if path.is_file():
            shutil.copy2(path, out / path.name)
    (out / 'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent / 'manifest.json').read_text())
    sources = [Path(__file__), Path('tools/build_inline_pitch_trial.py'), rom,
               parent / 'manifest.json']
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_audio_phase_position=dict(
        sources={str(p): sha(p) for p in sources}, changes=changes, phase=phase,
        release_ready=False, scope=__doc__))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), phase=phase, rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--phase', type=int, required=True)
    build(**vars(parser.parse_args()))
