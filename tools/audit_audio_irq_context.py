"""Compare complete real CPU context before hardware IRQ and after actual RTI."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha

FIELDS=('frame','line','cycle','clock','pc','a','x','y','s','p','dp','db','native_id','pending','depth')
PRESERVED=('pc','a','x','y','s','p','dp','db')


def analyze(raw):
    active=None;pairs=[];last_clock=-1
    for row in raw:
        if len(row)!=16 or row[0] not in ('I','R'):raise ValueError('Malformed IRQ event')
        event={k:int(v,16 if k=='pc' else 10) for k,v in zip(FIELDS,row[1:])}
        if event['clock']<=last_clock:raise ValueError('Nonmonotonic clocks')
        last_clock=event['clock']
        if row[0]=='I':
            if active is not None:raise ValueError('IRQ reentry before captured return')
            active=event
        else:
            if active is None:raise ValueError('Return without IRQ entry')
            failures=[k for k in PRESERVED if active[k]!=event[k]]
            if not active['p']&0x100:failures.append('unsupported_native_entry')
            if active['depth']!=event['depth']:failures.append('depth')
            pairs.append(dict(entry=active,returned=event,failures=failures,
                              clocks=event['clock']-active['clock']))
            active=None
    if active is not None:raise ValueError('Censored IRQ return')
    if not pairs:raise ValueError('No complete IRQs')
    return dict(passed=all(not p['failures'] for p in pairs),count=len(pairs),pairs=pairs,
        failures=[p for p in pairs if p['failures']])


def audit(capture,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(capture/'irq-context-capture.json')
    control=bound_report(Path(proof['reference'])/'irq-context-capture.json')
    if not proof['observer_neutral'] or control['observed']:raise ValueError('Wrong observer/control')
    with Path(proof['trace']).open() as f:raw=list(csv.reader(f))
    report=analyze(raw);controls={}
    for field in PRESERVED:
        changed=[list(r) for r in raw];index=1+FIELDS.index(field)
        r=next(r for r in changed if r[0]=='R');v=int(r[index],16 if field=='pc' else 10)^1
        r[index]=f'{v:06x}' if field=='pc' else str(v)
        controls[field+'_damage_rejected']=not analyze(changed)['passed']
    sources={**control['sources'],**proof['sources']}
    for p in (Path(__file__),Path('tests/test_audio_irq_context.py'),capture/'irq-context-capture.json',
              Path(proof['reference'])/'irq-context-capture.json'):sources[str(p)]=sha(p)
    report.update(sources=sources,controls=controls,release_ready=False,physical_verified=False,
        scope=__doc__+' Exact PB:PC, full A/B/X/Y/S, lazily packed P including E, DP and DB. '
        'NMI/coroutine paths and direct critical-section recovery are not IRQ observations.')
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],count=report['count'],failures=len(report['failures']),controls=controls)))
    return report['passed'] and all(controls.values())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','out'):p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(0 if audit(**vars(p.parse_args())) else 1)
