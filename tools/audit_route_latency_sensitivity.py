"""Inject delayed/missing display into copies of actual four-room evidence."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from tools.audit_display_cadence import measure
from tools.audit_main_display_latency import bound_report,join
from tools.benchmark_report import sha


def perturb(intervals,phases,event,mode):
    changed=deepcopy(phases);name=event['phase'];series=changed[name]['series']
    visible=event['display_frame'];target=event['camera']
    previous=next(r['camera'] for r in series if r['frame']==event['store_frame']-1)
    if mode=='one_frame_delay':
        selected=[r for r in series if r['frame']==visible]
    elif mode=='missing_camera':
        future=[i['commit']['frame'] for i in intervals if i['commit']['frame']>event['store_frame']]
        end=min(future)
        selected=[r for r in series if event['store_frame']<=r['frame']<=end and r['camera']==target]
    else:raise ValueError('Unknown mutation')
    if not selected:raise ValueError('Mutation has no target')
    for row in selected:row['camera']=previous
    changed[name]=measure(series)
    result=join(intervals,changed)
    observed=next(e for e in result['events'] if e['store_frame']==event['store_frame'])
    expected=event['store_to_display']+1 if mode=='one_frame_delay' else None
    if observed['store_to_display']!=expected:
        raise ValueError('Actual-route sensitivity control was not detected exactly')
    return dict(mode=mode,original=event,observed=observed,
        changed_frames=[r['frame'] for r in selected],synthetic=True,detected=True)


def audit(route,main,out):
    render=bound_report(route);cpu=bound_report(main)
    if render['sources'].get(str(main))!=sha(main):raise ValueError('Different main proof')
    # Normalize integer histogram keys to their JSON representation.
    actual=json.loads(json.dumps(join(cpu['intervals'],render['phases'])))
    if actual!={k:render[k] for k in actual}:raise ValueError('Changed baseline join')
    controls=[]
    for room in range(4):
        event=next(e for e in render['events'] if e['phase'].startswith(f'room{room}.'))
        for mode in ('one_frame_delay','missing_camera'):
            controls.append(perturb(cpu['intervals'],render['phases'],event,mode))
    result=dict(controls=controls,all_detected=all(c['detected'] for c in controls),
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_main_display_latency.py'),
            Path('tools/audit_display_cadence.py'),route,main)},release_ready=False,
        scope='Synthetic changes to in-memory copies of actual first qualified event in each room. '
              'No original capture, image, ROM or source trace modified. Detects latency checker '
              'sensitivity, not an actual extra-delay or missing-camera observation.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(controls=len(controls),all_detected=result['all_detected'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('route','main','out'):parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
