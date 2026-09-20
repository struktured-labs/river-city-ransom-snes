"""Check actual SPC receives, whole-run neutrality, and executed damaged players."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_sweep_driver_game import sites
from tools.benchmark_report import sha


def validate(records, payload, pcs):
    expected=[];at=0
    while at<len(payload):
        count=payload[at];at+=1
        if count not in (0,1) or at+count*23>len(payload):
            raise ValueError('Invalid stream')
        if count:
            expected.extend((i,value,pcs[i%2]) for i,value in enumerate(payload[at:at+23]))
            at+=23
    actual=[]
    for r in records:
        if len(r)!=3:raise ValueError('Invalid receiver trace')
        actual.append((int(r[0]),int(r[1]),int(r[2],16)))
    errors=[dict(index=i,expected=a,actual=b) for i,(a,b) in enumerate(zip(expected,actual)) if a!=b]
    return dict(passed=bool(expected) and len(actual)==len(expected) and not errors,
        expected_bytes=len(expected),actual_bytes=len(actual),mismatching_bytes=len(errors),
        first_mismatches=errors[:20])


def audit(candidate,fixture,normal,observed,trace,slow,wrong,wrong_trace,out):
    m,pcs,_=sites(candidate)
    f=bound_report(fixture/'manifest.json');n=bound_report(normal/'report.json')
    o=bound_report(observed/'report.json');s=bound_report(slow/'report.json')
    w=bound_report(wrong/'report.json')
    for execution, mutation in ((s,'double-frame'),(w,'wrong-port')):
        manifests=[Path(p) for p in execution['sources'] if p.endswith('/manifest.json')]
        if len(manifests)!=1:raise ValueError('Ambiguous executed negative fixture')
        damaged=bound_report(manifests[0])
        if (damaged.get('mutation')!=mutation or damaged['spc_sha256']!=f['spc_sha256'] or
                damaged['source_rom_sha256']!=f['source_rom_sha256'] or
                (manifests[0].parent/'stream.bin').read_bytes()!=(fixture/'stream.bin').read_bytes()):
            raise ValueError('Unrelated negative fixture')
    if f['spc_sha256']!=m['spc_sha256'] or f.get('mutation'):
        raise ValueError('Different engine or mutated positive fixture')
    if not n['passed'] or not o['passed'] or n['receipt']['rom_sha256']!=f['rom_sha256'] or o['receipt']['rom_sha256']!=f['rom_sha256']:
        raise ValueError('Incomplete/different positive replay')
    if any((normal/p).read_bytes()!=(observed/p).read_bytes() for p in ('audio.wav','timeline.json','memory.ram')):
        raise ValueError('Nonneutral receiver observer')
    payload=(fixture/'stream.bin').read_bytes()
    with trace.open() as stream:positive=validate(csv.reader(stream),payload,pcs)
    with wrong_trace.open() as stream:negative=validate(csv.reader(stream),payload,pcs)
    if (not positive['passed'] or negative['passed'] or not w['passed'] or s['passed'] or
            s['error']!='Missing source frame/cadence'):
        raise ValueError('Missing positive/negative sensitivity')
    result=dict(passed=True,observer_neutral=True,source_rom_sha256=m['rom_sha256'],
        replay_rom_sha256=f['rom_sha256'],spc_sha256=f['spc_sha256'],frames=n['frames'],
        packets=n['packets'],receiver=positive,wrong_port=negative,double_wait_error=s['error'],
        physical_audio_verified=False,release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),candidate/'manifest.json',fixture/'manifest.json',
            fixture/'player.sfc',fixture/'stream.bin',normal/'report.json',observed/'report.json',
            slow/'report.json',wrong/'report.json',trace,wrong_trace)},
        scope='Exact embedded game SPC engine, all packet bytes and source-frame cadence; '
              'complete WAV/timeline/RAM observer neutrality. Executed double-wait and wrong-port '
              'players rejected. Publication-frame scheduling, not original game sub-frame timing. '
              'Hardware playback and visual frame-code decoding still required.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','frames','packets','receiver','double_wait_error')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','fixture','normal','observed','trace','slow','wrong','wrong-trace','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
