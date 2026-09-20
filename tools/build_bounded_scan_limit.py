"""Reduce bounded full-ring search work while keeping final-batch admission intact."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT = '09bb1c0fd627fe5e8d4a0201f14bd2a44e2af99f1562270f8a1e3fa596c5ca66'


def patch(image, limit):
    if limit not in (32, 64, 96) or hashlib.sha256(image).hexdigest() != PARENT:
        raise ValueError('Need pinned bounded128 parent and a smaller scan limit')
    if image[0x838d:0x8390] != bytes.fromhex('a08000'):
        raise ValueError('Changed scan operand')
    data = bytearray(image); data[0x838e] = limit; checksum(data)
    return bytes(data)


def build(parent, out, limit):
    if out.exists():
        raise ValueError('Fresh variant required')
    meta = json.loads((parent/'manifest.json').read_text())
    image = patch((parent/'native-cpu.sfc').read_bytes(), limit)
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Changed parent metadata')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    paths = [Path(__file__), Path('tools/build_inline_pitch_trial.py'), parent/'manifest.json', parent/'native-cpu.sfc']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), bounded_scan_limit=dict(limit=limit,
        sources={str(p):sha(p) for p in paths}, release_ready=False, scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), limit=limit, rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'): p.add_argument('--'+k, type=Path, required=True)
    p.add_argument('--limit', type=int, required=True)
    build(**vars(p.parse_args()))
