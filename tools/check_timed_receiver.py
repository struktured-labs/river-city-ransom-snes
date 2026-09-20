"""Execute automatic SPC commit deadlines, isolation and continuous sound timers."""
import argparse
import ctypes as C
import json
from pathlib import Path
import time
from tools.check_interleaved_volume_state import VolumeDriver
from tools.check_staged_receiver import packet
from tools.check_sweep_driver import audit_deadlines
from tools.benchmark_report import sha
from tools.review_command_priority import bound
from tools.build_timed_receiver_fixture import stage


class Timed(VolumeDriver):
    def send(self,p,delay,deadline,labels):
        fn=self.lib.retro_rcr_driver_timed_packet
        fn.argtypes=[C.c_char_p]+[C.c_uint]*4+[C.POINTER(C.c_uint)];fn.restype=C.c_uint
        out=(C.c_uint*(16*412))()
        status=fn(bytes(p),delay,deadline,labels['arm'],labels['commit'],out)
        snapshots=[list(out[i*412:(i+1)*412]) for i in range(15)]
        meta=list(out[15*412:15*412+5]);self.out[:]=snapshots[13][:388]
        return status,snapshots,meta


def deadline_bounds(arm,complete,header):
    ticks=min(header,32)
    return max(arm+max(0,ticks-1)*512,complete),max(arm+ticks*512,complete)+1400


def case(core,engine,layout,labels,mode,delay,deadline,phase):
    run=Timed(core,engine,layout);run.boot()
    status,_,_=run.send(packet(mode,0),0,0,labels)
    if status:raise ValueError(f'Initial packet failed: {status}')
    epoch=run.out[387];run.wait(phase)
    before=list(run.out[:256]);new=packet(mode,1)
    status,s,meta=run.send(new,delay,deadline,labels)
    arm,commit,complete,leaks,seen=meta;errors=[]
    if status:errors.append(dict(kind='protocol',status=status))
    if not arm or not commit or not seen:errors.append(dict(kind='missing_timing'))
    if leaks:errors.append(dict(kind='early_active_writes',observations=leaks))
    for i,x in enumerate(s[:13]):
        if x[0x40:0x57]!=before[0x40:0x57]:errors.append(dict(kind='active_before_commit',snapshot=i))
        length=min(23,2*(i+1))
        if x[388:388+length]!=list(new[:length]):errors.append(dict(kind='staged_bytes',snapshot=i))
    if s[14][0x40:0x57]!=list(new):errors.append(dict(kind='commit_bytes'))
    if s[13][411]!=0 or s[13][386]:errors.append(dict(kind='ownership'))
    lower,upper=deadline_bounds(arm,complete,deadline)
    if not lower<=commit<=upper:errors.append(dict(kind='commit_deadline',observed=commit,lower=lower,upper=upper))
    run.wait(100000)
    clocks=audit_deadlines(run.events(),epoch,run.out[384],mode)
    if not clocks['passed']:errors.append(dict(kind='sound_timer_deadlines'))
    return dict(passed=not errors,mode=mode,delay=delay,deadline=deadline,phase=phase,errors=errors,
        timing=dict(arm=arm,complete=complete,commit=commit,ready=s[13][384],lower=lower,upper=upper,
            relative_commit=commit-arm,packet_late=complete>arm+min(deadline,32)*512),
        packet=list(new),before=before,snapshots=s,meta=meta,timers=clocks,events=run.events())


def check(build,fixture,parent,out):
    if out.exists():raise ValueError('Fresh output required')
    start=time.monotonic();proof=bound(build/'timed-core.json');core=Path(proof['core'])
    bound(Path('.deps/snes9x-staged-receiver-4055/staged-core.json'))
    meta=bound(fixture/'manifest.json');engine=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed fixture')
    m=json.loads((parent/'manifest.json').read_text());image=(parent/'native-cpu.sfc').read_bytes()
    at=m['sweep_driver_rom_offset'];base=image[at:at+m['sweep_driver_layout']['engine_bytes']]
    if stage(base)[0]!=engine:raise ValueError('Not exact timed fixture')
    cases=[case(core,engine,meta['layout'],meta['labels'],mode,delay,deadline,phase)
        for mode in (0,128) for delay in (0,256,512,2048)
        for deadline in (0,1,2,8,16,32,33,255) for phase in (0,127,511)]
    paths=[Path(__file__),Path('tools/check_staged_receiver.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/check_interleaved_volume_state.py'),Path('tools/build_timed_receiver_fixture.py'),
        Path('tools/spc_timed_receiver_probe.inc'),Path('tests/test_timed_receiver.py'),
        build/'timed-core.json',fixture/'manifest.json',fixture/'engine.bin',core]
    report=dict(passed=all(c['passed'] for c in cases),cases=cases,sources={str(p):sha(p) for p in paths},
        seconds=time.monotonic()-start,fixture_only=True,release_ready=False,scope=__doc__)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],cases=len(cases),seconds=report['seconds'],
        failures=[dict(mode=c['mode'],delay=c['delay'],deadline=c['deadline'],phase=c['phase'],errors=c['errors']) for c in cases if not c['passed']])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','fixture','parent','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
