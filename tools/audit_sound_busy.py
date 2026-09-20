"""Classify complete original sound-driver calls without treating intended busy returns as transfer loss."""
import argparse
import csv
import html
import json
from pathlib import Path
from tools.review_command_priority import bound
from tools.benchmark_report import sha

def parse(rows):
    active=None;calls=[];requests=[];other=[];clock=-1
    for raw in rows:
        if len(raw)!=18:raise ValueError('Malformed sparse trace')
        pc=int(raw[5],16);tick=int(raw[4])
        if tick<clock:raise ValueError('Nonmonotonic event stream')
        clock=tick
        if pc>>16!=0xc6:other.append(raw);continue
        item=dict(frame=int(raw[1]),line=int(raw[2]),cycle=int(raw[3]),clock=tick,pc=raw[5],a=int(raw[7]),x=int(raw[8]),y=int(raw[9]),stack=int(raw[10]))
        if pc==0xc68020:
            if raw[0]!='3' or raw[6]!='8a':raise ValueError('Wrong request opcode')
            requests.append(item);continue
        if pc==0xc68146:
            if active is not None or raw[0]!='0' or raw[6]!='2c':raise ValueError('Nested or malformed driver')
            active=dict(entry=item,accepted=None)
        elif pc==0xc6814b:
            if active is None or active['accepted'] is not None or raw[0]!='1' or raw[6]!='a2' or item['stack']!=active['entry']['stack']:raise ValueError('Unmatched accepted branch')
            active['accepted']=item
        elif pc==0xc6819a:
            if active is None or raw[0]!='2' or raw[6]!='60' or item['stack']!=active['entry']['stack']:raise ValueError('Unmatched return')
            active['return']=item;active['busy_return']=active['accepted'] is None
            active['clocks']=tick-active['entry']['clock']
            if active['clocks']<=0:raise ValueError('Invalid call duration')
            calls.append(active);active=None
        else:raise ValueError('Unknown watched PC')
    if active is not None or not calls:raise ValueError('Censored or empty call stream')
    return dict(calls=calls,requests=requests,other_bank_events=other)

def audit(before,after,out):
    if out.exists():raise ValueError('Fresh report required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tests/test_sound_busy.py'),Path('tools/review_command_priority.py'))}
    arms={};timings={}
    for tag,root in [('3955',before),('4007',after)]:
        proofpath=root/'sound-busy.json';proof=bound(proofpath)
        if not proof['observer_neutral'] or proof['frames']!=9090:raise ValueError('Wrong or non-neutral route')
        path=Path(proof['trace']);raw=list(csv.reader(path.open()));arms[tag]=parse(raw)
        timings[tag]={k:proof[k] for k in ('replay_seconds','total_seconds')}
        for p in (proofpath,path):sources[str(p)]=sha(p)
        missing_return=[r for r in raw if not(r[5]=='c6819a')]
        try:parse(missing_return)
        except ValueError:pass
        else:raise ValueError('Missing-return mutant escaped')
    summary={tag:dict(driver_calls=len(r['calls']),busy_returns=[c for c in r['calls'] if c['busy_return']],
                     request_count=len(r['requests']),other_bank_events=len(r['other_bank_events']),**timings[tag]) for tag,r in arms.items()}
    evidence=[]
    for tag,p in [('3955','build/source-divergence-parent-cpu-4015'),('4007','build/source-divergence-trial-cpu-4016')]:
        root=Path(p);proof=bound(root/'service-instructions.json');path=Path(proof['trace'])
        raw=list(csv.reader(path.open()));selected=[]
        for r in raw:
            if r[0]=='3276' and r[4] in ('c68024','c68029','c6811c','c68121','c68146','c68149','c6814b','c6819a'):selected.append(r)
        evidence.append(dict(candidate=tag,frame3276_instructions=selected))
        for p in (root/'service-instructions.json',path):sources[str(p)]=sha(p)
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>Original sound busy guard</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}</style><h1>Original busy guard explains the first changed packet</h1><p>The NES source and both SNES variants retain BIT $07FE / BMI return. In4007 frame3276, sound-state setup sets bit7 at line79, the timer enters at80, and the original driver returns through that guard.3955 runs its tick before setup begins at126. This is not lost SPC data; automatically replaying the tick would change original busy-guard behavior and has not been implemented.</p><p>All driver entries/accepted branches/returns and request entries are retained below. Busy paths remain separate, not counted as normal sound updates. The complete sparse observers preserve their same-core timelines and native PCM. No acoustic or release verdict; remaining changed sound events need attribution.</p><p><a href="../receiver-token-priority-source-review-4014/">Intact byte transfer and all source changes</a> · <a href="../receiver-token-priority-review-4013/">Timing and pictures</a> · <a href="report.json">Every event and exact bindings</a></p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(summary=summary,arms=arms,first_divergence=evidence,missing_return_mutants_rejected=True,sources=sources,
        artifacts={'index.html':sha(out/'index.html')},release_ready=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(calls=v['driver_calls'],busy=[c['entry']['frame'] for c in v['busy_returns']],requests=v['request_count']) for k,v in summary.items()}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
