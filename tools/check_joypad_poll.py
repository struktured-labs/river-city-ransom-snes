"""Compare the fast poll against the real generated legacy I/O stubs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha
from tools.build_native import stub

ROOT=Path(__file__).resolve().parents[1]
PREIMAGE=bytes.fromhex('ad16404a26ee4a2604ad17404a26ef4a2605cad0eb')


def inputs(first,count,live=False):
    return [bytes((i>>8,i&255,(i*13)&255,(i*7)&255,(i*3)&255,(i*19)&255,
        (1,2,255)[i%3] if live else 0,i&1,(i*11)&255,(i*17)&255,8,(i*29)&255,
        0x30|((i&1)<<3)|((i&2)<<1)|((i&4)>>2)|((i&8)<<3)|((i&16)<<3)|((i&32)>>4),
        (i>>1)&1,0,0)) for i in range(first,first+count)]


def expected(row,bank):
    rev=lambda v:int(f'{v:08b}'[::-1],2)
    p1,p2=(0,0) if row[6] else (rev(row[0]),rev(row[1]))
    cache=bytes(row[:2]) if row[6] else b'\xff\xff'
    flags=(row[12]&0x4c)|0x32|(row[5]&1)
    return bytes((p1,p2,0,0))+cache+bytes((row[6],p2&1,0,0x1b,0,row[11],
        flags,255,1,bank,0,0,0,0x17,0x40,0xaa,row[7],row[13]))+bytes(8)


def mutation_inputs():
    # A contiguous first chunk leaves pad1=0, hiding a reversed pad1 stream.
    return [inputs(i*257,1)[0] for i in range(256)]


def fixture():
    source=(ROOT/'snes/sprite_coordinates_test.asm').read_text()
    setup='''    lda f:$C90000,x
    sta a:$1C80
    lda f:$C90001,x
    sta a:$1C81
    lda f:$C90002,x
    sta $EE
    lda f:$C90003,x
    sta $EF
    lda f:$C90004,x
    sta $04
    lda f:$C90005,x
    sta $05
    lda f:$C90006,x
    sta a:$1C82
    beq :+
    lda #1
:
    sta $4016
    lda f:$C90007,x
    sta a:$1C0A
    lda f:$C9000D,x
    sta a:$1C83
    stz a:$1C20
    lda #$AA
    sta a:$1B22'''
    old='''    .repeat 4,i
        lda f:$C90000+i,x
        sta $08+i
        lda f:$C90004+i,x
        sta $0E+i
    .endrepeat'''
    old_guard=source[source.index('@guard:'):source.index('@check:')]
    new_guard='''@guard:
    cpy #4
    beq @next
    cpy #5
    beq @next
    cpy #$EE
    beq @next
    cpy #$EF
    beq @next
'''
    old_record='''    .repeat 4,i
        lda $08+i
        sta $0700+i
        lda $0E+i
        sta $0704+i
    .endrepeat'''
    record='\n'.join(f'    lda a:${addr:04X}\n    sta ${0x700+i:04X}' for i,addr in
        enumerate((0xee,0xef,4,5,0x1c80,0x1c81,0x1c82,0x1b24)))+'\n'+\
        '\n'.join(f'    lda a:${addr:04X}\n    sta ${0x713+i:04X}' for i,addr in
        enumerate((0x1b20,0x1b21,0x1b22,0x1c0a,0x1c83)))
    old_original=source[source.index('.segment "ORIGINAL"'):source.index('.segment "HEADER"')]
    original='''.segment "ORIGINAL"
.ifdef OPTIMIZED
    jmp native_joypad_poll
    .res 18,$EA
.else
@poll:
    jsr legacy1
    lsr
    rol $EE
    lsr
    rol $04
    jsr legacy2
    lsr
    rol $EF
    lsr
    rol $05
    dex
    bne @poll
.endif
.assert * = $FDA3, lderror, "Original pad continuation moved"
    rts
'''
    for a,b in ((old,setup),('jsr $EF11','jsr $FD8E'),(old_guard,new_guard),
                (old_record,record),('.include "sprite_coordinates.inc"',''),(old_original,original)):
        if source.count(a)!=1:raise ValueError('Ambiguous poll fixture transformation')
        source=source.replace(a,b)
    return source


def execute(core,out,matrix,bank,on,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    helper=(ROOT/'snes/joypad_poll.inc').read_text()
    if mutation:
        a,b=mutation
        if helper.count(a)!=1:raise ValueError('Ambiguous poll mutant')
        helper=helper.replace(a,b)
    (out/'joypad_poll.inc').write_text(helper)
    (out/'native_runtime.asm').write_text((ROOT/'snes/native_runtime.asm').read_text())
    (out/'test.asm').write_text(fixture())
    ca,ld=[str(ROOT/'.deps/cc65/bin'/n) for n in ('ca65','ld65')]
    def run(args):subprocess.run(args,check=True,capture_output=True)
    run([ca,'-g','-D','EXPERIMENTAL_JOYPAD_POLL=1','-D','video_prepare_bridge=32512',
        '-D','audio_publish_bridge=32512','-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'runtime.o'),str(out/'native_runtime.asm')])
    run([ld,'-C',str(ROOT/'snes/native_runtime.cfg'),'-Ln',str(out/'runtime.lbl'),
        '-o',str(out/'runtime.bin'),str(out/'runtime.o')])
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (out/'runtime.lbl').read_text().splitlines()}
    s1=stub(0xad,0x4016,labels['dispatch_read']);s2=stub(0xad,0x4017,labels['dispatch_read'])
    defs=['-D',f'SOURCE_BANK={bank}','-D',f'CASES={len(matrix)}','-D','legacy1=24576',
        '-D',f'legacy2={24576+len(s1)}','-D',f'native_joypad_poll={labels["native_joypad_poll"]}']
    if on:defs+=['-D','OPTIMIZED=1']
    run([ca,'-g',*defs,'-I',str(ROOT/'snes'),'-o',str(out/'test.o'),str(out/'test.asm')])
    run([ld,'-C',str(ROOT/'snes/joypad_poll_test.cfg'),'-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')])
    program=(out/'test.bin').read_bytes();rom=bytearray(2097152)
    for b in range(9):
        rom[b*65536+0x8000:(b+1)*65536]=program
        rom[b*65536+0x2000:b*65536+0x6000]=(out/'runtime.bin').read_bytes()
        rom[b*65536+0x6000:b*65536+0x6000+len(s1+s2)]=s1+s2
    rom[0x90000:0x90000+len(matrix)*16]=b''.join(matrix)
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(rom)
    result=subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','1600','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=60)
    (out/'execution.log').write_text(result.stdout+result.stderr);result.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    if int.from_bytes(ram[0x604:0x606],'little')!=len(matrix):raise ValueError('Incomplete pad matrix')
    records=ram[0x10000:0x10000+len(matrix)*32]
    for i,row in enumerate(matrix):
        got=records[i*32:(i+1)*32];want=expected(row,bank-0x40)
        if got!=want:raise ValueError(f'Pad oracle mismatch case{i}: {got.hex()} != {want.hex()}')
    return records,{str(p):sha(p) for p in out.iterdir() if p.is_file()}


def pair(core,out,chunk,live=False):
    bank=0xc1+chunk%8;matrix=inputs(0 if live else chunk*2048,256 if live else 2048,live)
    arms=[execute(core,out/f'{"live" if live else "chunk"}-{chunk:02d}-{int(on)}',matrix,bank,on) for on in (False,True)]
    if arms[0][0]!=arms[1][0]:raise ValueError('Poll differs from real legacy stubs')
    return dict(chunk=chunk,bank=bank,cases=len(matrix),arms=[a[1] for a in arms])


def audit(core,out):
    out.mkdir(parents=True,exist_ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases=list(pool.map(lambda n:pair(core,out,n),range(32)))
    live=pair(core,out,0,True)
    mutants=[]
    for name,change in (
        ('wrong-bit-order',('    rol $EE','    ror $EE')),
        ('lost-fill-ones',('    ror a:$1C80','    lsr a:$1C80')),
        ('lost-final-carry',('    lsr $05','    clc\n    nop')),
        ('wrong-mailbox',('    sta a:$1B24','    sta a:$1B25')),
        ('lost-expansion-clear',('    stz $04','    nop\n    nop'))):
        # Some instruction sequences intentionally appear on both paths.
        if name in ('wrong-bit-order','wrong-mailbox'):
            change=(change[0]+'\n    '+('sec' if name=='wrong-bit-order' else 'lsr $05'),
                    change[1]+'\n    '+('sec' if name=='wrong-bit-order' else 'lsr $05'))
        try:execute(core,out/name,mutation_inputs(),0xc3,True,change)
        except ValueError as error:
            if not str(error).startswith('Pad oracle mismatch'):raise
            mutants.append(dict(name=name,error=str(error)))
        else:raise ValueError('Surviving poll mutant: '+name)
    paths=[Path(__file__),ROOT/'snes/joypad_poll.inc',ROOT/'snes/joypad_poll_test.cfg',
        ROOT/'snes/sprite_coordinates_test.asm',ROOT/'snes/native_runtime.asm',ROOT/'tools/build_native.py',core]
    report=dict(passed=True,pad_pairs=65536,live_cases=256,cases=cases,live=live,mutants=mutants,
        sources={str(p):sha(p) for p in paths},scope='Executed real generic stubs versus cached poll; all cached pad pairs, '
        'registers, mailbox, original game zero-page guards, flags, mirrored DB. Live fallback tested with no attached buttons. '
        'No injected NMI or SNAC hardware qualification; whole-loop critical section differs from per-read masking.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,pad_pairs=65536,live_cases=256,mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();audit(a.core,a.out)
