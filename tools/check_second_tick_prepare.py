"""Execute retained producer policy and exactly-once service with a bridge spy."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]
ADDRESSES=(0x100,0x107,0x3f,0x3e,0x692,0x1ca0,0x1ceb,0x1ce1,0x10b)
STABLE=(0xc0,0,0,0,4,0,1,0,2)


def expected(state,pending,initial,action):
    task,guard,pause,fade,level,transition,armed,iteration,tick=state
    eligible=(task&0xc0==0xc0 and not guard&128 and not pause&32 and not fade&130
              and level==4 and transition==0 and armed!=0 and iteration==0 and tick==2)
    scheduled=served=fallback=initial
    calls=0
    if action<3:
        if eligible and not pending:
            pending=1;scheduled=(scheduled+1)&65535
        else:calls+=1
    if action in (1,2,3,4) and pending:
        pending=0;served=(served+1)&65535;calls+=1
        if action in (2,4):fallback=(fallback+1)&65535
    return bytes((pending,))+struct.pack('<HHH',scheduled,served,fallback),calls


def case(core,out,state,pending=0,initial=0,action=0,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    helper=(ROOT/'snes/second_tick_prepare.inc').read_text()
    if mutation:
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Ambiguous producer mutant')
        helper=helper.replace(old,new)
    (out/'second_tick_prepare.inc').write_text(helper)
    (out/'test.asm').write_text((ROOT/'snes/second_tick_prepare_test.asm').read_text())
    setup=dict(zip(ADDRESSES,state));setup[0x1b80]=pending
    for i in range(3):
        setup[0x1b81+i*2]=initial&255;setup[0x1b82+i*2]=initial>>8
    (out/'setup.inc').write_text('\n'.join(f'    lda #${v:02x}\n    sta a:${a:04x}' for a,v in setup.items())+'\n')
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-D',f'ACTION={action}','-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(rom)
    subprocess.run(['python3',str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],check=True,capture_output=True,timeout=30)
    ram=(out/'memory.ram').read_bytes();counters,calls=expected(state,pending,initial,action)
    original=bytearray(2048)
    for address,value in setup.items():
        if address<2048:original[address]=value
    # Seven bytes at $01F9..01FF are the maximum live emulation call stack:
    # fixture JSR -> fallback JSR -> bridge JSL. Return addresses legitimately
    # remain there after RTS/RTL. All other original-game RAM is invariant.
    if ram[:0x1f9]!=original[:0x1f9] or ram[0x200:2048]!=original[0x200:]:
        raise ValueError('Original game RAM outside call stack changed')
    if ram[0x1b80:0x1b87]!=counters or ram[0x1ba0]!=calls:raise ValueError('Producer ownership/counters/calls differ')
    if ram[0x6000:0x6006]!=bytes.fromhex('5678341200ff'):raise ValueError('X/Y/DP/DB/stack differs')
    if any(ram[a]!=v for a,v in zip(ADDRESSES,state)):raise ValueError('Guard state changed')
    return dict(state=state,pending=pending,initial=initial,action=action,calls=calls,
                files={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    states=[STABLE]
    for index,values in enumerate(((0,0x80,0xc1),(0x80,1),(0x20,1),(2,0x80,1),(0,3,5),(1,2),(0,2),(1,2),(0,1,3,255))):
        for value in values:
            state=list(STABLE);state[index]=value;states.append(tuple(state))
    matrix=[(state,0,0,action) for state in states for action in (0,1,2)]
    matrix += [(STABLE,pending,initial,action) for pending in (0,1,255) for initial in (255,65535) for action in range(5)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases=list(pool.map(lambda item:case(core,out/f'case-{item[0]:03d}',*item[1]),enumerate(matrix)))
    mutants=[]
    for name,args,mutation in (
        ('lost-clear',(STABLE,1,0,3),('stz a:$1B80','nop\n    nop\n    nop')),
        ('wrong-tick',(STABLE,0,0,0),('cmp #2','cmp #1')),
        ('lost-pause',((0xc0,0,0x20,0,4,0,1,0,2),0,0,0),('and #$20','and #0')),
        ('lost-rollover',(STABLE,0,65535,0),('inc a:$1B82','nop\n    nop\n    nop')),
        ('missing-service',(STABLE,1,0,4),('jsr second_tick_prepare_service','nop\n    nop\n    nop'))):
        try:case(core,out/name,*args,mutation)
        except ValueError as error:mutants.append(dict(name=name,error=str(error)))
        else:raise ValueError('Producer mutant survived: '+name)
    sources=[Path(__file__),ROOT/'snes/second_tick_prepare.inc',ROOT/'snes/second_tick_prepare_test.asm',
             ROOT/'snes/native_boot.cfg',ROOT/'snes/wram_clear.inc',ROOT/'tools/smoke_libretro.py',core]
    report=dict(passed=True,cases=cases,mutants=mutants,sources={str(p):sha(p) for p in sources},
                scope='Executed guard/ownership/rollover and bridge-call counts; original RAM outside seven emulation call-stack bytes and X/Y/DP/DB/SP. Bridge is a spy, not full producer scheduling or gameplay proof.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();run(args.core,args.out)
