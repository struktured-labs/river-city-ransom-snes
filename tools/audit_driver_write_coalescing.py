"""Original NES within-driver writes versus the current SNES snapshot protocol.

Different encounters; no per-event cross-platform correspondence or pop diagnosis.
"""
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
import csv
import html
import json
from pathlib import Path

from tools.analyze_audio_bus import analyze as bus_analysis
from tools.audit_main_display_latency import bound_report
from tools.audit_ordinary_route_timing import sound_pairs
from tools.audit_postpublish_keyon import load
from tools.audit_sweep_driver_game import metadata_events
from tools.benchmark_report import sha,verify_capture
from tools.capture_nes_audio_events import POINTS
from tools.nes_event_trace import validate


def parse_writes(records,frames):
    result=[];last_clock=-1;last_frame=0
    for r in records:
        if len(r)!=9:raise ValueError('Malformed NES APU write')
        frame,clock=int(r[0]),int(r[1]);pc,address=int(r[2],16),int(r[3],16)
        value,task,tick,busy,room=map(int,r[4:])
        if (not 1<=frame<=frames or frame<last_frame or clock<last_clock or
            not 0<=pc<=65535 or address not in (*range(0x4000,0x4014),0x4015,0x4017) or
            any(not 0<=x<=255 for x in (value,task,tick,busy,room))):
            raise ValueError('Invalid NES write bounds/order/address')
        result.append(dict(frame=frame,clock=clock,pc=pc,register=address-0x4000,
                           value=value,task=task,tick=tick,busy=busy,room=room))
        last_clock,last_frame=clock,frame
    if not result:raise ValueError('No NES APU writes')
    return result


def group_nes(writes,pairs):
    starts=[p['entry']['clock'] for p in pairs]
    if not starts or any(a>=b for a,b in zip(starts,starts[1:])):
        raise ValueError('Invalid driver interval sequence')
    groups=[dict(driver=i+1,entry=p['entry'],returned=p['returned'],writes=[])
            for i,p in enumerate(pairs)]
    outside=[]
    for w in writes:
        i=bisect_right(starts,w['clock'])-1
        if i<0 or w['clock']>pairs[i]['returned']['clock']:
            outside.append(w)
        else:
            groups[i]['writes'].append(w)
    return groups,outside


def summarize(groups):
    repeated=[];changing=[];quiet=[];events=[];counts=Counter()
    for group in groups:
        by=defaultdict(list)
        for w in group['writes']:
            by[w['register']].append(w);counts[str(w['register'])]+=1
        identity={k:v for k,v in group.items() if k!='writes'}
        for register,ws in by.items():
            if len(ws)<2:continue
            record=dict(**identity,register=register,values=[w['value'] for w in ws],writes=ws)
            repeated.append(record)
            if len(set(record['values']))>1:changing.append(record)
            if register in (3,7,11,15,23):events.append(record)
            if register in (0,4,12):
                for a,b in zip(ws,ws[1:]):
                    if a['value']&0x10 and b['value']&0x10 and a['value']&15==0 and b['value']&15:
                        quiet.append(dict(**identity,register=register,zero=a,nonzero=b,
                            clocks=b['clock']-a['clock'] if 'clock' in a else None))
    signatures=Counter((r['register'],tuple(r['values'])) for r in changing)
    return dict(groups=len(groups),writes=sum(len(g['writes']) for g in groups),
        register_counts=dict(counts),repeated_register_groups=repeated,
        changing_register_groups=changing,repeated_side_effect_registers=events,
        zero_then_nonzero_constant_volume=quiet,
        changing_patterns=[dict(register=k[0],values=list(k[1]),count=v) for k,v in signatures.most_common()])


