"""Current early-OAM optimization: actual hardware-memory checks and text deadline recovery."""
import csv
import html
import json
from collections import Counter
from pathlib import Path
import shutil
import argparse

from tools.audit_main_display_latency import bound_report
from tools.audit_sprite_publication import parse, translated
from tools.audio_packet_log import labels
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_sprite_prefix import installed_prefix


def sprite_check(events,first,last,y_map,attrs):
    failures=[];active=None;last_dma=None;transfers=[];generations=[]
    coverage={f:Counter() for f in range(first,last+1)}
    for e in events:
        if e['frame'] not in coverage:raise ValueError('Outside sprite window')
        if e['kind']=='S':
            if not generations or generations[-1]['source']!=e['shadow']:
                generations.append(dict(source=e['shadow'],frame=e['frame'],left_censored=not generations,
                    expected=translated(bytes.fromhex(e['shadow']),e['ctrl'],y_map,attrs).hex(),first_render=None))
        elif e['kind']=='D':
            if active is not None:failures.append('nested DMA')
            if (e['channel'],e['mode'],e['source'],e['target'])!=(0,0,0x7e5000,4) or e['count'] not in (256,544):
                failures.append('unsupported DMA')
            if bytes.fromhex(e['prepared'])[:256]!=translated(bytes.fromhex(e['cached']),e['ctrl'],y_map,attrs):
                failures.append('wrong translation')
            active=e
        elif e['kind']=='E':
            if active is None:failures.append('unmatched DMA end');continue
            # Both full and partial uploads must leave ALL544 bytes current.
            # In particular do not compare only the256 transferred bytes.
            if e['oam']!=active['prepared']:failures.append('incomplete physical OAM')
            transfers.append(dict(frame=active['frame'],bytes=active['count'],
                                  start=[active['line'],active['cycle']],end=[e['line'],e['cycle']]))
            last_dma=e['oam'];active=None
        elif e['kind']=='R':
            if last_dma is not None and e['oam']!=last_dma:failures.append('render OAM differs from completed DMA')
            coverage[e['frame']].update(range(e['first_y'],e['last_y']+1))
            match=next((g for g in reversed(generations) if e['oam'][:512]==g['expected']),None)
            if match is not None and match['first_render'] is None:match['first_render']=e['frame']
    if active is not None:failures.append('unfinished DMA')
    for f,c in coverage.items():
        if set(c)!=set(range(239)) or any(v!=1 for v in c.values()):failures.append(f'incomplete/duplicate rendering{f}')
    if not transfers or not generations:raise ValueError('Missing actual populations')
    known=[g for g in generations if not g['left_censored']]
    return dict(passed=not failures,failures=failures,transfers=transfers,
        counts=dict(Counter(t['bytes'] for t in transfers)),generations=generations,
        known_generations=len(known),unrendered=[g['frame'] for g in known if g['first_render'] is None],
        latency_histogram=dict(Counter(g['first_render']-g['frame'] for g in known if g['first_render'] is not None)))


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(Path(__file__)):sha(Path(__file__))}
    for name in ('audit_main_display_latency','audit_sprite_publication','audio_packet_log','benchmark_report',
                 'capture_combat_instructions','capture_sprite_prefix'):
        p=Path('tools')/(name+'.py');sources[str(p)]=sha(p)
    roots=dict(before=Path('build/receiver-local-poll-full-3940'),after=Path('build/early-oam-live-half-full-3957'))
    rows={}
    for arm,root in roots.items():
        receipt,rows[arm]=verify_capture(root)
        for name in ('capture.json','timeline.json','audio.wav'):
            p=root/name;sources[str(p)]=sha(p)
    if len(rows['before'])!=len(rows['after']):raise ValueError('Different route lengths')
    differences={k:[a['frame'] for a,b in zip(rows['before'],rows['after']) if a[k]!=b[k]]
                 for k in ('probe_052b','input_requested','input_delivered','video_sha256')}
    differences['logical_camera_x']=[a['frame'] for a,b in zip(rows['before'],rows['after'])
                                    if a['native']['logical_camera_x']!=b['native']['logical_camera_x']]
    text_proof=bound_report(Path('build/early-oam-live-half-text-review-3959/report.json'))
    sources.update(text_proof['sources'])
    p=Path('build/early-oam-live-half-text-review-3959/report.json');sources[str(p)]=sha(p)
    audio_path=Path('build/early-oam-live-half-audio-review-3962/report.json')
    audio=json.loads(audio_path.read_text());sources[str(audio_path)]=sha(audio_path)
    sources.update(audio['sources'])
    observed=Path('build/early-oam-live-half-sprites-observed-3965')
    p=observed/'sprite-events-capture.json';proof=bound_report(p)
    if not proof['observer_neutral']:raise ValueError('Non-neutral sprite observer')
    sources.update(proof['sources']);sources[str(p)]=sha(p)
    with installed_prefix(proof['last_phase']):
        receipt,srows=verify_capture(observed);control,crows=verify_capture(Path(proof['reference']))
    equivalent(receipt,srows,control,crows)
    candidate=Path('build/early-oam-live-half-game-3955')
    if receipt['rom_sha256']!=sha(candidate/'native-cpu.sfc'):raise ValueError('Wrong sprite ROM')
    symbols=labels(candidate/'native_boot.lbl');rom=(candidate/'native-cpu.sfc').read_bytes()
    ymap=rom[symbols['sprite_y_map']:symbols['sprite_y_map']+256]
    attrs=rom[symbols['sprite_attribute_map']:symbols['sprite_attribute_map']+256]
    with Path(proof['trace']).open() as f:events=parse(csv.reader(f))
    args=(proof['first'],proof['last'],ymap,attrs)
    sprites=sprite_check(events,*args)
    damaged=[dict(e) for e in events];at=next(i for i,e in enumerate(damaged) if e['kind']=='E')
    raw=bytearray.fromhex(damaged[at]['oam']);raw[300]^=1;damaged[at]['oam']=raw.hex()
    missing=[dict(e) for e in events];missing.pop(next(i for i,e in enumerate(missing) if e['kind']=='R'))
    negative=dict(stale_untransferred_tail_rejected=not sprite_check(damaged,*args)['passed'],
                  missing_render_coverage_rejected=not sprite_check(missing,*args)['passed'])
    if not all(negative.values()):raise ValueError('Bad observation survived')
    timings={}
    for arm,root,pcs in [('before',Path('build/receiver-local-poll-text-instructions-3951'),(0xc07300,0xc07329)),
                          ('after',Path('build/early-oam-live-half-instructions-3963'),(0xc07300,0xc05141))]:
        p=root/'service-instructions.json';trace=bound_report(p)
        if not trace['observer_neutral']:raise ValueError('Non-neutral CPU observation')
        sources.update(trace['sources']);sources[str(p)]=sha(p)
        with Path(trace['trace']).open() as stream:
            selected=[r for r in csv.reader(stream) if int(r[0])==5990 and int(r[4],16) in pcs]
        if len(selected)!=2 or tuple(int(r[4],16) for r in selected)!=pcs:raise ValueError('Wrong helper coverage')
        timings[arm]=dict(records=selected,elapsed_master_clocks=int(selected[1][3])-int(selected[0][3]))
    for path in ('build/early-oam-live-half-executed-3956/report.json','build/early-oam-live-half-macro-3960/report.json'):
        p=Path(path);proof=bound_report(p)
        if not proof['passed']:raise ValueError('Failed executed fixture')
        sources.update(proof['sources']);sources[str(p)]=sha(p)
        for records in ([proof['positive']] if 'positive' in proof else proof['positives']):
            sources.update(records)
        for m in proof.get('negative',proof.get('mutants',[])):sources.update(m['artifacts'])
    summary=dict(rom_sha256=sha(candidate/'native-cpu.sfc'),frames=len(rows['after']),
        difference_counts={k:len(v) for k,v in differences.items()},sprite_counts=sprites['counts'],
        sprite_latency=sprites['latency_histogram'],sprite_passed=sprites['passed'],
        helper_timing=timings,text_counts=text_proof['counts'],strict_text_pass=text_proof['no_publication_regression'])
    out.mkdir()
    body='''<!doctype html><meta charset="utf-8"><title>Early OAM: recovered dialogue deadline</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}
a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:10px}img{width:48%;image-rendering:pixelated}</style>
<h1>Smaller sprite uploads recover a dialogue deadline</h1>
<p>3934 left; experimental3955 right. First and hidden uploads remain544 bytes;
visible uploads subsequently send256 live bytes. Original graphics, sound engine,
byte budgets and beam deadlines are unchanged. No default promotion or hardware deployment.</p>
<p>The dialogue tile at row25/column12 has identical source5989 and preparation5990.
It reaches actual VRAM at5991 instead of5992. The frame5990 helper, including its
trampoline but before RTS, takes2,652 rather than4,850 master clocks. This is one
measured helper invocation, not a whole-game speed percentage.</p>
<p>The84-frame text gate still flags an unsupported playfield word at8236. Source
bytes match throughout these windows. All55 changed pictures and two logical-camera
differences remain; they are not waived. Broader DMA, combat, renderer, menu/palette
and physical-console qualification are pending. Audio remains non-pop-free.</p>
<p><a href="report.json">Exact records and all differences</a> ·
<a href="../early-oam-live-half-audio-review-3962/">Untouched native audio and packet timing</a> ·
<a href="../early-oam-live-half-text-review-3959/report.json">All text-window differences</a></p>'''
    body+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    for frame in differences['video_sha256']:
        body+=f'<h2>Frame {frame}</h2><div class="pair">'
        for arm,root in roots.items():
            row=rows[arm][frame-1];p=root/row['frame_image']
            if sha(p)!=row['frame_image_sha256']:raise ValueError('Changed image')
            name=f'{arm}-{frame}.png';shutil.copyfile(p,out/name);sources[str(p)]=sha(p)
            body+=f'<img src="{name}" alt="{arm} frame {frame}" loading="lazy">'
        body+='</div>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(dict(summary=summary,sprites=sprites,controls=negative,
        differences=differences,sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
