"""Try guarded audio recovery after camera preparation, before retained NMI."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = '83339328e5b5d10847ca76775de80f2b34b3a0e2c8427956e9eb6e0b0452ff24'
# PHP; JSL existing fast_recover; PLP; original LDA1CE0; JMP original BEQ.
# Existing recovery owns context, guards and pending; its returned policy is
# deliberately NOT written to4200 while the camera/retained handoff is masked.
HELPER = bytes.fromhex('08225479c128ade01c4c6b32')


def patch(data):
    image = bytearray(data)
    for bank in range(1, 9):
        base = bank * 65536
        if image[base+0x3268:base+0x326d] != bytes.fromhex('ade01cf01b'):
            raise ValueError('Changed retained NMI entry')
        if image[base+0x7f40:base+0x7f40+len(HELPER)] != b'\xff'*len(HELPER):
            raise ValueError('Occupied helper space')
        if image[base+0x7954:base+0x7963] != bytes.fromhex('ada31cd006ad201c29806b5cbe79c1'):
            raise ValueError('Changed guarded recovery target')
        image[base+0x3268:base+0x326b] = bytes.fromhex('4c407f')
        image[base+0x7f40:base+0x7f40+len(HELPER)] = HELPER
    checksum(image)
    return image


def build(parent, out):
    rom = parent/'native-cpu.sfc'
    if out.exists() or sha(rom) != PARENT_SHA:
        raise ValueError('Exact4033 and fresh output required')
    image = patch(rom.read_bytes())
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copyfile(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent/'manifest.json').read_text())
    paths = [Path(__file__), Path('tests/test_audio_pre_retained.py'),
             Path('tools/build_inline_pitch_trial.py'), rom, parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_audio_pre_retained=dict(
        sources={str(p):sha(p) for p in paths}, helper=HELPER.hex(), release_ready=False, scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent', 'out'):
        p.add_argument('--'+k, type=Path, required=True)
    build(**vars(p.parse_args()))
