"""Publish all tested beam cutoffs, retaining failed fade and loading gates."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_alley_budget_review import validate_entry


def build(out):
    cases=[('Fixed16','hidden-index-entry-1390','hidden-index-normal-1388',None),
           ('Cutoff96','hidden-deadline96-entry-1409','hidden-deadline96-normal-1406','hidden-deadline96-1404'),
           ('Cutoff112','hidden-deadline112-entry-1413','hidden-deadline112-normal-1412','hidden-deadline112-1411'),
           ('Cutoff128','hidden-deadline128-entry-1410','hidden-deadline128-normal-1407','hidden-deadline128-1405')]
    reports=[];sources={str(Path(__file__)):sha(Path(__file__))}
    for _,audit,capture,cart in cases:
        path=Path('build')/audit/'report.json';r=json.loads(path.read_text())
        validate_entry(r,Path('build')/capture);reports.append(r)
        for p in (path,Path('build')/capture/'capture.json'):sources[str(p)]=sha(p)
        if cart:
            p=Path('build')/cart/'manifest.json';manifest=json.loads(p.read_text())
            if sha(p.parent/'native-cpu.sfc')!=manifest['rom_sha256'] or manifest['rom_sha256']!=r['sources']['snes']['rom_sha256']:
                raise ValueError('Different experimental cartridge')
            for source,digest in manifest['hidden_row_deadline']['sources'].items():
                if sha(Path(source))!=digest:raise ValueError('Changed experiment source')
            sources[str(p)]=sha(p)
    path=Path('build/alley-fade-schedule-1408/report.json');schedule=bound_report(path)
    sources[str(path)]=sha(path)
    if not schedule['observer_neutral']:raise ValueError('Nonneutral phase comparison')
    out.mkdir(parents=True,exist_ok=False)
    def copy(path,name):
        shutil.copyfile(path,out/name);sources[str(path)]=sha(path)
    copy(path,'schedule.json')
    table=[];pictures=[]
    for room in range(1,4):
        pictures.append(f'<h3>Room {room}: rendering-enable +7</h3><section>')
        for i,(label,audit,_,_) in enumerate(cases):
            c=reports[i]['comparisons'][room-1];s=c['snes'];n=c['nes']
            mismatch=', '.join(str(j) for j,v in enumerate(c['mismatch_pixels_by_offset']) if v) or 'none'
            table.append(f'<tr><td>{room}</td><td>{label}</td><td>{s["first_nonblack_offset"]}/{n["first_nonblack_offset"]}</td>'
                f'<td>{s["room_change_to_visible"]}/{n["room_change_to_visible"]}</td>'
                f'<td>{s["rendering_off_to_visible"]}/{n["rendering_off_to_visible"]}</td><td>{mismatch}</td></tr>')
            name=f'room-{room}-{i}.png';copy(Path('build')/audit/f'room-{room}-07-snes.png',name)
            pictures.append(f'<figure><img src="{name}" alt="Room {room}, {label}"><figcaption>{label}</figcaption></figure>')
        name=f'room-{room}-nes.png';copy(Path('build')/cases[0][1]/f'room-{room}-07-nes.png',name)
        pictures.append(f'<figure><img src="{name}" alt="Original NES room {room}"><figcaption>NES</figcaption></figure></section>')
    links=[]
    for i,(label,audit,_,_) in enumerate(cases):
        copy(Path('build')/audit/'report.json',f'entry-{i}.json')
        links.append(f'<a href="../{audit}/">{label}: full40-frame audit</a>')
    page='''<!doctype html><meta charset="utf-8"><title>Hidden-row scanline cutoffs</title>
<style>body{background:#101821;color:#eef;font:17px/1.5 system-ui;max-width:1600px;margin:24px auto;padding:16px}
a{color:#9df}td,th{border:1px solid #567;padding:8px}table{border-collapse:collapse}
section{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}figure{margin:0}
img{width:100%;image-rendering:pixelated}.open{border-left:4px solid #eaa747;padding-left:14px}</style>
<h1>Beam-bounded hidden rows: all tested cutoffs</h1>
<p>No Rival deployment or restart. All candidates remain experimental and unqualified for release.</p>
<h2>Measured cause</h2><p>Original NES fade calls occur at entry offsets3/4/6 for the first three iterations.
The deployed port calls at4/5/7. Compact12 restores the first call to3, but the next two remain5/7.
Both systems' full observer timelines and PCM match their normal runs. CPU-cycle units differ and
encounters are not asserted equal work.</p>
<p><a href="../alley-fade-schedule-1408/">Exact main/fade call schedule</a></p>
<h2>Experimental scheduling rule</h2><p>A37-byte wrapper finishes one full direct row and its owned alias,
then reads the real vertical beam. At/after the cutoff and before line240 it ends this producer batch.
Late VBlank is not capped; the existing16-row maximum remains. Original fade counters, game logic,
audio engine, graphics and producer/consumer ownership code are unchanged. No mid-row/DMA interruption.</p>
<p class="open">These prototypes have full-route executions, not a complete boundary/ownership/scheduling
qualification for the new wrapper. No renderer, stable cadence or acoustic pass is inherited from the parent.</p>
<h2>Port / NES frame measurements</h2>
<table><tr><th>Room</th><th>Policy</th><th>From rendering on</th><th>From room change</th>
<th>From rendering off</th><th>Differing fade offsets</th></tr>'''+''.join(table)+'''</table>
<p>All tested cutoffs and all40 offsets are retained. No phase alignment, per-room cutoff or changed
acceptance threshold. Earlier colors remain differences rather than being silently marked exact.</p>
<h2>Unchanged original frame captures</h2>'''+''.join(pictures)+'''
<p class="open">Cutoff128 fixes the alley fade but makes the mall fade early and leaves alley's
rendering-off-to-visible duration late. Cutoff96 delays first scenery in every room. No release claim;
full-game speed, physical camera holds and remaining audio gaps are still open.</p>
<p>'''+ ' · '.join(links)+''' · <a href="schedule.json">Instruction schedule report</a>
 · <a href="manifest.json">Artifact and source hashes</a></p>'''
    (out/'index.html').write_text(page)
    (out/'manifest.json').write_text(json.dumps(dict(release_ready=False,sources=sources,
        artifacts={p.name:sha(p) for p in sorted(out.iterdir())}),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),release_ready=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
