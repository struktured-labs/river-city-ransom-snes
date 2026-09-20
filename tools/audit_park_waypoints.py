"""Report both completed and failed park routes without disguising timeouts.

State-adaptive inputs measure navigation/coverage, not same-input speed parity.
Independent normal-core replay must retain every frame and audio sample.
"""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture,sha
    from .analyze_spc_ack import analyze as analyze_ack
    from .audit_park_execution import packet_gaps,verify_ack_binding
except ImportError:
    from benchmark_report import verify_capture,sha
    from analyze_spc_ack import analyze as analyze_ack
    from audit_park_execution import packet_gaps,verify_ack_binding


def summary(receipt,rows):
    park=[r for r in rows if r['phase'].startswith('park')]
    rooms=Counter(bytes.fromhex(r['game_ram_hex'])[0x42] for r in park)
    return dict(complete=receipt['capture_complete'],frames=len(rows),park_frames=len(park),
                park_room_counts=dict(rooms),faults=sum(bool(r['fault']) for r in rows),
                phases=[{k:s[k] for k in ('name','frames','start_frame','end_frame','transition_matched')}
                        for s in receipt['segments'] if s['name'].startswith('park')])


def gates(a,b,normal_equal,events):
    return dict(both_complete=a['complete'] and b['complete'],
                no_native_faults=b['faults']==0,observer_neutral=normal_equal,
                both_observe_park=all(s['park_room_counts'].get(3,0)>=300 for s in (a,b)),
                no_stable_park_packet_gap_over_1_5_frames=not any(e['stable_unpaused_park'] for e in events))


def audit(reference,candidate,normal,ack,out,engine_size):
    folders=dict(nes=reference,snes=candidate,normal=normal)
    data={label:verify_capture(folder) for label,folder in folders.items()}
    for label,(r,rows) in data.items():
        if (r['system']!=('nes' if label=='nes' else 'snes') or
            r['scenario_name'] not in ('traversal-park-coverage','traversal-park-single-sweep') or
            any(x['input_requested']!=x['input_delivered'] for x in rows)):
            raise ValueError('Wrong park scenario/system or missing delivered inputs')
    receipts=[v[0] for v in data.values()]
    if len({r['scenario_sha256'] for r in receipts})!=1 or len({r['waypoint_policy_sha256'] for r in receipts})!=1:
        raise ValueError('Park scenarios/policies differ')
    if (receipts[1]['rom_sha256']!=receipts[2]['rom_sha256'] or
        receipts[0]['rom_sha256']!=receipts[1]['templates']['menu']['source_rom']):
        raise ValueError('Unmatched ROM identities')
    verify_ack_binding(receipts[1],ack)
    with ack.open() as f:timing=analyze_ack(csv.reader(f),paired=True,engine_size=engine_size)
    events=packet_gaps(data['snes'][1],timing)
    neutral=data['snes'][1]==data['normal'][1] and receipts[1]['audio_sha256']==receipts[2]['audio_sha256']
    summaries={label:summary(*v) for label,v in data.items()}
    checks=gates(summaries['nes'],summaries['snes'],neutral,events)
    report=dict(passed=all(checks.values()),gates=checks,summaries=summaries,
                stable_park_long_gap_count=sum(e['stable_unpaused_park'] for e in events),
                park_packet_gaps=events,acknowledged_packets=timing['acknowledged_packets'],
                sources={label:dict(capture_sha256=sha(folder/'capture.json'),
                    rom_sha256=data[label][0]['rom_sha256']) for label,folder in folders.items()},
                ack_sha256=sha(ack),audit_sha256=sha(Path(__file__)),
                scope='Same read-only navigation policy, independently evolving inputs and enemies. '
                'Not same-input speed parity or acoustic/physical audio certification. '
                'Incomplete routes FAIL; scenery comparison is a separate fixed-band audit.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    cards=[]
    # Same named checkpoints, never seek to a visually favorable substitute.
    names=['park_entry','park_00_east_sweep','park_00_west_sweep']
    names+=sorted({s['name'] for s in summaries['snes']['phases'] if s['transition_matched'] is False})
    for name in names:
        cards.append('<h2>'+html.escape(name)+'</h2><section>')
        for label in ('nes','snes'):
            phase=next((s for s in summaries[label]['phases'] if s['name']==name),None)
            if phase is None:continue
            image=f'{label}-{name}.png'
            shutil.copyfile(folders[label]/(name+'.png'),out/image)
            cards.append(f'<figure><img src="{image}"><figcaption>{label}: frame {phase["end_frame"]}, '
                         f'phase length {phase["frames"]}, matched {phase["transition_matched"]}</figcaption></figure>')
        cards.append('</section>')
    shutil.copyfile(candidate/'audio.wav',out/'snes-audio.wav')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Park waypoint audit</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;max-width:1200px;margin:30px auto}'
        'a{color:#9df}section{display:flex}figure{margin:12px}img{width:512px;image-rendering:pixelated}'
        'pre{white-space:pre-wrap}</style><h1>Park route: '+('PASS' if report['passed'] else 'FAIL')+'</h1><p>'+
        html.escape(report['scope'])+'</p><p><a href="report.json">Timing, coverage, full source hashes</a></p>'
        '<p>Full unedited SNES capture audio:</p><audio controls src="snes-audio.wav"></audio><pre>'+
        html.escape(json.dumps(dict(gates=checks,summaries=summaries),indent=2))+'</pre>'+''.join(cards))
    print(json.dumps(dict(passed=report['passed'],gates=checks,stable_park_long_gap_count=report['stable_park_long_gap_count']),indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','normal','ack','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--engine-size',type=lambda v:int(v,0),required=True)
    a=p.parse_args()
    raise SystemExit(0 if audit(a.reference,a.candidate,a.normal,a.ack,a.out,a.engine_size) else 1)
