"""Execute live sweep-clock and DSP publication, including stalled-port tests."""
import argparse
import ctypes as C
import itertools
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_sweep_driver import build,FIRST_HALF,FOUR_SECOND,FIVE_SECOND
from tools.prepare_audio import paired_engine,SOURCE_SHA256


def clock_step(phase,step,mode,ticks):
    phase+=512*ticks;count=0
    while phase>=(threshold:=FIRST_HALF if not step else FIVE_SECOND if mode else FOUR_SECOND):
        phase-=threshold;step^=1;count+=1
    return phase,step,count


def muted(period,control):
    return period<8 or (not control&8 and period+(period>>(control&7))>2047)


def audit_deadlines(events,epoch,end,mode):
    """Count independently of observations; censor only the final late window."""
    regular=[t for t in events if t>epoch+2000]
    expected=[];deadline=epoch+FIRST_HALF;step=1
    while deadline<=end+128:
        expected.append(deadline)
        deadline+=FIVE_SECOND if step and mode else FOUR_SECOND if step else FIRST_HALF
        step^=1
    required=sum(t+1400<=end for t in expected)
    offsets=[a-b for a,b in zip(regular,expected)]
    passed=(required<=len(regular)<=len(expected) and bool(offsets)
            and min(offsets)>=-128 and max(offsets)<=1400)
    return dict(passed=passed,required_events=required,possible_events=len(expected),
                observed_events=len(regular),deadline_offsets=offsets)


def realtime_case(run,mode,delay):
    run.boot();packet=bytearray(23)
    packet[0:8]=bytes((0x3f,0x94,172,0,0x3f,0x94,172,0))
    packet[20]=63|64|mode;packet[21]=3;packet[22]=195
    run.packet(packet,delay);epoch=run.out[387];at_reset=run.out[385]
    run.wait(1025280)
    clocks=run.events();audit=audit_deadlines(clocks,epoch,run.out[384],mode)
    immediate=[t for t in clocks if epoch<=t<=epoch+2000]
    audit['passed']=audit['passed'] and run.out[386]==0 and len(immediate)==bool(mode)
    return dict(mode=mode,delay=delay,**audit,
        epoch=epoch,end=run.out[384],events_at_reset=at_reset,events=clocks,
        immediate_events=immediate,bad_volume_writes=run.out[386])


class Driver:
    def __init__(self,core,image,layout):
        self.lib=C.CDLL(str(core.resolve()));self.image=image;self.layout=layout
        self.out=(C.c_uint*388)();self.log=(C.c_uint*65536)()
        specs={'load':[C.c_char_p]+[C.c_uint]*4,'boot':[C.POINTER(C.c_uint)],
            'seed':[C.c_char_p],'call':[C.c_uint,C.c_uint,C.POINTER(C.c_uint)],
            'wait':[C.c_uint,C.POINTER(C.c_uint)],
            'packet':[C.c_char_p,C.c_uint,C.POINTER(C.c_uint)],
            'events':[C.POINTER(C.c_uint),C.c_uint]}
        self.fn={}
        for name,args in specs.items():
            fn=getattr(self.lib,'retro_rcr_driver_'+name);fn.argtypes=args;fn.restype=C.c_uint
            self.fn[name]=fn
        self.load()

    def invoke(self,name,*args):
        result=self.fn[name](*args)
        if result:raise ValueError(f'Driver {name} failed: {result}')

    def load(self):
        d=self.layout['driver']
        self.invoke('load',self.image,len(self.image),d['half_pair'],d['publish'],d['idle'])

    def seed(self,dp):self.invoke('seed',bytes(dp))
    def call(self,label,value=0):self.invoke('call',self.layout['driver'][label],value,self.out)
    def boot(self):self.load();self.invoke('boot',self.out)
    def packet(self,p,delay=0):self.invoke('packet',bytes(p),delay,self.out)
    def wait(self,clocks):self.invoke('wait',clocks,self.out)
    def events(self):
        count=self.fn['events'](self.log,65536)
        if count==0xffffffff:raise ValueError('Event log overflow')
        return list(self.log[:count])