def group_snes(bus):
    groups=[];writes=[];packet=[]
    for r in bus:
        if r[0]=='W':
            writes.append(dict(frame=int(r[1]),line=int(r[2]),cycle=int(r[3]),native_id=int(r[4]),
                               register=int(r[5]),value=int(r[6]),pc=int(r[7],16)))
        else:
            if int(r[5])!=len(packet):raise ValueError('Reordered SNES packet')
            packet.append(int(r[6]))
            if len(packet)==23:
                groups.append(dict(packet=len(groups)+1,frame=int(r[1]),native_id=int(r[4]),
                                   payload=bytes(packet).hex(),writes=writes))
                writes=[];packet=[]
    if packet or writes:raise ValueError('Unflushed/truncated SNES bus')
    return groups


def corrupt_observed_final(bus):
    result=[list(r) for r in bus];seen=set()
    for r in result:
        index=int(r[5])
        if r[0]=='W':seen.add(index)
        elif index in seen and index<20:
            r[6]=str(int(r[6])^1)
            return result
    raise ValueError('No published register has an observed preceding CPU write')


def audit(nes,normal_nes,prior_nes,candidate,snes,normal_snes,out):
    if out.exists():raise ValueError('Fresh audit required')
    binding=bound_report(nes/'driver-writes.json');sources=dict(binding['sources'])
    n,nrows=verify_capture(nes);control,baseline=verify_capture(normal_nes)
    if not binding['observer_neutral'] or nrows!=baseline or any(n[k]!=control[k] for k in
        ('system','core_sha256','rom_sha256','frames','audio_sha256','scenario_sha256')):
        raise ValueError('Original NES write observer is not neutral')
    old,oldrows=verify_capture(prior_nes)
    # The old reference additionally requested four host PPU-register fields.
    # Their absence here is retained, not confused with a game-state change.
    common_equal=[{k:v for k,v in r.items() if k!='nes_ppu'} for r in baseline]==[
        {k:v for k,v in r.items() if k!='nes_ppu'} for r in oldrows]
    if not common_equal or any(control[k]!=old[k] for k in ('rom_sha256','frames','audio_sha256','scenario_sha256')):
        raise ValueError('Rebuilt core changed original execution/PCM')
    with Path(binding['events']).open() as f:events=list(csv.reader(f))
    validate(events,1,n['frames'],n['frames'],POINTS)
    pairs,censored=sound_pairs(events)
    with Path(binding['writes']).open() as f:writes=parse_writes(csv.reader(f),n['frames'])
    ngroups,outside=group_nes(writes,pairs);ns=summarize(ngroups)
    proof,_,_=load(snes,normal_snes,candidate)
    if proof['late_restarts']:raise ValueError('Current engine has late pulse configuration')
    sources.update(proof['sources']);sources.update(bound_report(snes/'pipeline-capture.json')['sources'])
    sr,srows=verify_capture(snes);sc,_=verify_capture(normal_snes)
    if sr['core_sha256']!=sc['core_sha256']:raise ValueError('SNES control is not same-core')
    buspath=Path(sr['audio_bus_trace']['path'])
    if sha(buspath)!=sr['audio_bus_trace']['sha256']:raise ValueError('Changed SNES bus')
    with buspath.open() as f:bus=list(csv.reader(f))
    transport=bus_analysis(bus,length_gate=True);metadata=metadata_events(bus)
    if transport['mismatches'] or transport['unflushed_cpu_writes'] or not metadata['passed']:
        raise ValueError('Current CPU-to-SPC transport/events differ')
    ss=summarize(group_snes(bus))
    if len(ss['changing_register_groups'])!=len(transport['changing_register_groups_between_packets']):
        raise ValueError('Independent coalescing analyses disagree')
    # Controls distinguish final-byte corruption from representational loss.
    changed=corrupt_observed_final(bus)
    if not bus_analysis(changed,length_gate=True)['mismatches']:
        raise ValueError('Corrupt final-value control escaped')
    zero_gaps=[r['clocks'] for r in ns['zero_then_nonzero_constant_volume']]
    result=dict(rom_sha256=sr['rom_sha256'],nes=ns,snes=ss,nes_outside_wrapper=outside,
        nes_censored=censored,nes_write_count=len(writes),nes_driver_calls=len(pairs),
        nes_constant_volume_zero_gap_cycles=dict(count=len(zero_gaps),minimum=min(zero_gaps,default=None),maximum=max(zero_gaps,default=None)),
        nes_new_core_common_timeline_equal=True,nes_older_reference_extra_field='nes_ppu',
        metadata=metadata,final_values_preserved=True,corrupt_final_value_control_rejected=True,
        actual_received_packets=transport['packet_count'],observer_neutral=True,
        sources=sources,release_ready=False,physical_pop_causality_proven=False,
        scope=__doc__+' NES groups are actual complete wrapper calls; SNES groups span all '
        'writes before a packet, including bootstrap/transition work outside the driver. '
        'No claim that differing group counts mean missing original game calls. '
        'Coalesced transient states are distinct from corrupt final bytes or lost event bits. '
        'NES timestamps are instruction-granular CPU clocks; no SNES/CPU/SPC time fitting.')
    for p in (Path(__file__),Path('tests/test_driver_write_coalescing.py'),
        Path('tools/build_nes_apu_clock_core.py'),Path('tools/analyze_audio_bus.py'),
        Path('tools/audit_sweep_driver_game.py'),Path('tools/audit_ordinary_route_timing.py'),
        Path('tools/nes_event_trace.py'),Path('tools/audit_postpublish_keyon.py'),
        Path('tools/benchmark_report.py'),nes/'driver-writes.json',nes/'capture.json',
        normal_nes/'capture.json',prior_nes/'capture.json',prior_nes/'timeline.json',
        snes/'capture.json',normal_snes/'capture.json',snes/'pipeline-capture.json',
        candidate/'manifest.json',candidate/'native-cpu.sfc',buspath):
        sources[str(p)]=sha(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Source changed: '+p)
    out.mkdir(parents=True)
    page='<!doctype html><meta charset="utf-8"><title>Original driver write coalescing</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}a{color:cyan}td,th{padding:8px}pre{white-space:pre-wrap}</style>'
    page+='<h1>Original driver writes versus snapshot transport</h1><p>'+html.escape(result['scope'])+'</p>'
    page+=f'<p>Current SNES: all{transport["packet_count"]:,} packets and{metadata["events"]:,} traced metadata events preserved. '
    page+=f'{len(ss["changing_register_groups"]):,} changing-register groups are coalesced into final values, not transmitted as full sub-frame event sequences.</p>'
    page+=f'<p>Original NES: {len(writes):,} APU writes; {len(pairs):,} complete driver calls; {len(outside):,} writes outside those calls retained.</p>'
    page+='<h2>Original constant-volume zero→nonzero intervals</h2><pre>'+html.escape(json.dumps(result['nes_constant_volume_zero_gap_cycles'],indent=2))+'</pre>'
    for label,s in (('NES driver calls',ns),('SNES publication groups',ss)):
        page+='<h2>'+label+'</h2><table><tr><th>Register offset</th><th>Values</th><th>Count</th></tr>'
        for r in s['changing_patterns'][:20]:page+='<tr><td>'+f'{r["register"]:02X}'+'</td><td>'+', '.join(f'{v:02X}' for v in r['values'])+'</td><td>'+str(r['count'])+'</td></tr>'
        page+='</table>'
    page+='<p><a href="report.json">Every write group, outside event, limitation and source hash</a></p>'
    (out/'index.html').write_text(page);result['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(nes_writes=len(writes),nes_calls=len(pairs),nes_outside=len(outside),
        nes_changing_groups=len(ns['changing_register_groups']),snes_changing_groups=len(ss['changing_register_groups']),
        nes_zero_gaps=result['nes_constant_volume_zero_gap_cycles'],packets=transport['packet_count'],metadata=metadata)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('nes','normal-nes','prior-nes','candidate','snes','normal-snes','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
