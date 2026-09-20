"""Offline bounded ring pointer/dirty cache. Preserve all PPU writes and ABI."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

HELPER = 0x6900
SIZE = 512
PREFIX = bytes.fromhex('080b9c0042')


def patch(image, helper, entry):
    if len(image) != 0x200000 or len(helper) != SIZE or not 0x2000 < entry < 0x4000:
        raise ValueError('Wrong ROM/helper extent')
    changed = bytearray(image)
    allowed = set(range(0xffdc, 0xffe0))
    body = image[65536+entry:65536+entry+5]
    if body != PREFIX:
        raise ValueError('Wrong ring entry')
    for bank in range(1,9):
        base = bank*65536
        if (image[base+entry:base+entry+5] != PREFIX or
                image[base+HELPER:base+HELPER+SIZE] != b'\xff'*SIZE):
            raise ValueError('Changed entry or occupied helper')
        changed[base+entry:base+entry+5] = b'\x4c'+HELPER.to_bytes(2,'little')+b'\xea\xea'
        changed[base+HELPER:base+HELPER+SIZE] = helper
        allowed.update(range(base+entry,base+entry+5))
        allowed.update(range(base+HELPER,base+HELPER+SIZE))
    checksum(changed)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,changed)) if a != b):
        raise ValueError('Unrelated ROM change')
    return bytes(changed)


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Changed parent')
    labels = symbols(parent/'native_runtime.lbl')
    start, end = labels['bulk_ring_bytes'], labels['native_ring_consumer']
    exits = [int(r.split()[1],16) for r in (parent/'native_runtime.lbl').read_text().splitlines()
             if r.split()[2] == '.@bytes_done' and start < int(r.split()[1],16) < end]
    if len(exits) != 1:
        raise ValueError('Ambiguous ring exit')
    defs = dict(PPU_POINTER=labels['ppu_pointer'],MARK_DIRTY=labels['mark_ppu_dirty'],
                OLD_DONE=exits[0],OLD_BODY=start+5)
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source,out/source.name)
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'ring-dirty.o'),'snes/ring_dirty_cache.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/ring_dirty_cache.cfg',
        '-Ln',str(out/'ring-dirty.lbl'),'-o',str(out/'ring-dirty.bin'),str(out/'ring-dirty.o')],check=True)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(),(out/'ring-dirty.bin').read_bytes(),start))
    paths = [Path(__file__),Path('snes/ring_dirty_cache.asm'),Path('snes/ring_dirty_cache.cfg'),
             Path('tools/build_inline_pitch_trial.py'),Path('tools/build_retained_producer_guard.py'),
             Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,
             parent/'manifest.json',parent/'native_runtime.lbl',out/'ring-dirty.bin',out/'ring-dirty.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ring_dirty_cache=dict(
        parent=str(parent),entry=start,helper=HELPER,size=SIZE,definitions=defs,
        sources={str(p):sha(p) for p in paths},scope=__doc__,release_ready=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
