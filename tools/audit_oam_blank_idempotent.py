"""Classify repeated actual black fills without accepting missing or duplicate sprite rendering."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools import audit_oam_blank_route as base
from tools.benchmark_report import sha


def spans(events,frames):
    coverage={};heights={};kinds=Counter();errors=[];black=[];repeated=[]
    for e in events:
        if e['kind'] not in 'RB':continue
        f=e['frame'];kind=e['kind'];kinds[kind]+=1
        if not 1<=f<=frames or not 0<=e['first_y']<=e['last_y']<e['height']:
            errors.append(dict(event=e['index'],kind='invalid_span'));continue
        if bool(e['blank'])!=(kind=='B'):errors.append(dict(event=e['index'],kind='wrong_blank_state'))
        c=coverage.setdefault(f,{});heights.setdefault(f,set()).add(e['height']);duplicates=[]
        for line in range(e['first_y'],e['last_y']+1):
            if line in c:
                if c[line]=='B' and kind=='B':duplicates.append(line)
                else:errors.append(dict(event=e['index'],frame=f,line=line,kind='duplicate_or_overwritten_render'))
            c[line]=kind
        if kind=='B':black.append(dict(event=e['index'],frame=f,first=e['first_y'],last=e['last_y']))
        if duplicates:repeated.append(dict(event=e['index'],frame=f,lines=duplicates))
    for f in range(1,frames+1):
        c=coverage.get(f,{})
        if not c:errors.append(dict(frame=f,kind='missing_frame'));continue
        if len(heights[f])!=1 or set(c)!=set(range(max(heights[f]))):
            errors.append(dict(frame=f,kind='missing_lines_or_changed_height'))
    return dict(passed=not errors,errors=errors,event_counts=dict(kinds),black_spans=black,frames=frames,
        repeated_black_writes=repeated,scope='Every line must be recorded as rendered or explicitly filled black. '
        'Only repeated B→B writes are idempotent: the bound renderer writes BUILD_PIXEL(0,0,0) in both. '
        'R→R, R→B, B→R duplicates and missing coverage still fail. All redundant black writes are retained.')


def audit(candidate,capture,out):
    original=base.spans
    try:
        base.spans=spans
        base.audit(candidate,capture,out)
    finally:base.spans=original
    report=json.loads((out/'report.json').read_text())
    page=out/'index.html';body=page.read_text()
    old='spans; every frame and line must occur once.'
    if body.count(old)!=1:raise ValueError('Changed presentation template')
    body=body.replace(old,'spans; every output line must be accounted for. Repeated fills of the same black value are retained explicitly; duplicate sprite-render spans still fail.')
    body=body.replace('<h1>3955:', '<h1>3955:')
    body+='<p>The earlier3987 strict exact-once audit rejects two repeated black fills of line19 at frame307. The core really performs these identical black writes; this report retains them rather than inventing missing sprite coverage or discarding the frame.</p>'
    page.write_text(body)
    report['sources'][str(Path(__file__))]=sha(Path(__file__))
    report['sources']['tests/test_oam_black_idempotence.py']=sha(Path('tests/test_oam_black_idempotence.py'))
    report['artifacts']['index.html']=sha(page)
    report['presentation_correction']='Identical forced-black re-writes are explicitly classified;3987 remains the strict failed audit.'
    if any(sha(Path(p))!=h for p,h in report['sources'].items()):raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','capture','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
