"""Characterize actual legacy sweep scheduling, not an NES conformance pass."""
import argparse
import ctypes as C
import itertools
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.correct_pulse_sweep import correct
from tools.prepare_audio import SOURCE_SHA256


def legacy_state(voice,control,accumulator,pending,reload):
    flags=(0x40<<voice) if reload else 0
    if not control&128 or not control&7:
        return (172,accumulator,pending,flags)
    period=200 if reload else 172
    count=accumulator+(0 if reload else pending)
    if count>=3*(((control>>4)&7)+1):
        count=0
        period+=period>>(control&7)
    return (period,count,0,0)


def check(core,out):
    source=Path('.deps/upernes/source/asm/Memblers_2a03.bin')
    if sha(source)!=SOURCE_SHA256:raise ValueError('Different legacy SPC')
    engine=correct(source.read_bytes())
    lib=C.CDLL(str(core.resolve()));execute=lib.retro_rcr_divider_case
    execute.argtypes=[C.c_char_p]+[C.c_uint]*6+[C.POINTER(C.c_uint)]
    execute.restype=C.c_uint
    def run(binary,voice,control,accumulator,pending,reload):
        state=(C.c_uint*5)()
        if execute(binary,len(binary),voice,control,accumulator,pending,reload,state):
            raise ValueError('SPC divider probe failed to return within timer period')
        return tuple(state)
    cases=0;errors=[];examples=[];clocks=set()
    for voice,p,accumulator,pending,mode,reload in itertools.product(
            range(2),range(8),range(24),range(16),('enabled','disabled','zero_shift'),range(2)):
        control=p*16+dict(enabled=132,disabled=4,zero_shift=128)[mode]
        state=run(engine,voice,control,accumulator,pending,reload)
        wanted=legacy_state(voice,control,accumulator,pending,reload)
        cases+=1;clocks.add(state[4])
        row=dict(voice=voice,divider=p+1,mode=mode,accumulator=accumulator,
                 pending=pending,reload=bool(reload),expected=wanted,actual=state[:4],ticks=state[4])
        if state[:4]!=wanted:errors.append(row)
        if voice==0 and p==1 and accumulator in (0,5) and pending==3:examples.append(row)
    # Executed source mutations, not edits to an expected JSON result.
    mutants={}
    for label,offset,original,replacement,case in (
        ('ignore_timer_reload_clear',0x598,bytes.fromhex('e4 fd'),bytes(2),(0,148,5,3,1)),
        ('read_counter_when_disabled',0x587,bytes.fromhex('f0 f9'),bytes(2),(0,20,0,3,0)),
        ('wrong_divider_table',0x694,bytes((6,)),bytes((5,)),(0,148,5,0,0))):
        if engine[offset:offset+len(original)]!=original:raise ValueError('Different mutation preimage')
        mutant=bytearray(engine);mutant[offset:offset+len(replacement)]=replacement
        state=run(bytes(mutant),*case)
        wanted=legacy_state(*case)
        mutants[label]=dict(detected=state[:4]!=wanted,case=case,actual=state,expected=wanted)
    out.mkdir(parents=True,exist_ok=False)
    paths=(Path(__file__),Path('tools/spc_divider_probe.inc'),Path('tools/correct_pulse_sweep.py'),
           Path('.deps/snes9x-divider-1077/apu/bapu/smp/smp.cpp'),
           Path('.deps/snes9x-divider-1077/apu/bapu/smp/core.cpp'),
           Path('.deps/snes9x-divider-1077/apu/bapu/smp/memory.cpp'),
           Path('.deps/snes9x-divider-1077/apu/bapu/smp/timing.cpp'),source,core)
    report=dict(passed=not errors and all(m['detected'] for m in mutants.values()),cases=cases,
        errors=errors,instruction_ticks=sorted(clocks),examples=examples,mutants=mutants,
        sources={str(p):sha(p) for p in paths},release_ready=False,nes_conformance=False,
        scope='Actual SPC interpreter executes both check_timers routines with corrected pulse-1 '
        'arithmetic. All eight dividers, accumulators 0..23, pending hardware counts 0..15, '
        'enabled/disabled/zero-shift and timer-reload states. Fresh hardware timer phase; '
        'not multi-call scheduling, counter overflow, negative sweeps, or a fix. Passing '
        'means the harness reproduces legacy behavior, including behavior unlike NES.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','errors','instruction_ticks','mutants')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):parser.add_argument('--'+name,type=Path,required=True)
    check(**vars(parser.parse_args()))
