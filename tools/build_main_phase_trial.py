"""Offline earlier main-loop admission; preserve the existing guarded wait and NMI policy."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

PHASE=64
SIZE=97


def patch(image,start):
    if len(image)!=0x200000 or not 0x2000<start<0x4000:raise ValueError('Wrong image/helper address')
    result=bytearray(image);sites=[];allowed=set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        base=bank*65536+start;body=image[base:base+SIZE]
        if body[:3]!=bytes.fromhex('084820') or body[-3:]!=bytes.fromhex('606860') or body.count(b'\xc9\x80\x90')!=1:
            raise ValueError('Changed phase helper')
        site=base+body.index(b'\xc9\x80\x90')+1
        result[site]=PHASE;sites.append(site);allowed.add(site)
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):raise ValueError('Unrelated change')
    return bytes(result),sites


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or meta['experimental_main_phase_line']!=128:
        raise ValueError('Need authenticated phase128 parent')
    start=symbols(parent/'native_runtime.lbl')['gameplay_phase_start']
    changed,sites=patch(rom.read_bytes(),start)
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(changed)
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),Path('snes/main_phase.inc'),
           rom,parent/'manifest.json',parent/'native_runtime.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_main_phase_line=PHASE,
        experimental_main_phase_reprobe=dict(parent=str(parent),phase=PHASE,old_phase=128,sites=sites,
        start=start,size=SIZE,sources={str(p):sha(p) for p in paths},release_ready=False,
        scope='Only eight compare immediates and checksum change. Existing eligibility, register preservation, '
              'interrupt enable and high-beam no-wrap behavior remain. Camera publication/latency must be requalified.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