def check(core,out,quick=False):
    source=Path('.deps/upernes/source/asm/Memblers_2a03.bin')
    if sha(source)!=SOURCE_SHA256:raise ValueError('Wrong source')
    base=paired_engine(source.read_bytes(),reset_notes=True,fast_reset=True)
    image,layout=build(base)
    paths=[Path(p) for p in ('tools/check_sweep_driver.py','tools/build_sweep_driver.py',
        'tools/build_sweep_kernel.py','tools/build_sweep_packet.py','tools/prepare_audio.py',
        'tools/spc_sweep_driver_probe.inc','.deps/snes9x-driver-1093/apu/bapu/smp/core.cpp',
        '.deps/snes9x-driver-1093/apu/bapu/smp/smp.cpp','.deps/snes9x-driver-1093/apu/bapu/smp/memory.cpp',
        '.deps/snes9x-driver-1093/apu/bapu/smp/timing.cpp')]+[source,core]
    sources={str(p):sha(p) for p in paths};run=Driver(core,image,layout)
    errors=[];clock_cases=0;publisher_cases=0
    def failure(kind,**data):
        if len(errors)<20:errors.append(dict(kind=kind,**data))
    dp=bytearray(256)
    dp[0x41]=dp[0x45]=148;dp[0x7a]=dp[0x83]=172
    for mode,step in itertools.product((0,128),range(2)):
        threshold=FIRST_HALF if not step else FIVE_SECOND if mode else FOUR_SECOND
        phases=range(threshold) if not quick else (0,1,511,512,threshold-2,threshold-1)
        for phase,ticks in itertools.product(phases,range(16)):
            dp[0x90]=3;dp[0x91]=7;dp[0x92]=dp[0x93]=0
            dp[0x98]=phase&255;dp[0x99]=phase>>8;dp[0x9a]=mode;dp[0x9c]=step
            dp[0xa6]=dp[0xa7]=0
            run.seed(dp);run.call('advance',ticks);clock_cases+=1
            wanted=clock_step(phase,step,mode,ticks)
            got=(run.out[0x98]|run.out[0x99]<<8,run.out[0x9c],run.out[0xa6]|run.out[0xa7]<<8)
            if got!=wanted or (run.out[0x90],run.out[0x91])!=(3-wanted[2],7-wanted[2]):
                failure('clock',mode=mode,step=step,phase=phase,ticks=ticks,actual=got,expected=wanted)
    run.load()
    periods=range(2048) if not quick else (0,7,8,31,172,255,256,1023,1024,2047)
    for voice,period,control,enable in itertools.product(range(2),periods,range(256),range(2)):
        dp=bytearray(256);lo=(0x7a,0x83)[voice];reg=voice*16
        dp[lo]=period&255;dp[lo+1]=period>>8;dp[0x41+voice*4]=control
        dp[0x40+voice*4]=0x3f;dp[0x55]=(1<<voice) if enable else 0
        run.seed(dp);run.call('publish');publisher_cases+=1
        volume=0 if not enable or muted(period,control) else 120
        got=(run.out[256+reg],run.out[257+reg])
        if got!=(volume,volume):failure('volume',voice=voice,period=period,control=control,enable=enable,actual=got,expected=volume)
        if volume:
            pitch=int.from_bytes(base[0xabd+2*period:0xabf+2*period],'little')
            actual=run.out[258+reg]|run.out[259+reg]<<8
            if actual!=pitch:failure('pitch',voice=voice,period=period,control=control,actual=actual,expected=pitch)
    # Explicit envelope/constant selection, including the legacy loop sentinel.
    envelope_cases=0
    for voice,constant,level,raw in itertools.product(range(2),range(2),range(17),range(16)):
        dp=bytearray(256);lo=(0x7a,0x83)[voice];dp[lo]=172
        dp[0x40+voice*4]=raw|(16 if constant else 0);dp[0x41+voice*4]=8
        dp[0x55]=1<<voice;dp[0x86+voice*3]=level
        run.seed(dp);run.call('publish');envelope_cases+=1
        wanted=(raw if constant else level if level<16 else 0)*8
        if (run.out[256+voice*16],run.out[257+voice*16])!=(wanted,wanted):failure('envelope',voice=voice,constant=constant,level=level,raw=raw)
    # Execute the real boot, ports, timer hardware, synthesis and idle loop.
    idle_cases=0
    for voice,level in itertools.product(range(2),range(17)):
        run.load();dp=bytearray(256);lo=(0x7a,0x83)[voice];dp[lo]=172
        dp[0x41+voice*4]=8;dp[0x55]=1<<voice;dp[0x86+voice*3]=15
        run.seed(dp);run.call('publish')
        dp=bytearray(run.out[:256]);dp[0x86+voice*3]=level
        run.seed(dp);run.call('idle');idle_cases+=1
        expected=(level if level<16 else 0)*8
        if (run.out[256+voice*16],run.out[257+voice*16])!=(expected,expected):
            failure('stale_idle_envelope',voice=voice,level=level)
    run.load();dp=bytearray(256)
    dp[0x40]=0x3f;dp[0x41]=0x94;dp[0x55]=1;dp[0x7a]=172
    run.seed(dp);run.call('publish');run.call('half_pair');run.call('idle');idle_cases+=1
    expected=int.from_bytes(base[0xabd+2*182:0xabf+2*182],'little')
    if (run.out[258]|run.out[259]<<8)!=expected:failure('stale_idle_pitch')
    realtime=[]
    for mode,delay in itertools.product((0,128),(0,2048)):
        result=realtime_case(run,mode,delay);realtime.append(result)
        if not result['passed']:failure('realtime',result=result)
    # Execute damaged binaries through exactly the same real-time test.
    mutants=[]
    for name,address,old,new,mode in (
        ('timer_twice_as_slow',0x747,b'\x04',b'\x08',0),
        ('missing_five_step_immediate',layout['driver']['reset_finish']-3,
         bytes((0x3f,layout['driver']['half_pair']&255,layout['driver']['half_pair']>>8)),bytes(3),128),
        ('legacy_volume_writer_restored',0x577,b'\xac',b'\xf3',0)):
        damaged=bytearray(image);offset=address-0x400
        if damaged[offset:offset+len(old)]!=old:raise ValueError('Mutant preimage: '+name)
        damaged[offset:offset+len(old)]=new
        test=Driver(core,bytes(damaged),layout)
        result=realtime_case(test,mode,2048)
        mutants.append(dict(name=name,rejected=not result['passed'],result=result))
        if result['passed']:failure('surviving_mutant',name=name)
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Changed source during execution: '+path)
    out.mkdir(parents=True,exist_ok=False);binary=out/'sweep-driver.bin';binary.write_bytes(image)
    report=dict(passed=not errors,quick=quick,clock_cases=clock_cases,publisher_cases=publisher_cases,
        envelope_cases=envelope_cases,idle_cases=idle_cases,errors=errors,realtime=realtime,mutants=mutants,layout=layout,
        sources={**sources,str(binary):sha(binary)},release_ready=False,physical_audio_verified=False,
        scope='Actual generated driver instructions, hardware timers, paired port receiver and DSP '
        'writes. Clock phase and publisher matrices plus one-second 4/5-step runs with sender '
        'delays. Rounded NTSC deadlines, 512-clock timer sampling, publication-time resets; '
        'not cycle-exact NES hardware, analog sound fidelity or full-game speed/scrolling.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','clock_cases','publisher_cases','envelope_cases','errors')},indent=2))
    print(json.dumps([dict(mode=r['mode'],delay=r['delay'],passed=r['passed'],events=len(r['events']),
        minimum=min(r['deadline_offsets'],default=None),maximum=max(r['deadline_offsets'],default=None)) for r in realtime]))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--quick',action='store_true');check(**vars(p.parse_args()))
