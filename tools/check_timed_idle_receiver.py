"""Held-envelope and automatic deadline qualification, including the actual frozen-envelope parent."""
import argparse
import json
from pathlib import Path
import time
from tools.check_timed_receiver import Timed,case
from tools.check_staged_receiver import packet
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def envelope(core,engine,layout,labels):
    run=Timed(core,engine,layout);run.boot();p=packet(0,0);p[0]=0x20;p[21]=1
    status,_,_=run.send(p,0,0,labels)
    if status:raise ValueError('Envelope initialization failed')
    p[20]=0;p[22]=0
    status,_,_=run.send(p,0,0,labels)
    if status:raise ValueError('Envelope restart-flag clear failed')
    before=list(run.out[:256]);p[2]=220;p[20]=4;p[22]=64
    status,s,meta=run.send(p,512,32,labels)
    return dict(passed=status==0 and meta[3]==0 and s[14][0x86]!=before[0x86],
        status=status,before_level=before[0x86],before_commit_level=s[14][0x86],
        first_ack_level=s[0][0x86],last_ack_level=s[12][0x86],meta=meta,snapshots=s)


def check(build,before,fixture,out):
    if out.exists():raise ValueError('Fresh output required')
    start=time.monotonic();proof=bound(build/'timed-core.json');core=Path(proof['core'])
    arms=[]
    for root in (before,fixture):
        meta=bound(root/'manifest.json');image=(root/'engine.bin').read_bytes()
        if sha(root/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed engine')
        arms.append((meta,image))
    old,new=arms
    env_before=envelope(core,old[1],old[0]['layout'],old[0]['labels'])
    env_after=envelope(core,new[1],new[0]['layout'],new[0]['labels'])
    cases=[case(core,new[1],new[0]['layout'],new[0]['labels'],mode,delay,deadline,phase)
        for mode in (0,128) for delay in (0,256,512,2048)
        for deadline in (0,1,2,8,16,32,33,255) for phase in (0,127,511)]
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/check_timed_receiver.py'),Path('tools/check_staged_receiver.py'),
        Path('tools/check_sweep_driver.py'),Path('tools/check_interleaved_volume_state.py'),build/'timed-core.json',core,
        before/'manifest.json',before/'engine.bin',fixture/'manifest.json',fixture/'engine.bin')}
    passed=env_after['passed'] and not env_before['passed'] and all(c['passed'] for c in cases)
    report=dict(passed=passed,before_envelope=env_before,after_envelope=env_after,cases=cases,
        sources=sources,seconds=time.monotonic()-start,fixture_only=True,release_ready=False,scope=__doc__)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,before={k:env_before[k] for k in ('before_level','before_commit_level')},
        after={k:env_after[k] for k in ('before_level','before_commit_level')},cases=len(cases),seconds=report['seconds'],
        failures=[dict(mode=c['mode'],delay=c['delay'],deadline=c['deadline'],phase=c['phase'],errors=c['errors']) for c in cases if not c['passed']])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','before','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
