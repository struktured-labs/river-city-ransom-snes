"""Execute original and unrolled column fetch with a separate RAM oracle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_oam_live_half import checksum

PREIMAGE=bytes.fromhex('a421b11a851ec8b11a851fa420b11e9d4505e82006c5e621e621a521c93090e0')


def inputs():
    tuples=[(8,x,y) for x in range(64) for y in range(32)]
    tuples += [(count,x,(count*19+x)&255) for count in range(256) for x in (0,1,31,44,45,63,128,255)]
    tuples += [(8,x,y) for x in range(256) for y in (0,127,128,255)]
    return [bytes((count,y,x,0x30|(i&0xcf),(i*37)&255,(i*13)&255,(i*29)&255,0))
            for i,(count,x,y) in enumerate(tuples)]


def expected(row,bank):
    count,column,x,flags,b,base,seed,_=row
    ram=bytearray(0x2000)
    for i in range(256):
        for address in (0,0x545,0x800,0x900,0xa00,0xb00,0xc00):ram[address+i]=i^seed
        for address in (0x1000,0x1100):ram[address+i]=((i^seed)&3)|8
    ram[0x1a:0x1c]=bytes((base,0x10));ram[0x20:0x22]=bytes((column,count))
    while True:
        low=ram[0x1000+base+count]
        high=ram[0x1000+base+((count+1)&255)]
        ram[0x1e:0x20]=bytes((low,high))
        ram[0x545+x]=ram[(low|(high<<8))+column]
        x=((x+1)&255)&63
        count=(count+2)&255;ram[0x21]=count
        if count>=48:break
    status=(flags&0x4c)|0x31|(2 if count==48 else 0)|(0x80 if (count-48)&128 else 0)
    registers=bytes((count,b,x,column,status,255,1,bank-0x40,0,0))
    return bytes(ram[:256])+bytes(ram[0x545:0x645])+registers+bytes(502)


def execute(core,out,matrix,bank,optimized,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    helper=Path('snes/column_fetch.inc').read_text()
    if mutation:
        before,after=mutation
        if helper.count(before)!=1:raise ValueError('Ambiguous column mutation')
        helper=helper.replace(before,after)
    (out/'column_fetch.inc').write_text(helper)
    (out/'test.asm').write_bytes(Path('snes/column_fetch_test.asm').read_bytes())
    defines=['-D',f'SOURCE_BANK={bank}','-D',f'CASES={len(matrix)}']
    if optimized:defines+=['-D','OPTIMIZED=1']
    subprocess.run(['.deps/cc65/bin/ca65','-g',*defines,'-I',str(out),'-I','snes',
        '-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/column_fetch_test.cfg',
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes()
    if not optimized and program[0x42c3:0x42e3]!=PREIMAGE:raise ValueError('Wrong original column block')
    image=bytearray(2097152)
    for i in range(9):image[i*65536+0x8000:(i+1)*65536]=program
    image[0x90000:0x90000+8*len(matrix)]=b''.join(matrix)
    (out/'test.sfc').write_bytes(checksum(image))
    result=subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'run.log').write_text(result.stdout+result.stderr);result.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    if int.from_bytes(ram[0x1804:0x1806],'little')!=len(matrix):raise ValueError('Incomplete column matrix')
    records=ram[0x10000:0x10000+len(matrix)*1024]
    for i,row in enumerate(matrix):
        got=records[i*1024:(i+1)*1024];want=expected(row,bank)
        if got!=want:
            differences=[(j,a,b) for j,(a,b) in enumerate(zip(got,want)) if a!=b]
            raise ValueError(f'Column oracle case{i}: {differences[:10]}')
    return records,{str(p):sha(p) for p in out.iterdir() if p.is_file()}


def run(core,out):
    out.mkdir(parents=True,exist_ok=False);matrix=inputs()
    def pair(index):
        chunk=matrix[index*64:(index+1)*64];bank=0xc1+index%8
        arms=[execute(core,out/f'chunk-{index:03d}-{int(on)}',chunk,bank,on) for on in (False,True)]
        if arms[0][0]!=arms[1][0]:raise ValueError('Column differs from original execution')
        memories=[(out/f'chunk-{index:03d}-{on}'/'memory.ram').read_bytes() for on in (0,1)]
        differences=[i for i,(a,b) in enumerate(zip(*memories)) if a!=b]
        # Original JSR C506 leaves two return-address bytes after returning;
        # faster completion changes only the terminal heartbeat count.
        if any(i not in (0x1fc,0x1fd,0x1c62,0x1c63) for i in differences):
            raise ValueError('Unexpected full-WRAM difference outside records')
        return dict(chunk=index,bank=bank,cases=len(chunk),records_equal=True,
                    full_wram_differences=differences,arms=[a[1] for a in arms])
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(pair,range(len(matrix)//64)))
    mutants=[]
    for name,mutation in (
        ('lost-ring-wrap',('and #$3F\n        tax','and #$7F\n        tax')),
        ('lost-pointer-increment',('        iny','        nop')),
        ('wrong-column-count',('.repeat 20, row','.repeat 19, row')),
        ('wrong-counter',('lda #10+row*2','lda #9+row*2')),
        ('wrong-exit-flags',('    cmp #$30\n    jmp $C2E3','    cmp #$31\n    jmp $C2E3')),
        ('lost-decimal-status',('native_column_fetch:','native_column_fetch:\n    cld')),
    ):
        try:
            # 64 records per fixture: choose a normal block whose input flags,
            # column bytes and X starts all vary for every negative control.
            execute(core,out/name,matrix[1792:1856],0xc1,True,mutation)
        except ValueError as error:mutants.append(dict(name=name,rejection=str(error)))
        else:raise ValueError('Column mutant survived: '+name)
    paths=[Path(__file__),Path('snes/column_fetch.inc'),Path('snes/column_fetch_test.asm'),
        Path('snes/column_fetch_test.cfg'),Path('snes/wram_clear.inc'),
        Path('tools/smoke_libretro.py'),Path('tools/check_oam_live_half.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),core]
    report=dict(passed=True,cases=len(matrix),chunks=cases,mutants=mutants,
        sources={str(p):sha(p) for p in paths},scope='Original machine code versus optimized execution and independent RAM model; '
        'all zero page and 256 possible first-write/ring destinations, A/B/X/Y/P/DP/DB/SP, '
        'all 256 entry counts, all 256 X values, pointer/column page crossings and eight banks. '
        'Final full WRAM compared except two expired stack bytes and terminal heartbeat. '
        'No injected interrupt; not full-game speed or physical hardware qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(matrix),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
