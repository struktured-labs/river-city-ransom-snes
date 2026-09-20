"""Staged receiver negative controls and repeated ordered commit qualification."""
import argparse
import json
from pathlib import Path
import time
from tools.check_staged_receiver import Staged,case,packet
from tools.check_receiver_poll_trial import stream
from tools import check_receiver_poll_trial as receiver
from tools.check_interleaved_volume_state import VolumeDriver
from tools.benchmark_report import sha
from tools.review_command_priority import bound


def changed(engine,at,old,new):
    result=bytearray(engine);i=at-0x400
    if result[i:i+len(old)]!=old or len(old)!=len(new):raise ValueError('Changed mutant guard')
    result[i:i+len(old)]=new
    return bytes(result)


def repeated(core,engine,layout,mode):
    run=Staged(core,engine,layout);run.boot();errors=[];records=[]
    for generation in range(101):
        p=packet(mode,bool(generation))
        if generation:
            for i in (2,6,10):p[i]=(80+generation*(i+1))%256
            for i in (3,7,11):p[i]=(generation+i)%8
            for i in (9,13,15,18,19):p[i]=(generation*(i+1))%256
            p[14]=generation%16;p[16]=generation%16;p[17]=generation%128
        delay=(0,256,512,2048)[generation%4];hold=(64,1024,20000)[generation%3]
        before=list(run.out[:256]);status,s=run.send(p,delay,hold)
        leaks=[i for i,x in enumerate(s[:13]) if x[0x40:0x57]!=before[0x40:0x57]]
        # Boot itself may leave23 active registers zero; the same isolation
        # rule applies to that first packet, rather than censoring it.
        if status or leaks or s[14][0x40:0x57]!=list(p) or s[12][388:411]!=list(p):
            errors.append(dict(generation=generation,status=status,leaks=leaks))
        if s[12][411]!=1 or s[13][411]!=0 or s[13][386]:
            errors.append(dict(generation=generation,ownership=True))
        records.append(dict(generation=generation,packet=list(p),delay=delay,hold=hold,
            before=before[0x40:0x57],held=s[12][0x40:0x57],staged=s[12][388:411],
            committed=s[14][0x40:0x57],first_ack=s[0][384],held_clock=s[12][384],
            committed_clock=s[14][384],ready_clock=s[13][384]))
    return dict(passed=not errors,mode=mode,errors=errors,records=records)


def qualify(build,fixture,first,parent,out):
    if out.exists():raise ValueError('Fresh output required')
    start=time.monotonic();proof=bound(build/'staged-core.json');core=Path(proof['core'])
    original=bound(first/'report.json');meta=bound(fixture/'manifest.json')
    engine=(fixture/'engine.bin').read_bytes()
    if not original['passed'] or sha(fixture/'engine.bin')!=meta['engine_sha256']:raise ValueError('Invalid first qualification')
    labels=meta['labels'];mutants={}
    # Wrong destination: publish received bytes straight into active state.
    direct=bytearray(engine)
    for pattern in (bytes.fromhex('e4f5d50036'),bytes.fromhex('e4f6d50036')):
        offset=direct.find(pattern,0x3540-0x400)
        if offset<0:raise ValueError('Missing receive store')
        direct[offset+2:offset+5]=bytes.fromhex('d44000')
    mutants['partial_active_leak']=bytes(direct)
    mutants['early_commit']=changed(engine,labels['hold']+3,b'\xd8',b'\x16')
    mutants['short_commit']=changed(engine,labels['copy']+7,b'\x17',b'\x16')
    call=engine.find(bytes.fromhex('3f5534'),labels['hold']-0x400)
    if call<0:raise ValueError('Missing hold timer call')
    mutants['hold_timer_removed']=changed(engine,call+0x400,bytes.fromhex('3f5534'),bytes(3))
    results={name:case(core,image,meta['layout'],0,2048,20000) for name,image in mutants.items()}
    repetitions=[repeated(core,engine,meta['layout'],mode) for mode in (0,128)]
    # Compatibility check: the appended test API must not alter ordinary
    # packet/timer execution of the untouched3955 engine.
    m=json.loads((parent/'manifest.json').read_text());raw=(parent/'native-cpu.sfc').read_bytes()
    at=m['sweep_driver_rom_offset'];baseline=raw[at:at+m['sweep_driver_layout']['engine_bytes']]
    oldcore=Path('.deps/snes9x-driver-1093/libretro/rcr_sweep_driver_libretro.so')
    previous=receiver.Driver
    try:
        receiver.Driver=VolumeDriver
        compatibility=[]
        for mode in (0,128):
            for delay in (0,256,512,2048):
                a=stream(oldcore,baseline,meta['layout'],mode,delay)
                b=stream(core,baseline,meta['layout'],mode,delay)
                compatibility.append(dict(mode=mode,delay=delay,identical=a==b,passed=a['passed'] and b['passed']))
    finally:receiver.Driver=previous
    passed=all(not r['passed'] for r in results.values()) and all(r['passed'] for r in repetitions) and all(r['identical'] and r['passed'] for r in compatibility)
    paths=[Path(__file__),Path('tools/check_staged_receiver.py'),Path('tools/check_receiver_poll_trial.py'),
        Path('tools/check_interleaved_volume_state.py'),Path('tools/check_sweep_driver.py'),
        build/'staged-core.json',first/'report.json',fixture/'manifest.json',fixture/'engine.bin',
        core,oldcore,parent/'native-cpu.sfc',parent/'manifest.json']
    report=dict(passed=passed,mutants=results,repeated=repetitions,compatibility=compatibility,
        sources={str(p):sha(p) for p in paths},seconds=time.monotonic()-start,fixture_only=True,release_ready=False,scope=__doc__)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,seconds=report['seconds'],mutants={n:r['errors'] for n,r in results.items()},
        repeat_errors=[r['errors'] for r in repetitions],compatibility=compatibility)))
    if not passed:raise ValueError('Staging qualification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','fixture','first','parent','out'):p.add_argument('--'+k,type=Path,required=True)
    qualify(**vars(p.parse_args()))
