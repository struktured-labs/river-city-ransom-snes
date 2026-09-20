"""Compare every original sound request ID/order, retaining frame and phase differences."""
import argparse
import csv
import html
import json
from pathlib import Path
from tools.audit_sound_busy import parse as parse_calls
from tools.review_command_priority import bound
from tools.benchmark_report import sha

def parse(rows):
    calls=parse_calls([r for r in rows if r[0]!='3'])
    requests=[];other=[]
    for r in rows:
        if r[0]!='3':continue
        if r[5]!='c6802f':other.append(r);continue
        if len(r)!=18 or r[6]!='f0' or not 0<=int(r[8])<=255:raise ValueError('Invalid request observation')
        requests.append(dict(frame=int(r[1]),line=int(r[2]),cycle=int(r[3]),clock=int(r[4]),request_id=int(r[8]),stack=int(r[10])))
    if not requests:raise ValueError('No request coverage')
    return dict(**calls,request_ids=requests,other_bank_request_events=other)

def require_identity(a,b):
    if not a or len(a)!=len(b) or [x['request_id'] for x in a]!=[x['request_id'] for x in b]:raise ValueError('Lost, changed or reordered request')

def audit(before,after,out):
    if out.exists():raise ValueError('Fresh report required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tests/test_sound_request_ids.py'),Path('tools/audit_sound_busy.py'),Path('tools/review_command_priority.py'))}
    arms={};timings={}
    for name,root in [('3955',before),('4007',after)]:
        proofpath=root/'sound-request-ids.json';proof=bound(proofpath)
        if not proof['observer_neutral'] or proof['points']!=[0x8146,0x814b,0x819a,0x802f]:raise ValueError('Wrong observation')
        path=Path(proof['trace']);arms[name]=parse(list(csv.reader(path.open())))
        for p in (path,proofpath):sources[str(p)]=sha(p)
        timings[name]={k:proof[k] for k in ('replay_seconds','total_seconds')}
    a,b=[arms[k]['request_ids'] for k in ('3955','4007')];require_identity(a,b)
    changed=[]
    for i,(x,y) in enumerate(zip(a,b)):
        changed.append(dict(index=i,request_id=x['request_id'],before=x,after=y,frame_delta=y['frame']-x['frame']))
    missing=b[:-1];wrong=[dict(x) for x in b];wrong[0]['request_id']^=1
    reordered=[dict(x) for x in b];i=next(i for i in range(len(b)-1) if b[i]['request_id']!=b[i+1]['request_id']);reordered[i:i+2]=reversed(reordered[i:i+2])
    for mutant in (missing,wrong,reordered):
        try:require_identity(a,mutant)
        except ValueError:pass
        else:raise ValueError('Request mutant escaped')
    summary=dict(requests=len(a),identity_and_order_equal=True,frame_differences=[r for r in changed if r['frame_delta']],
        busy_returns={k:[c['entry']['frame'] for c in arm['calls'] if c['busy_return']] for k,arm in arms.items()},
        timings=timings,negative_controls_rejected=['missing request','changed ID','reordered IDs'],
        release_ready=False,scope='Every request compared in observed order; no alignment or deletion. Equal IDs do not prove equal onset timing, sound-driver state, waveform or original-NES speed.')
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>Sound request identity</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}</style><h1>All230 sound requests retain identity and order</h1><p>The receiver trial4007 sends the same original sound request IDs as3955 in the same order. Four requests occur one frame later; all subframe timing differences are retained. The two original busy returns remain explicit. No request deletion, sequence alignment, waveform fitting or release promotion.</p><p><a href="report.json">Every request and phase</a> · <a href="../sound-busy-review-4019/">Busy-guard proof</a> · <a href="../receiver-token-priority-audio-review-4011/">Native audio</a></p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(dict(summary=summary,arms=arms,requests=changed,sources=sources,
        artifacts={'index.html':sha(out/'index.html')}),indent=2)+'\n')
    print(json.dumps(dict(requests=len(a),same_identity_and_order=True,frame_changes=[(r['index'],r['request_id'],r['before']['frame'],r['after']['frame']) for r in summary['frame_differences']])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
