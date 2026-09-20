"""Complete OAM integrity with independently recorded rendered/forced-black coverage."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_oam_route_tail import analyze
from tools.audit_sprite_publication import FIELDS
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent


def read(path):
    with path.open() as f:
        for i,raw in enumerate(csv.reader(f)):
            if len(raw)!=len(FIELDS) or raw[0] not in 'DERB':raise ValueError('Wrong event format')
            e=dict(zip(FIELDS,raw));e['index']=i
            for key in FIELDS[1:19]:e[key]=int(e[key],16 if key in ('pc','source') else 10)
            for key in ('prepared','oam'):
                e[key]=bytes.fromhex(e[key])
                if len(e[key])!=544:raise ValueError('Incomplete OAM payload')
            yield e


def spans(events,frames):
    coverage={};heights={};kinds=Counter();errors=[];black=[]
    for e in events:
        if e['kind'] not in 'RB':continue
        f=e['frame'];kind=e['kind'];kinds[kind]+=1
        if not 1<=f<=frames or not 0<=e['first_y']<=e['last_y']<e['height']:
            errors.append(dict(event=e['index'],kind='invalid_span'));continue
        if bool(e['blank'])!=(kind=='B'):errors.append(dict(event=e['index'],kind='wrong_blank_state'))
        coverage.setdefault(f,Counter()).update(range(e['first_y'],e['last_y']+1))
        heights.setdefault(f,set()).add(e['height'])
        if kind=='B':black.append(dict(frame=f,first=e['first_y'],last=e['last_y']))
    for f in range(1,frames+1):
        c=coverage.get(f,{})
        if not c:errors.append(dict(frame=f,kind='missing_frame'));continue
        if len(heights[f])!=1 or set(c)!=set(range(max(heights[f]))) or any(v!=1 for v in c.values()):
            errors.append(dict(frame=f,kind='missing_or_duplicate_lines'))
    return dict(passed=not errors,errors=errors,event_counts=dict(kinds),black_spans=black,frames=frames)


def audit(candidate,capture,out):
    if out.exists():raise ValueError('Fresh report required')
    proof=bound_report(capture/'oam-blank-route.json')
    if not proof['observer_neutral']:raise ValueError('Non-neutral observer')
    receipt,rows=verify_capture(capture);control,old=verify_capture(Path(proof['reference']))
    equivalent(receipt,rows,control,old)
    rom=candidate/'native-cpu.sfc'
    if receipt['rom_sha256']!=sha(rom) or rom.read_bytes()[0x5131:0x5134]!=bytes.fromhex('8d0b42'):
        raise ValueError('Wrong current publisher anchor')
    trace=Path(proof['trace'])
    memory=analyze(e for e in read(trace) if e['kind']!='B')
    coverage=spans(read(trace),receipt['frames'])
    # Preserve the prior strict R-only result. Only explicit B events can
    # establish what happened on its missing lines, not phase names or masks.
    def missing_blank():
        removed=False
        for e in read(trace):
            if e['kind']=='B' and not removed:removed=True;continue
            yield e
        if not removed:raise ValueError('No blank mutation target')
    def stale_tail():
        damaged=False
        for e in read(trace):
            if e['kind']=='B':continue
            if e['kind']=='E' and e['pc']==0xc05134 and not damaged:
                payload=bytearray(e['oam']);payload[300]^=1;e=dict(e,oam=bytes(payload));damaged=True
            yield e
        if not damaged:raise ValueError('No physical-memory mutation target')
    bad=analyze(stale_tail())
    negatives=dict(missing_black_span_rejected=not spans(missing_blank(),receipt['frames'])['passed'],
                   stale_static_tail_rejected=any(e['kind']=='complete_oam_not_current' for e in bad['failures']))
    if not all(negatives.values()):raise ValueError('Incomplete/corrupt observation survived')
    summary=dict(passed=not memory['failures'] and coverage['passed'],frames=receipt['frames'],
        production_uploads=len(memory['production_transfers']),sizes=memory['counts'],
        memory_failures=len(memory['failures']),render_events=coverage['event_counts'].get('R',0),
        black_events=coverage['event_counts'].get('B',0),coverage_failures=len(coverage['errors']),
        partial_render_frames_retained=len(memory['incomplete_render_frames']))
    sources=dict(proof['sources'])
    for p in (Path(__file__),Path('tools/audit_oam_route_tail.py'),Path('tools/audit_sprite_publication.py'),
              Path('tools/audit_main_display_latency.py'),Path('tools/benchmark_report.py'),
              Path('tools/capture_combat_instructions.py'),Path('tests/test_oam_blank_route.py'),
              capture/'oam-blank-route.json',rom):sources[str(p)]=sha(p)
    out.mkdir()
    body='''<!doctype html><meta charset="utf-8"><title>Full OAM and black-span coverage</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}</style>
<h1>3955: sprite integrity through full-route blanking transitions</h1>
<p>All544 actual OAM bytes must match staging after every production transfer.
Every recorded sprite-render span checks the static tail. A separate event marks
the exact lines the renderer fills black, so blank lines are accounted for—not
assumed rendered or silently excluded. Missing black spans and corrupted static
tail mutations must fail.</p><p>The earlier3977 R-only coverage failure remains
preserved. This fresh same-core neutral replay records both rendered and black
spans; every frame and line must occur once. Cross-core compatibility is checked
separately. No alignment, emulated memory edits, ROM logger or output filtering.</p>'''
    body+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><p>Not a complete-game, live-sprite latency, original-NES speed or pop-free audio certificate. No hardware deployment.</p><p><a href="report.json">All transfers, spans, failures and bindings</a> · <a href="../early-oam-live-half-review-3966/">Picture changes and measured improvement</a> · <a href="../early-oam-live-half-palette-review-3983/">Palette check</a> · <a href="../progress-3728/">Progress</a></p>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(dict(summary=summary,memory=memory,coverage=coverage,
        controls=negatives,sources=sources,artifacts={'index.html':sha(out/'index.html')},release_ready=False),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','capture','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
