"""Extend exact commit-to-render joins to every stable captured room segment."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_display_cadence import cameras,measure,rendering_enabled
from tools.audit_main_display_latency import bound_report,join
from tools.audit_route_loop_cadence import stable_room
from tools.benchmark_report import sha,verify_capture


def segments(rows,rendered,system='snes'):
    if system not in ('nes','snes'):raise ValueError('Unsupported system')
    groups=[];current=[];excluded=[]
    for i,row in enumerate(rows):
        room=stable_room(rows[max(0,i-1):i+1]) if i else None
        valid=(room is not None and i>0 and rendering_enabled(row,system) and
               rendering_enabled(rows[i-1],system))
        if not valid:
            if current:groups.append(current);current=[]
            excluded.append(dict(frame=row['frame'],reason='Non-stable/transition/disabled boundary'))
            continue
        if row['frame'] not in rendered or len(rendered[row['frame']])!=1:
            raise ValueError('Missing/split actual rendered camera')
        if current and current[-1]['room']!=room:groups.append(current);current=[]
        current.append(dict(frame=row['frame'],camera=rendered[row['frame']][0],room=room))
    if current:groups.append(current)
    phases={};counts=Counter()
    for group in groups:
        room=group[0]['room']
        if len(group)<2:
            excluded.append(dict(frame=group[0]['frame'],reason='Single-frame stable segment'));continue
        name=f'room{room}.segment{counts[room]:02d}';counts[room]+=1
        phases[name]=measure([dict(frame=r['frame'],camera=r['camera']) for r in group])
    if set(counts)!={0,1,2,3}:raise ValueError('Missing room coverage')
    return phases,excluded


def audit(latency,render,normal,out):
    proof=bound_report(latency);receipt,rows=verify_capture(render);control,baseline=verify_capture(normal)
    if (rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k] for k in
            ('rom_sha256','audio_sha256','scenario_sha256','frames')) or
            proof['sources'].get(str(normal/'capture.json'))!=sha(normal/'capture.json')):
        raise ValueError('Need common observer-neutral control')
    wanted=[row['frame'] for i,row in enumerate(rows) if i and stable_room(rows[i-1:i+1]) is not None
            and rendering_enabled(row,'snes') and rendering_enabled(rows[i-1],'snes')]
    binding=receipt['render_scroll_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256'] or binding['first']>min(wanted) or binding['last']<max(wanted):
        raise ValueError('Missing complete renderer trace')
    with trace.open() as f:rendered=cameras(csv.DictReader(f),'snes',wanted)
    phases,excluded=segments(rows,rendered)
    result=join(proof['intervals'],phases)
    result.update(observer_neutral=True,rendered_frames=len(wanted),phases=phases,
        excluded_rendering_boundaries=excluded,
        room_events={str(room):sum(e['phase'].startswith(f'room{room}.') for e in result['events'])
                     for room in range(4)},release_ready=False,original_route_latency_equivalence=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_main_display_latency.py'),
            Path('tools/audit_display_cadence.py'),Path('tools/audit_route_loop_cadence.py'),
            render/'capture.json',normal/'capture.json',trace,latency)},
        scope='All stable room0..3 segments, every160-line rendered camera covered. Actual pre-store '
              'camera value joined without fitted lag; blanks/fades/transition boundaries and '
              'unchanged/out-of-phase commits retained. Current SNES route only; original NES '
              'comparison remains the separately qualified park window. No frame-end-gate waiver.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('rendered_frames','room_events','store_to_display',
        'start_to_display','missing_display')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('latency','render','normal','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
