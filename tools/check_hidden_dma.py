"""Exercise real DMA, state-limited budgets, immutable row retirement and VRAM."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def retirement(state,enabled,chr_bytes,row_start,row_runs,queue_gap):
    budget=(4096 if enabled and state==2 else 2048)-chr_bytes
    selected=[];cursor=row_start;visits=32 if budget else 0
    while visits:
        # The consumer tests ready flags before its remaining-byte guard.
        # Even an exhausted batch can skip an unready following slot.
        if cursor==queue_gap:
            cursor=(cursor+1)%128;visits-=1;continue
        if budget<64:break
        size=2 if cursor<127 and budget>=128 and cursor+1!=queue_gap else 1
        if row_runs and state==2:
            size=1
            while cursor+size<128 and (size+1)*64<=budget and cursor+size!=queue_gap:size+=1
        selected.extend(range(cursor,cursor+size));budget-=size*64
        cursor=(cursor+size)%128;visits-=1
    return selected,budget,cursor


def case(core,out,state,enabled,source=None,planar=False,chr_bytes=2048,row_start=0,row_runs=False,queue_gap=None,fastrom=False):
    out.mkdir(parents=True,exist_ok=False)
    flags=['-D',f'TRANSITION_STATE={state}','-D',f'CHR_BYTES={chr_bytes}','-D',f'ROW_START={row_start}']
    if enabled:flags+=['-D','EXPERIMENTAL_HIDDEN_DMA=1']
    if planar:flags+=['-D','EXPERIMENTAL_PLANAR_ROWS=1']
    if row_runs:flags+=['-D','EXPERIMENTAL_HIDDEN_ROW_RUN=1']
    if fastrom:flags+=['-D','FASTROM_TEST=1']
    if queue_gap is not None:flags+=['-D',f'QUEUE_GAP={queue_gap}']
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*flags,'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(source or ROOT/'snes/hidden_dma_test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(rom)&65535;struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum)
    (out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','300',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    selected,budget,cursor=retirement(state,enabled,chr_bytes,row_start,row_runs,queue_gap)
    if state==0 and (planar or row_runs):
        # Visible publication may stop at its beam deadline before the byte
        # budget. Require a nonempty legal queue prefix when work fits, then
        # independently verify every VRAM byte, retained flag and byte count.
        observed=[i for i in selected if ram[0x1d00+i]==1]
        if observed!=selected[:len(observed)] or (selected and not observed):
            raise ValueError('Visible DMA did not retire a nonempty legal prefix')
        selected=observed
        budget=2048-chr_bytes-len(selected)*64
        cursor=(selected[-1]+1)%128 if selected else row_start
        if selected and cursor==queue_gap:cursor=(cursor+1)%128
        if ram[0x1c7b]:raise ValueError('Visible final publication overran VBlank')
    count=len(selected)
    expected=bytearray(0x4000 if planar or row_runs else 0x3000)
    expected[:chr_bytes]=bytes((0x5a,0xa5))*(chr_bytes//2)
    if planar:
        for row in selected:
            start=0x2000+row*64
            expected[start:start+64:2]=ram[0x3000+row*32:0x3020+row*32]
            expected[start+1:start+64:2]=ram[0x4000+row*32:0x4020+row*32]
    else:
        for row in selected:expected[0x2000+row*64:0x2040+row*64]=ram[0x3000+row*64:0x3040+row*64]
    if ram[0x8000:0x8000+len(expected)]!=expected:raise ValueError('VRAM differs from exact bounded CHR/row oracle')
    if ram[0x1d00:0x1d80]!=bytes(1 if row in selected or row==queue_gap else 3 for row in range(128)):
        raise ValueError('Row retirement lost a newer shadow or exceeded its budget')
    if ram[0x1e80:0x1f00]!=bytes(1 if row in selected else 2 for row in range(128)):
        raise ValueError('Initial row requirement retirement mismatch')
    if ram[0x1d80] or ram[0x1ca0]!=state or ram[0x1c74]!=cursor or int.from_bytes(ram[0x1e1a:0x1e1c],'little')!=budget:
        raise ValueError('Unexpected remaining budget, cursor, transition or CHR job')
    return dict(state=state,enabled=enabled,rows_retired=count,chr_bytes=chr_bytes,row_start=row_start,queue_gap=queue_gap,vram_bytes=chr_bytes+count*64)


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    cases=[case(core,out/f'state-{s}-enabled-{int(e)}',s,e) for e in (False,True) for s in (0,1,2)]
    original=(ROOT/'snes/native_video.asm').read_text()
    mutations=(('state1-leak',1,'cmp #2\n    bne @normal_dma_budget','cmp #1\n    bne @normal_dma_budget'),
        ('wrong-state2-budget',2,'lda #4096','lda #2048'),
        ('missing-forced-blank',2,'lda #$80\n    sta $2100\n    jmp @on_time','lda #$0F\n    sta $2100\n    jmp @on_time'))
    negatives=[]
    for name,state,old,new in mutations:
        if original.count(old)!=1:raise ValueError('Ambiguous mutation '+name)
        directory=out/name;directory.mkdir()
        fixture=directory/'hidden_dma_test.asm';fixture.write_bytes((ROOT/'snes/hidden_dma_test.asm').read_bytes())
        (directory/'native_video.asm').write_text(original.replace(old,new))
        try:case(core,directory/'run',state,True,fixture)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Mutant incorrectly passed: '+name)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=True,cases=cases,negative_controls=negatives,core_sha256=digest(core),
        checker_sha256=digest(Path(__file__)),source_sha256={str(p.relative_to(ROOT)):digest(p) for p in
            (ROOT/'snes/native_video.asm',ROOT/'snes/hidden_dma_test.asm')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.sfc','.ram','.asm','.log')},
        scope='One real publisher call: state0 VBlank, state1/state2 active display. Entire 12KiB VRAM readback, '
              '2048-byte CHR plus bounded immutable rows, remaining budget, queue ownership and transition barrier. Not a whole-game timing claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),negative_controls=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
