"""Select complete zero-volume runs with unchanged upper bits and an audible predecessor.

Only within a complete original sound-wrapper call. Keep all final writes,
reloads, enable writes and mode changes. This is an audio sensitivity experiment,
not a model of the complete SNES snapshot protocol.
"""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

from tools.audit_driver_write_coalescing import parse_writes,group_nes
from tools.audit_main_display_latency import bound_report
from tools.audit_ordinary_route_timing import sound_pairs
from tools.benchmark_report import sha,verify_capture
from tools.capture_nes_audio_events import POINTS
from tools.nes_event_trace import validate


def key(w):
    return (w['frame'],w['clock'],w['pc'],w['register'],w['value'])


def select(writes,pairs):
    previous={};priors={};seen=set()
    for w in writes:
        k=key(w)
        if k in seen:raise ValueError('Duplicate write identity')
        seen.add(k);priors[k]=previous.get(w['register']);previous[w['register']]=w
    groups,_=group_nes(writes,pairs)
    selected=[];excluded=[]
    for g in groups:
        by=defaultdict(list)
        for w in g['writes']:
            if w['register'] in (0,4,12):by[w['register']].append(w)
        for register,ws in by.items():
            i=0
            while i<len(ws):
                first=ws[i]
                if not first['value']&16 or first['value']&15:
                    i+=1;continue
                j=i+1
                while j<len(ws) and ws[j]['value']==first['value']:j+=1
                before=priors[key(first)];after=ws[j] if j<len(ws) else None
                reasons=[]
                if before is None:reasons.append('unknown preceding control')
                elif not before['value']&15:reasons.append('preceding volume already zero')
                elif before['value']&240 != first['value']&240:reasons.append('mode/duty changes at zero')
                if after is None:reasons.append('no final nonzero in same wrapper')
                elif not after['value']&15 or after['value']&240 != first['value']&240:
                    reasons.append('final mode/duty differs or still zero')
                case=dict(driver=g['driver'],register=register,previous=before,zeros=ws[i:j],
                    final=after,entry=g['entry'],returned=g['returned'],exclusions=reasons)
                if not reasons:
                    case['duration_cycles']=after['clock']-first['clock']
                    selected.append(case)
                else:excluded.append(case)
                i=j
    selected.sort(key=lambda c:c['zeros'][0]['clock'])
    drops=sorted((w for c in selected for w in c['zeros']),key=lambda w:w['clock'])
    if not drops:raise ValueError('No qualifying zero-volume runs')
    return selected,excluded,drops


def plan(capture,out):
    if out.exists():raise ValueError('Fresh plan required')
    binding=bound_report(capture/'driver-writes.json');receipt,_=verify_capture(capture)
    if not binding['observer_neutral']:raise ValueError('Unqualified original trace')
    with Path(binding['events']).open() as f:events=list(csv.reader(f))
    validate(events,1,receipt['frames'],receipt['frames'],POINTS)
    pairs,_=sound_pairs(events)
    with Path(binding['writes']).open() as f:writes=parse_writes(csv.reader(f),receipt['frames'])
    selected,excluded,drops=select(writes,pairs)
    out.mkdir(parents=True)
    schedule=''.join(f'{w["frame"]},{w["clock"]},{w["pc"]:04x},{w["register"]+0x4000:04x},{w["value"]}\n' for w in drops)
    (out/'schedule.csv').write_text(schedule)
    sources=dict(binding['sources'])
    for p in (Path(__file__),Path('tests/test_nes_volume_suppression.py'),
        Path('tools/audit_driver_write_coalescing.py'),Path('tools/audit_ordinary_route_timing.py'),
        capture/'driver-writes.json',capture/'capture.json',out/'schedule.csv'):
        sources[str(p)]=sha(p)
    result=dict(selected=selected,excluded=excluded,drops=drops,source_frames=receipt['frames'],
        original_capture=str(capture),rom_sha256=receipt['rom_sha256'],sources=sources,
        release_ready=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(runs=len(selected),drops=len(drops),excluded=len(excluded),
        registers=sorted({w['register'] for w in drops}))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','out'):p.add_argument('--'+name,type=Path,required=True)
    plan(**vars(p.parse_args()))
