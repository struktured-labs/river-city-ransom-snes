"""Offline late-retained-return guard; preserve the pending producer for next NMI.

The existing camera admission deadline can be bypassed by its retained NMI's
unconditional fallback, followed by another producer. Gate only both direct
NMI-return call sites, only for the exact camera continuation and owned job.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

HELPER=0x7B00


def symbols(path):
    return {r.split()[2].lstrip('.'):int(r.split()[1],16) for r in path.read_text().splitlines()}


def patch(image,helper,labels,entries):
    if len(image)!=0x200000 or len(helper)!=256 or helper[0]!=0x20:
        raise ValueError('Unexpected ROM/helper extent')
    start,end=labels['nmi_rti_return'],labels['apu_length_write']
    if not 0x2000<=start<end<0x4000:
        raise ValueError('Unexpected NMI return range')
    result=bytearray(image);sites=[];allowed=set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        base=bank*65536
        if image[base+HELPER:base+HELPER+256]!=b'\xff'*256:
            raise ValueError('Occupied guard space')
        block=image[base+start:base+end]
        for old,new in (('second_tick_prepare_fallback','guarded_fallback'),
                        ('second_tick_prepare','guarded_prepare')):
            needle=b'\x20'+labels[old].to_bytes(2,'little')
            if block.count(needle)!=1 or not HELPER<=entries[new]<HELPER+256:
                raise ValueError('Missing/ambiguous NMI-return call or wrong entry')
            site=base+start+block.index(needle)
            result[site+1:site+3]=entries[new].to_bytes(2,'little')
            sites.append(dict(site=site,original=labels[old],replacement=entries[new]))
            allowed.update((site+1,site+2))
        result[base+HELPER:base+HELPER+256]=helper
        allowed.update(range(base+HELPER,base+HELPER+256))
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated ROM edit')
    return bytes(result),sites


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or not meta['experimental_second_tick_prepare']:
        raise ValueError('Need authenticated retained-producer candidate')
    labels=symbols(parent/'native_runtime.lbl')
    if labels['camera_deferred_nmi_return']==labels['nmi_rti_return']:
        raise ValueError('Ambiguous continuation')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-D',f'FALLBACK={labels["second_tick_prepare_fallback"]}',
        '-D',f'PREPARE={labels["second_tick_prepare"]}',
        '-D',f'CAMERA_RETURN={labels["camera_deferred_nmi_return"]}',
        '-o',str(out/'retained-guard.o'),'snes/retained_producer_guard.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/retained_producer_guard.cfg',
        '-Ln',str(out/'retained-guard.lbl'),'-o',str(out/'retained-guard.bin'),str(out/'retained-guard.o')],check=True)
    helper=(out/'retained-guard.bin').read_bytes();entries=symbols(out/'retained-guard.lbl')
    changed,sites=patch(rom.read_bytes(),helper,labels,entries)
    (out/'native-cpu.sfc').write_bytes(changed)
    paths=[Path(__file__),Path('snes/retained_producer_guard.asm'),Path('snes/retained_producer_guard.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
        parent/'manifest.json',rom,parent/'native_runtime.lbl',out/'retained-guard.bin',out/'retained-guard.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_retained_producer_guard=dict(
        helper=HELPER,entries=entries,sites=sites,cutoff=194,default_enabled=False,
        release_ready=False,scope=__doc__,sources={str(p):sha(p) for p in paths}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
