"""Queue real masked VBlank flags and tail-chain service after the current exit."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

HELPER,SIZE=0x7200,512


def sites(image,labels,boot):
    base=65536
    first,last=labels['bulk_ring_bytes'],labels['native_ring_consumer']
    body=image[base+first:base+last]
    result={}
    for name,needle in (('long',bytes.fromhex('bf450500')),('short',bytes.fromhex('bd4505'))):
        if body.count(needle)!=1:raise ValueError('Changed ring load preimage')
        result[name]=first+body.index(needle)
    first,last=labels['nmi_rti_return'],labels['apu_length_write']
    body=image[base+first:base+last]
    needle=bytes.fromhex('68a868aa6848dabae8e8e8e8')
    if body.count(needle)!=1:raise ValueError('Changed NMI return-stack policy')
    result['return']=first+body.index(needle)
    entry=boot['nmi']
    if image[entry:entry+7]!=bytes.fromhex('9c004248ad1042'):
        raise ValueError('Changed native NMI acknowledgment entry')
    return result


def patch(image,helper,entries,where):
    if len(image)!=0x200000 or len(helper)!=SIZE:
        raise ValueError('Wrong ROM/helper extent')
    changes=(('long',bytes.fromhex('bf450500'),b'\x22'+entries['ring_read_long'].to_bytes(2,'little')+b'\xc1'),
             ('short',bytes.fromhex('bd4505'),b'\x20'+entries['ring_read_short'].to_bytes(2,'little')),
             ('return',bytes.fromhex('68a868'),b'\x4c'+entries['queued_return'].to_bytes(2,'little')))
    if any(not HELPER<=v<HELPER+SIZE for v in entries.values()):
        raise ValueError('Helper entries outside allocation')
    result=bytearray(image); allowed=set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        base=bank*65536
        if image[base+HELPER:base+HELPER+SIZE]!=b'\xff'*SIZE:
            raise ValueError('Occupied queue helper')
        for name,old,new in changes:
            at=base+where[name]
            if image[at:at+len(old)]!=old:raise ValueError('Different mirrored caller')
            result[at:at+len(old)]=new;allowed.update(range(at,at+len(old)))
        result[base+HELPER:base+HELPER+SIZE]=helper
        allowed.update(range(base+HELPER,base+HELPER+SIZE))
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result)


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text()); rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or meta['experimental_raster']:
        raise ValueError('Wrong parent/source')
    if meta.get('experimental_ring_dirty_cache') or meta.get('experimental_ring_stride_cache'):
        raise ValueError('Queue poll placement requires the original ring implementation')
    labels=symbols(parent/'native_runtime.lbl'); boot=symbols(parent/'native_boot.lbl')
    image=rom.read_bytes(); where=sites(image,labels,boot)
    defs=dict(RETURN_BODY=where['return']+3,NMI_AFTER_ACK=boot['nmi']+7)
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'queued-vblank.o'),'snes/queued_vblank.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/queued_vblank.cfg','-Ln',str(out/'queued-vblank.lbl'),
        '-o',str(out/'queued-vblank.bin'),str(out/'queued-vblank.o')],check=True)
    entries=symbols(out/'queued-vblank.lbl')
    (out/'native-cpu.sfc').write_bytes(patch(image,(out/'queued-vblank.bin').read_bytes(),entries,where))
    files=[Path(__file__),Path('snes/queued_vblank.asm'),Path('snes/queued_vblank.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('tools/build_retained_producer_guard.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',
        parent/'native_runtime.lbl',parent/'native_boot.lbl',out/'queued-vblank.bin',out/'queued-vblank.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_queued_vblank=dict(
        parent=str(parent),helper=HELPER,size=SIZE,sites=where,entries=entries,definitions=defs,
        sources={str(p):sha(p) for p in files},scope=__doc__,release_ready=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],sites=where)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
