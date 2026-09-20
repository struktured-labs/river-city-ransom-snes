"""Test full-ring row discovery without changing DMA byte/time limits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = 'ac0640cd708a62e2b7568f2c92e8f64e416bdd1b4154c0bf5279f18984275fae'
SITE = 0x838D
PREIMAGE = bytes.fromhex('a02000ada01c29ff00c90200d003a08000')


def patch(image):
    if hashlib.sha256(image).hexdigest() != PARENT_SHA:
        raise ValueError('Need exact guarded-volume parent')
    if image[SITE:SITE+len(PREIMAGE)] != PREIMAGE:
        raise ValueError('Changed row-scan budget preimage')
    result = bytearray(image)
    result[SITE+1] = 128
    checksum(result)
    changes = [i for i, (a, b) in enumerate(zip(image, result)) if a != b]
    if any(i != SITE+1 and not 0xFFDC <= i < 0xFFE0 for i in changes):
        raise ValueError('Unrelated mutation')
    return bytes(result), changes


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Changed parent manifest')
    image, changes = patch(rom.read_bytes())
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    paths = [Path(__file__), Path('tests/test_full_row_scan.py'),
             Path('tools/build_inline_pitch_trial.py'), rom, parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_full_row_scan=dict(
        parent=str(parent), scan_entries_before=32, scan_entries_after=128,
        changed_offsets=changes, sources={str(p): sha(p) for p in paths},
        release_ready=False, scope=__doc__+' Existing row_room/final_room guards, '
        '2048-byte budget, immutable staged-row ownership and hidden scan unchanged.'))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], changes=changes)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent', 'out'):
        p.add_argument('--'+k, type=Path, required=True)
    build(**vars(p.parse_args()))
