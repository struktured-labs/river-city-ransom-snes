"""Execute guarded main-start phase using real beam and a subsequent real NMI."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_oam_live_half import checksum

STABLE={0x100:0xc0,0x107:0,0x3f:0,0x3e:0,0x692:4,0x1ca0:0,
        0x1c0a:0,0x1c83:0,0x1ce0:0,0x1ce1:0,0x1ceb:1,0x1c20:0x80,0x10b:2}


def eligible(state):
    return (state[0x100]&0xc0==0xc0 and not state[0x107]&128 and
        not state[0x3f]&32 and not state[0x3e]&130 and state[0x692]==4 and
        not any(state[a] for a in (0x1ca0,0x1c0a,0x1c83,0x1ce0,0x1ce1)) and
        state[0x1ceb]!=0 and bool(state[0x1c20]&128))


def case(core,out,line,state,mutation=None,flags=0x4c,phase=96):
    out.mkdir(parents=True,exist_ok=False)
    helper=Path('snes/main_phase.inc').read_text()
    if mutation:
        before,after=mutation
        if helper.count(before)!=1:raise ValueError('Ambiguous phase mutation')
        helper=helper.replace(before,after)
    (out/'main_phase.inc').write_text(helper)
    (out/'test.asm').write_bytes(Path('snes/main_phase_test.asm').read_bytes())
    (out/'setup.inc').write_text('\n'.join(f'    lda #${v:02x}\n    sta a:${a:04x}' for a,v in state.items())+'\n')
    subprocess.run(['.deps/cc65/bin/ca65','-g','-D',f'TARGET_LINE={line}','-D',f'MAIN_PHASE_LINE={phase}',
        '-D',f'INPUT_FLAGS={flags}',
        '-I',str(out),'-I','snes','-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg',
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    image=bytearray(2097152);image[0x8000:0x10000]=(out/'test.bin').read_bytes()
    (out/'test.sfc').write_bytes(checksum(image))
    result=subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'run.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Phase fixture did not complete: '+result.stderr[-400:])
    ram=(out/'memory.ram').read_bytes()
    expected=bytes((0,0x5a,0x56,0x78,(flags&0x4d)|0x32,255,0x34,0x12,0))
    if ram[0x6000:0x6009]!=expected:
        raise ValueError('Main entry A/B/X/Y/P/SP/DP/DB differs: '+ram[0x6000:0x6009].hex())
    finish=int.from_bytes(ram[0x600a:0x600c],'little')
    target=max(line,phase) if eligible(state) else line
    if not target<=finish<=target+2:raise ValueError(f'Unexpected wait/frame wrap: {line} -> {finish}, expected{target}')
    if ram[0x1ba1]!=1 or ram[0x10b]!=0 or ram[0x1ce1]!=1:
        raise ValueError('Main marker/tick reset or following NMI differs')
    for a,v in state.items():
        if a not in (0x10b,0x1ce1) and ram[a]!=v:raise ValueError('Eligibility state changed')
    return dict(line=line,phase=phase,state=state,flags=flags,eligible=eligible(state),finish=finish,nmis=ram[0x1ba1],
        sources={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def run(core,out,phase=96):
    if not 1<=phase<=160:raise ValueError('Phase must be1..160')
    out.mkdir(parents=True,exist_ok=False)
    matrix=[(line,STABLE) for line in sorted(set((0,1,40,max(0,phase-2),phase-1,phase,phase+1,160,239,240,250,255,256,260)))]
    for address,values in ((0x100,(0,0x80,0xc1)),(0x107,(1,128)),(0x3f,(1,32)),
        (0x3e,(1,2,128)),(0x692,(0,3,5)),(0x1ca0,(1,2)),(0x1c0a,(1,255)),
        (0x1c83,(1,255)),(0x1ce0,(1,255)),(0x1ce1,(1,255)),(0x1ceb,(0,2)),
        (0x1c20,(0,1,0x81)),(0x10b,(0,1,3,255))):
        for value in values:matrix.append((40,{**STABLE,address:value}))
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases=list(pool.map(lambda item:case(core,out/f'case-{item[0]:03d}',*item[1],phase=phase),enumerate(matrix)))
    cases += [case(core,out/f'carry-set-{line}',line,STABLE,flags=0x4d,phase=phase) for line in (40,phase-1,phase,256)]
    mutants=[]
    for name,line,state,mutation in (
        ('wrong-target',40,STABLE,('cmp #MAIN_PHASE_LINE','cmp #160')),
        ('lost-high-bit',256,STABLE,('and #1\n    bne @high','and #0\n    bne @high')),
        ('lost-pause',40,{**STABLE,0x3f:32},('and #$20','and #0')),
        ('lost-flags',40,STABLE,('    plp\n    jmp','    pla\n    jmp')),
        ('masked-nmi',40,STABLE,('gameplay_phase_wait:','gameplay_phase_wait:\n    stz $4200')),
    ):
        try:case(core,out/name,line,state,mutation,phase=phase)
        except ValueError as error:mutants.append(dict(name=name,rejection=str(error)))
        else:raise ValueError('Main phase mutant survived: '+name)
    paths=[Path(__file__),Path('snes/main_phase.inc'),Path('snes/main_phase_test.asm'),
        Path('snes/native_boot.cfg'),Path('snes/wram_clear.inc'),
        Path('tools/check_oam_live_half.py'),Path('tools/smoke_libretro.py'),core]
    report=dict(passed=True,phase=phase,cases=cases,mutants=mutants,sources={str(p):sha(p) for p in paths},
        scope='Real beam guards, high bit, register/flag preservation, original main marker/tick reset and following real NMI. '
              'No game-speed or input-latency certification; no full original NMI body in fixture.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--phase',type=int,default=96)
    run(**vars(p.parse_args()))
