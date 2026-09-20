"""Publish scoped converter savings alongside the still-failing loading gates."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.build_alley_budget_review import validate_entry


def build(out):
    roots=dict(oracle='hidden-index-oracle-1389',timing='hidden-index-timing-1387',
        patch='hidden-index-patch-1394',before='alley-main-phases-1384',after='hidden-index-phases-1396',
        cadence='hidden-index-cadence-1399',renderer='hidden-index-render-audit-1400')
    reports={k:bound_report(Path('build')/v/'report.json') for k,v in roots.items()}
    if any(not reports[k]['passed'] for k in ('oracle','timing','patch','cadence','renderer')):
        raise ValueError('Failed scoped prerequisite; inspect before publishing')
    cases=[('Current16','postpublish-entry-1371','postpublish-normal-1322'),
           ('Index16','hidden-index-entry-1390','hidden-index-normal-1388'),
           ('Index12','hidden-index12-entry-1393','hidden-index12-normal-1392')]
    entries=[]
    for _,directory,capture in cases:
        report=json.loads((Path('build')/directory/'report.json').read_text())
        validate_entry(report,Path('build')/capture)
        entries.append(report)
    out.mkdir(parents=True,exist_ok=False)
    sources={str(Path(__file__)):sha(Path(__file__))}
    loaded=[verify_capture(Path('build')/name) for name in
            ('postpublish-normal-1322','hidden-index-normal-1388')]
    (a,old),(b,new)=loaded
    if not a['capture_complete'] or not b['capture_complete'] or a['scenario_sha256']!=b['scenario_sha256']:
        raise ValueError('Incomplete or different comparison routes')
    if a['rom_sha256']!=entries[0]['sources']['snes']['rom_sha256'] or b['rom_sha256']!=entries[1]['sources']['snes']['rom_sha256']:
        raise ValueError('Different comparison cartridge')
    if len(old)!=len(new):raise ValueError('Frame counts differ; do not compare by frame index')
    route=dict(frames=len(old),wav_equal=a['audio_sha256']==b['audio_sha256'],
        differences={k:[x['frame'] for x,y in zip(old,new) if x[k]!=y[k]] for k in
                     ('video_sha256','game_ram_hex','input_delivered','fault')})
    (out/'route.json').write_text(json.dumps(route,indent=2)+'\n')
    for name in ('postpublish-normal-1322','hidden-index-normal-1388'):
        path=Path('build')/name/'capture.json';sources[str(path)]=sha(path)
    def copy(path,name):
        shutil.copyfile(path,out/name);sources[str(path)]=sha(path)
    for key,directory in roots.items():copy(Path('build')/directory/'report.json',key+'.json')
    table=[];cards=[]
    for room in range(1,4):
        for (label,_,_),r in zip(cases,entries):
            c=r['comparisons'][room-1];s=c['snes'];n=c['nes']
            table.append(f'<tr><td>{room}</td><td>{label}</td><td>{s["room_change_to_visible"]} / {n["room_change_to_visible"]}</td>'
                         f'<td>{s["first_nonblack_offset"]} / {n["first_nonblack_offset"]}</td>'
                         f'<td>{c["all_fixed_offset_backgrounds_exact"]}</td></tr>')
        cards.append(f'<h3>Room {room}, rendering-enable +7</h3><section>')
        for i,(label,directory,side) in enumerate([('NES',cases[0][1],'nes'),
                *[(c[0],c[1],'snes') for c in cases]]):
            name=f'room-{room}-{i}.png'
            copy(Path('build')/directory/f'room-{room}-07-{side}.png',name)
            cards.append(f'<figure><img src="{name}" alt="Room {room} {label}"><figcaption>{label}</figcaption></figure>')
        cards.append('</section>')
    for i,(_,directory,_) in enumerate(cases):copy(Path('build')/directory/'report.json',f'entry-{i}.json')
    savings=[s['saved_clocks'] for s in reports['timing']['samples']]
    phases=[]
    for key in ('before','after'):
        phases.append([next(s for s in n['stages'] if s['name']=='native_prepare')['phases'][0]['elapsed_clocks']
                       for n in reports[key]['interrupts'][:3]])
    costs=''.join(f'<tr><td>{i+1}</td><td>{a}</td><td>{b}</td><td>{a-b}</td></tr>'
                  for i,(a,b) in enumerate(zip(*phases)))
    links=' · '.join(f'<a href="{k}.json">{k}</a>' for k in (*roots,'route'))
    links+=' · '+' · '.join(f'<a href="../{directory}/">{label} entry collage</a>' for label,directory,_ in cases)
    page=f'''<!doctype html><meta charset="utf-8"><title>Compact row conversion: faster, loading still open</title>
<style>body{{background:#101821;color:#eaf0f7;font:17px/1.5 system-ui;max-width:1400px;margin:24px auto;padding:16px}}
a{{color:#9df}}td,th{{border:1px solid #567;padding:8px}}table{{border-collapse:collapse}}
section{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}figure{{margin:0}}
img{{width:100%;image-rendering:pixelated}}.open{{border-left:4px solid #eaa747;padding-left:14px}}</style>
<h1>Compact row converter: measured savings, not a release</h1>
<p>Experimental ROM c83ebaa82b88. Rival remains on fa882cb61138; no restart or controller changes.</p>
<p>Keep the attribute index in Y and precompute both pattern halves in a 128-byte table.
The complete helper shrinks from792 to779 bytes. Only its existing ROM region and checksum change;
original graphics, game logic and SPC code are untouched.</p>
<h2>Executed tests</h2><p>{len(reports['oracle']['cases']):,} full VRAM/ownership cases pass; all
{len(reports['oracle']['mutants'])} deliberately broken variants fail. Both mirroring modes and pattern halves,
every starting row, three budgets, changed repeated calls and dirty/queued aliases are exercised.
The game helper exactly matches the executed oracle after address relocation.</p>
<p>Eight equal-output ten-row experiments save {min(savings):,}–{max(savings):,} master clocks per batch.
The timing observer preserves each run's full RAM. These are helper savings, not whole-game speed ratios.</p>
<h2>Actual first three hidden alley row phases</h2>
<table><tr><th>Invocation</th><th>Current clocks</th><th>Index clocks</th><th>Difference</th></tr>{costs}</table>
<p>Both complete instruction-observed routes match their own normal timeline and PCM.
Elapsed clocks include DMA/events. Other interrupt work can grow as timing changes;
first-main-to-fade elapsed time falls only{reports['before']['main_to_fade_clocks']-reports['after']['main_to_fade_clocks']:,}
clocks, and does not cross the display deadline.</p>
<h2>Loading acceptance still FAILS</h2><p>Port / NES values; no alignment search or relaxed deadline.</p>
<table><tr><th>Room</th><th>Build</th><th>Frames from room change</th><th>Frames from rendering on</th>
<th>All40 fade offsets exact?</th></tr>{''.join(table)}</table>
<p class="open">Index16 retains the current alley failure. Index12 improves later fade colors but still
misses initial visibility. Neither is promoted. No per-room timing hacks or original fade-counter changes.</p>
<h2>Unchanged captures at one fixed offset</h2>{''.join(cards)}
<h2>Scoped scrolling and cadence checks</h2><p>The Index16 candidate's fresh full-route renderer audit passes
{reports['renderer']['eligible_frames']:,} eligible frames with no split/stale-camera failures.
Its stable main-loop cadence and park hold checks pass. This is not tile-content certification,
equal-work original-game speed, or a physical audio pass.</p>
<p class="open">The current and candidate normal routes have the same{route['frames']:,}-frame length.
Delivered-input differences: {len(route['differences']['input_delivered'])};
video-frame differences: {len(route['differences']['video_sha256'])}; complete PCM equal: {route['wav_equal']}.
Do not claim whole-route output equivalence.
The remaining physical audio gaps and hardware camera-hold questions are unresolved.</p>
<p>{links} · <a href="manifest.json">Artifact hashes</a></p>'''
    (out/'index.html').write_text(page)
    manifest=dict(release_ready=False,sources=sources,artifacts={p.name:sha(p) for p in sorted(out.iterdir())})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),artifacts=len(manifest['artifacts']),release_ready=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
