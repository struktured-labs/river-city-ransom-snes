"""Controlled one-immediate hidden-row budget experiment on the exact game ROM.

No instruction layout, audio engine, game data, graphics, or splash changes.
The existing transition-state-2 guard remains byte-for-byte intact.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct

from tools.benchmark_report import sha


def patch(image, start, end, before, budget):
    if not all(type(v) is int for v in (start, end, before, budget)) or not (
            0x8000 <= start < end < 0xffc0 and 1 <= before <= 16 and 1 <= budget <= 16):
        raise ValueError('Invalid producer range or bounded row budget')
    pattern = bytes.fromhex('ada01cc902d004a9')+bytes((before,))
    block = image[start:end]
    if block.count(pattern) != 1:
        raise ValueError('Missing/nonunique guarded producer preimage')
    at = start+block.index(pattern)+len(pattern)-1
    result = bytearray(image)
    result[at] = budget
    result[0xffdc:0xffe0] = b'\xff\xff\0\0'
    checksum = sum(result) & 65535
    struct.pack_into('<HH', result, 0xffdc, checksum ^ 65535, checksum)
    return bytes(result), at


def build(parent, budget, out):
    manifest = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != manifest['rom_sha256']:
        raise ValueError('Different parent cartridge')
    labels = {r.split()[2].lstrip('.'):int(r.split()[1],16)
              for r in (parent/'native_boot.lbl').read_text().splitlines()}
    original = (parent/'native-cpu.sfc').read_bytes()
    data, at = patch(original, labels['native_prepare'], labels['prepare_palette'],
                     manifest['experimental_hidden_rows'], budget)
    changed = [i for i,(a,b) in enumerate(zip(original,data)) if a != b]
    if any(i != at and not 0xffdc <= i < 0xffe0 for i in changed):
        raise ValueError('Unrelated ROM mutation')
    shutil.copytree(parent,out)
    (out/'native-cpu.sfc').write_bytes(data)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_hidden_rows=budget,
        hidden_budget_trial=dict(previous_budget=json.loads((parent/'manifest.json').read_text())['experimental_hidden_rows'],
            budget=budget, offset=at, changed_bytes=changed, release_ready=False,
            sources={str(p):sha(p) for p in (Path(__file__), parent/'manifest.json',
                parent/'native-cpu.sfc', parent/'native_boot.lbl')}))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(budget=budget,offset=at,changed_bytes=len(changed),sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--budget',type=int,required=True)
    build(**vars(parser.parse_args()))
