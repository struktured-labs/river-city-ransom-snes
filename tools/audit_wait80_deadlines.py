"""Attribute the two wait80 text regressions to source, preparation or publication."""
import argparse
import html
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def first_current(records, key, target):
    return next((r['frame'] for r in records if r[key]==target),None)


def classify(before,after,target):
    # A bounded generation window must start with the previous value; never
    # turn left-censored evidence into an onset measurement.
    if not before or not after or [r['frame'] for r in before]!=[r['frame'] for r in after]:
        raise ValueError('Different or missing frame coverage')
    if any(a['source']!=b['source'] for a,b in zip(before,after)):
        raise ValueError('Different original source generations')
    if any(r[0][k]==target for r in (before,after) for k in ('source','prepared','vram')):
        raise ValueError('Left-censored generation')
    times=[{k:first_current(records,k,target) for k in ('source','prepared','vram')}
           for records in (before,after)]
    if any(t is None for arm in times for t in arm.values()):raise ValueError('Right-censored generation')
    for arm in times:
        if not arm['source']<=arm['prepared']<=arm['vram']:raise ValueError('Invalid pipeline ordering')
    a,b=times
    return dict(before=a,after=b,prepare_delay=b['prepared']-a['prepared'],
                display_delay=b['vram']-a['vram'],
                source_equal=a['source']==b['source'],
                publication_lag_before=a['vram']-a['prepared'],
                publication_lag_after=b['vram']-b['prepared'])


def audit(before,after,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(Path(__file__)):sha(Path(__file__))};states={}
    for name,root in (('before',before),('after',after)):
        proof=bound_report(root/'publication-state.json')
        if not proof['observer_neutral']:raise ValueError('Missing exact-core neutrality')
        sources.update(proof['sources']);sources[str(root/'publication-state.json')]=sha(root/'publication-state.json')
        states[name]={int(f):Path(v['path']).read_bytes() for f,v in proof['samples'].items()}
    cases=[]
    for column,target,lo,hi in ((15,232,5994,5998),(18,218,6000,6005)):
        arms={}
        for name,data in states.items():
            records=[]
            for f in range(lo,hi+1):
                raw=data[f]
                if len(raw)!=196608:raise ValueError('Wrong snapshot geometry')
                off=25*64+column*2
                records.append(dict(frame=f,source=raw[0x12000+25*32+column],
                    prepared=raw[0x3000+off],vram=raw[0x24000+off],
                    prepared_high=raw[0x3001+off],vram_high=raw[0x24001+off],flag=raw[0x1d19]))
            if any(r['prepared_high']!=8 or r['vram_high']!=8 for r in records):
                raise ValueError('Changed text attributes')
            arms[name]=records
        cases.append(dict(row=25,column=column,target=target,records=arms,
                          attribution=classify(arms['before'],arms['after'],target)))
    sources['tools/audit_main_display_latency.py']=sha(Path('tools/audit_main_display_latency.py'))
    sources['tests/test_wait80_deadlines.py']=sha(Path('tests/test_wait80_deadlines.py'))
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>Text delay attribution</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}</style><h1>Source on time; preparation one frame late</h1><p>All sampled states retained; no alignment. These are frame-boundary observations, not physical scanout timestamps. Same-core full primary timeline/native PCM observation is neutral in each arm. No source generation is censored in these two selected windows. No release verdict.</p><pre>'+html.escape(json.dumps(cases,indent=2))+'</pre><p><a href="report.json">Records and bindings</a> · <a href="../audio-boundary-wait80-gallery-3928/">Full picture differences</a></p>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed sources')
    (out/'report.json').write_text(json.dumps(dict(cases=cases,sources=sources,
        artifacts={'index.html':sha(out/'index.html')},release_ready=False),indent=2)+'\n')
    print(json.dumps([c['attribution'] for c in cases]))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
