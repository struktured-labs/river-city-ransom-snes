"""Differentially execute the SPC kernel and FCEUmm's actual sweep functions."""
import argparse
import csv
import ctypes as C
import itertools
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_sweep_kernel import build


class Runner:
    def __init__(self,spc,nes,code=None):
        self.spc=C.CDLL(str(spc.resolve()));self.nes=C.CDLL(str(nes.resolve()))
        self.code,self.entries=build() if code is None else code
        self.init=self.spc.retro_rcr_kernel_init
        self.init.argtypes=[C.c_char_p,C.c_uint,C.c_uint];self.init.restype=C.c_uint
        self.spc_seed=self.spc.retro_rcr_kernel_seed
        self.nes_seed=self.nes.retro_rcr_nes_sweep_seed
        for fn in (self.spc_seed,self.nes_seed):
            fn.argtypes=[C.c_uint]*5;fn.restype=C.c_uint
        self.spc_event=self.spc.retro_rcr_kernel_event
        self.nes_event=self.nes.retro_rcr_nes_sweep_event
        for fn in (self.spc_event,self.nes_event):
            fn.argtypes=[C.c_uint]*3+[C.POINTER(C.c_uint)];fn.restype=C.c_uint
        self.native=(C.c_uint*6)();self.reference=(C.c_uint*4)()
        self.reset()

    def reset(self):
        if self.init(self.code,len(self.code),0x400):raise ValueError('Kernel init failed')
        for voice in (0,1):self.seed(voice,0,0,0,0)

    def seed(self,*state):
        if self.spc_seed(*state) or self.nes_seed(*state):raise ValueError('Invalid initial state')

    def event(self,voice,event,value=0):
        label=('half','write_control','write_low','write_high')[event]
        if self.spc_event(voice,self.entries[f'v{voice}_{label}'],value,self.native):
            raise ValueError('SPC kernel did not return')
        if self.nes_event(voice,event,value,self.reference):raise ValueError('NES event failed')
        return tuple(self.native),tuple(self.reference)


def replay_observed(runner,trace):
    # The NES event API clocks both voices at once, while each SPC entry clocks
    # only its selected voice. For trace validation we use actual recorded state
    # directly; no second reference clock can accidentally advance the partner.
    runner.reset();cases=0;errors=[];ticks=[]
    with trace.open() as stream:
        for raw in csv.reader(stream):
            kind,frame,clock,voice,address,value,period,control,count,reload,ready=raw
            voice=int(voice)
            if kind=='B':continue
            event=0 if kind=='H' else int(address)%4
            if kind=='W' and event==0:continue # volume write has no sweep state effect.
            label=('half','write_control','write_low','write_high')[event]
            if runner.spc_event(voice,runner.entries[f'v{voice}_{label}'],int(value),runner.native):
                raise ValueError('Trace execution did not return')
            wanted=tuple(map(int,(period,control,count,reload)))
            observed=tuple(runner.native[:4]);cases+=1;ticks.append(runner.native[4])
            if observed!=wanted or runner.native[5]:
                if len(errors)<20:errors.append(dict(row=raw,actual=observed,expected=wanted,
                                                     unexpected_dp_changes=runner.native[5]))
    return dict(passed=not errors,events=cases,errors=errors,max_instruction_ticks=max(ticks))


