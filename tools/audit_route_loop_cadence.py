"""Compare complete original main-loop cadence across all four sampled rooms.

Keeps encounter/workload differences explicit; not an input-latency or full-game gate.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_nes_filter import bound
from tools.benchmark_report import sha,verify_capture
from tools.nes_event_trace import validate


def nes_pair(events):
    active=None;loops=[];censored=[]
    for row in events:
        event=int(row[3])
        r=dict(frame=int(row[0]),line=int(row[1]),clock=int(row[2]),
               tick=int(row[6]),stack=int(row[12]))
        if event==0:
            if active is not None:raise ValueError('NES iteration restarted before completion')
            active=dict(start=r,input=None)
        elif event==1:
            if active is None or active['input'] is not None or r['tick']!=0:
                raise ValueError('Missing, duplicate or uncleared input entry')
            if r['stack']!=active['start']['stack']:raise ValueError('NES input stack differs')
            active['input']=r
        elif event==2:
            if active is None:
                censored.append(dict(kind='leading completion',event=r));continue
            if active['input'] is None or r['stack']!=active['start']['stack']:
                raise ValueError('NES finish lacks input or stack restoration')
            loops.append(dict(**active,finish=r,nmi_advances=r['tick'],
                              elapsed_clocks=r['clock']-active['start']['clock']))
            active=None
        else:raise ValueError('Unexpected NES event')
    if active is not None:censored.append(dict(kind='trailing iteration',event=active))
    if not loops:raise ValueError('No complete NES loops')
    return loops,censored


def stable_room(rows):
    rooms=set()
    for row in rows:
        ram=bytes.fromhex(row['game_ram_hex'])
        if len(ram)!=2048:raise ValueError('Need complete game RAM')
        rooms.add(ram[0x42])
        if (ram[0x100]!=0xc0 or ram[0x107]&128 or ram[0x3f]&32 or
                ram[0x3e]&130 or ram[0x692]!=4 or row.get('native',{}).get('transition_state',0)):
            return None
    return next(iter(rooms)) if len(rooms)==1 and next(iter(rooms)) in range(4) else None


def measure(loops,rows):
    rooms={str(i):dict(iterations=[],start_intervals=[]) for i in range(4)}
    excluded=[]
    for loop in loops:
        a,b=loop['start']['frame'],loop['finish']['frame']
        if not 1<=a<=b<=len(rows):raise ValueError('Loop outside timeline')
        room=stable_room(rows[a-1:b])
        (excluded if room is None else rooms[str(room)]['iterations']).append(loop)
    for key,value in rooms.items():
        for a,b in zip(value['iterations'],value['iterations'][1:]):
            first,last=a['start']['frame'],b['start']['frame']
            if stable_room(rows[first-1:last])==int(key):
                value['start_intervals'].append(dict(first=first,last=last,frames=last-first,
                    clocks=b['start']['clock']-a['start']['clock']))
        value['nmi_advances']=dict(Counter(str(x['nmi_advances']) for x in value['iterations']))
        value['start_frame_spans']=dict(Counter(str(x['frames']) for x in value['start_intervals']))
        value['off_cadence_iterations']=[x for x in value['iterations'] if x['nmi_advances']!=2]
        value['off_cadence_starts']=[x for x in value['start_intervals'] if x['frames']!=2]
    passed=all(len(v['iterations'])>=64 and v['start_intervals'] and
               not v['off_cadence_iterations'] and not v['off_cadence_starts'] for v in rooms.values())
    return dict(sampled_two_tick_cadence=passed,minimum_iterations_per_room=64,
                rooms=rooms,excluded=excluded)


def audit(nes,normal_nes,snes,normal_snes,rom,out):
    n,nrows=verify_capture(nes);normal,baseline=verify_capture(normal_nes)
    if nrows!=baseline or not n['capture_complete'] or any(n[k]!=normal[k] for k in
            ('rom_sha256','audio_sha256','scenario_sha256','frames')):
        raise ValueError('NES observer not complete and neutral')
    s=bound(snes);sr,srows=verify_capture(normal_snes)
    if (not s['observer_neutral'] or s['sources'].get(str(normal_snes/'capture.json'))!=sha(normal_snes/'capture.json')
            or sr['scenario_sha256']!=n['scenario_sha256']):raise ValueError('Unbound/different SNES scenario')
    if sha(rom)!=n['rom_sha256']:raise ValueError('Different original ROM')
    data=rom.read_bytes()
    for pc,wanted in ((0xf27d,bytes.fromhex('a9008d0b01')),(0xf282,bytes.fromhex('2031f7')),
                      (0xf2da,bytes.fromhex('ee2b05'))):
        if data[16+0x10000+pc:16+0x10000+pc+len(wanted)]!=wanted:raise ValueError('NES loop opcode changed')
    binding=n['nes_event_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256'] or binding['points']!={'0':'f27d','1':'f282','2':'f2da'}:
        raise ValueError('Incorrect NES trace binding')
    with trace.open() as f:events=list(csv.reader(f))
    validate(events,binding['first'],binding['last'],n['frames'],binding['points'])
    loops,censored=nes_pair(events)
    native=sorted(s['iterations']+s['excluded'],key=lambda x:x['start']['clock'])
    result=dict(nes=measure(loops,nrows),snes=measure(native,srows),nes_censored=censored,
        snes_censored=s['censored'],observer_neutral=True,release_ready=False,
        input_latency_verified=False,matched_encounter_speed_verified=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/nes_event_trace.py'),
            Path('tools/benchmark_report.py'),nes/'capture.json',normal_nes/'capture.json',
            normal_snes/'capture.json',snes,trace,rom)},
        scope='All four room IDs0..3, stable gameplay only using identical original RAM predicates. '
              'Complete exact-PC start/input/F2DA loops; original NES clears010B before input and '
              'counts actual game ticks, SNES uses observed16-bit native NMI advances. All excluded '
              'and censored loops retained. Encounters and route lengths differ; no equal-work '
              'ratio, whole-game speed, physical latency or background-publication waiver.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({system:{room:{k:len(v) if k in ('iterations','start_intervals') else v
        for k,v in values.items() if k in ('iterations','start_intervals','nmi_advances','start_frame_spans')}
        for room,values in result[system]['rooms'].items()} for system in ('nes','snes')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('nes','normal-nes','snes','normal-snes','rom','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
