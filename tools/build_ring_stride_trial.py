"""Offline exact-count PPU ring stride32 pointer cache; no graphics/timer changes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

HELPER=0x6900
PREFIX=bytes.fromhex('080b9c0042')


def assemble(parent,out):
    labels=symbols(parent/'native_runtime.lbl')
    start,end=labels['bulk_ring_bytes'],labels['native_ring_consumer']
    done=[int(r.split()[1],16) for r in (parent/'native_runtime.lbl').read_text().splitlines()
          if r.split()[2]=='.@bytes_done' and start<int(r.split()[1],16)<end]
    if len(done)!=1:raise ValueError('Ambiguous ring exit')
    defs=dict(PPU_POINTER=labels['ppu_pointer'],MARK_DIRTY=labels['mark_ppu_dirty'],
              OLD_DONE=done[0],OLD_BODY=start+len(PREFIX))
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'ring-stride.o'),'snes/ring_stride_cache.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/ring_stride_cache.cfg','-Ln',str(out/'ring-stride.lbl'),
        '-o',str(out/'ring-stride.bin'),str(out/'ring-stride.o')],check=True)
    return (out/'ring-stride.bin').read_bytes(),start,defs


def patch(image,helper,start):
    if len(image)!=0x200000 or len(helper)!=256 or not 0x2000<start<0x4000:
        raise ValueError('Wrong cartridge/helper extent')
    result=bytearray(image);allowed=set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        base=bank*65536
        if image[base+start:base+start+5]!=PREFIX or image[base+HELPER:base+HELPER+256]!=b'\xff'*256:
            raise ValueError('Changed entry or occupied helper space')
        result[base+start:base+start+5]=b'\x4c'+HELPER.to_bytes(2,'little')+b'\xea\xea'
        result[base+HELPER:base+HELPER+256]=helper
        allowed.update(range(base+start,base+start+5));allowed.update(range(base+HELPER,base+HELPER+256))
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result)


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    helper,start,defs=assemble(parent,out)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(),helper,start))
    paths=[Path(__file__),Path('snes/ring_stride_cache.asm'),Path('snes/ring_stride_cache.cfg'),
        Path('tools/build_inline_pitch_trial.py'),parent/'manifest.json',rom,parent/'native_runtime.lbl',
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),out/'ring-stride.bin',out/'ring-stride.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ring_stride_cache=dict(
        parent=str(parent),helper=HELPER,entry=start,definitions=defs,release_ready=False,
        sources={str(p):sha(p) for p in paths},scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
