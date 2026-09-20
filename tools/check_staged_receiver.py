"""Execute real SPC staging, per-byte isolation, held timers and explicit commit."""
import argparse
import ctypes as C
import json
from pathlib import Path
import time
from tools.check_interleaved_volume_state import VolumeDriver
from tools.check_sweep_driver import audit_deadlines
from tools.benchmark_report import sha
from tools.review_command_priority import bound
from tools.build_staged_receiver_fixture import stage


class Staged(VolumeDriver):
    def send(self,packet,delay,hold):
        fn=self.lib.retro_rcr_driver_staged_packet
        fn.argtypes=[C.c_char_p,C.c_uint,C.c_uint,C.POINTER(C.c_uint)];fn.restype=C.c_uint
        out=(C.c_uint*(15*412))()
        status=fn(bytes(packet),delay,hold,out)
        snapshots=[list(out[i*412:(i+1)*412]) for i in range(15)]
        self.out[:]=snapshots[13][:388]
        return status,snapshots


def packet(mode,variant):
    p=bytearray(23)
    p[:8]=bytes((0x3f,8,172 if not variant else 220,0,0x3b,8,180 if not variant else 120,0))
    p[8:20]=bytes((0x80,0,90 if not variant else 100,0,0x1f,0,5 if not variant else 7,0,0,0,0,0))
    p[20]=63|(64|mode if not variant else 0)
    p[21]=3;p[22]=195
    return p


def case(core,engine,layout,mode,delay,hold):
    run=Staged(core,engine,layout);run.boot()
    status,initial=run.send(packet(mode,0),0,64)
    if status:raise ValueError(f'Initial packet failed: {status}')
    before=list(run.out[:256]);epoch=run.out[387]
    new=packet(mode,1);status,snaps=run.send(new,delay,hold)
    errors=[]
    if status:errors.append(dict(kind='protocol',status=status))
    for i,s in enumerate(snaps[:13]):
        if s[0x40:0x57]!=before[0x40:0x57]:errors.append(dict(kind='active_before_commit',snapshot=i))
        length=min(23,2*(i+1))
        if s[388:388+length]!=list(new[:length]):errors.append(dict(kind='staged_bytes',snapshot=i))
    if snaps[12][411]!=1 or snaps[13][411]!=0:errors.append(dict(kind='pending_ownership'))
    if snaps[14][0x40:0x57]!=list(new):errors.append(dict(kind='commit_bytes'))
    if snaps[13][386]:errors.append(dict(kind='volume_owner',writes=snaps[13][386]))
    # Hold an update across multiple old-state half-frame deadlines. Include
    # initial and terminal censoring through the existing independent oracle.
    run.wait(100000)
    timing=audit_deadlines(run.events(),epoch,run.out[384],mode)
    if not timing['passed']:errors.append(dict(kind='timer_deadlines'))
    return dict(mode=mode,delay=delay,hold=hold,passed=not errors,errors=errors,
        snapshots=snaps,before=before,packet=list(new),timing=timing,events=run.events(),
        status=status,epoch=epoch,end=run.out[384])


def check(build,fixture,parent,out):
    if out.exists():raise ValueError('Fresh report required')
    start=time.monotonic();proof=bound(build/'staged-core.json')
    core=Path(proof['core'])
    meta=bound(fixture/'manifest.json');engine=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed fixture')
    m=json.loads((parent/'manifest.json').read_text());raw=(parent/'native-cpu.sfc').read_bytes()
    at=m['sweep_driver_rom_offset'];base=raw[at:at+m['sweep_driver_layout']['engine_bytes']]
    if stage(base)[0]!=engine:raise ValueError('Fixture differs from patch')
    cases=[case(core,engine,meta['layout'],mode,delay,hold) for mode in (0,128)
           for delay in (0,256,512,2048) for hold in (64,1024,20000)]
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/check_sweep_driver.py'),
        Path('tools/check_interleaved_volume_state.py'),Path('tools/build_staged_receiver_fixture.py'),
        Path('tools/spc_staged_receiver_probe.inc'),Path('tools/spc_sweep_driver_probe.inc'),
        build/'staged-core.json',core,fixture/'manifest.json',fixture/'engine.bin')}
    report=dict(passed=all(c['passed'] for c in cases),cases=cases,sources=sources,
        seconds=time.monotonic()-start,fixture_only=True,release_ready=False,scope=__doc__)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],cases=len(cases),seconds=report['seconds'],
        failures=[dict(mode=c['mode'],delay=c['delay'],hold=c['hold'],errors=c['errors']) for c in cases if not c['passed']])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','fixture','parent','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
