"""Verify every current-publisher upload and rendered static OAM tail across a full route."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_sprite_publication import FIELDS
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent


def read_events(path):
    with path.open() as stream:
        for i,raw in enumerate(csv.reader(stream)):
            if len(raw)!=len(FIELDS) or raw[0] not in 'DER':raise ValueError('Unexpected OAM event')
            e=dict(zip(FIELDS,raw));e['index']=i
            for key in FIELDS[1:19]:e[key]=int(e[key],16 if key in ('pc','source') else 10)
            for key in ('prepared','oam'):
                e[key]=bytes.fromhex(e[key])
                if len(e[key])!=544:raise ValueError('Incomplete OAM bytes')
            yield e


def analyze(events):
    active=None;tail=None;first=None;failures=[];transfers=[];other=[];kinds=Counter()
    coverage={};heights={};render_events=0;unbound_renders=[]
    for e in events:
        kinds[e['kind']]+=1
        if e['kind']=='D':
            if active is not None:failures.append(dict(event=e['index'],kind='nested_dma'))
            active=e
            if e['pc']==0xc05134:
                if (e['channel'],e['mode'],e['source'],e['target'])!=(0,0,0x7e5000,4) or e['count'] not in (256,544):
                    failures.append(dict(event=e['index'],kind='wrong_production_descriptor'))
                if first is None:
                    first=e['index']
                    if e['count']!=544:failures.append(dict(event=e['index'],kind='first_upload_not_full'))
                if e['count']==256 and e['oam'][256:]!=e['prepared'][256:]:
                    failures.append(dict(event=e['index'],kind='static_tail_stale_before_partial'))
        elif e['kind']=='E':
            if active is None:failures.append(dict(event=e['index'],kind='unmatched_end'));continue
            record=dict(start_event=active['index'],end_event=e['index'],frame=active['frame'],
                        start=[active['line'],active['cycle']],end=[e['line'],e['cycle']],
                        count=active['count'],blank=active['blank'],pc=hex(active['pc']))
            if active['pc']==0xc05134:
                if e['oam']!=active['prepared']:
                    failures.append(dict(event=e['index'],kind='complete_oam_not_current'))
                if e['prepared']!=active['prepared']:
                    failures.append(dict(event=e['index'],kind='staging_changed_during_dma'))
                tail=active['prepared'][256:];transfers.append(record)
            else:other.append(record)
            active=None
        elif e['kind']=='R':
            if not (0<=e['first_y']<=e['last_y']<e['height']):
                failures.append(dict(event=e['index'],kind='invalid_render_span'));continue
            f=e['frame'];coverage.setdefault(f,Counter()).update(range(e['first_y'],e['last_y']+1))
            heights.setdefault(f,set()).add(e['height']);render_events+=1
            if tail is None:unbound_renders.append(e['index'])
            elif e['oam'][256:]!=tail:
                failures.append(dict(event=e['index'],kind='rendered_static_tail_changed'))
    if active is not None:failures.append(dict(event=active['index'],kind='unfinished_dma'))
    incomplete=[]
    for f,c in coverage.items():
        if len(heights[f])!=1 or set(c)!=set(range(max(heights[f]))) or any(v!=1 for v in c.values()):
            incomplete.append(dict(frame=f,heights=sorted(heights[f]),covered=len(c),duplicates=[y for y,n in c.items() if n!=1]))
    if not transfers or not render_events:raise ValueError('Missing actual transfer/render population')
    return dict(passed=not failures and not incomplete,failures=failures,incomplete_render_frames=incomplete,
                event_counts=dict(kinds),production_transfers=transfers,other_transfers=other,
                counts=dict(Counter(r['count'] for r in transfers)),render_frames=sorted(coverage),
                renders_before_first_production=unbound_renders,
                scope='All544 physical bytes checked after every current-publisher DMA; before partial uploads and at every recorded render span the288-byte tail must remain current. Initial pre-publisher display is explicitly unbound. Not live-sprite generation latency, palette/text freshness or unrecorded console scenes.')


def audit(candidate,capture,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(capture/'oam-route.json')
    if not proof['observed'] or not proof['observer_neutral']:raise ValueError('Neutral observation required')
    receipt,rows=verify_capture(capture);control,old=verify_capture(Path(proof['reference']))
    equivalent(receipt,rows,control,old)
    rom=(candidate/'native-cpu.sfc').read_bytes()
    if receipt['rom_sha256']!=sha(candidate/'native-cpu.sfc') or rom[0x5131:0x5134]!=bytes.fromhex('8d0b42'):
        raise ValueError('Wrong publisher/DMA anchor')
    trace=Path(proof['trace']);result=analyze(read_events(trace))
    def corrupt_tail():
        done=False
        for e in read_events(trace):
            if not done and e['kind']=='E' and e['pc']==0xc05134:
                raw=bytearray(e['oam']);raw[300]^=1;e=dict(e,oam=bytes(raw));done=True
            yield e
        if not done:raise ValueError('No mutation target')
    bad=analyze(corrupt_tail())
    negative=any(f['kind']=='complete_oam_not_current' for f in bad['failures'])
    if not negative:raise ValueError('Stale static tail survived')
    result['no_render_event_frames']=sorted(set(range(1,receipt['frames']+1))-set(result['render_frames']))
    result['no_render_event_scope']='Retained, not counted as render coverage or silently assumed visible.'
    sources=dict(proof['sources'])
    for p in (Path(__file__),Path('tests/test_oam_route_tail.py'),Path('tools/audit_main_display_latency.py'),
              Path('tools/audit_sprite_publication.py'),Path('tools/benchmark_report.py'),
              Path('tools/capture_combat_instructions.py'),candidate/'native-cpu.sfc',capture/'oam-route.json'):
        sources[str(p)]=sha(p)
    out.mkdir()
    brief={k:result[k] for k in ('passed','counts','event_counts','failures','incomplete_render_frames')}
    body='''<!doctype html><meta charset="utf-8"><title>Full-route static sprite tail</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}</style>
<h1>3955: full-route actual sprite memory</h1><p>Fresh boot, complete same-core
primary timeline and native PCM neutrality. All544 physical sprite-memory bytes
are checked after every current-publisher upload, including the288 bytes omitted
by partial transfers. Every recorded render span checks the static tail too.</p>
<p>Initial display before the first publisher and frames without render events
remain explicit in JSON. This is not all-game coverage or a proof of live-sprite
latency, palette/text freshness, original-NES speed or clean sound.</p>'''
    body+='<pre>'+html.escape(json.dumps(brief,indent=2))+'</pre><p><a href="report.json">Every transfer, coverage and source binding</a> · <a href="../early-oam-live-half-review-3966/">Picture differences and measured deadline recovery</a></p>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(result=result,sources=sources,controls=dict(stale_untransferred_tail_rejected=negative),
                artifacts={'index.html':sha(out/'index.html')},release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(brief))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','capture','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
