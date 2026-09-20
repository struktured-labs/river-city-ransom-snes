"""Independent multi-row VRAM oracle for invocation-local high-byte caching."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.check_rows import expected_rows
from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]


def initial_flags(start,mirror):
    flags=bytearray(128)
    for i in range(20):
        row=(start+i)&127
        flags[row^(32 if mirror else 64)]=i%4
    for i in range(20):flags[(start+i)&127]=1
    return flags


def expected(shadow,flags,start,mirror,half,budget,details=False):
    flags=bytearray(flags);requirements=bytearray([2]*128)
    vram=bytearray(bytes.fromhex('5aa5')*4096)
    tiles=expected_rows(shadow,half,mirror)
    row=start;retired=[]
    for _ in range(128):
        if flags[row]==1:
            if row%32>=30:flags[row]=0
            else:
                alias=row^(32 if mirror else 64)
                for target in ([row,alias] if flags[alias]==1 else [row]):
                    vram[target*64:(target+1)*64]=tiles[row*64:(row+1)*64]
                    flags[target]=0;requirements[target]-=1;retired.append(target)
                budget-=1
        row=(row+1)&127
        if not budget:break
    result = (vram,flags,requirements,retired)
    return result+(row,budget,127-_) if details else result


def case(core,out,start=0,mirror=0,half=0,budget=10,calls=1,enabled=True,mutation=None,sparse_pages=False,
         direct_pair=False,dirty_alias=False,compact_index=False):
    out.mkdir(parents=True,exist_ok=False)
    seed=(start*7)&255
    shadows=[bytes((i^(i>>8)^seed^(call*255))&255 for i in range(4096)) for call in range(calls)]
    flags=initial_flags(start,mirror)
    if dirty_alias:
        for i in range(20):flags[((start+i)&127)^(32 if mirror else 64)]=1
    if sparse_pages:
        flags=bytearray(128);flags[0]=flags[32]=1
    (out/'shadow.bin').write_bytes(b''.join(shadows));(out/'flags.bin').write_bytes(flags)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    for name in ('hidden_high_cache_test.asm','native_prepare.asm','hidden_direct_rows.inc'):
        source=(ROOT/'snes'/name).read_text()
        if mutation and mutation[0]==name:
            _,old,new=mutation
            if source.count(old)!=1:raise RuntimeError('Ambiguous mutant')
            source=source.replace(old,new)
        (out/name).write_text(source)
    defs=dict(SOURCE_ROW=start,MIRROR_MODE=mirror,PATTERN_HALF=half,HIDDEN_ROW_BUDGET=budget,
        CALLS=calls,TRANSITION_STATE=2,EXPERIMENTAL_ATTRIBUTE_LOOKUP=1,EXPERIMENTAL_FUSED_ALIAS_ROWS=1,
        EXPERIMENTAL_HIDDEN_DIRECT_ROWS=1,EXPERIMENTAL_ALIAS_WORD_COPY=1)
    if enabled:defs['EXPERIMENTAL_HIDDEN_HIGH_CACHE']=1
    if direct_pair:defs['EXPERIMENTAL_HIDDEN_DIRECT_PAIR']=1
    if compact_index:defs['EXPERIMENTAL_HIDDEN_COMPACT_INDEX']=1
    args=[s for k,v in defs.items() for s in ('-D',f'{k}={v}')]
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*args,'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'hidden_high_cache_test.asm')],capture_output=True,check=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],capture_output=True,check=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';checksum=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum);(out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr);result.check_returncode()
    vram,flags,requirements,retired,cursor,remaining,scan_left=expected(
        shadows[-1],flags,start,mirror,half^((calls-1)*16),budget,details=True)
    ram=(out/'memory.ram').read_bytes()
    for label,actual,wanted in (
        ('VRAM',ram[0x8000:0xa000],vram),('flags',ram[0x1d00:0x1d80],flags),
        ('requirements',ram[0x1e80:0x1f00],requirements),('shadow',ram[0x12000:0x13000],shadows[-1]),
        ('immutable staging',ram[0x3000:0x5000],bytes((i^(i>>8))&255 for i in range(8192)))):
        if actual!=wanted:raise ValueError('Hidden cache '+label+' differs')
    if ram[0x1c76] != cursor or ram[0x1c6b:0x1c6d] != bytes((remaining,scan_left)):
        raise ValueError('Hidden cache cursor/budget differs')
    return dict(start=start,mirror=mirror,half=half,budget=budget,calls=calls,enabled=enabled,
                direct_pair=direct_pair,dirty_alias=dirty_alias,
                compact_index=compact_index,
                sparse_pages=sparse_pages,retired=retired,rom_sha256=sha(out/'test.sfc'),ram_sha256=sha(out/'memory.ram'))


def run(core,out,full=False):
    out.mkdir(parents=True,exist_ok=False)
    files=[ROOT/'snes'/n for n in ('hidden_high_cache_test.asm','native_prepare.asm','hidden_direct_rows.inc',
        'hidden_direct_probe_setup.inc','hidden_direct_probe_readback.inc','native_boot.cfg','wram_clear.inc')]
    files += [Path(__file__),ROOT/'tools/check_rows.py',ROOT/'tools/smoke_libretro.py']
    sources={str(p):sha(p) for p in files}
    starts=range(128) if full else (0,1,2,28,29,30,31,32,60,63,64,92,95,96,124,127)
    matrix=list(itertools.product(starts,(0,1),(0,16),(1,2,10,16),(1,2)))
    def execute(item):
        i,args=item;return case(core,out/f'case-{i:04d}',*args)
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(execute,enumerate(matrix)))
    controls=[case(core,out/f'uncached-{start}',start=start,enabled=False) for start in (0,28,60,124)]
    mutants=[]
    for name,options,mutation in (
        ('missing-invalidation',dict(budget=1,calls=2),('native_prepare.asm','lda #$FFFF\n    sta $20','nop\n    nop\n    nop\n    nop\n    nop')),
        ('missing-quadrant',dict(budget=10),('hidden_direct_rows.inc','ora $12\n    cmp $20','nop\n    nop\n    cmp $20')),
        ('missing-physical-page',dict(sparse_pages=True),('hidden_direct_rows.inc','lda $04\n    clc\n    adc $10','lda #0\n    clc\n    adc $10')),
        ('always-reuse',dict(budget=10),('hidden_direct_rows.inc','cmp $20\n    bne :+','cmp $20\n    nop\n    nop'))):
        try:case(core,out/name,**options,mutation=mutation)
        except ValueError as error:mutants.append(dict(name=name,error=str(error)))
        else:raise ValueError('Unsafe cache mutant survived: '+name)
    if sources!={str(p):sha(p) for p in files}:raise ValueError('Sources changed during oracle')
    report=dict(passed=True,cases=results,uncached_controls=controls,mutants=mutants,sources=sources,
        core_sha256=sha(core),scope='Full real tilemap VRAM, all ownership/requirements, unchanged shadow/staging; '
        'multirow budgets, ring/page/quadrant crossings and cache invalidation across changed source/pattern calls.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--full',action='store_true');run(**vars(p.parse_args()))
