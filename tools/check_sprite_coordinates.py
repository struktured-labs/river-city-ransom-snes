"""Execute original and unrolled coordinate loops over all low-byte input pairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]
PREIMAGE=bytes.fromhex('a200b50818750e9508b50f75099509e8e8e00490ed')


def inputs(first,count):
    high=(0,1,0x7f,0x80,0xfe,0xff,0x55,0xaa)
    rows=[]
    for i in range(first,first+count):
        a,b=i>>8,i&255
        flags=0x30|((i&1)<<3)|((i&2)<<1)|((i&4)>>2)|((i&8)<<3)|((i&16)<<3)|((i&32)>>4)
        rows.append(bytes((a,high[(i>>9)&7],a^0x5a,high[(i>>1)&7],
            b,high[(i>>5)&7],b^0xa5,high[(i>>8)&7],
            (i*13)&255,(i*7)&255,(i*17)&255,(i*29)&255,flags,0,0,0)))
    return rows


def binary_expected(row,bank):
    if row[12]&8:raise ValueError('Binary oracle does not model decimal ADC')
    sums=[(int.from_bytes(row[i:i+2],'little')+int.from_bytes(row[i+4:i+6],'little'))&65535 for i in (0,2)]
    carry=(row[2]+row[6])>>8
    high=(row[3]+row[7]+carry)&255
    overflow=bool((~(row[3]^row[7])&(row[3]^high))&128)
    flags=(row[12]&4)|0x33|(0x40 if overflow else 0)
    return b''.join(s.to_bytes(2,'little') for s in sums)+row[4:8]+bytes(
        (high,row[9],4,row[11],flags,255,1,bank,0,0,0))+bytes(13)


def execute(core,out,matrix,bank,optimized,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    helper=(ROOT/'snes/sprite_coordinates.inc').read_text()
    if mutation:
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Ambiguous coordinate mutant')
        helper=helper.replace(old,new)
    (out/'sprite_coordinates.inc').write_text(helper)
    # ca65 resolves includes beside its input first. Compile the local fixture
    # so negative controls really use this arm's mutated helper.
    (out/'test.asm').write_text((ROOT/'snes/sprite_coordinates_test.asm').read_text())
    (out/'inputs.bin').write_bytes(b''.join(matrix))
    defs=['-D',f'SOURCE_BANK={bank}','-D',f'CASES={len(matrix)}']
    if optimized:defs+=['-D','OPTIMIZED=1']
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*defs,'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/sprite_coordinates_test.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes()
    if not optimized and program[0x6f11:0x6f26]!=PREIMAGE:raise ValueError('Reference loop differs from original')
    rom=bytearray(2097152)
    for b in range(9):rom[b*65536+0x8000:(b+1)*65536]=program
    rom[0x90000:0x90000+len(matrix)*16]=b''.join(matrix)
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(rom)
    run=subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','1400','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=60)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    if int.from_bytes(ram[0x604:0x606],'little')!=len(matrix):raise ValueError('Incomplete coordinate matrix')
    records=ram[0x10000:0x10000+len(matrix)*32]
    for i,row in enumerate(matrix):
        got=records[i*32:(i+1)*32]
        if got[18]:raise ValueError('Coordinate helper changed unrelated zero page')
        if not row[12]&8 and got!=binary_expected(row,bank-0x40):
            raise ValueError(f'Coordinate binary oracle mismatch case{i}: {got.hex()} expected {binary_expected(row,bank-0x40).hex()}')
    return records,{str(p):sha(p) for p in out.iterdir() if p.is_file()}


def pair(core,out,chunk):
    bank=0xc1+chunk%8;matrix=inputs(chunk*2048,2048);arms=[]
    for enabled in (False,True):arms.append(execute(core,out/f'chunk-{chunk:02d}-{int(enabled)}',matrix,bank,enabled))
    if arms[0][0]!=arms[1][0]:raise ValueError('Unrolled coordinate records differ from original execution')
    return dict(chunk=chunk,bank=bank,cases=len(matrix),binary_cases=sum(not r[12]&8 for r in matrix),
        records_equal=True,arms=[a[1] for a in arms])


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),ROOT/'snes/sprite_coordinates.inc',ROOT/'snes/sprite_coordinates_test.asm',
        ROOT/'snes/sprite_coordinates_test.cfg',ROOT/'snes/wram_clear.inc',ROOT/'tools/smoke_libretro.py',
        ROOT/'tools/benchmark_report.py',ROOT/'.deps/cc65/bin/ca65',ROOT/'.deps/cc65/bin/ld65',core]
    sources={str(p):sha(p) for p in paths}
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(lambda i:pair(core,out,i),range(32)))
    # Chunk one includes a carry out of the first high-byte addition;
    # chunk zero cannot expose a missing CLC before the second coordinate.
    mutants=[];matrix=inputs(2048,2048)
    baseline=(out/'chunk-01-0/memory.ram').read_bytes()[0x10000:0x20000]
    for name,mutation in (
        ('no-low-carry-clear',('lda $0A\n    clc','lda $0A\n    nop')),
        ('wrong-high-offset',('lda $11','lda $10')),
        ('wrong-exit-flags',('cpx #4','cpx #5')),
        ('clobbered-y',('jmp $EF26','tay\n    jmp $EF26')),
        ('missing-high-store',('sta $09','nop\n    nop')),
        ('corrupted-decimal-mode',('native_sprite_coordinates:','native_sprite_coordinates:\n    cld'))):
        try:
            records,_=execute(core,out/name,matrix,0xc2,True,mutation)
            if records!=baseline:raise ValueError('Original execution records differ')
        except ValueError as error:
            mutants.append(dict(name=name,error=str(error),files={str(p):sha(p) for p in (out/name).iterdir() if p.is_file()}))
        else:raise ValueError('Coordinate mutant survived: '+name)
    if sources!={str(p):sha(p) for p in paths}:raise ValueError('Coordinate sources changed')
    report=dict(passed=True,cases=cases,mutants=mutants,sources=sources,low_byte_pairs=65536,
        scope='Original and optimized 65816 E=1 execution, all65536 low-byte input pairs, '
              'varied upper bytes/decimal/I/C/V/N/Z/A/B/X/Y across eight ROM banks. '
              '32768 binary cases also use independent arithmetic/register oracle. '
              'Unrelated zero page, source offsets, DP/DB/stack preserved. No interrupts injected; '
              'decimal cases compare SNES original-loop behavior, not NES decimal semantics. Not game speed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,pairs=65536,mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
