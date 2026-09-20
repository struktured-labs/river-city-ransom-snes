"""Executed broken deadlines and ordered-stream tests for the automatic receiver."""
import argparse
import json
from pathlib import Path
import time
from tools.check_timed_receiver import Timed, case, deadline_bounds
from tools.check_staged_receiver import packet
from tools.qualify_staged_receiver import changed
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def timing_errors(meta, first_ack, deadline):
    arm,commit,complete,leaks,seen=meta
    errors=[]
    if not 0<arm<=first_ack:errors.append('arm_not_before_first_ack')
    lo,hi=deadline_bounds(arm,complete,deadline)
    if not lo<=commit<=hi:errors.append('commit_deadline')
    if leaks or not seen:errors.append('isolation_or_missing_commit')
    return errors


def repeated(core,image,meta,mode):
    run=Timed(core,image,meta['layout']);run.boot();records=[];errors=[]
    for generation in range(101):
        p=packet(mode,bool(generation))
        if generation:
            for i in (2,6,10):p[i]=(80+generation*(i+1))%256
            for i in (3,7,11):p[i]=(generation+i)%8
            for i in (9,13,15,18,19):p[i]=(generation*(i+1))%256
            p[14]=generation%16;p[16]=generation%16;p[17]=generation%128
        delay=(0,256,512,2048)[generation%4]
        deadline=(0,1,8,16,32,255)[generation%6]
        before=list(run.out[0x40:0x57]);status,s,m=run.send(p,delay,deadline,meta['labels'])
        problems=timing_errors(m,s[0][384],deadline)
        if status:problems.append('protocol')
        if any(x[0x40:0x57]!=before for x in s[:13]):problems.append('partial_active_write')
        if s[14][0x40:0x57]!=list(p) or s[12][388:411]!=list(p):problems.append('lost_or_reordered_bytes')
        if s[13][411] or s[13][386]:problems.append('ownership')
        if problems:errors.append(dict(generation=generation,errors=problems))
        records.append(dict(generation=generation,packet=list(p),delay=delay,deadline=deadline,
            meta=m,first_ack=s[0][384],ready=s[13][384],committed=s[14][0x40:0x57]))
    return dict(passed=not errors,errors=errors,records=records)


def qualify(build,fixture,out):
    if out.exists():raise ValueError('Fresh output required')
    start=time.monotonic();proof=bound(build/'timed-core.json')
    bound(Path('.deps/snes9x-staged-receiver-4055/staged-core.json'))
    meta=bound(fixture/'manifest.json');core=Path(proof['core']);image=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed engine')
    labels=meta['labels']
    mutants={
        'frozen_countdown':changed(image,labels['store'],bytes.fromhex('c51836'),bytes(3)),
        'premature_commit':changed(image,labels['hold'],bytes.fromhex('e51836'),bytes.fromhex('e80000')),
        'lost_final_flags':changed(image,labels['copy']+7,b'\x17',b'\x16'),
        'lost_sound_timer_delta':changed(image,labels['store']+4,bytes.fromhex('5f3232'),bytes.fromhex('6f0000')),
        'header_relatched_each_pair':changed(image,0x3549,bytes.fromhex('f0035f5f35'),bytes(5)),
    }
    controls={}
    for name,raw in mutants.items():
        r=case(core,raw,meta['layout'],labels,0,512,32,0)
        extra=timing_errors(r['meta'],r['snapshots'][0][384],32)
        controls[name]=dict(passed=r['passed'] and not extra,errors=r['errors'],extra_errors=extra,result=r)
    streams=[repeated(core,image,meta,mode) for mode in (0,128)]
    passed=all(not r['passed'] for r in controls.values()) and all(r['passed'] for r in streams)
    paths=[Path(__file__),Path('tools/check_timed_receiver.py'),Path('tools/check_staged_receiver.py'),
        Path('tools/qualify_staged_receiver.py'),Path('tools/check_interleaved_volume_state.py'),
        Path('tools/check_sweep_driver.py'),build/'timed-core.json',fixture/'manifest.json',fixture/'engine.bin',core]
    report=dict(passed=passed,controls=controls,streams=streams,seconds=time.monotonic()-start,
        sources={str(p):sha(p) for p in paths},fixture_only=True,release_ready=False,scope=__doc__)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,seconds=report['seconds'],
        controls={n:dict(passed=r['passed'],errors=r['errors'],extra=r['extra_errors']) for n,r in controls.items()},
        streams=[r['errors'] for r in streams])))
    if not passed:raise ValueError('Timed receiver qualification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
    qualify(**vars(p.parse_args()))
