"""Exercise fresh and acknowledged VBlank edges across camera completion."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

try:
    from .check_hidden_dma import ROOT
    from .check_hidden_row_runs import digest
except ImportError:
    from check_hidden_dma import ROOT
    from check_hidden_row_runs import digest


def case(core,out,line,nops,served,enabled,clear_event=False,omit_ack=False,safe=False,
         static_state=None, static_arm=False, expect_armed=True, mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'snes/native_runtime.asm').read_text()
    hook='camera_deferred_nmi_exit:'+source.split('camera_deferred_nmi_exit:',1)[1].split('\n.endif\n\nnmi_task_return:',1)[0]
    if clear_event:
        hook=hook.replace('    load_interrupt_enable\n    sta $4200','    lda $4210\n    load_interrupt_enable\n    sta $4200',1)
    (out/'camera_hook.inc').write_text(hook+'\n')
    defs=dict(TARGET_LINE=line,DELAY_NOPS=nops,SERVICED_EVENT=int(served))
    if enabled:defs['EXPERIMENTAL_CAMERA_NMI_REENABLE']=1
    if safe:defs['EXPERIMENTAL_CAMERA_SAFE_PUBLISH']=1
    if static_state is not None:
        defs['STATIC_ARM_TEST']=1
        defs.update({'STATIC_'+k.upper():v for k,v in static_state.items()})
    if static_arm:defs['EXPERIMENTAL_STATIC_CAMERA_ARM']=1
    if mutation:
        helper=(ROOT/'snes/camera_static_ready.inc').read_text()
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Nonunique static-arm mutation')
        (out/'camera_static_ready.inc').write_text(helper.replace(old,new))
    if omit_ack:defs['OMIT_ACK']=1
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*[x for k,v in defs.items() for x in ('-D',f'{k}={v}')],
        '-I',str(out),'-I',str(ROOT/'snes'),'-o',str(out/'test.o'),str(ROOT/'snes/camera_edge_test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),'-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes();rom[0xffdc:0xffe0]=b'\xff\xff\0\0'
    total=sum(rom)&65535;struct.pack_into('<HH',rom,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(rom)
    subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','300','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],check=True,capture_output=True,timeout=30)
    ram=(out/'memory.ram').read_bytes()
    if ram[0x6000:0x6005]!=bytes.fromhex('30355678ff'):raise ValueError('Camera hook changed register/stack result')
    low,high=(0,0) if static_state is None and safe and 30<=line<194 else (0x30,1)
    if ram[0xf6]!=0x30 or any(ram[k]!=v for k,v in ((0x1c94,low),(0x1c97,low),(0x1c95,high),(0x1c98,high),(0x1ce1,int(not expect_armed)),(0x1ce0,0))):
        raise ValueError('Camera publication or retained state mismatch')
    if ram[0x1ceb]!=int(expect_armed):raise ValueError('Wrong static-camera arming decision')
    return dict(target_line=line,nops=nops,previously_serviced=served,enabled=enabled,nmi_count=ram[0x6005],
                armed=ram[0x1ceb],static_state=static_state,static_arm=static_arm)


def run(core,out,safe=False):
    out.mkdir(parents=True,exist_ok=False);cases=[];old=[]
    for line,nops,served in ([(239,n,False) for n in (0,20,40,60,80,100,120)]+[(241,0,False),(250,0,False),(243,0,True),(250,0,True)]):
        name=f'{line}-{nops}-{int(served)}'
        result=case(core,out/(name+'-new'),line,nops,served,True,safe=safe)
        if result['nmi_count']!=1:raise ValueError('Fresh event lost or acknowledged event duplicated: '+str(result))
        cases.append(result)
        old.append(case(core,out/(name+'-old'),line,nops,served,False,safe=safe))
    if not any(r['nmi_count']==0 for r in old):raise ValueError('Old wait failed to reproduce lost-event bug')
    negatives=[]
    for name,line,served,clear,omit in (('cleared-fresh-event',241,False,True,False),('unacknowledged-duplicate',243,True,False,True)):
        result=case(core,out/name,line,0,served,True,clear,omit,safe=safe)
        if result['nmi_count']==1:raise ValueError('Interrupt mutant passed: '+name)
        negatives.append(dict(name=name,result=result))
    visible=[]
    if safe:
        for line in (10,29,30,38,158,159,193,194):
            result=case(core,out/f'visible-{line}',line,0,False,True,safe=True)
            # All these calls return before the fixture's line200 measurement
            # cutoff; it deliberately does not wait for a future VBlank.
            if result['nmi_count']!=0:
                raise ValueError('Unexpected visible-edge interrupt count')
            visible.append(result)
    report=dict(passed=True,safe_publication=safe,cases=cases,visible_cases=visible,old_wait_controls=old,negative_controls=negatives,core_sha256=digest(core),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'snes/camera_edge_test.asm',ROOT/'snes/native_runtime.asm',ROOT/'snes/interrupt_policy.inc',ROOT/'snes/camera_publish_safe.inc',ROOT/'snes/camera_static_ready.inc')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.inc','.sfc','.ram','.lbl','.json')},
        scope='Extracted production camera hook against real NMI/MMIO emulation, overscan VBlank at line 240. '
              'Fresh masked edges and previously acknowledged edges must each produce exactly one total service before the next frame. '
              'Caller register/stack and camera-latch values checked. Old wait and cleared-event/missing-ack controls retained.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),old_lost=sum(r['nmi_count']==0 for r in old),mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--safe',action='store_true')
    a=p.parse_args();run(a.core,a.out,a.safe)
