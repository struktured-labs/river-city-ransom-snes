"""Measure hidden room-loading row stages, with a complete neutral replay."""
import argparse
import csv
import json
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
    from .audit_park_spans import parse, position
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit_park_spans import parse, position


def audit(capture,normal,spans,out):
    receipt,frames=verify_capture(capture)
    control,_=verify_capture(normal)
    for r in (receipt,control):
        if not r['capture_complete'] or r['system']!='snes':raise ValueError('Need complete SNES captures')
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=control[key]:raise ValueError('Observer changed '+key)
    if any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in frames):
        raise ValueError('Faulty or mismatched-input capture')
    binding=receipt['span_trace']
    if binding['sha256']!=sha(spans):raise ValueError('Unbound spans')
    rows=parse(csv.reader(spans.open()),binding)
    samples=[]
    for a,b in zip(rows,rows[1:]):
        if a['event']==1 and b['event']==2 and a['transition']==2:
            if a['nmi']!=b['nmi']:raise ValueError('Interrupt interrupted row conversion')
            samples.append(dict(start=position(a),end=position(b),room=a['room'],
                task=a['task'],clocks=b['clock']-a['clock']))
    if len(samples)<3:raise ValueError('Insufficient hidden row-stage observations')
    report=dict(observer_equivalent=True,frames=receipt['frames'],row_stages=samples,
        sources=dict(capture_sha256=sha(capture/'capture.json'),normal_sha256=sha(normal/'capture.json'),
            spans_sha256=sha(spans),rom_sha256=receipt['rom_sha256'],core_sha256=receipt['core_sha256'],
            normal_core_sha256=control['core_sha256'],audit_sha256=sha(Path(__file__))),
        scope='Every adjacent row-entry to palette-entry span with transition state 2 in this bound window. '
              'Inclusive elapsed clocks, not exclusive instructions or full-game speed. Complete replay timeline and PCM match normal core.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observer_equivalent=True,frames=report['frames'],row_stages=samples),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','spans','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.capture,a.normal,a.spans,a.out)
