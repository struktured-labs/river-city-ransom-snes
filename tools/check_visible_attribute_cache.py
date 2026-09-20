"""Execute complete visible-row staging with cache hits, misses and poisoned queues."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import itertools
import json
import os
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha
from tools.check_rows import expected_rows
from tools.check_hidden_high_cache import initial_flags

ROOT=Path(__file__).resolve().parents[1]
STARTS=(0,1,2,28,29,30,31,32,60,63,64,92,95,96,124,127)


def expected(shadow,flags,start,mirror,half,budget):
    staging=bytearray((i^(i>>8))&255 for i in range(8192))
    flags=bytearray(flags);tiles=expected_rows(shadow,half,mirror);converted=[]
    row=start
    for visited in range(128):
        if flags[row]==1:
            if row%32>=30:flags[row]=0
            else:
                alias=row^(32 if mirror else 64)
                for target in ([row,alias] if flags[alias]==1 else [row]):
                    staging[target*64:(target+1)*64]=tiles[row*64:(row+1)*64]
                    flags[target]=2
                converted.append(row);budget-=1
        row=(row+1)&127
        if budget==0:break
    return staging,flags,row,budget,127-visited,converted


def case(core,out,start=0,mirror=0,half=0,budget=2,calls=1,enabled=True,mutation=None,sparse=False):
    out.mkdir(parents=True,exist_ok=False)
    seed=(start*7)&255
    shadows=[bytes((i^(i>>8)^seed^(call*255))&255 for i in range(4096)) for call in range(calls)]
    flags=initial_flags(start,mirror)
    if sparse:flags=bytearray(128);flags[0]=flags[32]=1
    (out/'shadow.bin').write_bytes(b''.join(shadows));(out/'flags.bin').write_bytes(flags)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    source=(ROOT/'snes/native_prepare.asm').read_text()
    if mutation:
        old,new=mutation
        if source.count(old)!=1:raise RuntimeError('Nonunique visible-cache mutant')
        source=source.replace(old,new)
    (out/'native_prepare.asm').write_text(source)
    fixture=(ROOT/'snes/hidden_high_cache_test.asm').read_text().replace('cache_test_return:',
        'cache_test_return:\n    rep #$20\n    .a16\n    tdc\n    sta f:$7E6000\n'
        '    tsc\n    sta f:$7E6002\n    sep #$20\n    .a8\n    phb\n    pla\n    sta f:$7E6004')
    fixture=fixture.replace('    .repeat CALLS, call',
        '    sep #$20\n    .a8\n    lda #$A5\n    sta a:$1B5F\n'
        '    lda #$5A\n    sta a:$1B80\n    rep #$20\n    .a16\n    .repeat CALLS, call')
    (out/'test.asm').write_text(fixture)
    defs=dict(SOURCE_ROW=start,MIRROR_MODE=mirror,PATTERN_HALF=half,GAMEPLAY_ROW_BUDGET=budget,
        CALLS=calls,TRANSITION_STATE=0,EXPERIMENTAL_ATTRIBUTE_LOOKUP=1,EXPERIMENTAL_FUSED_ALIAS_ROWS=1,
        EXPERIMENTAL_ALIAS_WORD_COPY=1)
    if enabled:defs['EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE']=1
    args=[s for k,v in defs.items() for s in ('-D',f'{k}={v}')]
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*args,'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'test.asm')],capture_output=True,check=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],capture_output=True,check=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';checksum=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum);(out/'test.sfc').write_bytes(rom)
    run=subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'run.log').write_text(run.stdout+run.stderr);run.check_returncode()
    staging,wanted_flags,cursor,remaining,scan_left,converted=expected(shadows[-1],flags,start,mirror,half^((calls-1)*16),budget)
    ram=(out/'memory.ram').read_bytes()
    for label,actual,wanted in (
        ('staging',ram[0x3000:0x5000],staging),('flags',ram[0x1d00:0x1d80],wanted_flags),
        ('VRAM',ram[0x8000:0xa000],bytes.fromhex('5aa5')*4096),
        ('requirements',ram[0x1e80:0x1f00],bytes([2])*128),
        ('shadow',ram[0x12000:0x13000],shadows[-1]),
        ('cache-boundary guards',bytes((ram[0x1b5f],ram[0x1b80])),bytes((0xa5,0x5a))),
        ('DP/stack/DB',ram[0x6000:0x6005],bytes.fromhex('001eff1f00'))):
        if actual!=wanted:raise ValueError('Visible cache '+label+' differs')
    if ram[0x1c76]!=cursor or ram[0x1c6b:0x1c6d]!=bytes((remaining,scan_left)):
        raise ValueError('Visible cache cursor/budget differs')
    attributes=sorted({shadows[-1][((row//32//2) if mirror else (row//32%2))*1024+960+(row%32//4)*8+group]
                       for row in converted for group in range(8)})
    return dict(start=start,mirror=mirror,half=half,budget=budget,calls=calls,enabled=enabled,
                sparse=sparse,converted=converted,attributes=attributes,
                files={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def timing(core,folder):
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (folder/'test.lbl').read_text().splitlines()}
    points=[f'c0{labels[k]:04x}' for k in ('native_prepare','prepare_palette')]
    env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
    env.update(RCR_SPAN_TRACE=str(folder/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='120',
               RCR_SPAN_PC0=points[0],RCR_SPAN_PC1=points[1])
    subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(folder/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(folder/'observed.ram'),'--receipt',str(folder/'observed.json')],
        check=True,capture_output=True,env=env,timeout=30)
    if sha(folder/'memory.ram')!=sha(folder/'observed.ram'):raise ValueError('Observer changed WRAM')
    entries=list(csv.reader((folder/'spans.csv').open()))
    if len(entries)!=2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(entries)):
        raise ValueError('Incomplete timing observation')
    return dict(clocks=int(entries[1][4])-int(entries[0][4]),
                files={str(p):sha(p) for p in folder.iterdir() if p.is_file()})


def run(core,timing_core,out):
    out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),ROOT/'snes/native_prepare.asm',ROOT/'snes/hidden_high_cache_test.asm',
        ROOT/'snes/hidden_direct_probe_setup.inc',ROOT/'snes/hidden_direct_probe_readback.inc',
        ROOT/'snes/wram_clear.inc',ROOT/'snes/native_boot.cfg',ROOT/'tools/check_rows.py',
        ROOT/'tools/check_hidden_high_cache.py',ROOT/'tools/smoke_libretro.py',core,timing_core,
        ROOT/'.deps/cc65/bin/ca65',ROOT/'.deps/cc65/bin/ld65']
    sources={str(p):sha(p) for p in paths}
    matrix=list(itertools.product(STARTS,(0,1),(0,16),(1,2,10),(1,2)))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda item:case(core,out/f'case-{item[0]:04d}',*item[1]),enumerate(matrix)))
    mutants=[]
    for name,options,mutation in (
        ('missing-invalidation',dict(budget=1,calls=2),('lda #$FFFF\n    sta $26','nop\n    nop\n    nop\n    nop\n    nop')),
        ('missing-quadrant',dict(budget=10),('ora $12\n    cmp $26','nop\n    nop\n    cmp $26')),
        ('missing-page',dict(sparse=True,budget=2),('lda $04\n    clc\n    adc $10\n    ora $12\n    cmp $26','lda #0\n    clc\n    adc $10\n    ora $12\n    cmp $26')),
        ('always-reuse',dict(budget=2),('cmp $26\n    bne @miss','cmp $26\n    nop\n    nop')),
        ('wrong-cache-bank',{},('sta a:$1B60+group*4','sta a:$55E0+group*4')),
        ('wrong-cache-width',{},('prepare_visible_attribute_cache:\n    .a16','prepare_visible_attribute_cache:\n    .a8'))):
        try:case(core,out/name,mutation=mutation,**options)
        except ValueError as error:
            mutants.append(dict(name=name,error=str(error),files={str(p):sha(p) for p in (out/name).iterdir() if p.is_file()}))
        else:raise ValueError('Unsafe cache mutant survived: '+name)
    costs=[]
    for start,budget in ((0,1),(0,2),(1,2),(2,2),(28,2),(31,2),(0,10)):
        arms={}
        for enabled in (False,True):
            folder=out/f'timing-{start}-{budget}-{int(enabled)}'
            case(core,folder,start=start,budget=budget,enabled=enabled)
            arms[str(enabled)]=timing(timing_core,folder)
        costs.append(dict(start=start,budget=budget,arms=arms,
                          saved_master_clocks=arms['False']['clocks']-arms['True']['clocks']))
    if sources!={str(p):sha(p) for p in paths}:raise ValueError('Sources changed during oracle')
    report=dict(passed=True,cases=results,mutants=mutants,timings=costs,sources=sources,
        attributes=sorted({v for row in results for v in row['attributes']}),
        scope='Complete8192-byte staging,128 ownership flags, unchanged original shadow/VRAM/requirements, '
              'DP/DB/stack, cursor and budget; one/two/ten rows, page/quadrant/ring boundaries and '
              'changed source/pattern between calls. Timing observers match complete WRAM. '
              'Not full-game pacing, acoustics or deployment qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=len(results),mutants=len(mutants),attributes=len(report['attributes']),
                         timings=[(r['start'],r['budget'],r['saved_master_clocks']) for r in costs])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','timing-core','out'):parser.add_argument('--'+name,type=Path,required=True)
    run(**vars(parser.parse_args()))
