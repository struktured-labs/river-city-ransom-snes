"""Bind input-only park encounter captures to game state and SPC timing."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture, sha
    from .analyze_spc_ack import analyze as analyze_ack
except ImportError:
    from benchmark_report import verify_capture, sha
    from analyze_spc_ack import analyze as analyze_ack


def summarize(rows):
    park = []
    for row in rows:
        if not row['phase'].startswith('park'):
            continue
        ram = bytes.fromhex(row['game_ram_hex'])
        park.append(dict(row, room=ram[0x42], pause_flag=bool(ram[0x3f]&0x20),
                         task=ram[0x100], loop_tick=ram[0x10b]))
    if not park:
        raise ValueError('No park stress input phases were executed')
    holds = []
    first = None
    def eligible(row):
        return (row['room']==3 and not row['pause_flag'] and '_run' in row['phase']
                and row['task'] & 0xc0 == 0xc0
                and not row.get('native', {}).get('transition_state', 0))
    def finish(stop):
        if first is not None and stop-first>=4:
            sample=park[first:stop]
            nmis=[r['nmi_counter'] for r in sample if r['nmi_counter'] is not None]
            holds.append({'first_frame':sample[0]['frame'],
                          'last_frame':sample[-1]['frame'], 'frames':len(sample),
                          'phase':sample[0]['phase'],
                          'nmi_advances':sum((b-a)&0xffff for a,b in zip(nmis,nmis[1:])) if nmis else None,
                          'pcs':dict(Counter(hex(r['native']['pc']) for r in sample if 'native' in r)),
                          'audio_rms':[round(r['audio']['rms'],1) for r in sample]})
    for i,row in enumerate(park):
        previous = park[i-1] if i else None
        repeated = (eligible(row) and previous is not None and eligible(previous)
                    and previous['phase']==row['phase'] and previous['frame']+1==row['frame']
                    and previous['scene_sha256']==row['scene_sha256'])
        if repeated:
            if first is None:
                first=i-1
        elif first is not None:
            finish(i)
            first=None
    finish(len(park))
    active = [r for r in park if eligible(r)]
    gaps=[]
    for a,b in zip(park,park[1:]):
        if eligible(a) and eligible(b) and a['phase']==b['phase'] and a['nmi_counter'] is not None:
            gaps.append((b['nmi_counter']-a['nmi_counter'])&0xffff)
    return {'park_frames':len(park), 'room_counts':dict(Counter(r['room'] for r in park)),
            'active_run_frames':len(active), 'pause_frames':sum(r['pause_flag'] for r in park),
            'nmi_step_histogram':dict(Counter(gaps)),
            'scene_holds':sorted(holds,key=lambda r:r['frames'],reverse=True),
            'scene_hold_scope':'Repeated animation pixels are review candidates, not proof of a stalled game tick.',
            'faults':sum(bool(r['fault']) for r in park)}


def packet_gaps(rows, timing):
    absolute = timing.get('absolute_completion_timing')
    if absolute is None:
        raise ValueError('Park execution audit requires a nine-column absolute-clock ACK trace')
    events=[]
    for gap in absolute['long_intervals']:
        first,last=gap['before']['frame'],gap['after']['frame']
        # Include both boundary frames plus one trailing frame conservatively:
        # a packet can finish at scanline zero before the core frame increments.
        observed=rows[max(0,first-1):min(len(rows),last+1)]
        if not any(r['phase'].startswith('park') for r in observed):
            continue
        stable=all(r['phase'].startswith('park')
                   and bytes.fromhex(r['game_ram_hex'])[0x42]==3
                   and not bytes.fromhex(r['game_ram_hex'])[0x3f]&0x20
                   and r['native']['task'] & 0xc0 == 0xc0
                   and not r['native']['guard'] & 0x80
                   and r['native']['transition_state']==0 for r in observed)
        events.append(dict(gap,nominal_frames=round(gap['master_clocks']/357366,4),
                           stable_unpaused_park=stable,
                           phases=sorted({r['phase'] for r in observed}),
                           pcs=dict(Counter(hex(r['native']['pc']) for r in observed))))
    return sorted(events,key=lambda r:r['master_clocks'],reverse=True)


def verify_ack_binding(receipt, ack):
    if receipt.get('spc_ack_trace', {}).get('sha256') != sha(ack):
        raise ValueError('ACK trace is not bound to this capture receipt')


def build(reference,candidate,ack,out,engine_size,triple=False):
    receipt_a,a=verify_capture(reference)
    receipt_b,b=verify_capture(candidate)
    if receipt_a['system']!='nes' or receipt_b['system']!='snes':
        raise ValueError('Need original NES and candidate SNES capture')
    if any(not r['capture_complete'] or r['scenario_name']!='traversal-park-stress'
           for r in (receipt_a,receipt_b)):
        raise ValueError('Incomplete/wrong input-only park captures')
    if receipt_a['scenario_sha256']!=receipt_b['scenario_sha256']:
        raise ValueError('Park input scenarios differ')
    if any(r['input_requested']!=r['input_delivered'] for r in a+b):
        raise ValueError('Requested inputs were not delivered')
    verify_ack_binding(receipt_b,ack)
    with ack.open() as source:
        timing=analyze_ack(csv.reader(source),paired=not triple,triple=triple,engine_size=engine_size)
    events=packet_gaps(b,timing)
    report={'nes':summarize(a),'snes':summarize(b),
            'source':{'nes_capture_sha256':sha(reference/'capture.json'),
                      'snes_capture_sha256':sha(candidate/'capture.json'),
                      'nes_rom_sha256':receipt_a['rom_sha256'],
                      'snes_rom_sha256':receipt_b['rom_sha256']},
            'scope':'Same inputs, independently evolving enemy states. Repeated scene frames and NMI/packet cadence are measured; combat poses are not forced to match.'}
    report['source']['spc_ack_sha256']=sha(ack)
    report['park_packet_gaps']=events
    stable=[g for g in events if g['stable_unpaused_park']]
    report['gates']={
        'both_reach_park_running':all(report[s]['active_run_frames']>=300 for s in ('nes','snes')),
        'no_native_faults':report['snes']['faults']==0,
        'no_stable_park_packet_gap_over_1_5_frames':not stable,
    }
    report['stable_park_long_gap_count']=len(stable)
    report['timing_scope']='Packet delivery deadlines, not acoustic tempo/popping certification. Enemy states diverge; scene holds alone do not fail.'
    report['acknowledged_packets']=timing['acknowledged_packets']
    report['data_phase_timing']=timing['data_phase_timing']
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    images=[]
    for label,directory in [('nes',reference),('snes',candidate)]:
        for phase in ('park_arrival','park_00_right_run','park_02_paused','park_07_left_run'):
            name=label+'-'+phase+'.png'
            shutil.copyfile(directory/(phase+'.png'),out/name)
            images.append(f'<figure><figcaption>{label}: {phase}</figcaption><img src="{name}"></figure>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Park execution timing</title>
<style>body{background:#111820;color:#eee;font:16px system-ui;max-width:1200px;margin:30px auto}figure{display:inline-block;margin:12px}img{width:384px;image-rendering:pixelated}a{color:#9cf}pre{white-space:pre-wrap}</style>
<h1>Original NES and SNES · park encounter</h1><p>Ordinary double-tap run inputs after the shop-exit route.
Room, original pause flags, scene pixels, game ticks, native PC and every SPC acknowledgement are retained.
Enemy states may diverge; this is not an exact combat-state speed oracle.</p>
<p><a href="report.json">Complete timing and source hashes</a></p>'''+''.join(images)+
        '<pre>'+html.escape(json.dumps({k:report[k] for k in ('nes','snes','park_packet_gaps')},indent=2))+'</pre>')
    print(json.dumps({'gates':report['gates'], 'stable_park_long_gap_count':len(stable),
                     'longest_stable_gap':stable[:1]},indent=2))
    return all(report['gates'].values())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','ack','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--engine-size',type=lambda value:int(value,0),required=True)
    p.add_argument('--triple',action='store_true')
    args=p.parse_args()
    raise SystemExit(0 if build(args.reference,args.candidate,args.ack,args.out,args.engine_size,args.triple) else 1)
