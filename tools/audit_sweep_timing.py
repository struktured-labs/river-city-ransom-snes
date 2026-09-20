"""Join actual NES timer writes/half-frame updates to actual SPC sweep reloads."""
import argparse
from bisect import bisect_right
import csv
import json
from pathlib import Path

from tools.analyze_audio_bus import analyze
from tools.analyze_spc_receive import compare
from tools.audit_main_display_latency import bound_report
from tools.audit_stimulus_audio import verify_sources
from tools.benchmark_report import sha
from tools.replay_nes_apu_stimulus import publication_writes

SPC_HZ=32040*32
NES_HZ=1789772.7272727273
RELOAD_PC={0:0x9a4,1:0xac9}
UPDATE_PC={0:{0xa3d,0xa4c},1:{0xb54,0xb63}}


def nes_events(records):
    writes=[];changes=[[],[]];pending={};previous=-1;half_frames=[[],[]]
    for raw in records:
        if len(raw)!=11 or raw[0] not in ('W','B','H'):raise ValueError('Invalid NES sweep row')
        kind=raw[0];frame,clock,voice,address,value,period,control,count,reload,ready=map(int,raw[1:])
        if clock<previous or voice not in (0,1) or ready not in (0,1):raise ValueError('Invalid NES sweep ordering/state')
        previous=clock
        r=dict(kind=kind,completed_frame=frame,clock=clock,voice=voice,address=address,
               value=value,period=period,control=control,count=count,reload=reload,ready=bool(ready))
        if kind=='W':
            if voice in pending:raise ValueError('Write inside half-frame update')
            if ready:writes.append(r)
        elif kind=='B':
            if voice in pending:raise ValueError('Unfinished half-frame update')
            pending[voice]=r
        else:
            before=pending.pop(voice,None)
            if before is None or before['clock']!=clock:raise ValueError('Unpaired half-frame update')
            half_frames[voice].append(dict(before=before,after=r))
            if before['period']!=period:changes[voice].append(dict(**r,before_period=before['period']))
    if pending:raise ValueError('Truncated half-frame update')
    return writes,changes,half_frames


def bind_writes(observed,rows):
    shifted,mapping=publication_writes(rows)
    expected=[(r,m) for r,m in zip(shifted,mapping) if int(r[5])<8]
    if len(expected)!=len(observed):raise ValueError('Pulse write count differs')
    result=[]
    for event,(row,meta) in zip(observed,expected):
        if (event['completed_frame']+1,event['address'],event['value']) != tuple(map(int,(row[1],row[5],row[6]))):
            raise ValueError('Actual pulse write differs from source order/frame/value')
        result.append(dict(**event,packet=meta['packet'],source_frame=meta['publication_frame']))
    return result


def next_event(events,clock,limit):
    clocks=[e['clock'] for e in events]
    index=bisect_right(clocks,clock)
    return events[index] if index<len(events) and events[index]['clock']<limit else None


def reload_context(written,reload,writes,changes):
    """Retain a split-register interleave; never count unlike starts as equal."""
    packet_writes=[w for w in writes if w['packet']==written['packet']
                   and w['voice']==written['voice'] and w['clock']<=written['clock']]
    timers=[w for w in packet_writes if w['address']%4 in (2,3)]
    between=[]
    classification='matching_reload' if written['period']==reload['period'] else 'unexplained_reload_difference'
    if len(timers)>=2:
        low,high=timers[-2:]
        between=[c for c in changes if low['clock']<c['clock']<high['clock']]
        # Deliberately narrow proof: the final pair must be low then high, and
        # every observed sweep must chain exactly from the low-write period.
        if classification!='matching_reload' and low['address']%4==2 and high['address']%4==3 and between:
            period=low['period'];chain=True
            for event in between:
                chain &= event['before_period']==period
                period=event['period']
            raw_period=((high['value']&7)<<8)|low['value']
            observed_period=((high['value']&7)<<8)|(period&255)
            if chain and raw_period==reload['period'] and observed_period==written['period']:
                classification='nes_half_frame_between_split_timer_writes'
    return dict(reload_period_matches=written['period']==reload['period'],
                classification=classification,packet_writes=packet_writes,
                changes_between_last_timer_writes=between)


