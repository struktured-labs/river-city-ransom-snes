"""Execute fused signed sprite-position arithmetic against the original block."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]
PREIMAGE=bytes.fromhex('a9008509850ba51a0aa8b12ea604f00249ff850829ff1002c609c8b12e850a1002c60ba200b50818750e9508b50f75099509e8e8e00490ed')


def inputs(first,count):
    high=(0,1,0x7f,0x80,0xfe,0xff,0x55,0xaa)
    result=[]
    for i in range(first,first+count):
        flags=0x30|((i&1)<<3)|((i&2)<<1)|((i&4)>>2)|((i&8)<<3)|((i&16)<<3)|((i&32)>>4)
        result.append(bytes((i>>8,i&255,(i*13)&255,high[(i>>9)&7],
            (i*7)&255,high[(i>>5)&7],(0,1,0x80,0xff)[(i>>1)&3],(i*29)&255,
            (i*11)&255,(i*17)&255,(i*3)&255,(i*19)&255,flags,0,0,0)))
    return result


def binary_expected(row,bank):
    if row[12]&8:raise ValueError('Binary oracle does not model decimal mode')
    dx=row[0]^(255 if row[6] else 0);dy=row[1]
    signed=lambda v:v if v<128 else v-256
    x=(int.from_bytes(row[2:4],'little')+signed(dx))&65535
    y=(int.from_bytes(row[4:6],'little')+signed(dy))&65535
    high=y>>8;sign=255 if dy&128 else 0
    overflow=bool((~(row[5]^sign)&(row[5]^high))&128)
    flags=(row[12]&4)|0x33|(0x40 if overflow else 0)
    return struct.pack('<HH',x,y)+row[2:6]+bytes((high,row[9],4,(2*row[7]+1)&255,
        flags,255,1,bank,0,0,0,row[6],row[7],0,3,row[0],row[1]))+bytes(7)


def fixture():
    """Reuse the proven register recorder; replacements fail closed on drift."""
    source=(ROOT/'snes/sprite_coordinates_test.asm').read_text()
    old='''    .repeat 4,i
        lda f:$C90000+i,x
        sta $08+i
        lda f:$C90004+i,x
        sta $0E+i
    .endrepeat'''
    setup='''    .repeat 4,i
        lda f:$C90002+i,x
        sta $0E+i
    .endrepeat
    lda f:$C90006,x
    sta $04
    lda f:$C90007,x
    sta $1A
    rep #$20
    .a16
    and #$007F
    asl
    tay
    sep #$20
    .a8
    lda f:$C90000,x
    sta $0300,y
    lda f:$C90001,x
    sta $0301,y
    stz $2E
    lda #3
    sta $2F'''
    guard='''@guard:
    cpy #4
    beq @next
    cpy #$1A
    beq @next
    cpy #$2E
    beq @next
    cpy #$2F
    beq @next'''
    record='''    lda $04
    sta $0713
    lda $1A
    sta $0714
    rep #$20
    .a16
    and #$007F
    asl
    tay
    sep #$20
    .a8
    lda $2E
    sta $0715
    lda $2F
    sta $0716
    lda $0300,y
    sta $0717
    lda $0301,y
    sta $0718
    ldx $0602'''
    old_original=source[source.index('.segment "ORIGINAL"'):source.index('.segment "HEADER"')]
    original='''.segment "ORIGINAL"
.ifdef OPTIMIZED
    jmp native_sprite_position
    .res 53,$EA
.else
    .byte '''+','.join(f'${v:02x}' for v in PREIMAGE)+'''
.endif
.assert * = $EF26, lderror, "Original position exit moved"
    rts
'''
    for a,b in ((old,setup),('jsr $EF11','jsr $EEEE'),('@guard:',guard),('    ldx $0602',record),
                ('sprite_coordinates.inc','sprite_position.inc'),(old_original,original)):
        if source.count(a)!=1:raise ValueError('Ambiguous position fixture transformation')
        source=source.replace(a,b)
    return source


def execute(core,out,matrix,bank,optimized,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    helper=(ROOT/'snes/sprite_position.inc').read_text()
    if mutation:
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Ambiguous position mutant')
        helper=helper.replace(old,new)
    (out/'sprite_position.inc').write_text(helper)
    (out/'test.asm').write_text(fixture())
    (out/'inputs.bin').write_bytes(b''.join(matrix))
    defs=['-D',f'SOURCE_BANK={bank}','-D',f'CASES={len(matrix)}']
    if optimized:defs+=['-D','OPTIMIZED=1']
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*defs,'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/sprite_position_test.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes()
    if not optimized and program[0x6eee:0x6f26]!=PREIMAGE:raise ValueError('Wrong original position block')
    rom=bytearray(2097152)
    for b in range(9):rom[b*65536+0x8000:(b+1)*65536]=program
    rom[0x90000:0x90000+len(matrix)*16]=b''.join(matrix)
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(rom)
    run=subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','1600','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=60)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    if int.from_bytes(ram[0x604:0x606],'little')!=len(matrix):raise ValueError('Incomplete position matrix')
    records=ram[0x10000:0x10000+len(matrix)*32]
    for i,row in enumerate(matrix):
        got=records[i*32:(i+1)*32]
        if got[18]:raise ValueError('Position helper changed unrelated zero page')
        if not row[12]&8 and got!=binary_expected(row,bank-0x40):
            raise ValueError(f'Position binary oracle mismatch case{i}: {got.hex()} != {binary_expected(row,bank-0x40).hex()}')
    return records,{str(p):sha(p) for p in out.iterdir() if p.is_file()}


def pair(core,out,chunk):
    bank=0xc1+chunk%8;matrix=inputs(chunk*2048,2048)
    arms=[execute(core,out/f'chunk-{chunk:02d}-{int(on)}',matrix,bank,on) for on in (False,True)]
    if arms[0][0]!=arms[1][0]:raise ValueError('Fused position differs from original execution')
    return dict(chunk=chunk,bank=bank,cases=len(matrix),records_equal=True,arms=[a[1] for a in arms])


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),ROOT/'snes/sprite_position.inc',ROOT/'snes/sprite_position_test.cfg',
        ROOT/'snes/sprite_coordinates_test.asm',ROOT/'snes/wram_clear.inc',ROOT/'tools/smoke_libretro.py',
        ROOT/'tools/benchmark_report.py',ROOT/'.deps/cc65/bin/ca65',ROOT/'.deps/cc65/bin/ld65',core]
    sources={str(p):sha(p) for p in paths}
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(lambda i:pair(core,out,i),range(32)))
    matrix=inputs(2048,2048);baseline=(out/'chunk-01-0/memory.ram').read_bytes()[0x10000:0x20000]
    mutants=[]
    for name,mutation in (
        ('wrong-flip',('eor #$FF','eor #$7F')),
        ('missing-low-carry-clear',('clc\n    adc $10','nop\n    adc $10')),
        ('wrong-y-origin',('adc $11','adc $0F')),
        ('wrong-exit-flags',('cpx #4','cpx #5')),
        ('lost-table-step',('    iny','    nop')),
        ('lost-decimal-mode',('native_sprite_position:','native_sprite_position:\n    cld'))):
        try:
            records,_=execute(core,out/name,matrix,0xc2,True,mutation)
            if records!=baseline:raise ValueError('Original position records differ')
        except ValueError as error:mutants.append(dict(name=name,error=str(error)))
        else:raise ValueError('Position mutant survived: '+name)
    if sources!={str(p):sha(p) for p in paths}:raise ValueError('Position sources changed')
    report=dict(passed=True,cases=cases,mutants=mutants,sources=sources,offset_pairs=65536,
        scope='All65536 signed offset byte pairs, varied flips/origins/index/flags/registers/banks. Original E=1 code versus fused8-bit arithmetic;32768 binary oracle cases. Decimal checks compare SNES original behavior. No interrupts injected; not full-game speed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,pairs=65536,mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();run(args.core,args.out)
