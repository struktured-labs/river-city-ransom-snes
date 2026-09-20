"""Retarget only statically known PPU writes; leave generic dispatch and other IO untouched."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_ppu_register_trial import build as assemble_build, HELPER, SIZE, PREFIX
from tools.build_retained_producer_guard import symbols


def patch(image,helper,entry,meta):
    if len(image)!=0x200000 or len(helper)!=SIZE:
        raise ValueError('Wrong image/helper extent')
    stubs = sorted(set(r['stub'] for r in meta['patches']))
    ends = dict(zip(stubs,stubs[1:]+[0x6000+meta['stub_bytes']]))
    targets = sorted(set(r['stub'] for r in meta['patches'] if r.get('opcode') in (0x8d,0x8e,0x8c)
        and r.get('operand',-1)>>8==0x20 and r['operand']&7 in (0,3,5,6)))
    if not targets or any(not 0x6000<=s<ends[s]<=HELPER for s in targets):
        raise ValueError('Invalid target stub table')
    needle = b'\x22'+entry.to_bytes(2,'little')+b'\xc1'
    changed = bytearray(image)
    allowed = set(range(0xffdc,0xffe0))
    sites = []
    for bank in range(1,9):
        base = bank*65536
        if (image[base+entry:base+entry+len(PREFIX)]!=PREFIX or
                image[base+HELPER:base+HELPER+SIZE]!=b'\xff'*SIZE):
            raise ValueError('Dispatcher changed or helper occupied')
        for start in targets:
            block = image[base+start:base+ends[start]]
            if block!=image[65536+start:65536+ends[start]] or block.count(needle)!=1:
                raise ValueError('Different/ambiguous mirrored PPU call')
            at = base+start+block.index(needle)+1
            changed[at:at+2] = HELPER.to_bytes(2,'little')
            sites.append(at)
            allowed.update((at,at+1))
        changed[base+HELPER:base+HELPER+SIZE] = helper
        allowed.update(range(base+HELPER,base+HELPER+SIZE))
    checksum(changed)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,changed)) if a!=b):
        raise ValueError('Unrelated change')
    return bytes(changed),sites,targets


def build(parent,out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:
        raise ValueError('Changed parent')
    entry = symbols(parent/'native_runtime.lbl')['dispatch_write']
    with tempfile.TemporaryDirectory(prefix='rcr-targeted-ppu-') as directory:
        compiled = Path(directory)/'trial'
        assemble_build(parent,compiled)
        helper = (compiled/'ppu-register.bin').read_bytes()
        changed,sites,targets = patch(rom.read_bytes(),helper,entry,meta)
        out.mkdir(parents=True)
        for p in parent.iterdir():
            if p.is_file():
                shutil.copy2(p,out/p.name)
        for name in ('ppu-register.o','ppu-register.bin','ppu-register.lbl'):
            shutil.copy2(compiled/name,out/name)
    (out/'native-cpu.sfc').write_bytes(changed)
    paths = [Path(__file__),Path('tools/build_ppu_register_trial.py'),Path('snes/ppu_register_fast.asm'),
             Path('snes/ppu_register_fast.cfg'),Path('tools/build_inline_pitch_trial.py'),
             Path('tools/build_retained_producer_guard.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
             rom,parent/'manifest.json',parent/'native_runtime.lbl',out/'ppu-register.bin',out/'ppu-register.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ppu_targeted=dict(
        parent=str(parent),helper=HELPER,size=SIZE,entry=entry,sites=sites,targets=targets,
        sources={str(p):sha(p) for p in paths},scope=__doc__,release_ready=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],target_stubs=len(targets))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
