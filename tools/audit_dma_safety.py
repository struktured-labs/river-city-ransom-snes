"""Check full general-DMA envelopes against actual forced blank or conservative VBlank bounds."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture

FIELDS=('start_frame','start_line','start_cycle','start_blank','start_height',
        'end_frame','end_line','end_cycle','end_blank','end_height',
        'channel','count','source','target','mode','reverse','remaining','native_id','transition')
# B-bus offsets written by each SNES DMA mode; inspect every targeted register.
OFFSETS=((0,),(0,1),(0,),(0,1),(0,1,2,3),(0,1),(0,),(0,1))
SENSITIVE={0x04,0x18,0x19,0x22}


def classify(event):
    e=event
    if (not 0<=e['channel']<8 or not 0<=e['mode']<8 or not 0<e['count']<=65536 or
        not 0<=e['target']<256 or not 0<=e['source']<=0xffffff or
        any(not 0<=e[k]<262 for k in ('start_line','end_line')) or
        any(e[k] not in (224,239) for k in ('start_height','end_height')) or
        any(e[k] not in (0,1) for k in ('start_blank','end_blank','reverse'))):
        raise ValueError('Invalid DMA envelope fields')
    targets={(e['target']+i)&255 for i in OFFSETS[e['mode']]}
    if e['reverse'] or not targets&SENSITIVE:
        return 'other'
    if e['remaining']:
        return 'aborted'
    if e['start_blank'] and e['end_blank']:
        return 'forced_blank'
    # No line0 exception: this conservative whole-envelope gate uses the
    # pinned core's ScreenHeight+FIRST_VISIBLE_LINE boundary (FIRST=1).
    # A frame counter change means crossing active scanout, even if both
    # endpoints appear to be in VBlank. Unstable blank/height is not accepted.
    if (e['start_blank']==e['end_blank']==0 and e['start_height']==e['end_height'] and
        e['start_frame']==e['end_frame'] and
        e['start_height']+1<=e['start_line']<=e['end_line']<262 and
        (e['start_line']!=e['end_line'] or e['end_cycle']>=e['start_cycle'])):
        return 'vblank'
    return 'unsafe_or_unproven'


def parse(raw):
    events=[]
    for i,row in enumerate(raw):
        if len(row)!=len(FIELDS):raise ValueError('Malformed DMA envelope')
        event=dict(zip(FIELDS,(int(v,16 if j in (12,13) else 10) for j,v in enumerate(row))))
        event['classification']=classify(event);event['index']=i
        if events and (event['start_frame'],event['start_line'],event['start_cycle'])<(
            events[-1]['start_frame'],events[-1]['start_line'],events[-1]['start_cycle']):
            # IPPU frame counter increments at line1; scanline0 is the only
            # legitimate raw-coordinate inversion within the same IPPU frame.
            prior=events[-1]
            if not(event['start_frame']==prior['start_frame'] and event['start_line']==0 and prior['start_line']>0):
                raise ValueError('DMA start order moved backwards')
        events.append(event)
    if not events:raise ValueError('No DMA coverage')
    return events


def audit(capture,control,out):
    if out.exists():raise ValueError('Fresh report required')
    binding=bound_report(capture/'dma-capture.json');baseline=bound_report(control/'dma-capture.json')
    if not binding['observed'] or not binding['observer_neutral'] or baseline['observed'] or binding['reference']!=str(control):
        raise ValueError('Wrong observer/control pair')
    receipt,rows=verify_capture(capture);original,before=verify_capture(control)
    if rows!=before or any(receipt[k]!=original[k] for k in ('core_sha256','rom_sha256','audio_sha256')):
        raise ValueError('Changed observed execution')
    with Path(binding['trace']).open() as f:events=parse(csv.reader(f))
    failures=[e for e in events if e['classification'] in ('aborted','unsafe_or_unproven')]
    visible=[e for e in events if e['classification']=='vblank']
    if not visible or not any(e['classification']=='forced_blank' for e in events):
        raise ValueError('Missing visible/forced-blank DMA populations')
    controls={}
    template=visible[0]
    for label,changed in (('active_scanout',dict(start_line=120,end_line=122)),
                          ('crossed_frame',dict(end_frame=template['end_frame']+1)),
                          ('unfinished_transfer',dict(remaining=1))):
        controls[label+'_rejected']=classify(dict(template,**changed)) in ('aborted','unsafe_or_unproven')
    if not all(controls.values()):raise ValueError('Unsafe DMA trace mutation survived')
    sources={**binding['sources'],**baseline['sources']}
    for p in (Path(__file__),Path('tests/test_dma_safety.py'),Path('tools/snes9x_dma_safety.inc'),
              capture/'dma-capture.json',control/'dma-capture.json'):
        sources[str(p)]=sha(p)
    report=dict(passed=not failures,rom_sha256=receipt['rom_sha256'],frames=len(rows),
        dma_transfers=len(events),populations=dict(Counter(e['classification'] for e in events)),
        target_counts=dict(Counter(f'{e["target"]:02x}' for e in events)),failures=failures,
        latest_visible_end=max(e['end_line'] for e in visible),
        latest_visible_transfers=sorted(visible,key=lambda e:(e['end_line'],e['end_cycle']),reverse=True)[:32],
        controls=controls,sources=sources,release_ready=False,physical_verified=False,
        scope=__doc__+' Actual core PPU state, not game transition flags. Every CPU general DMA is '
        'observed; HDMA is excluded. Whole-envelope conservative timing, not per-byte hardware validation. '
        'Source-built and observer-on/off execution must preserve all game frames and native PCM. '
        'Unsafe/unproven envelopes fail rather than treating a transition flag as forced blank.')
    out.mkdir(parents=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Full-route DMA safety</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1000px;margin:2em auto}a{color:cyan}pre{white-space:pre-wrap}</style>'
        f'<h1>General DMA envelope audit: {"PASS" if report["passed"] else "FAIL"}</h1>'
        '<p>'+html.escape(report['scope'])+'</p><pre>'+html.escape(json.dumps({k:report[k] for k in
        ('frames','dma_transfers','populations','latest_visible_end','controls','failures')},indent=2))+
        '</pre><p><a href="report.json">Hash-bound observations and limits</a></p>')
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    report['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','dma_transfers','populations','latest_visible_end','controls')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('capture','control','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
