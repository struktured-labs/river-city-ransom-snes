"""Publish actual combat cadence and physical scrolling evidence without waivers."""
import argparse
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def build(out):
    combat=Path('build/combat-loop-audit-1294/report.json')
    camera=Path('build/physical-scroll-camera-1312/report.json')
    audio=Path('build/physical-scroll-audio-1313/report.json')
    coordinator=Path('build/physical-scroll-1305/report.json')
    c=bound_report(combat);a=bound_report(audio);b=bound_report(coordinator)
    v=json.loads(camera.read_text());video=Path('build/physical-scroll-1311.mp4')
    if sha(video)!=v['video_sha256'] or not c['passed']:
        raise ValueError('Different video or failed combat gate')
    if sha(Path('tools/audit_physical_camera.py'))!=v['implementation_sha256']:
        raise ValueError('Camera implementation changed')
    if not all(v['matcher_controls'].values()):raise ValueError('Camera matcher controls failed')
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p):sha(p) for p in (Path(__file__),combat,camera,audio,coordinator,video)}
    for name,p in (('combat.json',combat),('camera.json',camera),('audio.json',audio),
                   ('capture.json',coordinator),('rival.mp4',video)):
        shutil.copyfile(p,out/name)
    figures=[]
    choices=[('build/scroll-street-paused-1304.png','Before traversal: paused at the school'),
             ('build/scroll-after-1306.png','After traversal: scenery moved; paused'),
             ('build/scroll-snac-1308.png','SNAC restored to Yes'),
             ('build/scroll-handoff-1310.png','Final handoff, OSD closed')]
    choices += [(f'build/physical-scroll-inspect-1314-{i:02d}.png',f'Decoded video frame {n} (one-based)')
                for i,n in enumerate((660,661,1063,1065,1067),1)]
    for path,label in choices:
        p=Path(path);shutil.copyfile(p,out/p.name);sources[str(p)]=sha(p)
        figures.append(f'<figure><a href="{p.name}"><img loading="lazy" src="{p.name}"></a>'
                       f'<figcaption>{label}</figcaption></figure>')
    players=[]
    for path,meta in a['clips'].items():
        p=Path(path)
        if sha(p)!=meta['sha256']:raise ValueError('Native audio clip changed')
        shutil.copyfile(p,out/p.name);sources[str(p)]=sha(p)
        players.append(f'<p>{p.stem}, original 48 kHz samples</p><audio controls src="{p.name}"></audio>')
    table=''.join(f'<tr><td>{name}</td><td>{c["nes"]["phases"][name]["iterations"]}</td>'
        f'<td>{phase["iterations"]}</td><td>2 ticks / 2-frame starts</td></tr>'
        for name,phase in c['snes']['phases'].items())
    html='''<!doctype html><meta charset="utf-8"><title>Combat speed and Rival scrolling</title>
<style>body{background:#10141b;color:#e4edf4;font:17px/1.5 system-ui;max-width:1200px;margin:30px auto;padding:20px}
a{color:#72d9ee}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:15px}
img,video{width:100%}figure{margin:0}figcaption{font-size:14px}td,th{padding:8px;border:1px solid #506070}
table{border-collapse:collapse}.open{border-left:4px solid #ffc16a;padding-left:12px}audio{width:100%}</style>
<h1>Combat speed regression + real Rival scrolling</h1><p>September18, 2026 · unchanged game ROM0956bd97b78f.</p>
<h2>Executed original NES/SNES loop timing</h2>
<p>701 complete loops in each encounter pass across approach, taking hits, counterattack, pause and resume.
Every complete loop starting in these phases is included, even when paused or hit. Both game-tick counts
and physical emulator frame-start spacing are checked independently. Entire audio and frame/RAM timelines
match independent normal runs with observers disabled.</p>
<table><tr><th>Phase</th><th>NES loops</th><th>SNES loops</th><th>Timing</th></tr>'''+table+'''</table>
<p>Three derived-data controls per system catch an extra tick, changed start frame and missing loop.
One SNES three-tick loop at frames1192–1195 is retained in the street-loading phase; it is not called a gameplay pass.
Different enemy encounters mean this is not an equal-work full-game speed ratio.</p>
<h2>Actual Rival video, ordinary controller input</h2>
<p>22.7-second requested episode fully inside a30-second raw/OBS recording: unpause,16 seconds right/jump,
4 seconds left/jump, pause. No game RAM edits or replacement game ROM. Scenery actually moves this time.</p>
<video controls preload="metadata" src="rival.mp4"></video>
<p>1,791 decoded pictures;1,782 accepted scenery pairs,8 rejected pairs retained.
Measured nonzero horizontal steps:88 two-pixel,26 one-pixel,1 three-pixel. Hold histogram:
47×2 frames,3×18,1×1,1×12,3×26,1×4. Fixed matcher sensitivity controls pass.</p>
<p class="open">The one-frame interval660→661 and four-frame interval1063→1067 remain unresolved.
OBS can duplicate/drop frames, and camera stops can arise from gameplay. The enemy changes position
inside the four-frame camera hold, so the entire picture is not frozen. This does not prove the hold matches NES.
No smoothness, physical full-speed or pop-free certification is inferred.</p>
<h2>Native recording audio</h2><p>Raw and AAC share DeckLink/OBS. A fixed sample offset is fitted only on seconds4–7.
Held-out waveform correlations are0.494–0.726, too weak for sample-exact event attribution.
The retained214.7ms AAC quiet interval near23.125s follows the pause request; raw shows256.0ms.
The recordings have real gameplay sound; this is not a short-click detector.</p>'''+''.join(players)+'''
<h2>Untouched before/after and irregular-interval frames</h2><div class="grid">'''+''.join(figures)+'''</div>
<p>Final state: same cartridge, game paused on school street, SNAC Yes, OSD closed.
Owned OBS recording stopped, debug tap removed, routing and saved SNES configuration unchanged.</p>
<p><a href="combat.json">Combat audit</a> · <a href="camera.json">Every camera pair</a> ·
<a href="audio.json">Raw/AAC audit</a> · <a href="capture.json">Input/recording coordinator</a> ·
<a href="manifest.json">Hashes</a> · <a href="../packet-player-review-1291/">Same-command hardware audio replay</a></p>'''
    (out/'index.html').write_text(html)
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()},release_ready=False),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),frames=len(choices))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
