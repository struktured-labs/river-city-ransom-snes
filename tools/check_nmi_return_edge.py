"""Execute production return tail and publisher against real NMI/MMIO."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.benchmark_report import sha


def case(core,out,line,delay,served,retained,enabled,stack=255,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    defs=dict(TARGET_LINE=line,DELAY_NOPS=delay,SERVICED_EVENT=int(served),
        RETAINED_RETURN=int(retained),INITIAL_STACK=stack)
    if enabled:defs['EXPERIMENTAL_RETAINED_RETURN_EDGE']=1
    if mutation:defs[mutation]=1
    assembly=Path('snes/nmi_return_edge_test.asm')
    if mutation=='WRONG_STACK_PAGE':
        helper=Path('snes/nmi_return_tail.inc').read_text()
        if helper.count('lda a:$0100,x')!=2:raise ValueError('Nonunique stack mutation')
        (out/'mutated_return_tail.inc').write_text(helper.replace('lda a:$0100,x','lda a:$0200,x'))
        assembly=out/'fixture.asm'
        assembly.write_text(Path('snes/nmi_return_edge_test.asm').read_text().replace(
            '.include "nmi_return_tail.inc"','.include "mutated_return_tail.inc"'))
    subprocess.run(['.deps/cc65/bin/ca65','-g',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I',str(out),'-I','snes','-o',str(out/'test.o'),str(assembly)],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    image=bytearray(2097152);image[0x8000:0x10000]=(out/'test.bin').read_bytes()
    image[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(image)&65535
    struct.pack_into('<HH',image,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(image)
    subprocess.run([sys.executable,'tools/smoke_libretro.py','--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        check=True,capture_output=True,timeout=30)
    ram=(out/'memory.ram').read_bytes()
    if ram[0x6000:0x6005]!=bytes((64,53,86,120,stack)) or ram[0x6006] or ram[0x6007]:
        raise ValueError('Return ABI/depth mismatch: '+ram[0x6000:0x6008].hex())
    if ram[0x1c7b]:raise ValueError('Publisher overran VBlank')
    publisher_line=ram[0x1c7c]|ram[0x1c7d]<<8
    if publisher_line>=243 and ram[0x1d00]!=2:raise ValueError('Late publisher consumed queued row')
    return dict(line=line,delay=delay,served=served,retained=retained,enabled=enabled,stack=stack,
        nmis=ram[0x6005],publisher_entries=ram[0x1c7a],publisher_line=publisher_line,
        queued_row=ram[0x1d00],mutation=mutation,
        artifacts={str(p):sha(p) for p in (out/'test.sfc',out/'memory.ram',out/'receipt.json',out/'test.lbl')})


def check(core,out):
    sources={str(p):sha(p) for p in (Path(__file__),Path('snes/nmi_return_edge_test.asm'),
        Path('snes/nmi_return_tail.inc'),Path('snes/native_video.asm'),Path('snes/interrupt_policy.inc'),core)}
    out.mkdir(parents=True,exist_ok=False);cases=[];controls=[]
    for line,delay,served in ([(239,n,False) for n in (0,20,40,60,80,100,120)]+
                             [(241,0,False),(243,0,False),(250,0,False),(243,0,True),(250,0,True)]):
        name=f'{line}-{delay}-{int(served)}'
        for retained in (False,True):
            old=case(core,out/(name+f'-old-{int(retained)}'),line,delay,served,retained,False)
            new=case(core,out/(name+f'-new-{int(retained)}'),line,delay,served,retained,True)
            if retained and new['nmis']!=1:raise ValueError('Lost or duplicate retained event: '+str(new))
            # The extra stack-identity check changes a few boundary cycles.
            # For an already active VBlank, ordinary returns must still wait;
            # retain all near-edge old/new differences rather than hiding them.
            if not retained and line>=241 and old['nmis']!=new['nmis']:
                raise ValueError('Ordinary return wait policy changed')
            if not retained and new['nmis']>1:raise ValueError('Duplicate ordinary service')
            cases.append(new);controls.append(old)
    for stack in range(256):
        r=case(core,out/f'stack-{stack}',250,0,False,True,True,stack)
        if r['nmis']!=1:raise ValueError('Stack-dependent event loss')
        cases.append(r)
    mutations=[]
    for mutation in ('CLEAR_FRESH','OMIT_ACK','WRONG_STACK_PAGE'):
        r=case(core,out/mutation,250,0,False,True,True,mutation=mutation)
        if r['nmis']==1:raise ValueError('Surviving mutation')
        mutations.append(r)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed fixture source')
    if not any(r['retained'] and r['nmis']==0 for r in controls):raise ValueError('Old lost-edge control did not fail')
    ordinary_edge_differences=[dict(old=a,new=b) for a,b in zip(controls,cases)
        if not b['retained'] and a['nmis']!=b['nmis']]
    report=dict(passed=True,cases=cases,controls=controls,mutations=mutations,sources=sources,
        ordinary_edge_timing_differences=ordinary_edge_differences,
        scope='Production return tail, real SNES interrupt registers and complete production '
        'publisher. Synthetic original P/PCL/PCH/A/X/Y frame; not complete translated game-NMI body. '
        'Fresh/acknowledged events, ordinary-return preservation, register/stack/depth and late '
        'queue preservation checked. Full-game and hardware qualification remain required.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),controls=len(controls),mutations=len(mutations))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
