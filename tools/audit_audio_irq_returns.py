"""Actual phase80 IRQ A/B/X/Y and stack returns; P/DB/DP are not in this observer."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha


def returns(events, entry_pc=0xc1791b):
    pairs=[];active=None
    for i,e in enumerate(events):
        if e['pc']==entry_pc:
            if active is not None:raise ValueError('IRQ reentered before return')
            active=e
        if active is None or e['pc']&0xffff!=0xf1d8:continue
        if e['opcode']!=0x40:raise ValueError('Not the original RTI opcode')
        if i+1==len(events):raise ValueError('Missing post-RTI observation')
        after=events[i+1]
        faults=[]
        for field in ('a','x','y'):
            if e[field]!=active[field] or after[field]!=active[field]:faults.append(field)
        if e['s']!=active['s'] or after['s']!=0x100+((active['s']+3)&255):faults.append('stack')
        pairs.append(dict(entry=active,rti=e,resumed=after,failures=faults))
        active=None
    if active is not None:raise ValueError('Unreturned IRQ at trace boundary')
    if not pairs:raise ValueError('No observed IRQ returns')
    return dict(passed=all(not p['failures'] for p in pairs),pairs=pairs,count=len(pairs))


def audit(capture,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(capture/'pause-observer.json')
    if not proof['observer_neutral']:raise ValueError('Non-neutral trace')
    path=Path(proof['traces']['RCR_INSTRUCTION_TRACE'])
    with path.open() as f:events=parse(csv.reader(f),proof['first'],proof['last'])
    result=returns(events)
    changed=[dict(e) for e in events]
    target=result['pairs'][0]['resumed']['clock']
    next(e for e in changed if e['clock']==target)['x']^=1
    mutation_rejected=not returns(changed)['passed']
    if not mutation_rejected:raise ValueError('Register damage escaped gate')
    sources=dict(proof['sources'])
    for p in (Path(__file__),capture/'pause-observer.json',Path('tools/audit_park_instructions.py'),
              Path('tests/test_audio_irq_returns.py')):sources[str(p)]=sha(p)
    result.update(sources=sources,changed_x_rejected=mutation_rejected,release_ready=False,
        scope=__doc__+' Bounded1430–1445 trace. This does not validate unobserved interrupt '
        'phases, the exact intended return PC, bank flags or stack-wrap safety elsewhere.')
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','count','changed_x_rejected')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