def check(spc,nes,trace,out,quick=False):
    observer_path=Path('build/sweep-timing-nes-1074/sweep-observer.json')
    observer=bound_report(observer_path)
    if observer['sources'].get(str(trace))!=sha(trace):raise ValueError('Different observed trace')
    paths=(Path(__file__),Path('tools/build_sweep_kernel.py'),Path('tools/spc_sweep_kernel_probe.inc'),
        Path('tools/fceumm_sweep_kernel_probe.inc'),
        Path('.deps/fceumm-kernel-1082/src/sound.c'),
        Path('.deps/snes9x-kernel-1082/apu/bapu/smp/smp.cpp'),
        Path('.deps/snes9x-kernel-1082/apu/bapu/smp/core.cpp'),observer_path,trace,spc,nes)
    sources={str(p):sha(p) for p in paths}
    runner=Runner(spc,nes);cases=0;errors=[];clock_min=10000;clock_max=0
    # All 11-bit periods and controls; focus countdown boundaries while testing
    # every divider value through the control field. Reload is independently varied.
    periods=range(2048) if not quick else (0,7,8,15,16,172,255,256,1023,1024,2047)
    for voice,period,control,count,reload in itertools.product(
            range(2),periods,range(256),(0,1,2,8),range(2)):
        runner.seed(voice,period,control,count,reload)
        actual,wanted=runner.event(voice,0)
        cases+=1;clock_min=min(clock_min,actual[4]);clock_max=max(clock_max,actual[4])
        if actual[:4]!=wanted or actual[5]:
            if len(errors)<20:errors.append(dict(input=(voice,period,control,count,reload),
                                                actual=actual,expected=wanted))
        if cases%1000000==0:print(json.dumps(dict(executed=cases,errors=len(errors))),flush=True)
    # Stateful event sequences exercise all divider countdown values and all
    # timer bytes, plus repeated identical sweep-register writes.
    sequences=0;sequence_errors=[]
    for voice,p,phase in itertools.product(range(2),range(8),range(9)):
        control=0x84|(p<<4);runner.reset();runner.seed(voice,172,control,phase,0)
        actions=[(0,0)]*3+[(1,control),(1,control)]+[(0,0)]*12
        actions += [(2,144),(0,0),(3,0)]+[(0,0)]*12
        actions += [(1,4)]+[(0,0)]*12+[(1,control)]+[(0,0)]*12
        actions += [(2,value) for value in range(256)]+[(3,value) for value in range(256)]
        for event,value in actions:
            actual,wanted=runner.event(voice,event,value);sequences+=1
            if actual[:4]!=wanted or actual[5]:
                if len(sequence_errors)<20:sequence_errors.append(dict(voice=voice,p=p,phase=phase,
                    event=event,value=value,actual=actual,expected=wanted))
    observed=replay_observed(runner,trace)
    mutations={}
    code,entries=build()
    overflow_offset=code.index(bytes.fromhex('c4976808'))+3
    for label,patches,state,event,value in (
        ('freeze_disabled_divider',[(entries['v0_half']-0x400,bytes((0x6f,)))],(0,172,4,2,0),0,0),
        ('lose_sweep_reload',[(entries['v0_write_control']-0x400+2,bytes((0x6f,)))],(0,172,148,2,0),1,148),
        ('wrong_pulse1_borrow',[(entries['v0_negative']-0x400,bytes((0x80,)))],(0,172,140,1,0),0,0),
        ('accept_overflow',[(overflow_offset,bytes((16,)))],(0,2047,132,1,0),0,0),
        ('corrupt_other_voice',[(entries['v0_write_control']-0x400+1,bytes((0x45,)))],
             (0,172,148,2,0),1,148)):
        mutant=bytearray(code)
        for offset,data in patches:mutant[offset:offset+len(data)]=data
        run=Runner(spc,nes,(bytes(mutant),entries));run.seed(*state)
        actual,wanted=run.event(state[0],event,value)
        mutations[label]=dict(detected=actual[:4]!=wanted or bool(actual[5]),
                             actual=actual,expected=wanted)
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Source changed during execution: '+path)
    out.mkdir(parents=True,exist_ok=False)
    binary=out/'sweep-kernel.bin';binary.write_bytes(code)
    report=dict(passed=not errors and not sequence_errors and observed['passed'] and
        all(m['detected'] for m in mutations.values()),quick=quick,cases=cases,errors=errors,
        sequence_events=sequences,sequence_errors=sequence_errors,observed=observed,mutations=mutations,
        instruction_ticks=dict(minimum=clock_min,maximum=clock_max),kernel_bytes=len(code),entries=entries,
        coverage=dict(voices=[0,1],periods='all 0..2047' if not quick else list(periods),
            controls='all 0..255',initial_countdowns=[0,1,2,8],reload_flags=[0,1],
            stateful_initial_countdowns=list(range(9)),
            stateful_dividers=list(range(1,9)),timer_write_values='all 0..255'),
        sources={**sources,str(binary):sha(binary)},release_ready=False,physical_audio_verified=False,
        scope='Actual new SPC instructions versus actual FCEUmm FrameSoundStuff and Write_PSG, '
        'plus stateful execution of the observed NES sweep trace. Tests divider/reload/period '
        'semantics at caller-supplied half-frame events, not real-time clock generation, '
        'transport integration, DSP mute/waveform behavior, or hardware stutter. Not deployed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','errors','sequence_events','sequence_errors',
        'observed','instruction_ticks','mutations','kernel_bytes')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('spc','nes','trace','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--quick',action='store_true');check(**vars(p.parse_args()))
