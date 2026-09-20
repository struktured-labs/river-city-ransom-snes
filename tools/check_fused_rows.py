"""Exact production conversion with poisoned old snapshots and all alias states."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

try:
    from .check_rows import expected_rows
except ImportError:
    from check_rows import expected_rows

ROOT=Path(__file__).resolve().parents[1]
ROWS=(0,1,2,4,8,15,16,20,24,28,29,32,33,34,47,60,61,64,65,66,79,92,93,96,97,98,111,124,125)


def attribute_values():
    # Actual eight attribute addresses consumed by each selected physical row.
    return sorted({(address^(address>>8)^seed)&255
        for row,mirror,seed,group in itertools.product(ROWS,(0,1),(0,64,128,192),range(8))
        for physical in [(row//32//2) if mirror else (row//32%2)]
        for address in [physical*1024+960+(row%32//4)*8+group]})


def expected(row,mirror,half,state,shadow_seed=0,planar=False):
    staging=bytearray((i^(i>>8))&255 for i in range(8192))
    shadow=bytes((i^(i>>8)^shadow_seed)&255 for i in range(4096))
    converted=expected_rows(shadow,half,mirror)
    alias=row^(32 if mirror else 64)
    for target in ([row,alias] if state==1 else [row]):
        if planar:
            for plane in (0,1):
                start=plane*4096+target*32
                staging[start:start+32]=converted[row*64+plane:(row+1)*64:2]
        else:staging[target*64:(target+1)*64]=converted[row*64:(row+1)*64]
    flags=bytearray(128);flags[row]=2;flags[alias]=2 if state==1 else state
    return staging,flags


def case(core,out,row,mirror,half,state,enabled=True,source=None,fastrom=False,shadow_seed=0,planar=False,direct_state=None,visible_cache=False):
    out.mkdir(parents=True,exist_ok=False)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    defs=dict(SOURCE_ROW=row,MIRROR_MODE=mirror,PATTERN_HALF=half,ALIAS_STATE=state,
        ALIAS_XOR=32 if mirror else 64,GAMEPLAY_ROW_BUDGET=1,EXPERIMENTAL_ATTRIBUTE_LOOKUP=1,
        EXPERIMENTAL_ALIAS_WORD_COPY=1,SHADOW_XOR=shadow_seed)
    if planar:defs['EXPERIMENTAL_PLANAR_ROWS']=1
    elif enabled:defs['EXPERIMENTAL_FUSED_ALIAS_ROWS']=1
    if fastrom:defs['FASTROM_TEST']=1
    if visible_cache:defs['EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE']=1
    extra_includes=[]
    if direct_state is not None:
        defs.update(EXPERIMENTAL_HIDDEN_DIRECT_ROWS=1,HIDDEN_ROW_BUDGET=1,TRANSITION_STATE=direct_state)
        extra_includes=['-I',str((source or ROOT/'snes/fused_row_test.asm').parent)]
        original=(source or ROOT/'snes/fused_row_test.asm').read_text()
        original=original.replace('    jsr native_prepare','    .include "hidden_direct_probe_setup.inc"\n    jsr native_prepare')
        original=original.replace('fused_test_return:','fused_test_return:\n    .include "hidden_direct_probe_readback.inc"')
        source=out/'fixture.asm';source.write_text(original)
    flags=[part for k,v in defs.items() for part in ('-D',f'{k}={v}')]
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*flags,'-I',str(out),*extra_includes,'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(source or ROOT/'snes/fused_row_test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(rom)&65535;struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum)
    (out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','300','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    ram=(out/'memory.ram').read_bytes();staging,flags=expected(row,mirror,half,state,shadow_seed,planar)
    if direct_state is not None:
        vram=bytearray(bytes.fromhex('5aa5')*4096);requirements=bytearray([2]*128)
        if direct_state==2:
            staging=bytearray((i^(i>>8))&255 for i in range(8192))
            alias=row^(32 if mirror else 64)
            flags=bytearray(128);flags[alias]=state
            converted=expected_rows(bytes((i^(i>>8)^shadow_seed)&255 for i in range(4096)),half,mirror)
            for target in ([row,alias] if state==1 else [row]):
                vram[target*64:(target+1)*64]=converted[row*64:(row+1)*64]
                flags[target]=0;requirements[target]=1
        if ram[0x8000:0xa000]!=vram:raise ValueError('Direct hidden row actual VRAM differs from independent tile oracle')
        if ram[0x1e80:0x1f00]!=requirements:raise ValueError('Direct hidden row retired wrong initial requirements')
    if ram[0x3000:0x5000]!=staging:raise ValueError('Fused row changed wrong staging bytes or lost tile/attribute data')
    if ram[0x1d00:0x1d80]!=flags:raise ValueError('Fused row changed immutable queue ownership')
    if ram[0x12000:0x13000]!=bytes((i^(i>>8)^shadow_seed)&255 for i in range(4096)):
        raise ValueError('Fused row modified original nametable shadow')


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    if attribute_values()!=list(range(256)):raise ValueError('Executed matrix misses attribute values')
    matrix=list(itertools.product(ROWS,(0,1),(0,16),range(4),(0,64,128,192)))
    def execute(args):
        row,mirror,half,state,seed=args
        case(core,out/f'row-{row}-mirror-{mirror}-half-{half}-state-{state}-seed-{seed}',
             row,mirror,half,state,shadow_seed=seed)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(execute,matrix))
    original=(ROOT/'snes/native_prepare.asm').read_text()
    negatives=[]
    for name,state,old,new in (
        ('queued-overwrite',2,'cmp #1\n    bne :+\n    jmp fused_dirty_alias','cmp #2\n    bne :+\n    jmp fused_dirty_alias'),
        ('wrong-alias-address',1,'sta f:$7E3000 + alias_delta + group_offset + pair*4 + tile*2,x','sta f:$7E3002 + alias_delta + group_offset + pair*4 + tile*2,x'),
        ('lost-ready-flag',1,'lda #2\n    sta $1D00,x\n    rep #$20','lda #0\n    sta $1D00,x\n    rep #$20')):
        if original.count(old)!=1:raise ValueError('Ambiguous fused mutation '+name)
        directory=out/name;directory.mkdir()
        fixture=directory/'fused_row_test.asm';fixture.write_bytes((ROOT/'snes/fused_row_test.asm').read_bytes())
        (directory/'native_prepare.asm').write_text(original.replace(old,new))
        try:case(core,directory/'run',0,0,0,state,source=fixture)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Fused mutant passed: '+name)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=True,cases=len(matrix),source_rows=ROWS,attribute_values=attribute_values(),shadow_seeds=[0,64,128,192],negative_controls=negatives,
        core_sha256=digest(core),checker_sha256=digest(Path(__file__)),
        source_sha256=digest(ROOT/'snes/native_prepare.asm'),
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.sfc','.ram','.asm','.log')},
        scope='Full 8192 staging bytes, all 128 queue flags, unchanged original shadow; 29 source rows, '
              'both mirrors/pattern halves, all alias states, four shadow patterns covering every attribute byte. '
              'Production one-row budget; no original art or timing relaxation.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=report['cases'],negative_controls=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
