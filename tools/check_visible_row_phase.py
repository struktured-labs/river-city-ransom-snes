"""Execute production phased row preparation, including untouched deferred queues."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha
from tools.check_hidden_high_cache import initial_flags
from tools.check_visible_attribute_cache import expected

ROOT=Path(__file__).resolve().parents[1]
ADDRESSES=(0x100,0x107,0x3f,0x3e,0x692,0x1ca0,0x10b)
STABLE=(0xc0,0,0,0,4,0)


def budget_for(state):
    task,guard,pause,fade,level,transition,tick=state
    if task&0xc0!=0xc0:return 4
    stable=not (guard&0x80 or pause&0x20 or fade&0x82 or transition) and level==4
    return (4 if tick==1 else 0 if tick==2 else 2) if stable else 2


def case(core,out,state,start=0,mirror=0,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    shadow=bytes((i^(i>>8))&255 for i in range(4096))
    flags=initial_flags(start,mirror)
    (out/'shadow.bin').write_bytes(shadow);(out/'flags.bin').write_bytes(flags)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    source=(ROOT/'snes/native_prepare.asm').read_text().replace(
        '.include "visible_row_phase.inc"',(ROOT/'snes/visible_row_phase.inc').read_text())
    if mutation:
        old,new=mutation
        if source.count(old)!=1:raise ValueError('Ambiguous phase mutation')
        source=source.replace(old,new)
    (out/'native_prepare.asm').write_text(source)
    fixture=(ROOT/'snes/hidden_high_cache_test.asm').read_text()
    setup='\n'.join(f'    lda #${v:02X}\n    sta a:${a:04X}' for a,v in zip(ADDRESSES,state))
    fixture=fixture.replace('        sta $0100','        sta $0100\n'+setup)
    fixture=fixture.replace('cache_test_return:',
        'cache_test_return:\n    rep #$20\n    .a16\n    tdc\n    sta f:$7E6000\n'
        '    tsc\n    sta f:$7E6002\n    sep #$20\n    .a8\n    phb\n    pla\n    sta f:$7E6004')
    (out/'test.asm').write_text(fixture)
    defs=dict(SOURCE_ROW=start,MIRROR_MODE=mirror,PATTERN_HALF=0,CALLS=1,TRANSITION_STATE=0,
        EXPERIMENTAL_ATTRIBUTE_LOOKUP=1,EXPERIMENTAL_FUSED_ALIAS_ROWS=1,
        EXPERIMENTAL_ALIAS_WORD_COPY=1,EXPERIMENTAL_VISIBLE_ROW_PHASE=1)
    args=[x for k,v in defs.items() for x in ('-D',f'{k}={v}')]
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*args,'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';checksum=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum);(out/'test.sfc').write_bytes(rom)
    subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],check=True,capture_output=True,timeout=30)
    ram=(out/'memory.ram').read_bytes();budget=budget_for(state)
    original=bytearray(2048);original[:2]=bytes.fromhex('ff1f') # staging seed's final STX $00
    for address,value in zip(ADDRESSES,state):
        if address<2048:original[address]=value
    if budget:
        staging,wanted_flags,cursor,left,scan,rows=expected(shadow,flags,start,mirror,0,budget)
    else:
        staging=bytes((i^(i>>8))&255 for i in range(8192))
        wanted_flags,cursor,left,scan,rows=flags,start,0,0,[]
    for name,actual,wanted in (
        ('staging',ram[0x3000:0x5000],staging),('flags',ram[0x1d00:0x1d80],wanted_flags),
        ('VRAM',ram[0x8000:0xa000],bytes.fromhex('5aa5')*4096),
        ('shadow',ram[0x12000:0x13000],shadow),('requirements',ram[0x1e80:0x1f00],bytes([2])*128),
        ('original policy state',bytes(ram[a] for a in ADDRESSES),bytes(state)),
        ('complete original game RAM',ram[:2048],original),
        ('DP/stack/DB',ram[0x6000:0x6005],bytes.fromhex('001eff1f00'))):
        if actual!=wanted:raise ValueError('Row phase '+name+' differs')
    if (ram[0x1c76],ram[0x1c6b],ram[0x1c6c])!=(cursor,left,scan):
        raise ValueError('Row phase cursor/budget differs')
    if not budget and ram[0x1c85]!=1:raise ValueError('Deferred dirty work was consumed')
    return dict(state=state,start=start,mirror=mirror,budget=budget,converted=rows,
                files={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),ROOT/'snes/native_prepare.asm',ROOT/'snes/visible_row_phase.inc',
        ROOT/'snes/hidden_high_cache_test.asm',ROOT/'snes/hidden_direct_probe_setup.inc',
        ROOT/'snes/hidden_direct_probe_readback.inc',ROOT/'snes/wram_clear.inc',
        ROOT/'snes/native_boot.cfg',ROOT/'tools/check_visible_attribute_cache.py',
        ROOT/'tools/check_rows.py',ROOT/'tools/check_hidden_high_cache.py',
        ROOT/'tools/smoke_libretro.py',core,ROOT/'.deps/cc65/bin/ca65',ROOT/'.deps/cc65/bin/ld65']
    sources={str(p):sha(p) for p in paths}
    states=[STABLE+(tick,) for tick in (0,1,2,3,255)]
    for index,value in ((0,0),(0,0x80),(1,0x80),(2,0x20),(3,2),(3,0x80),
                        (4,0),(4,3),(5,1),(5,2)):
        for tick in (1,2):
            state=list(STABLE+(tick,));state[index]=value;states.append(tuple(state))
    matrix=[(state,start,mirror) for state in states for start in (0,1,28,31,63,127) for mirror in (0,1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases=list(pool.map(lambda item:case(core,out/f'case-{item[0]:04d}',*item[1]),enumerate(matrix)))
    mutants=[]
    for name,state,mutation in (
        ('wrong-first-budget',STABLE+(1,),('@first:\n    lda #4','@first:\n    lda #2')),
        ('no-defer',STABLE+(2,),('    lda #0\n    rts\n@first:','    lda #2\n    rts\n@first:')),
        ('missing-pause-guard',(0xc0,0,0x20,0,4,0,2),('and #$20\n    bne @ordinary','and #0\n    bne @ordinary')),
        ('missing-transition-guard',(0xc0,0,0,0,4,2,2),('lda a:$1CA0\n    bne @ordinary','lda #0\n    bne @ordinary')),
        ('counter-overreach',STABLE+(3,),('cmp #2\n    bne @ordinary','cmp #2\n    bcc @ordinary')),
        ('lost-pending-work',STABLE+(2,),('jsr visible_row_phase_budget','stz $1C85\n    jsr visible_row_phase_budget'))):
        try:case(core,out/name,state,mutation=mutation)
        except ValueError as error:
            mutants.append(dict(name=name,error=str(error),files={str(p):sha(p) for p in (out/name).iterdir() if p.is_file()}))
        else:raise ValueError('Unsafe phase mutant survived: '+name)
    if sources!={str(p):sha(p) for p in paths}:raise ValueError('Oracle sources changed')
    report=dict(passed=True,cases=cases,mutants=mutants,sources=sources,
        scope='Executed guarded four/zero/two row policy, full staging/queue/VRAM/shadow/requirements, '
              'original policy state, DP/DB/stack and deferred dirty latch. Not a scheduling or acoustic verdict.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