def audit(snes,nes,out):
    sp=bound_report(snes/'sweep-observer.json');np=bound_report(nes/'sweep-observer.json')
    if not(sp['observer_neutral'] and np['observer_neutral']):raise ValueError('Unqualified sweep observer')
    replay=verify_sources(Path(np['normal'])/'report.json')
    bus=snes.with_name(snes.name+'-bus.csv');received=snes.with_name(snes.name+'-received.csv')
    with bus.open() as stream:rows=list(csv.reader(stream))
    offered=analyze(rows,length_gate=True)
    with received.open() as stream:transport=compare(rows,list(csv.reader(stream)),paired=True)
    if offered['mismatches'] or offered['unflushed_cpu_writes'] or not transport['passed']:
        raise ValueError('SPC transport failed')
    original_bus=[Path(p) for p in replay['sources'] if p.endswith('-bus.csv')]
    if len(original_bus)!=1 or sha(original_bus[0])!=sha(bus):raise ValueError('NES replay used a different bus')
    with Path(np['trace']).open() as stream:writes,changes,halves=nes_events(csv.reader(stream))
    writes=bind_writes(writes,rows)
    final_write={};timer_writes=[[],[]]
    for w in writes:
        if w['address']%4 in (2,3):
            final_write[w['packet'],w['voice']]=w
            timer_writes[w['voice']].append(w)
    reloads=[[],[]];updates=[[],[]];startup=[];last=-1
    with Path(sp['trace']).open() as stream:
        for raw in csv.reader(stream):
            if len(raw)!=10:raise ValueError('Invalid SPC sweep row')
            packet,clock,pc,voice,period,control,count,enable,source_period,flags=(
                int(v,16 if i==2 else 10) for i,v in enumerate(raw))
            if clock<=last or voice not in (0,1) or not 0<=packet<=len(offered['packets']):
                raise ValueError('Invalid SPC sweep ordering/state')
            last=clock
            r=dict(packet=packet,clock=clock,pc=pc,voice=voice,period=period,control=control,
                   count=count,enable=enable,source_period=source_period,flags=flags)
            if not packet:
                startup.append(r);continue
            if pc==RELOAD_PC[voice]:
                if period!=source_period:raise ValueError('Reload differs from received timer')
                reloads[voice].append(r)
            elif pc in UPDATE_PC[voice]:updates[voice].append(r)
            else:raise ValueError('Unexpected executed sweep store PC')
    results=[];excluded=[]
    for voice in (0,1):
        for index,reload in enumerate(reloads[voice]):
            key=reload['packet'],voice
            if key not in final_write:raise ValueError('SPC reload lacks a corresponding NES timer write')
            written=final_write[key]
            # Every timer write is a boundary, including writes while disabled.
            following=next_event(timer_writes[voice],written['clock'],float('inf'))
            limit=following['clock'] if following else float('inf')
            next_reload=reloads[voice][index+1]['clock'] if index+1<len(reloads[voice]) else float('inf')
            original=next_event(changes[voice],written['clock'],limit)
            native=next_event(updates[voice],reload['clock'],next_reload)
            row=dict(voice=voice,packet=reload['packet'],source_frame=written['source_frame'],
                     timer_write=written,spc_reload=reload,nes_change=original,spc_change=native,
                     reload_context=reload_context(written,reload,writes,changes[voice]))
            if not(reload['enable']&(1<<voice)) or not original or not native:
                excluded.append(row);continue
            row.update(nes_delay_cycles=original['clock']-written['clock'],
                       spc_delay_ticks=native['clock']-reload['clock'])
            row['nes_delay_ms']=row['nes_delay_cycles']*1000/NES_HZ
            row['spc_delay_ms']=row['spc_delay_ticks']*1000/SPC_HZ
            row['difference_ms']=row['spc_delay_ms']-row['nes_delay_ms']
            row['first_target_matches']=original['period']==native['period']
            results.append(row)
    if not results:raise ValueError('No paired reload/change observations')
    summary={}
    for voice in (0,1):
        selected=[r for r in results if r['voice']==voice]
        summary[str(voice)]=dict(paired=len(selected),excluded=sum(r['voice']==voice for r in excluded),
            first_target_mismatches=sum(not r['first_target_matches'] for r in selected),
            reload_period_mismatches=sum(not r['reload_context']['reload_period_matches'] for r in selected),
            split_write_interleaves=sum(r['reload_context']['classification']==
                'nes_half_frame_between_split_timer_writes' for r in selected),
            unexplained_reload_differences=sum(r['reload_context']['classification']==
                'unexplained_reload_difference' for r in selected),
            minimum_difference_ms=min(r['difference_ms'] for r in selected),
            maximum_difference_ms=max(r['difference_ms'] for r in selected),
            mean_difference_ms=sum(r['difference_ms'] for r in selected)/len(selected))
    # Exact half-frame intervals; startup is retained separately, not fitted.
    intervals={str(v):sorted(set(b['before']['clock']-a['before']['clock']
        for a,b in zip(halves[v],halves[v][1:]))) for v in (0,1)}
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/replay_nes_apu_stimulus.py'),
        Path('tools/analyze_spc_receive.py'),Path('tools/analyze_audio_bus.py'),
        snes/'sweep-observer.json',nes/'sweep-observer.json',Path(np['normal'])/'report.json',
        bus,received,Path(sp['trace']),Path(np['trace']))}
    report=dict(observer_neutral=True,spc_packets=transport['packets'],
        actual_ordered_pulse_writes=len(writes),summary=summary,pairs=results,excluded=excluded,
        spc_startup=startup,nes_half_frame_interval_cycles=intervals,
        sources=sources,release_ready=False,physical_audio_verified=False,
        scope='Actual source-matched NES writes and observed half-frame pitch changes versus actual '
        'SPC timer reloads and pitch updates. Delays measured from the last timer write/reload, '
        'never fitted waveform offsets. APU writes are preserved but NES replay is frame-quantized; '
        'this comparison does not recover original sub-frame NES command timing or prove hardware stutter. '
        'Events without changes before the next timer/reload boundary remain excluded explicitly.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(packets=transport['packets'],writes=len(writes),summary=summary),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('snes','nes','out'):parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
