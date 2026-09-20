"""Execute all legal pulse-1 sweep arithmetic inputs on the actual SPC core."""
import argparse
import ctypes as C
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.correct_pulse_sweep import correct
from tools.prepare_audio import SOURCE_SHA256


def expected(period,shift,negate):
    # FCEUmm FrameSoundStuff: curfreq -= (mod + (P ^ 1)) for negate,
    # otherwise curfreq += mod. Target here is BEFORE overflow/mute handling.
    delta=period>>shift
    return (period-delta-1 if negate else period+delta)&65535


def check(core,out):
    source=Path('.deps/upernes/source/asm/Memblers_2a03.bin')
    if sha(source)!=SOURCE_SHA256:raise ValueError('Different legacy SPC')
    legacy=source.read_bytes();patched=correct(legacy)
    lib=C.CDLL(str(core.resolve()));execute=lib.retro_rcr_sweep_case
    execute.argtypes=[C.c_char_p,C.c_uint,C.c_uint,C.c_uint,C.c_uint,C.POINTER(C.c_uint)]
    execute.restype=C.c_uint
    def run(engine,period,shift,negate):
        ticks=C.c_uint();target=execute(engine,len(engine),period,shift,negate,C.byref(ticks))
        if target==0xffffffff:raise ValueError('SPC probe did not reach the arithmetic boundary')
        return target,ticks.value
    errors=[];old_errors=0;timing_errors=[];cases=0;examples=[]
    for period in range(8,2048):
        for shift in range(1,8):
            for negate in (0,1):
                wanted=expected(period,shift,negate)
                before,old_ticks=run(legacy,period,shift,negate)
                after,new_ticks=run(patched,period,shift,negate)
                cases+=1;old_errors+=before!=wanted
                row=dict(period=period,shift=shift,negate=bool(negate),expected=wanted,
                         legacy=before,corrected=after,legacy_ticks=old_ticks,corrected_ticks=new_ticks)
                if after!=wanted:errors.append(row)
                if old_ticks!=new_ticks:timing_errors.append(row)
                if period in (8,172,216,257,2047) and shift in (1,4,7):examples.append(row)
    mutants={}
    for label in ('restore_unconditional_decrement','omit_extra_borrow','wrong_padding_duration'):
        mutant=bytearray(patched)
        if label=='restore_unconditional_decrement':mutant[0x60b:0x618]=legacy[0x60b:0x618]
        elif label=='omit_extra_borrow':mutant[0x641]=0x80
        else:mutant[0x60b:0x618]=bytes(7)+bytes((0x2f,4))+bytes(4)
        observed=[]
        for negate in (0,1):
            target,ticks=run(bytes(mutant),172,4,negate)
            _,baseline_ticks=run(legacy,172,4,negate)
            observed.append(dict(negate=bool(negate),target=target,ticks=ticks,
                rejected=target!=expected(172,4,negate) or ticks!=baseline_ticks))
        mutants[label]=dict(synthetic=True,detected=any(x['rejected'] for x in observed),observations=observed)
    out.mkdir(parents=True,exist_ok=False)
    binary=out/'corrected-spc.bin';binary.write_bytes(patched)
    paths=(Path(__file__),Path('tools/correct_pulse_sweep.py'),Path('tools/spc_sweep_probe.inc'),
        Path('.deps/snes9x-sweep-1054/apu/bapu/smp/smp.cpp'),
        Path('.deps/snes9x-sweep-1054/apu/bapu/smp/core.cpp'),
        Path('.deps/fceumm/src/sound.c'),source,core,binary)
    result=dict(passed=not errors and not timing_errors and all(x['detected'] for x in mutants.values()),
        cases=cases,legacy_arithmetic_mismatches=old_errors,corrected_arithmetic_mismatches=len(errors),
        corrected_timing_mismatches=len(timing_errors),errors=errors,timing_errors=timing_errors,
        examples=examples,mutants=mutants,changed_offsets=[i for i,(a,b) in enumerate(zip(legacy,patched)) if a!=b],
        sources={str(p):sha(p) for p in paths},release_ready=False,
        scope='Actual SPC instruction execution from $09FC through $0A4B, every input period 8..2047, '
        'shift 1..7 and both directions. Checks target arithmetic BEFORE overflow/mute handling, '
        'and preserves cycle count through this block. Not divider timing, pulse2, full waveform fidelity, '
        'hardware stutter or game-level validation. No ROM deployment.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','cases','legacy_arithmetic_mismatches',
        'corrected_arithmetic_mismatches','corrected_timing_mismatches','changed_offsets')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):parser.add_argument('--'+name,type=Path,required=True)
    check(**vars(parser.parse_args()))
