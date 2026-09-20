"""Attribute one captured missed-frame worker to instruction-entry elapsed clocks."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha

CALLS = ((0xf16d,0xf170,'FDF4 entry work'),(0xf18c,0xf18f,'FC4D PPU update'),
         (0xf19e,0xf1a1,'E6BF'),(0xf1a1,0xf1a4,'E30A'),
         (0xf1ac,0xf1af,'E2D2'),(0xf1d0,0xf1d3,'FF07'))


def parse(source, first, last):
    rows=[]
    for row in source:
        if len(row)!=10:
            raise ValueError('Need ten-column instruction-entry trace')
        r=dict(zip(('frame','line','cycle','clock','pc','opcode','a','x','y','s'),
                   (int(v,16 if i in (4,5) else 10) for i,v in enumerate(row))))
        if not first<=r['frame']<=last or not 0<=r['pc']<=0xffffff or not 0<=r['opcode']<=255:
            raise ValueError('Instruction outside capture bounds')
        if rows and r['clock']<=rows[-1]['clock']:
            raise ValueError('Instruction clocks not strictly increasing')
        rows.append(r)
    if len(rows)<2:
        raise ValueError('Empty instruction trace')
    return rows


def section(rows, start, end):
    selected=[r for r in rows if start<=r['clock']<=end]
    if not selected or selected[0]['clock']!=start or selected[-1]['clock']!=end:
        raise ValueError('Missing exact stage-boundary instruction')
    costs=Counter()
    for a,b in zip(selected,selected[1:]):
        # Runtime is replicated in game banks; do not merge bank C0 producer
        # addresses or original game routines across distinct ROM banks.
        pc=a['pc']
        key=f'runtime:{pc&65535:04x}' if pc>>16!=0xc0 and 0x2000<=pc&65535<0x3000 else f'{pc:06x}'
        costs[key]+=b['clock']-a['clock']
    return dict(master_clocks=end-start, instructions=len(selected)-1,
                top_instruction_elapsed=[dict(pc=pc,clocks=clocks) for pc,clocks in costs.most_common(25)]),selected


def build(capture, control, trace, spans, out, frame):
    receipt,_=verify_capture(capture)
    baseline,_=verify_capture(control)
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=baseline[key]:
            raise ValueError('Observer changed control execution')
    if any(r['system']!='snes' or not r['capture_complete'] for r in (receipt,baseline)):
        raise ValueError('Incomplete/wrong-system capture')
    binding=receipt.get('instruction_trace',{})
    if binding.get('sha256')!=sha(trace) or receipt.get('span_trace',{}).get('sha256')!=sha(spans):
        raise ValueError('Unbound instruction or stage trace')
    with trace.open() as source:
        rows=parse(csv.reader(source),binding['first'],binding['last'])
    with spans.open() as source:
        events=list(csv.reader(source))
    def event(index):
        values=[int(r[4]) for r in events if int(r[0])==index and int(r[1])==frame]
        if len(values)!=1:
            raise ValueError('Ambiguous/missing stage in selected raw frame')
        return values[0]
    nmi,selected=section(rows,event(8),event(7))
    sound,_=section(rows,event(10),event(11))
    nmi['original_call_sites']=[]
    for start,end,label in CALLS:
        sites=[[r for r in selected if r['pc']&65535==pc] for pc in (start,end)]
        if any(len(s)!=1 for s in sites) or sites[0][0]['opcode']!=0x20:
            raise ValueError('Original NMI call-site sequence differs')
        nmi['original_call_sites'].append(dict(name=label,caller=f'{start:04x}',
            clocks=sites[1][0]['clock']-sites[0][0]['clock'],
            start_line=sites[0][0]['line'],end_line=sites[1][0]['line']))
    report=dict(frame=frame,nmi=nmi,sound=sound,observer_equivalent=True,
        sources=dict(capture_sha256=sha(capture/'capture.json'),control_sha256=sha(control/'capture.json'),
                     instruction_sha256=sha(trace),span_sha256=sha(spans),
                     rom_sha256=receipt['rom_sha256'],core_sha256=receipt['core_sha256'],
                     audit_sha256=sha(Path(__file__))),
        scope='Instruction-entry elapsed master clocks include DMA/events between dispatches; '
              'not exclusive CPU instruction costs. Exact single missed-frame paths, not averages '
              'or original NES speed/audio certification. Full observed timeline and WAV match control.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Missed-frame instruction costs</title>
<style>body{background:#111820;color:#eee;font:16px system-ui;max-width:1100px;margin:30px auto}
pre{white-space:pre-wrap}a{color:#9cf}</style><h1>Missed-frame instruction costs</h1><p>'''+
        html.escape(report['scope'])+'</p><p><a href="report.json">Raw measurements and hashes</a></p><pre>'+
        html.escape(json.dumps(dict(nmi=nmi,sound=sound),indent=2))+'</pre>')
    print(json.dumps(nmi['original_call_sites'],indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','control','trace','spans','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--frame',type=int,required=True)
    a=p.parse_args()
    build(a.capture,a.control,a.trace,a.spans,a.out,a.frame)
