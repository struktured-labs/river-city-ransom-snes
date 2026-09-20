"""Measure actual completed sound-packet spacing, retaining transitions separately."""
import argparse
from bisect import bisect_right
import csv
import json
from pathlib import Path
import statistics
from tools.audit_busy_combat import classify
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture


def audit(normal,observed,qualification,out):
    if out.exists():raise ValueError('Fresh report required')
    proof=bound_report(qualification/'report.json');receipt,rows=verify_capture(normal)
    obs,other=verify_capture(observed)
    if not proof['passed'] or rows!=other or any(receipt[k]!=obs[k] for k in
            ('core_sha256','rom_sha256','audio_sha256')):raise ValueError('Different/non-neutral qualified replay')
    if proof['summary']['rom_sha256']!=receipt['rom_sha256']:raise ValueError('Wrong qualified cartridge')
    binding=obs['dsp_latency_observer']['traces']['RCR_DSP_LATENCY_TRACE'];path=Path(binding['path'])
    if sha(path)!=binding['sha256'] or proof['sources'].get(str(path))!=binding['sha256']:
        raise ValueError('Trace not bound to validated DSP execution')
    events=[]
    with path.open() as f:
        for r in csv.reader(f):
            if r[0]!='R' or int(r[1])==0:continue
            packet,tick,samples,pending=map(int,r[1:])
            if packet!=len(events)+1 or samples!=(tick-pending+4)//32:raise ValueError('Changed ready order/clock')
            events.append(dict(packet=packet,tick=tick,generated_samples=samples,pending_clocks=pending))
    if len(events)!=proof['summary']['audio']['packets']:raise ValueError('Incomplete packet coverage')
    starts=[r['audio_start_sample'] for r in rows];stable=[];excluded=[]
    for a,b in zip(events,events[1:]):
        if b['tick']<=a['tick']:raise ValueError('Nonmonotonic packet completion')
        first=bisect_right(starts,(a['tick']+4)//32);last=bisect_right(starts,(b['tick']+4)//32)
        if not 1<=first<=last<=len(rows):raise ValueError('Packet outside native callback timeline')
        context=classify(rows[first-1:last])
        event=dict(first=a,second=b,first_frame=first,last_frame=last,context=context,
            gap_ticks=b['tick']-a['tick'],gap_ms=(b['tick']-a['tick'])*1000/(32040*32))
        (stable if context['room'] is not None else excluded).append(event)
    if not stable:raise ValueError('No stable gameplay coverage')
    values=[r['gap_ms'] for r in stable]
    summary=dict(stable_intervals=len(stable),excluded_intervals=len(excluded),
        minimum_ms=min(values),median_ms=statistics.median(values),maximum_ms=max(values),
        largest=sorted(stable,key=lambda r:r['gap_ticks'],reverse=True)[:16])
    sources=dict(proof['sources'])
    for p in (Path(__file__),Path('tools/audit_busy_combat.py'),qualification/'report.json',
              normal/'capture.json',normal/'timeline.json',observed/'capture.json',path):sources[str(p)]=sha(p)
    report=dict(summary=summary,stable=stable,excluded=excluded,sources=sources,
        release_ready=False,pop_free_verified=False,physical_attribution=False,
        scope=__doc__+' Ready-clock differences use the validated DSP tick domain (32 ticks per native32040Hz sample). '
        'Frame classification maps that absolute clock to untouched native callback ranges; it is not CPU '
        'instruction timing or request-to-driver latency. No interval is called a pop, dropped tick or tempo '
        'fault solely from its size. Next separate driver scheduling from driver duration and SPC work.')
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='largest'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('normal','observed','qualification','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
